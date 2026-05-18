"""
api/attendance.py  — enhanced with period-locking, attendance-window logic,
                     and SELF_VERIFY-first session-anchored pipeline
─────────────────────────────────────────────────────────────────────────────
Changes vs 2026-04-30 (period-locking edition)
----------------------------------------------
★★ SELF_VERIFY-first pipeline (2026-05)
   detect-face-only now accepts two new query parameters:
     • session_id   – opaque token identifying the browser tab / device
     • force_scope  – if true, never fall back past SELF_VERIFY

   When a session anchor is present (see POST /anchor below) the endpoint:
     1. Runs SELF_VERIFY against ONLY the anchored user's embeddings first.
        This is an O(1) lookup vs O(N) for a full section scan.
     2. Returns immediately on match (short-circuit).
     3. Falls through to section_roster on miss (unless force_scope=true).

★★ New endpoint — POST  /api/v1/attendance/anchor
   Body: { session_id, user_id, period_id? }
   Creates (or refreshes) a session anchor.  Requires authentication.

★★ New endpoint — DELETE /api/v1/attendance/anchor
   Body/query: { session_id }
   Releases the caller's anchor.  Requires authentication.

All previous endpoints and behaviours are unchanged.
"""

import gc
import logging
import base64
import io
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Body, File, Form, UploadFile, status, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from schemas.attendance_schemas import (
    StudentRegistrationRequest, StudentRegistrationResponse,
    StudentListResponse, StudentInfo,
    MarkAttendanceRequest, MarkAttendanceResponse, AttendanceListResponse,
    AttendanceRecord, DailyReportResponse,
    ErrorResponse, ValidationErrorResponse,
    BatchRegisterRequest, BatchRegisterResponse,
    BatchMarkAttendanceRequest, BatchMarkAttendanceResponse,
    StreamConfig, StreamHealth,
    HealthCheckResponse, SystemStatsResponse,
)
from schemas.teacher_schemas import WindowClosedResponse, WindowAwareMarkResponse

import numpy as np
from scipy.spatial.distance import cosine
from services.firebase_service import get_firebase_service, FirebaseService
from decorators.auth_decorators import get_optional_user, get_current_user
from database.student_repository import StudentRepository
from config.constants import DB_FIELD_STUDENT_ID, COLLECTION_TIMETABLE
from services.rtsp_stream_handler import get_stream_manager
from services.attendance_lock_service import get_lock_service
from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
)
from services.embedding_scope_service import get_scope_service
from models.scoped_matcher import match_against_scope

# ★ Session anchoring
from services.session_anchor_service import get_anchor_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES  = 10 * 1024 * 1024   # 10 MB
TARGET_LONG_EDGE  = 640
COSINE_THRESHOLD  = 0.55


# ══════════════════════════════════════════════════════════════════════════════
# Request / Response schemas for anchor endpoints
# ══════════════════════════════════════════════════════════════════════════════

class AnchorRequest(BaseModel):
    session_id: str
    user_id:    str
    period_id:  Optional[str] = None
    ttl:        Optional[int] = None    # seconds; None → service default (7200)


class AnchorReleaseRequest(BaseModel):
    session_id: str


# ══════════════════════════════════════════════════════════════════════════════
# Image helpers  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def _resize_if_needed(image_array: np.ndarray, long_edge: int = TARGET_LONG_EDGE) -> np.ndarray:
    h, w = image_array.shape[:2]
    max_dim = max(h, w)
    if max_dim <= long_edge:
        return image_array
    import cv2
    scale = long_edge / max_dim
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)
    logger.debug("Resized %dx%d → %dx%d (scale=%.2f)", w, h, new_w, new_h, scale)
    return resized


# ══════════════════════════════════════════════════════════════════════════════
# Window / lock helpers  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_attendance_status(
    window_phase: str,
    period: dict,
) -> str:
    if window_phase == "grace":
        return "late"
    if window_phase == "open":
        try:
            start_str = period.get("start_time", "00:00")
            start_dt  = datetime.strptime(
                datetime.now().strftime("%Y-%m-%d ") + start_str,
                "%Y-%m-%d %H:%M",
            )
            elapsed = (datetime.now() - start_dt).total_seconds() / 60.0
            return "late" if elapsed > LATE_THRESHOLD_MINUTES else "present"
        except Exception:
            pass
    return "present"


def _get_window_for_period(period_id: Optional[str]) -> Optional[dict]:
    if not period_id:
        return None
    lock_svc = get_lock_service()
    if not lock_svc:
        return None
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
        if db is None:
            return None
        pd_doc = db.collection("periods").document(period_id).get()
        if not pd_doc.exists:
            return None
        return lock_svc.get_window_status(pd_doc.to_dict())
    except Exception as exc:
        logger.warning("Window check failed for %s: %s", period_id, exc)
        return None


def _window_closed_response(window: dict, student_id: Optional[str] = None) -> JSONResponse:
    return JSONResponse(
        status_code=423,
        content={
            "success":    False,
            "student_id": student_id,
            "message":    window.get("message", "Attendance window closed."),
            "window":     window,
        },
    )


async def _maybe_autolock(period_id: str) -> None:
    if not period_id:
        return
    try:
        lock_svc = get_lock_service()
        window   = _get_window_for_period(period_id)
        if lock_svc and window and window.get("phase") == "locked":
            from services.firebase_service import get_firebase_service
            fb = get_firebase_service()
            db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
            if db:
                pd_doc = db.collection("periods").document(period_id).get()
                if pd_doc.exists:
                    period   = pd_doc.to_dict()
                    class_id = period.get("class_id", "")
                    lock_svc.lock_period(
                        period_id=period_id,
                        class_id=class_id,
                        actor_id="system",
                        reason="auto",
                    )
                    logger.info("Auto-locked period %s after grace window expired", period_id)
    except Exception as exc:
        logger.debug("_maybe_autolock swallowed: %s", exc)


def _resolve_scope(
    scope_mode: str,
    student_id: Optional[str],
    section_id: Optional[str],
):
    scope_svc = get_scope_service()
    if scope_svc is None:
        return None
    if scope_mode == "self_verify" and student_id:
        return scope_svc.resolve_student_scope(student_id)
    if scope_mode == "section_roster" and section_id:
        return scope_svc.resolve_section_scope(section_id)
    return None


def _get_candidate_ids_for_user(user, period_id: Optional[str] = None, limit: int = 500):
    try:
        fb = get_firebase_service()
        if fb is None:
            return None

        if user.is_student():
            if period_id:
                try:
                    db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
                    class_id = None
                    if db:
                        pd_doc = db.collection(COLLECTION_TIMETABLE).document(period_id).get()
                        if pd_doc.exists:
                            class_id = pd_doc.to_dict().get("class_id") or pd_doc.to_dict().get("section_id")
                    if class_id:
                        repo = StudentRepository()
                        students = repo.list_students(course_id=class_id)
                        candidate_ids = [s.get(DB_FIELD_STUDENT_ID) or s.get("student_id") for s in students if s]
                        seen = set()
                        out = []
                        for sid in candidate_ids:
                            if not sid or sid in seen:
                                continue
                            seen.add(sid)
                            out.append(sid)
                            if len(out) >= limit:
                                break
                        if out:
                            return out
                except Exception:
                    pass
            return [user.user_id]

        class_id = None
        if period_id:
            try:
                db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
                if db:
                    pd_doc = db.collection(COLLECTION_TIMETABLE).document(period_id).get()
                    if pd_doc.exists:
                        class_id = pd_doc.to_dict().get("class_id") or pd_doc.to_dict().get("section_id")
            except Exception:
                class_id = None

        repo = StudentRepository()
        candidate_ids = []

        if user.is_teacher():
            if class_id:
                students = repo.list_students(course_id=class_id)
                candidate_ids = [s.get(DB_FIELD_STUDENT_ID) or s.get("student_id") for s in students if s]
            else:
                for sec in (user.assigned_sections or []):
                    students = repo.list_students(course_id=sec)
                    candidate_ids.extend([s.get(DB_FIELD_STUDENT_ID) or s.get("student_id") for s in students if s])
        else:
            return None

        seen = set()
        out = []
        for sid in candidate_ids:
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(sid)
            if len(out) >= limit:
                break
        return out
    except Exception:
        return None


def _queue_verified_outcome(
    record_id: str,
    student_id: str,
    period_id: Optional[str],
    confidence: float,
    marked_at_iso: str,
) -> None:
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        if fb is None:
            logger.warning(
                "Firebase service unavailable; cannot queue verified outcome. "
                "record_id=%s student=%s", record_id, student_id,
            )
            return

        db = (
            getattr(fb, "firestore_db", None) or
            getattr(fb, "_firestore", None) or
            getattr(fb, "db", None)
        )
        if db is None:
            logger.warning(
                "Firestore DB not available. Cannot queue verified outcome for record_id=%s",
                record_id,
            )
            return

        if not record_id or not student_id:
            logger.error(
                "Cannot queue verified outcome: invalid inputs. "
                "record_id=%s student_id=%s", record_id, student_id,
            )
            return

        payload = {
            "record_id":  record_id,
            "student_id": student_id,
            "period_id":  period_id or None,
            "confidence": round(float(confidence), 4),
            "verified":   True,
            "verified_at": marked_at_iso,
            "source":     "confirm_attendance",
            "queued_at":  datetime.now().isoformat(),
        }
        doc_ref = db.collection("verified_face_outcomes").document(record_id)
        doc_ref.set(payload, merge=True)
        logger.info(
            "✓ Verified outcome queued: record_id=%s student=%s confidence=%.2f",
            record_id, student_id, confidence,
        )
    except Exception as exc:
        logger.error(
            "Failed to queue verified outcome (non-fatal): "
            "record_id=%s student=%s period=%s error=%s",
            record_id, student_id, period_id, exc, exc_info=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Inference helpers  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def _run_detection_and_embedding(image_array: np.ndarray):
    import cv2
    from models.model_manager import ModelManager
    image_array = _resize_if_needed(image_array)
    try:
        detector  = ModelManager.get_yolov8_detector()
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        detections = detector.detect(image_bgr)
    except Exception as exc:
        logger.error("Face detection error: %s", exc)
        return None, {"matched": False, "message": f"Face detection failed: {exc}"}
    finally:
        try:
            del image_bgr
        except NameError:
            pass
        gc.collect()

    if not detections:
        return None, {
            "matched": False,
            "message": "No face detected. Ensure your face is clearly visible.",
        }

    best_face = max(detections, key=lambda x: x[4])
    x1, y1, x2, y2, conf = best_face
    h, w = image_array.shape[:2]
    pad_x = int((x2 - x1) * 0.1)
    pad_y = int((y2 - y1) * 0.1)
    x1 = max(0, int(x1) - pad_x)
    y1 = max(0, int(y1) - pad_y)
    x2 = min(w, int(x2) + pad_x)
    y2 = min(h, int(y2) + pad_y)
    face_crop = image_array[y1:y2, x1:x2].copy()
    del image_array, detections
    gc.collect()

    try:
        extractor = ModelManager.get_facenet_extractor()
        embedding = extractor.extract_embedding(face_crop)
    except ImportError:
        return None, {"matched": False, "message": "Face recognition model not loaded."}
    except Exception as exc:
        logger.error("Embedding error: %s", exc)
        return None, {"matched": False, "message": f"Could not process face: {exc}"}
    finally:
        del face_crop
        gc.collect()

    if embedding is None:
        return None, {"matched": False, "message": "Could not extract face features."}
    return embedding, None


async def _extract_embedding_from_upload(file: UploadFile):
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(400, "Empty file received")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image exceeds 10 MB limit")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Failed to read file: {exc}")

    try:
        from PIL import Image
        image_array = np.array(Image.open(io.BytesIO(contents)).convert("RGB"))
    except Exception as exc:
        raise HTTPException(400, f"Invalid image format: {exc}")
    finally:
        del contents
        gc.collect()

    embedding, error_content = await run_in_threadpool(_run_detection_and_embedding, image_array)
    del image_array
    gc.collect()

    if error_content is not None:
        return None, JSONResponse(status_code=200, content=error_content)
    return embedding, None


def _match_embedding_sync(
    embedding: np.ndarray,
    firebase,
    threshold: float = COSINE_THRESHOLD,
    candidate_student_ids: Optional[List[str]] = None,
    candidate_course_id: Optional[str] = None,
):
    from database.student_repository import StudentRepository

    best_distance = float("inf")
    best_student = None
    candidates: List[dict] = []

    try:
        if candidate_student_ids:
            for sid in candidate_student_ids:
                st = firebase.get_student(sid)
                if st:
                    candidates.append(st)
        elif candidate_course_id:
            repo = StudentRepository()
            students = repo.list_students(course_id=candidate_course_id)
            candidates.extend(students)
        else:
            candidates = firebase.get_all_students()
    except Exception:
        candidates = firebase.get_all_students()

    for student in candidates:
        stored_embs = FirebaseService.get_all_embeddings(student)
        for arr in stored_embs:
            try:
                if arr.shape != embedding.shape:
                    continue
            except Exception:
                continue
            dist = float(cosine(embedding, arr))
            if dist < best_distance:
                best_distance = dist
                best_student = student

    confidence = float(1.0 - min(best_distance, 1.0)) if best_student else 0.0
    return best_student, confidence, best_distance


def _rank_embedding_candidates_sync(
    embedding: np.ndarray,
    firebase,
    candidate_student_ids: Optional[List[str]] = None,
    candidate_course_id: Optional[str] = None,
    limit: int = 3,
) -> List[dict]:
    from database.student_repository import StudentRepository

    candidates: List[dict] = []
    try:
        if candidate_student_ids:
            for sid in candidate_student_ids:
                st = firebase.get_student(sid)
                if st:
                    candidates.append(st)
        elif candidate_course_id:
            repo = StudentRepository()
            students = repo.list_students(course_id=candidate_course_id)
            candidates.extend(students)
        else:
            candidates = firebase.get_all_students()
    except Exception:
        candidates = firebase.get_all_students()

    try:
        q = embedding.astype(np.float32)
        q = q / (np.linalg.norm(q) + 1e-10)
    except Exception:
        q = embedding

    ranked: List[dict] = []
    for student in candidates:
        best_score = -1.0
        for arr in FirebaseService.get_all_embeddings(student):
            try:
                if arr.shape != embedding.shape:
                    continue
                e = arr.astype(np.float32)
                e = e / (np.linalg.norm(e) + 1e-10)
                score = float(np.dot(q, e))
                if score > best_score:
                    best_score = score
            except Exception:
                continue
        if best_score >= 0.0:
            ranked.append({
                "student_id":   student.get("student_id", ""),
                "student_name": student.get("name", "Unknown"),
                "confidence":   round(max(0.0, min(1.0, best_score)), 4),
            })

    ranked.sort(key=lambda item: item["confidence"], reverse=True)
    return ranked[:limit]


def _scoped_match(
    embedding: np.ndarray,
    firebase,
    user,
    period_id: Optional[str],
    scope_mode: str,
    student_id: Optional[str],
    section_id: Optional[str],
    exclude_student_ids: Optional[List[str]] = None,
):
    from datetime import datetime
    from models.identity_context import ScopeTarget, IdentityScopeType
    from services.identity_context_service import IdentityContextService
    from services.scoped_embedding_search import ScopedEmbeddingSearch

    scope = None
    try:
        if user is not None:
            if user.is_student() and scope_mode == "section_roster":
                roster_ids = _get_candidate_ids_for_user(user, period_id=period_id) or [user.user_id]
                if exclude_student_ids:
                    blocked = {sid for sid in exclude_student_ids if sid}
                    roster_ids = [sid for sid in roster_ids if sid not in blocked]
                scope = ScopeTarget(
                    scope_type=IdentityScopeType.SECTION,
                    student_ids=roster_ids,
                    resolved_by=user.user_id,
                    resolved_at=datetime.now().isoformat(),
                    period_id=period_id,
                )
            else:
                svc = IdentityContextService(firebase_client=firebase, period_detection_service=None)
                scope = svc.resolve(user, period_id=period_id)
        else:
            if scope_mode == "self_verify" and student_id:
                scope = ScopeTarget(
                    scope_type=IdentityScopeType.SELF,
                    student_ids=[student_id],
                    resolved_by=student_id,
                    resolved_at=datetime.now().isoformat(),
                )
            elif scope_mode == "section_roster" and section_id and firebase:
                try:
                    db = getattr(firebase, "firestore_db", None) or getattr(firebase, "_firestore", None)
                    ids = []
                    if db:
                        docs = db.collection("enrollments").where("section_id", "==", section_id).stream()
                        ids = [d.to_dict().get("student_id") for d in docs]
                        ids = [i for i in ids if i]
                    if exclude_student_ids:
                        blocked = {sid for sid in exclude_student_ids if sid}
                        ids = [sid for sid in ids if sid not in blocked]
                    scope = ScopeTarget(
                        scope_type=IdentityScopeType.SECTION,
                        student_ids=ids,
                        resolved_by="anonymous",
                        resolved_at=datetime.now().isoformat(),
                        section_id=section_id,
                    )
                except Exception:
                    scope = ScopeTarget(
                        scope_type=IdentityScopeType.GLOBAL,
                        student_ids=[],
                        resolved_by="anonymous",
                        resolved_at=datetime.now().isoformat(),
                    )
            else:
                scope = ScopeTarget(
                    scope_type=IdentityScopeType.GLOBAL,
                    student_ids=[],
                    resolved_by="anonymous",
                    resolved_at=datetime.now().isoformat(),
                )
    except Exception:
        scope = ScopeTarget(
            scope_type=IdentityScopeType.GLOBAL,
            student_ids=[],
            resolved_by="system",
            resolved_at=datetime.now().isoformat(),
        )

    searcher = ScopedEmbeddingSearch(firebase_service=firebase)
    result = searcher.search(embedding, scope)
    return result


def _self_verify_scoped_match(
    embedding: np.ndarray,
    firebase,
    anchored_user_id: str,
    period_id: Optional[str],
    exclude_student_ids: Optional[List[str]] = None,
):
    """
    Dedicated SELF_VERIFY scope runner for the anchor short-circuit path.

    Builds a strict SELF scope for ``anchored_user_id`` and delegates to
    ``ScopedEmbeddingSearch.search()``.  This is intentionally separate from
    the general ``_scoped_match`` so that it is always guaranteed to use
    ``IdentityScopeType.SELF`` regardless of any caller-supplied
    ``scope_mode`` parameter.
    """
    from models.identity_context import ScopeTarget, IdentityScopeType
    from services.scoped_embedding_search import ScopedEmbeddingSearch

    scope = ScopeTarget(
        scope_type=IdentityScopeType.SELF,
        student_ids=[anchored_user_id],
        resolved_by=anchored_user_id,
        resolved_at=datetime.now().isoformat(),
        period_id=period_id,
    )
    searcher = ScopedEmbeddingSearch(firebase_service=firebase)
    return searcher.search(embedding, scope)


# ══════════════════════════════════════════════════════════════════════════════
# ★★ NEW: POST /anchor — create / refresh a session anchor
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/anchor",
    summary="Pin an authenticated user to a session for SELF_VERIFY-first detection",
    status_code=status.HTTP_200_OK,
)
async def anchor_session(
    body: AnchorRequest,
    user = Depends(get_current_user),
):
    """
    Create (or refresh) a session anchor that pins ``user_id`` to
    ``session_id``.

    Once anchored, calls to ``detect-face-only`` that include the matching
    ``session_id`` will short-circuit to a SELF_VERIFY scope — only the
    anchored student's embeddings are searched first, giving O(1) lookup
    latency instead of a full O(N) section scan.

    Authorization rules
    -------------------
    * A student may only anchor their **own** ``user_id``.
    * A teacher or admin may anchor any ``user_id`` (useful for kiosk / proxy
      flows where a teacher pre-anchors the station to an incoming student).

    The anchor expires automatically after the configured TTL (default 2 h).
    Call this endpoint again to reset the TTL.

    Body
    ----
    ```json
    {
      "session_id": "tab_abc123",
      "user_id":    "student_42",
      "period_id":  "period_001",   // optional — for window-status context
      "ttl":        3600            // optional override in seconds
    }
    ```

    Response
    --------
    ```json
    {
      "anchored":         true,
      "session_id":       "tab_abc123",
      "user_id":          "student_42",
      "period_id":        "period_001",
      "remaining_seconds": 3600
    }
    ```
    """
    # ── Authorisation guard ────────────────────────────────────────────────────
    caller_is_student = getattr(user, "is_student", lambda: False)()
    if caller_is_student and user.user_id != body.user_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Students may only anchor their own user_id. "
                f"Caller={user.user_id!r} requested user_id={body.user_id!r}."
            ),
        )

    # ── Optional: verify the user_id is a known student ───────────────────────
    firebase = get_firebase_service()
    if firebase:
        student = firebase.get_student(body.user_id)
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"No student record found for user_id={body.user_id!r}.",
            )

    # ── Create / refresh anchor ────────────────────────────────────────────────
    from services.session_anchor_service import ANCHOR_TTL_SECONDS as _DEFAULT_TTL
    anchor_svc = get_anchor_service()
    entry = anchor_svc.anchor(
        session_id=body.session_id,
        user_id=body.user_id,
        period_id=body.period_id,
        ttl=float(body.ttl) if body.ttl else _DEFAULT_TTL,
    )

    logger.info(
        "Anchor created by %s: session=%s → user=%s period=%s",
        user.user_id, body.session_id, body.user_id, body.period_id or "–",
    )

    return JSONResponse(status_code=200, content={
        "anchored":          True,
        "session_id":        entry.session_id,
        "user_id":           entry.user_id,
        "period_id":         entry.period_id,
        "remaining_seconds": int(entry.remaining_seconds),
    })


# ══════════════════════════════════════════════════════════════════════════════
# ★★ NEW: DELETE /anchor — release a session anchor
# ══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/anchor",
    summary="Release a session anchor",
    status_code=status.HTTP_200_OK,
)
async def release_anchor(
    session_id: str = Query(..., description="Session ID to release"),
    user = Depends(get_current_user),
):
    """
    Remove the session anchor for ``session_id``.

    Authorization rules
    -------------------
    * A student may only release an anchor they own.
    * A teacher or admin may release any anchor.

    Idempotent — returns success even if no anchor exists.

    Query params
    ------------
    ``session_id`` — the session to release.

    Response
    --------
    ```json
    { "released": true,  "session_id": "tab_abc123" }
    { "released": false, "session_id": "tab_abc123", "reason": "not_found" }
    ```
    """
    caller_is_student = getattr(user, "is_student", lambda: False)()
    owner_guard = user.user_id if caller_is_student else None

    anchor_svc = get_anchor_service()

    # Teachers/admins may forcibly release any session
    if not caller_is_student:
        anchor_svc.release(session_id, owner_id=None)
        return JSONResponse(status_code=200, content={
            "released": True, "session_id": session_id,
        })

    released = anchor_svc.release(session_id, owner_id=owner_guard)
    if not released:
        # Check whether it was a ownership mismatch or just not found
        existing = anchor_svc.get_anchor(session_id)
        reason = "ownership_mismatch" if existing else "not_found"
        return JSONResponse(status_code=200, content={
            "released": False, "session_id": session_id, "reason": reason,
        })

    return JSONResponse(status_code=200, content={
        "released": True, "session_id": session_id,
    })


# ══════════════════════════════════════════════════════════════════════════════
# NEW: GET /window-status  (unchanged from previous version)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/window-status",
    summary="Real-time attendance window status for a period (student-facing polling)",
)
async def get_window_status(
    period_id: str = Query(..., description="Period ID to check"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
):
    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")

    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
        if db is None:
            raise HTTPException(503, "Firestore not available")
        pd_doc = db.collection("periods").document(period_id).get()
        if not pd_doc.exists:
            raise HTTPException(404, f"Period '{period_id}' not found")
        window = lock_svc.get_window_status(pd_doc.to_dict(), date)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Window status check failed: {exc}")

    return JSONResponse(status_code=200, content=window)


@router.get(
    "/candidates",
    summary="Return candidate student IDs for the authenticated user and optional period",
)
async def get_candidates(
    period_id: Optional[str] = Query(None),
    limit: int = Query(500),
    user = Depends(get_current_user),
):
    candidates = _get_candidate_ids_for_user(user, period_id=period_id, limit=limit)
    return JSONResponse(status_code=200, content={
        "candidate_student_ids": candidates,
        "count": len(candidates) if candidates is not None else None,
    })


# ══════════════════════════════════════════════════════════════════════════════
# NEW: GET /record/{record_id}/audit  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/record/{record_id}/audit",
    summary="Audit trail for an attendance record",
)
async def get_record_audit(record_id: str):
    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")
    try:
        trail = lock_svc.get_audit_trail(record_id)
    except Exception as exc:
        raise HTTPException(500, f"Could not retrieve audit trail: {exc}")
    return JSONResponse(status_code=200, content={
        "record_id":   record_id,
        "entry_count": len(trail),
        "audit_trail": trail,
    })


# ══════════════════════════════════════════════════════════════════════════════
# ★★ ENHANCED: detect-face-only — SELF_VERIFY-first when session is anchored
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/detect-face-only",
    status_code=status.HTTP_200_OK,
    summary="Detect and identify face — does NOT write to database",
)
async def detect_face_only(
    request: Request,
    file: UploadFile = File(..., description="JPEG or PNG image"),
    period_id: Optional[str] = Query(None),
    candidate_student_ids: Optional[str] = Query(None),
    candidate_course_id: Optional[str] = Query(None),
    scope_mode:  str           = Query("section_roster", description="self_verify | section_roster"),
    student_id:  Optional[str] = Query(None),
    section_id:  Optional[str] = Query(None),
    exclude_student_ids: Optional[str] = Query(None),
    # ★ Session-anchor parameters
    session_id:  Optional[str] = Query(
        None,
        description=(
            "Opaque session token (e.g. browser tab ID). "
            "When a matching anchor exists, SELF_VERIFY runs first before "
            "falling back to section_roster."
        ),
    ),
    force_scope: bool = Query(
        False,
        description=(
            "When true, the anchored SELF_VERIFY result is final — "
            "no fallback to section_roster on a miss. "
            "Requires session_id + an active anchor."
        ),
    ),
    user = Depends(get_optional_user),
):
    """
    Detect and identify a face without writing an attendance record.

    SELF_VERIFY-first pipeline
    --------------------------
    When ``session_id`` is supplied and a live session anchor exists, the
    endpoint runs a fast O(1) SELF_VERIFY pass first:

    ┌─────────────────────────────────────────────────────┐
    │ 1. Check session anchor for session_id              │
    │    ↓ anchor found                                   │
    │ 2. SELF_VERIFY against anchored user's embeddings   │
    │    ↓ match            ↓ miss                        │
    │ 3. Return (200)    force_scope?                     │
    │                       ↓ yes       ↓ no              │
    │                    Return(miss) Section-roster scan │
    └─────────────────────────────────────────────────────┘

    Without an anchor (or when no anchor exists for the given session_id),
    the existing section_roster / legacy fallback path runs unchanged.
    """
    excluded_ids = (
        [s.strip() for s in exclude_student_ids.split(",")]
        if exclude_student_ids else None
    )

    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    # ── Metadata extraction from request (for liveness fusion) ────────────────
    device_id = request.headers.get("X-Device-ID")
    ip_address = request.client.host if request.client else None
    geolocation_str = request.headers.get("X-Geolocation")  # Expected format: "lat,lon"
    geolocation = None
    if geolocation_str:
        try:
            parts = geolocation_str.split(",")
            if len(parts) == 2:
                geolocation = {"lat": float(parts[0]), "lon": float(parts[1])}
        except (ValueError, IndexError):
            logger.warning("Invalid geolocation header: %s", geolocation_str)

    from services.liveness import LoginMetadata
    login_metadata = LoginMetadata(
        device_id=device_id,
        ip_address=ip_address,
        geolocation=geolocation,
        time_of_day_hour=datetime.now().hour,
        known_device=device_id is not None,
        expected_location=True,  # Assume in-classroom
    )

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    # Optional window status (non-blocking, UI-only)
    window_info = _get_window_for_period(period_id)

    # ── ★ SELF_VERIFY-first: short-circuit when session is anchored ───────────
    if session_id:
        anchor_svc   = get_anchor_service()
        anchor_entry = anchor_svc.get_anchor(session_id)

        if anchor_entry is not None:
            anchored_user_id = anchor_entry.user_id
            logger.debug(
                "Session anchor active: session=%s → user=%s (force_scope=%s)",
                session_id, anchored_user_id, force_scope,
            )

            try:
                sv_result = await run_in_threadpool(
                    _self_verify_scoped_match,
                    embedding,
                    firebase,
                    anchored_user_id,
                    period_id or anchor_entry.period_id,
                    excluded_ids,
                )

                anchor_meta = {
                    "session_id": session_id,
                    "user_id":    anchored_user_id,
                }

                if sv_result.matched:
                    # ✅ Fast path — anchored identity confirmed
                    del embedding
                    gc.collect()
                    logger.info(
                        "SELF_VERIFY-first HIT: session=%s user=%s → %s "
                        "(conf=%.3f, vectors=%d)",
                        session_id, anchored_user_id, sv_result.student_id,
                        sv_result.confidence, sv_result.candidates_searched,
                    )
                    return JSONResponse(status_code=200, content={
                        "matched":      True,
                        "message":      (
                            f"Face identified: {sv_result.student_name} "
                            "(session-anchored self-verify)"
                        ),
                        "student_name": sv_result.student_name,
                        "student_id":   sv_result.student_id,
                        "confidence":   round(sv_result.confidence, 4),
                        "scope_mode":   "self_verify",
                        "anchor":       anchor_meta,
                        "window":       window_info,
                    })

                # SELF_VERIFY missed
                logger.debug(
                    "SELF_VERIFY-first MISS: session=%s user=%s "
                    "(conf=%.3f, force_scope=%s)",
                    session_id, anchored_user_id, sv_result.confidence, force_scope,
                )

                if force_scope:
                    # Caller wants a hard stop — no section-roster fallback
                    del embedding
                    gc.collect()
                    return JSONResponse(status_code=200, content={
                        "matched":     False,
                        "message":     (
                            sv_result.message
                            or "Face did not match your registered profile."
                        ),
                        "confidence":  round(sv_result.confidence, 4),
                        "scope_mode":  "self_verify",
                        "anchor":      anchor_meta,
                        "force_scope": True,
                        "window":      window_info,
                    })

                # force_scope=False → fall through to section_roster below
                # (embedding is still alive; do NOT delete it here)

            except Exception as _sv_exc:
                # SELF_VERIFY attempt failed — log and fall through gracefully
                logger.warning(
                    "SELF_VERIFY-first attempt raised (swallowed, falling back): "
                    "session=%s user=%s error=%s",
                    session_id, anchored_user_id, _sv_exc,
                )

    # ── Existing section_roster / scoped-match path ───────────────────────────
    try:
        scoped_result = await run_in_threadpool(
            _scoped_match,
            embedding, firebase, user, period_id,
            scope_mode, student_id, section_id, excluded_ids,
        )

        if hasattr(scoped_result, "matched"):
            if not scoped_result.matched:
                suggestions = await run_in_threadpool(
                    _rank_embedding_candidates_sync,
                    embedding, firebase,
                    [s.strip() for s in candidate_student_ids.split(",")] if candidate_student_ids else None,
                    candidate_course_id,
                    3,
                )

                legacy_best_student, legacy_confidence, legacy_best_distance = await run_in_threadpool(
                    _match_embedding_sync,
                    embedding, firebase, COSINE_THRESHOLD, None, None,
                )
                if legacy_best_student is not None and legacy_best_distance <= COSINE_THRESHOLD:
                    del embedding
                    gc.collect()
                    return JSONResponse(status_code=200, content={
                        "matched":             True,
                        "message":             f"Face identified: {legacy_best_student.get('name', 'Unknown')} (legacy fallback)",
                        "student_name":        legacy_best_student.get("name", "Unknown"),
                        "student_id":          legacy_best_student.get("student_id", ""),
                        "confidence":          round(legacy_confidence, 4),
                        "scope_mode":          scope_mode,
                        "window":              window_info,
                        "suggested_candidates": suggestions,
                    })

                del embedding
                gc.collect()
                no_match_msg = (
                    "Face does not match your registered profile."
                    if scope_mode == "self_verify"
                    else scoped_result.message
                )
                return JSONResponse(status_code=200, content={
                    "matched":             False,
                    "message":             no_match_msg,
                    "scope_mode":          scope_mode,
                    "window":              window_info,
                    "suggested_candidates": suggestions,
                })

            best_student = {
                "student_id": scoped_result.student_id,
                "name":       scoped_result.student_name,
            }
            confidence   = scoped_result.confidence
            best_distance = scoped_result.distance

        else:
            # Legacy object fallback
            if not candidate_student_ids and not candidate_course_id and user is not None:
                derived = _get_candidate_ids_for_user(user, period_id=period_id)
                candidate_ids  = derived
                candidate_course = None
            else:
                candidate_ids  = [s.strip() for s in candidate_student_ids.split(",")] if candidate_student_ids else None
                candidate_course = candidate_course_id

            if excluded_ids:
                blocked = {sid for sid in excluded_ids if sid}
                candidate_ids = [sid for sid in (candidate_ids or []) if sid not in blocked] if candidate_ids else candidate_ids

            best_student, confidence, best_distance = await run_in_threadpool(
                _match_embedding_sync,
                embedding, firebase, COSINE_THRESHOLD,
                candidate_ids, candidate_course,
            )

        del embedding
        gc.collect()

        if best_student is None:
            return JSONResponse(status_code=200, content={
                "matched":    False,
                "message":    f"Face not recognised. Similarity: {max(0.0, 1 - best_distance):.2f}",
                "scope_mode": scope_mode,
                "window":     window_info,
            })

        return JSONResponse(status_code=200, content={
            "matched":      True,
            "message":      f"Face identified: {best_student.get('name', 'Unknown')}",
            "student_name": best_student.get("name", "Unknown"),
            "student_id":   best_student.get("student_id", ""),
            "confidence":   round(confidence, 4),
            "scope_mode":   scope_mode,
            "window":       window_info,
        })

    except ImportError:
        return JSONResponse(status_code=200, content={
            "matched": False, "message": "Server missing scipy library."
        })
    except Exception as exc:
        logger.error("Matching error: %s", exc)
        raise HTTPException(500, f"Face matching failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# confirm-attendance  (unchanged from period-locking edition)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/confirm-attendance",
    status_code=status.HTTP_200_OK,
    summary="Confirm and persist attendance after user approval (window-enforced)",
)
async def confirm_attendance(
    student_id: str = Form(...),
    confidence: float = Form(0.0),
    period_id: Optional[str] = Form(None),
    frame: Optional[UploadFile] = File(None),
):
    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    student = firebase.get_student(student_id)
    if not student:
        raise HTTPException(404, f"Student {student_id} not found in the system.")

    window     = _get_window_for_period(period_id)
    att_status = "present"
    period_doc = None

    if window is not None:
        if not window["is_open"]:
            return _window_closed_response(window, student_id)
        try:
            from services.firebase_service import get_firebase_service as _gfs
            fb2 = _gfs()
            db  = getattr(fb2, "firestore_db", None) or getattr(fb2, "_firestore", None)
            if db and period_id:
                pd_doc = db.collection("periods").document(period_id).get()
                period_doc = pd_doc.to_dict() if pd_doc.exists else None
        except Exception:
            pass

        if period_doc:
            att_status = _compute_attendance_status(window.get("phase", "open"), period_doc)

    try:
        timestamp = datetime.now()
        result    = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="web_confirmed",
            metadata={
                "method":            "face_recognition_confirmed",
                "confirmed_by_user": True,
                "period_id":         period_id,
                "attendance_status": att_status,
            },
        )
        record_id    = result.get("record_id", "")
        student_name = student.get("name", "Unknown")

        lock_svc = get_lock_service()
        if lock_svc and record_id:
            record_snapshot = {
                "record_id":  record_id,
                "student_id": student_id,
                "period_id":  period_id,
                "status":     att_status,
                "confidence": round(confidence, 4),
                "markedAt":   timestamp.isoformat(),
                "method":     "face_recognition_confirmed",
            }
            lock_svc.write_audit(
                record_id=record_id,
                action="CREATE",
                actor_id=student_id,
                after=record_snapshot,
            )

        if record_id:
            _queue_verified_outcome(
                record_id=record_id,
                student_id=student_id,
                period_id=period_id,
                confidence=confidence,
                marked_at_iso=timestamp.isoformat(),
            )

            if frame is not None:
                try:
                    learned_embedding, error_content = await _extract_embedding_from_upload(frame)
                    if error_content is None and learned_embedding is not None:
                        firebase.store_embedding(student_id, learned_embedding)
                        firebase.compute_and_update_prototype(student_id)
                except Exception:
                    logger.exception("Failed to store/update prototype for %s", student_id)

            try:
                if period_id:
                    from services.realtime_service import get_realtime_service
                    rt_svc = get_realtime_service()
                    section_id_for_broadcast = (period_doc or {}).get("class_id", "")
                    if section_id_for_broadcast:
                        asyncio.create_task(rt_svc.broadcast(
                            event_type="attendance_marked",
                            section_id=section_id_for_broadcast,
                            payload={
                                "record_id":  record_id,
                                "student_id": student_id,
                                "period_id":  period_id,
                                "status":     att_status,
                                "confidence": round(confidence, 4),
                                "markedAt":   timestamp.isoformat(),
                            },
                        ))
            except Exception:
                logger.debug("Realtime broadcast failed (swallowed)")

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return JSONResponse(status_code=200, content={
            "success":      True,
            "record_id":    record_id,
            "student_id":   student_id,
            "student_name": student_name,
            "status":       att_status,
            "confidence":   round(confidence, 4),
            "timestamp":    timestamp.isoformat(),
            "window":       window,
            "message": (
                f"Attendance marked as {att_status.upper()} for {student_name}."
                + (" You are late." if att_status == "late" else "")
            ),
        })
    except Exception as exc:
        logger.error(
            "Failed to save confirmed attendance for student=%s: %s",
            student_id, exc, exc_info=True,
        )
        raise HTTPException(
            500,
            f"Attendance recording failed: {type(exc).__name__}: {str(exc)}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# detect-face  (legacy, unchanged from period-locking edition)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/detect-face",
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Detect face and mark attendance (window-enforced, 5-attempt limit)",
)
async def detect_face_and_mark(
    file: UploadFile = File(...),
    period_id: Optional[str] = Query(None),
):
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    window = _get_window_for_period(period_id)
    if window and not window["is_open"]:
        del embedding
        gc.collect()
        return _window_closed_response(window)

    try:
        from services.face_attempt_service import get_face_attempt_service
        attempt_svc = get_face_attempt_service(
            getattr(firebase, "firestore_db", None) or getattr(firebase, "_firestore", None)
        )

        best_student, confidence, best_distance = await run_in_threadpool(
            _match_embedding_sync, embedding, firebase, COSINE_THRESHOLD
        )
        del embedding
        gc.collect()

        if best_student is None or best_distance > COSINE_THRESHOLD:
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": (
                    f"Face not recognised. "
                    f"Best similarity: {max(0.0, 1 - best_distance):.2f} "
                    f"(threshold: {1 - COSINE_THRESHOLD:.2f}). "
                    "Ensure your face is clearly visible and well-lit, "
                    "or ask admin to register your face profile."
                ),
                "window": window,
            })

        student_id   = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")

        can_attempt, current_attempts = attempt_svc.can_attempt(student_id, period_id)
        if not can_attempt:
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": (
                    f"Maximum detection attempts ({current_attempts}) reached for this period. "
                    "Please ask an instructor for assistance."
                ),
                "window": window,
                "attempt_limit_exceeded": True,
            })

        att_status = "present"
        if window:
            att_status = _compute_attendance_status(window.get("phase", "open"), best_student)

        timestamp = datetime.now()
        result    = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="web_upload",
            metadata={
                "method":            "face_recognition_upload",
                "threshold":         COSINE_THRESHOLD,
                "distance":          best_distance,
                "period_id":         period_id,
                "attendance_status": att_status,
            },
        )
        record_id = result.get("record_id", "")
        attempt_svc.reset_attempts(student_id, period_id)

        lock_svc = get_lock_service()
        if lock_svc and record_id:
            lock_svc.write_audit(
                record_id=record_id,
                action="CREATE",
                actor_id=student_id,
                after={
                    "record_id":  record_id,
                    "student_id": student_id,
                    "period_id":  period_id,
                    "status":     att_status,
                    "confidence": round(confidence, 4),
                    "markedAt":   timestamp.isoformat(),
                    "method":     "face_recognition_upload",
                },
            )

        try:
            if period_id:
                from services.realtime_service import get_realtime_service
                rt_svc = get_realtime_service()
                try:
                    from services.firebase_service import get_firebase_service as _gfs
                    fb2 = _gfs()
                    db2 = getattr(fb2, "firestore_db", None) or getattr(fb2, "_firestore", None)
                    section_for_broadcast = None
                    if db2 and period_id:
                        pd_doc = db2.collection(COLLECTION_TIMETABLE).document(period_id).get()
                        if pd_doc.exists:
                            section_for_broadcast = pd_doc.to_dict().get("class_id", "")
                except Exception:
                    section_for_broadcast = None
                if section_for_broadcast:
                    asyncio.create_task(rt_svc.broadcast(
                        event_type="attendance_marked",
                        section_id=section_for_broadcast,
                        payload={
                            "record_id": record_id, "student_id": student_id,
                            "period_id": period_id, "status": att_status,
                            "confidence": round(confidence, 4),
                            "markedAt": timestamp.isoformat(),
                        },
                    ))
        except Exception:
            logger.debug("Realtime broadcast failed (swallowed)")

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return JSONResponse(status_code=200, content={
            "matched":      True,
            "message":      f"Attendance marked as {att_status.upper()} for {student_name}.",
            "record_id":    record_id,
            "student_name": student_name,
            "student_id":   student_id,
            "status":       att_status,
            "confidence":   round(confidence, 4),
            "timestamp":    timestamp.isoformat(),
            "window":       window,
        })
    except ImportError:
        return JSONResponse(status_code=200, content={
            "matched": False, "message": "Server missing scipy library."
        })
    except Exception as exc:
        logger.error("Matching error: %s", exc)
        raise HTTPException(500, f"Face matching failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# mark-attendance  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/mark-attendance",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mark_attendance(request: MarkAttendanceRequest) -> MarkAttendanceResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")

        student = firebase.get_student(request.student_id)
        if not student:
            raise HTTPException(404, f"Student {request.student_id} not found")

        period_id = None
        if request.metadata:
            period_id = request.metadata.get("period_id")

        window = _get_window_for_period(period_id)
        if window and not window["is_open"]:
            raise HTTPException(
                status_code=423,
                detail={"message": window.get("message", "Attendance window closed."), "window": window},
            )

        timestamp = request.timestamp or datetime.now()
        result    = firebase.mark_attendance(
            student_id=request.student_id,
            timestamp=timestamp,
            confidence=request.confidence,
            track_id=request.track_id,
            camera_id=request.camera_id,
            metadata=request.metadata,
        )
        record_id = result["record_id"]

        lock_svc = get_lock_service()
        if lock_svc and record_id:
            lock_svc.write_audit(
                record_id=record_id,
                action="CREATE",
                actor_id=request.student_id,
                after={
                    "record_id": record_id, "student_id": request.student_id,
                    "period_id": period_id, "status": "present",
                    "confidence": round(request.confidence, 4),
                    "markedAt": timestamp.isoformat(), "method": "mark_attendance_api",
                },
            )

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return MarkAttendanceResponse(
            success=True, record_id=record_id,
            student_id=request.student_id,
            timestamp=timestamp.isoformat(),
            message="Attendance marked successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to mark attendance: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# mark-mobile  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/mark-mobile",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mark_attendance_mobile(
    student_id:   str = Query(...),
    image_base64: str = Query(...),
    period_id:    Optional[str] = Query(None),
) -> MarkAttendanceResponse:
    try:
        from models.model_manager import ModelManager
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")

        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(404, f"Student {student_id} not found")

        window = _get_window_for_period(period_id)
        if window and not window["is_open"]:
            raise HTTPException(
                status_code=423,
                detail={"message": window.get("message", "Attendance window closed."), "window": window},
            )

        from PIL import Image
        try:
            image_data  = base64.b64decode(image_base64)
            image_array = np.array(Image.open(io.BytesIO(image_data)).convert("RGB"))
            del image_data
        except Exception as exc:
            raise HTTPException(400, f"Invalid image format: {exc}")
        image_array = _resize_if_needed(image_array)

        def _mobile_inference():
            THRESHOLD = 0.6
            extractor = ModelManager.get_facenet_extractor()
            embedding = extractor.extract_embedding(image_array)
            if embedding is None:
                raise ValueError("No face detected")
            embeddings = FirebaseService.get_all_embeddings(student)
            if not embeddings:
                raise ValueError("No face profile found for student")
            best_match = min(float(cosine(embedding, arr)) for arr in embeddings)
            conf = float(1.0 - min(best_match, 1.0))
            if best_match > THRESHOLD:
                raise ValueError(f"Face does not match. Confidence: {conf:.2f}")
            return conf

        try:
            confidence = await run_in_threadpool(_mobile_inference)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except (ImportError, HTTPException):
            raise
        except Exception as exc:
            raise HTTPException(400, str(exc))
        finally:
            del image_array
            gc.collect()

        att_status = "present"
        if window:
            att_status = _compute_attendance_status(window.get("phase", "open"), student)

        timestamp = datetime.now()
        result    = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="mobile_app",
            metadata={
                "method":            "face_recognition_mobile",
                "period_id":         period_id,
                "attendance_status": att_status,
            },
        )
        record_id = result["record_id"]

        lock_svc = get_lock_service()
        if lock_svc and record_id:
            lock_svc.write_audit(
                record_id=record_id,
                action="CREATE",
                actor_id=student_id,
                after={
                    "record_id": record_id, "student_id": student_id,
                    "period_id": period_id, "status": att_status,
                    "confidence": round(confidence, 4),
                    "markedAt": timestamp.isoformat(), "method": "face_recognition_mobile",
                },
            )

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return MarkAttendanceResponse(
            success=True, record_id=record_id, student_id=student_id,
            timestamp=timestamp.isoformat(),
            message=f"Attendance marked as {att_status.upper()} (confidence: {confidence:.2f})",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to mark attendance: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# daily-report  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance/daily-report")
async def get_daily_report(
    date: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
):
    if class_id:
        try:
            from services.attendance_service import AttendanceService
            svc    = AttendanceService()
            report = svc.generate_daily_report(class_id=class_id, date=date)
            return JSONResponse(status_code=200, content=report)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except Exception as exc:
            logger.error("generate_daily_report error: %s", exc)
            raise HTTPException(500, f"Failed to generate report: {exc}")

    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")
        report_date = datetime.fromisoformat(date) if date else None
        report      = firebase.get_daily_report(report_date)
        if "error" in report:
            raise HTTPException(500, report["error"])
        from schemas.attendance_schemas import DailyReportResponse as _DR
        return _DR(
            date=report["date"],
            total_records=report["total_records"],
            unique_students=report["unique_students"],
            records=[],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to generate report: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Student management  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/register-student",
    response_model=StudentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_student(request: StudentRegistrationRequest) -> StudentRegistrationResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")
        existing = firebase.get_student(request.student_id)
        if existing:
            raise HTTPException(409, f"Student {request.student_id} already registered")
        embeddings_array = np.array(request.embeddings[0])
        firebase.register_student(
            student_id=request.student_id, name=request.name, email=request.email,
            embeddings=embeddings_array, phone=request.phone, metadata=request.metadata,
        )
        for emb in request.embeddings[1:]:
            firebase.store_embedding(request.student_id, np.array(emb))
        return StudentRegistrationResponse(
            success=True, student_id=request.student_id, message="Student registered successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error registering student: %s", exc)
        raise HTTPException(500, f"Failed to register student: {exc}")


@router.get("/students", response_model=StudentListResponse)
async def get_students(
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> StudentListResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")
        all_students = firebase.get_all_students()
        paginated    = all_students[offset: offset + limit]
        students_info = [
            StudentInfo(
                student_id=s.get("student_id", ""), name=s.get("name", ""),
                email=s.get("email", ""), phone=s.get("phone"),
                registered_at=s.get("registered_at", ""), last_seen=s.get("last_seen"),
                attendance_count=s.get("attendance_count", 0),
                status=s.get("status", "active"), metadata=s.get("metadata"),
            )
            for s in paginated
        ]
        return StudentListResponse(success=True, count=len(students_info), students=students_info)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to retrieve students: {exc}")


@router.get("/students/{student_id}", response_model=StudentInfo)
async def get_student(student_id: str) -> StudentInfo:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")
        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(404, f"Student {student_id} not found")
        return StudentInfo(
            student_id=student.get("student_id", ""), name=student.get("name", ""),
            email=student.get("email", ""), phone=student.get("phone"),
            registered_at=student.get("registered_at", ""), last_seen=student.get("last_seen"),
            attendance_count=student.get("attendance_count", 0),
            status=student.get("status", "active"), metadata=student.get("metadata"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get student: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Attendance query  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance", response_model=AttendanceListResponse)
async def get_attendance(
    student_id: Optional[str] = Query(None),
    date_from:  Optional[str] = Query(None),
    date_to:    Optional[str] = Query(None),
    limit:      int = Query(100, ge=1, le=1000),
    offset:     int = Query(0, ge=0),
) -> AttendanceListResponse:
    try:
        firebase   = get_firebase_service()
        if not firebase:
            raise HTTPException(503, "Firebase service not initialized")
        from_date  = datetime.fromisoformat(date_from) if date_from else None
        to_date    = datetime.fromisoformat(date_to)   if date_to   else None
        records    = firebase.get_attendance_records(
            student_id=student_id, date_from=from_date, date_to=to_date, limit=limit + offset,
        )
        paginated  = records[offset: offset + limit]
        att_records = [
            AttendanceRecord(
                record_id=str(r.get("timestamp", "")), student_id=r.get("student_id", ""),
                timestamp=r.get("timestamp", ""), date=r.get("date", ""), time=r.get("time", ""),
                confidence=r.get("confidence", 0.0), track_id=r.get("track_id"),
                camera_id=r.get("camera_id", "default"), status=r.get("status", "present"),
                metadata=r.get("metadata"),
            )
            for r in paginated
        ]
        return AttendanceListResponse(success=True, count=len(att_records), records=att_records)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to retrieve attendance: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Stream management  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/streams", response_model=StreamHealth, status_code=status.HTTP_201_CREATED)
async def add_stream(request: StreamConfig) -> StreamHealth:
    try:
        manager      = get_stream_manager()
        classroom_id = getattr(request, "classroom_id", None)
        handler = manager.add_stream(
            stream_id=request.stream_id, rtsp_url=request.rtsp_url,
            frame_skip=request.frame_skip,
            min_consecutive_frames=request.min_consecutive_frames,
            confidence_threshold=request.confidence_threshold,
            classroom_id=classroom_id,
        )
        if not handler:
            raise HTTPException(400, "Failed to add stream")
        if request.enabled:
            manager.start_stream(request.stream_id)
        return StreamHealth(
            stream_id=request.stream_id,
            status="running" if request.enabled else "idle",
            last_frame=None, frames_processed=0, fps=0.0, errors=0,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to add stream: {exc}")


@router.get("/streams")
async def get_streams():
    try:
        manager = get_stream_manager()
        streams = manager.get_all_streams()
        return {"success": True, "count": len(streams), "streams": streams}
    except Exception as exc:
        raise HTTPException(500, f"Failed to get streams: {exc}")


@router.get("/streams/{stream_id}")
async def get_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        handler = manager.get_stream(stream_id)
        if handler is None:
            raise HTTPException(404, f"Stream {stream_id} not found")
        return {"success": True, "stream": handler.get_metrics()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get stream: {exc}")


@router.get("/streams/{stream_id}/ai-status")
async def get_stream_ai_status(stream_id: str):
    try:
        manager = get_stream_manager()
        handler = manager.get_stream(stream_id)
        if handler is None:
            raise HTTPException(404, f"Stream {stream_id} not found")
        m = handler.get_metrics()
        is_ai_active: bool = m.get("is_ai_active", False)
        return JSONResponse(status_code=200, content={
            "stream_id":             stream_id,
            "classroom_id":          m.get("classroom_id"),
            "is_ai_active":          is_ai_active,
            "display_status":        "Live Monitoring" if is_ai_active else "System Idle",
            "last_ai_trigger":       m.get("last_ai_trigger"),
            "students_loaded":       m.get("students_loaded", False),
            "students_loaded_count": m.get("students_loaded_count", 0),
            "student_load_error":    m.get("student_load_error"),
            "fps":                   m.get("fps", 0.0),
            "active_tracks":         m.get("active_tracks", 0),
            "marked_students_today": m.get("marked_students", 0),
            "stream_status":         m.get("status", "unknown"),
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get AI status: {exc}")


@router.post("/streams/{stream_id}/start")
async def start_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.start_stream(stream_id):
            raise HTTPException(404, f"Stream {stream_id} not found")
        return {"success": True, "message": f"Stream {stream_id} started."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to start stream: {exc}")


@router.post("/streams/{stream_id}/stop")
async def stop_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.stop_stream(stream_id):
            raise HTTPException(404, f"Stream {stream_id} not found")
        return {"success": True, "message": f"Stream {stream_id} stopped"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to stop stream: {exc}")


@router.post("/streams/{stream_id}/reload-students")
async def reload_students(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.reload_students(stream_id):
            raise HTTPException(404, f"Stream {stream_id} not found")
        return {"success": True, "message": f"Student reload triggered for {stream_id}."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to reload students: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Health / Stats  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    try:
        from models.model_manager import ModelManager
        firebase   = get_firebase_service()
        manager    = get_stream_manager()
        lock_svc   = get_lock_service()
        anchor_svc = get_anchor_service()
        services = {
            "firebase":     "healthy" if firebase  else "unavailable",
            "streams":      "healthy" if manager   else "unavailable",
            "models":       "healthy" if ModelManager.is_initialized() else "not_initialized",
            "lock_service": "healthy" if lock_svc  else "unavailable",
            "anchor_service": f"healthy ({anchor_svc.count()} active anchors)",
        }
        return HealthCheckResponse(status="healthy", services=services, uptime_seconds=0)
    except Exception as exc:
        return HealthCheckResponse(status="error", services={"error": str(exc)}, uptime_seconds=0)


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats() -> SystemStatsResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            return SystemStatsResponse()
        all_students       = firebase.get_all_students()
        attendance_records = firebase.get_attendance_records(limit=10000)
        today              = datetime.now().date()
        today_records      = []
        for r in attendance_records:
            try:
                if datetime.fromisoformat(str(r.get("date", ""))).date() == today:
                    today_records.append(r)
            except Exception:
                pass
        return SystemStatsResponse(
            total_students=len(all_students),
            total_attendance_records=len(attendance_records),
            total_detections_today=len(today_records),
            average_confidence=(
                sum(r.get("confidence", 0) for r in attendance_records) /
                len(attendance_records) if attendance_records else 0
            ),
        )
    except Exception as exc:
        raise HTTPException(500, f"Failed to get stats: {exc}")