"""
api/attendance_session_diagnostics.py
──────────────────────────────────────
Diagnostic endpoint for per-session anchor and embedding stats.

HOW TO INTEGRATE
────────────────
This file is a self-contained snippet designed to be copy-pasted into
``attendance_backend/api/attendance.py`` directly after the
``GET /window-status`` endpoint (around line 290).

The only import additions required at the top of attendance.py are:

    from services.session_anchor_store import get_anchor_store

All other symbols (router, get_firebase_service, FirebaseService,
get_current_user, JSONResponse, HTTPException, Query, Depends, Optional,
logger) are already imported there.

ENDPOINT CONTRACT
─────────────────
GET /api/v1/attendance/session/{session_id}/diagnostics
    ?include_embedding_stats=true   (default true)

Auth: caller must be an admin OR the owner of the anchored session.

Response 200:
{
  "session_id":          "cam-01",
  "anchored":            true,
  "anchored_student_id": "stu_abc",
  "anchored_student_name": "Alice",
  "anchor_age_seconds":  42.1,
  "ttl_seconds":         300.0,
  "ttl_remaining_seconds": 257.9,   // null when ttl=0 (no expiry)
  "scope_type":          "SELF",
  "embedding_stats": {              // null when include_embedding_stats=false
    "sample_count":      7,
    "centroid_norm":     0.9981,
    "embedding_variance":0.0034,    // from Firestore field if present
    "adaptive_threshold":0.519      // computed from variance + base
  },
  "last_search": {                  // always null for now — hook reserved
    "similarity":  null,
    "fused_score": null,
    "searched_at": null
  }
}

Response 404: session not anchored.
Response 403: caller is not admin or session owner.
Response 503: anchor store not available.
"""

# ── paste starts here ────────────────────────────────────────────────────────
import time as _time  # aliased to avoid shadowing datetime


@router.get(
    "/session/{session_id}/diagnostics",
    summary=(
        "Diagnostic: anchored identity + embedding stats for a session "
        "(admin or session owner only)"
    ),
)
async def get_session_diagnostics(
    session_id: str,
    include_embedding_stats: bool = Query(
        True,
        description=(
            "When true (default), fetch per-user centroid norm, sample count, "
            "and embedding variance from Firestore. "
            "Set false for a lightweight anchor-only check."
        ),
    ),
    user=Depends(get_current_user),
):
    """
    Returns real-time diagnostic information for the given session/stream ID.

    Useful for tuning adaptive thresholds in the field without tailing logs:

    * **anchored** — whether the session is locked to a student after login
    * **embedding_stats** — centroid norm, sample count, variance, and the
      resulting adaptive threshold that ``ScopedEmbeddingSearch`` would apply
    * **last_search** — hook for a future per-request similarity cache; always
      null in this revision

    Auth rules
    ──────────
    * Admins may query any session.
    * A student/teacher may query only the session anchored to their own
      ``user_id``.  Any other session returns HTTP 403.
    """
    # ── 1. Resolve anchor store ───────────────────────────────────────────────
    try:
        from services.session_anchor_store import get_anchor_store
        store = get_anchor_store()
    except Exception as exc:
        raise HTTPException(503, f"Anchor store unavailable: {exc}")

    # ── 2. Fetch anchor (may be None / expired) ───────────────────────────────
    anchor = store.get(session_id)

    # ── 3. Auth check ─────────────────────────────────────────────────────────
    caller_is_admin = getattr(user, "is_admin", lambda: False)()
    caller_id = getattr(user, "user_id", None)

    if not caller_is_admin:
        # Non-admins may only inspect a session that is anchored to themselves
        if anchor is None or anchor.student_id != caller_id:
            raise HTTPException(
                403,
                "Access denied: you may only inspect sessions anchored to your own account.",
            )

    # ── 4. Build base response ────────────────────────────────────────────────
    if anchor is None:
        return JSONResponse(
            status_code=404,
            content={
                "session_id": session_id,
                "anchored":   False,
                "message":    "Session is not anchored (no active identity lock).",
            },
        )

    age_seconds = _time.time() - anchor.anchored_at
    ttl = anchor.ttl_seconds
    ttl_remaining = max(0.0, ttl - age_seconds) if ttl > 0 else None

    scope_type = None
    try:
        scope_type = anchor.scope.scope_type.value  # e.g. "SELF"
    except Exception:
        pass

    payload: dict = {
        "session_id":            session_id,
        "anchored":              True,
        "anchored_student_id":   anchor.student_id,
        "anchored_student_name": anchor.student_name,
        "anchor_age_seconds":    round(age_seconds, 2),
        "ttl_seconds":           ttl if ttl > 0 else None,
        "ttl_remaining_seconds": round(ttl_remaining, 2) if ttl_remaining is not None else None,
        "scope_type":            scope_type,
        "embedding_stats":       None,
        "last_search": {
            "similarity":  None,   # reserved — wire up once per-request cache exists
            "fused_score": None,
            "searched_at": None,
        },
    }

    # ── 5. Optional embedding stats ───────────────────────────────────────────
    if include_embedding_stats:
        payload["embedding_stats"] = await _fetch_embedding_stats(
            anchor.student_id
        )

    return JSONResponse(status_code=200, content=payload)


async def _fetch_embedding_stats(student_id: str) -> dict:
    """
    Fetch per-student embedding stats from Firestore and compute derived values.

    Returns a dict with:
      sample_count        — number of stored embedding vectors
      centroid_norm       — L2 norm of the mean embedding (should be ~1 for
                            normalised embeddings; deviation flags drift)
      embedding_variance  — pre-computed variance field (distance space) if
                            stored by the enrolment pipeline; else estimated
                            on-the-fly from stored vectors
      adaptive_threshold  — threshold that ScopedEmbeddingSearch would apply
                            given the variance and global base
    """
    import numpy as np
    from starlette.concurrency import run_in_threadpool

    def _sync_fetch():
        try:
            firebase = get_firebase_service()
            if not firebase:
                return None

            student = firebase.get_student(student_id)
            if not student:
                return None

            embeddings = FirebaseService.get_all_embeddings(student)
            sample_count = len(embeddings)

            # Variance: prefer the pre-computed field; estimate otherwise
            stored_variance = student.get("embedding_variance")

            centroid_norm = None
            estimated_variance = None

            if embeddings:
                try:
                    arrs = [
                        e.astype(np.float32) / (np.linalg.norm(e) + 1e-10)
                        for e in embeddings
                        if isinstance(e, np.ndarray) and e.size > 0
                    ]
                    if arrs:
                        stacked = np.stack(arrs, axis=0)        # (N, D)
                        centroid = np.mean(stacked, axis=0)
                        centroid_norm = float(np.linalg.norm(centroid))

                        if stored_variance is None and len(arrs) > 1:
                            # Estimate variance as mean squared cosine distance
                            # from centroid (cheap proxy, no scipy needed)
                            c_norm = centroid / (np.linalg.norm(centroid) + 1e-10)
                            dists = [float(1.0 - np.dot(c_norm, e)) for e in arrs]
                            estimated_variance = float(np.var(dists))
                except Exception as inner:
                    logger.debug("Embedding stats computation error: %s", inner)

            variance = (
                float(stored_variance)
                if stored_variance is not None
                else estimated_variance
            )

            # Compute adaptive threshold using the same formula as
            # face_recognition_service.compute_adaptive_threshold
            adaptive_threshold = None
            if variance is not None:
                try:
                    from services.face_recognition_service import (
                        compute_adaptive_threshold,
                    )
                    from config.constants import FACE_RECOGNITION_THRESHOLD
                    adaptive_threshold = round(
                        compute_adaptive_threshold(
                            base_threshold=FACE_RECOGNITION_THRESHOLD,
                            variance=variance,
                        ),
                        4,
                    )
                except Exception as thresh_exc:
                    logger.debug("Adaptive threshold computation error: %s", thresh_exc)

            return {
                "sample_count":       sample_count,
                "centroid_norm":      round(centroid_norm, 6) if centroid_norm is not None else None,
                "embedding_variance": round(variance, 6) if variance is not None else None,
                "variance_source":    (
                    "firestore_field" if stored_variance is not None
                    else ("estimated" if estimated_variance is not None else "unavailable")
                ),
                "adaptive_threshold": adaptive_threshold,
            }

        except Exception as exc:
            logger.warning("_fetch_embedding_stats failed for %s: %s", student_id, exc)
            return None

    return await run_in_threadpool(_sync_fetch)
# ── paste ends here ──────────────────────────────────────────────────────────