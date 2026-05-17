"""
services/scoped_embedding_search.py
─────────────────────────────────────
Scoped embedding search: applies an IdentityScope to narrow the candidate
pool before running cosine similarity matching.

Features (merged)
──────────────────
Session anchoring (Doc 8)
  After a successful SELF / SELF_VERIFY match, the caller anchors the session
  to a single student_id so every subsequent frame only searches that user.
  ``SessionAnchorStore`` is thread-safe and supports optional TTL expiry.

Adaptive thresholding — two complementary strategies
  1. Firestore variance (primary) — ``_fetch_embedding_variance()`` reads the
     pre-computed per-dimension variance stored at enrollment time and passes
     it through ``compute_adaptive_threshold()`` (from face_recognition_service).
     This is the most accurate signal because it reflects the actual spread of
     the user's enrolled embeddings.
  2. Live similarity history (fallback) — ``per_user_adaptive_threshold()``
     maintains a rolling window of recent match scores (mean − 1σ) for users
     whose Firestore document does not yet carry variance stats (e.g. legacy
     single-photo enrollments).  Falls back to ``_ADAPTIVE_BASE`` when fewer
     than 3 history samples exist.
  Both strategies apply to SELF *and* SELF_VERIFY scopes.

Quick-accept path (Doc 9)
  When ``QUICK_ACCEPT_SELF_VERIFY=true`` (env) and the SELF_VERIFY session
  clears the adaptive threshold + liveness gate, ``ScopedMatchResult``
  carries ``quick_accept=True`` so ``OptimizedAttendancePipeline`` can bypass
  the multi-frame temporal verifier and mark attendance immediately.

Liveness + metadata fusion (Doc 9)
  ``search()`` accepts an optional ``liveness_result`` and ``login_metadata``.
  When supplied, ``fuse_confidence()`` produces the final confidence score;
  otherwise the raw prototype score is used.

Integration note for rtsp_stream_handler.py
────────────────────────────────────────────
  anchor_store = SessionAnchorStore()

  # On successful login-face match:
  anchor_store.anchor(stream_id, student_id, student_name, scope, ttl_seconds=300)

  # Per-frame: check anchor first
  anchor = anchor_store.get(stream_id)
  if anchor:
      scope = ScopeTarget(
          scope_type=IdentityScopeType.SELF_VERIFY,
          student_ids=[anchor.student_id],
          resolved_by=anchor.student_id,
      )

  # On logout / stream end:
  anchor_store.clear(stream_id)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.distance import cosine

try:
    from attendance_backend.models.identity_context import (
        IdentityScopeType,
        ScopeTarget,
        ScopedMatchResult,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from models.identity_context import (
        IdentityScopeType,
        ScopeTarget,
        ScopedMatchResult,
    )

try:
    from attendance_backend.services.face_recognition_service import (
        compute_adaptive_threshold,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from services.face_recognition_service import compute_adaptive_threshold

try:
    from attendance_backend.services.liveness import (
        LivenessResult,
        LoginMetadata,
        fuse_confidence,
    )
    _LIVENESS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LIVENESS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ── Search / voting constants ──────────────────────────────────────────────────

COSINE_THRESHOLD: float = 0.55

T_PROTO: float = 0.58          # minimum prototype score to consider a match
T_VOTE: float = 0.35           # minimum softmax vote share to confirm
TOP_K: int = 10                # top-K embeddings used in weighted vote
ALPHA: float = 10.0            # temperature for softmax vote weighting

# ── Firestore-variance adaptive threshold (primary) ───────────────────────────
# Mirrors the constants used in face_recognition_service.compute_adaptive_threshold.

ADAPTIVE_K: float = 1.5        # std-dev multiplier
ADAPTIVE_MIN: float = 0.30     # floor
ADAPTIVE_MAX: float = 0.80     # ceiling

# ── History-based adaptive threshold (fallback) ───────────────────────────────

_ADAPTIVE_BASE: float = 0.60   # floor / default when no history
_HISTORY_WINDOW: int = 20      # rolling window of match scores per user

# ── Quick-accept ──────────────────────────────────────────────────────────────

QUICK_ACCEPT_SELF_VERIFY: bool = (
    os.environ.get("QUICK_ACCEPT_SELF_VERIFY", "true").lower() == "true"
)


# ─────────────────────────────────────────────────────────────────────────────
# Session anchoring (Doc 8)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionAnchor:
    """
    Represents a locked identity for a stream/session.

    Attributes:
        stream_id:    Opaque session/stream key (e.g. RTSP URL, websocket id).
        student_id:   Anchored student.
        student_name: Display name (for logging).
        scope:        The scope that produced the successful match (stored for
                      audit / replay purposes).
        anchored_at:  Unix timestamp when anchor was set.
        ttl_seconds:  If > 0 the anchor expires automatically after this many
                      seconds.  Pass 0 to disable TTL.
    """
    stream_id: str
    student_id: str
    student_name: str
    scope: ScopeTarget
    anchored_at: float = field(default_factory=time.time)
    ttl_seconds: float = 0.0

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self.anchored_at) > self.ttl_seconds


class SessionAnchorStore:
    """
    Thread-safe store for active session anchors.

    Usage
    -----
    ::

        store = SessionAnchorStore()

        # After a successful match:
        store.anchor(
            stream_id="cam-01", student_id="stu_abc",
            student_name="Alice", scope=current_scope, ttl_seconds=300,
        )

        # Per-frame check:
        anchor = store.get("cam-01")  # None if absent or expired

        # On logout / stream teardown:
        store.clear("cam-01")

    ``SessionAnchorStore`` is intentionally a plain in-process store.
    For multi-process / multi-host deployments back it with Redis by
    subclassing and overriding ``anchor``, ``get``, and ``clear``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._anchors: Dict[str, SessionAnchor] = {}

    def anchor(
        self,
        stream_id: str,
        student_id: str,
        student_name: str,
        scope: ScopeTarget,
        ttl_seconds: float = 0.0,
    ) -> SessionAnchor:
        """
        Set (or replace) an anchor for ``stream_id``.

        Returns the created :class:`SessionAnchor`.
        """
        a = SessionAnchor(
            stream_id=stream_id,
            student_id=student_id,
            student_name=student_name,
            scope=scope,
            ttl_seconds=ttl_seconds,
        )
        with self._lock:
            self._anchors[stream_id] = a
        logger.info(
            "Session anchored: stream=%s student=%s ttl=%ss",
            stream_id,
            student_id,
            ttl_seconds if ttl_seconds > 0 else "∞",
        )
        return a

    def get(self, stream_id: str) -> Optional[SessionAnchor]:
        """
        Return the active anchor for ``stream_id``, or ``None``.

        Expired anchors are evicted and ``None`` is returned.
        """
        with self._lock:
            a = self._anchors.get(stream_id)
            if a is None:
                return None
            if a.is_expired:
                del self._anchors[stream_id]
                logger.info(
                    "Session anchor expired: stream=%s student=%s",
                    stream_id, a.student_id,
                )
                return None
            return a

    def clear(self, stream_id: str) -> bool:
        """
        Remove the anchor for ``stream_id``.

        Returns ``True`` if an anchor existed and was removed.
        """
        with self._lock:
            removed = self._anchors.pop(stream_id, None)
        if removed:
            logger.info(
                "Session anchor cleared: stream=%s student=%s",
                stream_id, removed.student_id,
            )
            return True
        return False

    def all_active(self) -> List[SessionAnchor]:
        """Return a snapshot of all non-expired anchors."""
        with self._lock:
            return [a for a in self._anchors.values() if not a.is_expired]


# ─────────────────────────────────────────────────────────────────────────────
# Scoped embedding search
# ─────────────────────────────────────────────────────────────────────────────

class ScopedEmbeddingSearch:
    """
    Embedding search with identity scoping, adaptive per-user thresholds, an
    optional liveness-fused quick-accept path for SELF_VERIFY sessions, and
    full session-anchor support.

    Parameters
    ----------
    firebase_service:
        Injected Firebase client.  Pass ``None`` in unit tests.
    quick_accept_enabled:
        Instance-level override for ``QUICK_ACCEPT_SELF_VERIFY``.
        When ``None``, the module-level env flag is used.
    """

    def __init__(
        self,
        firebase_service=None,
        quick_accept_enabled: Optional[bool] = None,
    ) -> None:
        self._fb = firebase_service
        self._quick_accept_enabled: bool = (
            QUICK_ACCEPT_SELF_VERIFY
            if quick_accept_enabled is None
            else quick_accept_enabled
        )
        # Per-user rolling similarity history for fallback adaptive threshold.
        # {user_id: [similarity_score, ...]}  (capped at _HISTORY_WINDOW)
        self._similarity_history: Dict[str, List[float]] = {}

    # ── Public configuration ──────────────────────────────────────────────────

    def set_quick_accept(self, enabled: bool) -> None:
        """Toggle the quick-accept path at runtime without recreating the object."""
        self._quick_accept_enabled = enabled
        logger.info(
            "Quick-accept SELF_VERIFY: %s", "ENABLED" if enabled else "DISABLED"
        )

    # ── Adaptive threshold — two strategies ──────────────────────────────────

    def _firestore_adaptive_threshold(
        self, student_id: Optional[str]
    ) -> Optional[float]:
        """
        Primary adaptive threshold: fetch pre-computed embedding variance from
        Firestore and pass it through ``compute_adaptive_threshold()``.

        Returns ``None`` if the variance field is absent or the fetch fails,
        allowing the caller to fall through to the history-based fallback.
        """
        variance = self._fetch_embedding_variance(student_id)
        if variance is None:
            return None
        thresh = compute_adaptive_threshold(
            base_threshold=T_PROTO,
            variance=variance,
            k=ADAPTIVE_K,
            min_threshold=ADAPTIVE_MIN,
            max_threshold=ADAPTIVE_MAX,
        )
        logger.debug(
            "Firestore adaptive threshold for %s: base=%.3f var=%.4f → %.3f",
            student_id, T_PROTO, variance, thresh,
        )
        return thresh

    def per_user_adaptive_threshold(self, user_id: str) -> float:
        """
        Fallback adaptive threshold: derive from the local similarity history.

        Algorithm: threshold = max(_ADAPTIVE_BASE, mean − 1σ) capped at 0.95.
        Falls back to ``_ADAPTIVE_BASE`` when fewer than 3 samples exist.

        This is used when the Firestore document does not yet carry an
        ``embedding_variance`` field (e.g. legacy single-photo enrollments).

        Parameters
        ----------
        user_id:
            Student / user identifier.

        Returns
        -------
        float
            Threshold in [_ADAPTIVE_BASE, 0.95].
        """
        history = self._similarity_history.get(user_id, [])
        if len(history) < 3:
            return _ADAPTIVE_BASE

        arr = np.array(history[-_HISTORY_WINDOW:], dtype=np.float32)
        mean_sim = float(np.mean(arr))
        std_sim = float(np.std(arr))
        threshold = float(np.clip(mean_sim - std_sim, _ADAPTIVE_BASE, 0.95))

        logger.debug(
            "History adaptive threshold for %s: %.4f (mean=%.3f, std=%.3f, n=%d)",
            user_id, threshold, mean_sim, std_sim, len(arr),
        )
        return threshold

    def _effective_adaptive_threshold(self, student_id: Optional[str]) -> float:
        """
        Return the best available adaptive threshold for ``student_id``.

        Priority: Firestore variance (primary) → history-based (fallback).
        """
        thresh = self._firestore_adaptive_threshold(student_id)
        if thresh is not None:
            return thresh
        return self.per_user_adaptive_threshold(student_id or "")

    def _record_similarity(self, user_id: str, similarity: float) -> None:
        """Append a match score to the user's history ring buffer."""
        history = self._similarity_history.setdefault(user_id, [])
        history.append(similarity)
        if len(history) > _HISTORY_WINDOW:
            history.pop(0)

    # ── Main search entry-point ───────────────────────────────────────────────

    def search(
        self,
        query_embedding: np.ndarray,
        scope: ScopeTarget,
        threshold: float = COSINE_THRESHOLD,
        liveness_result: Optional["LivenessResult"] = None,
        login_metadata: Optional["LoginMetadata"] = None,
    ) -> ScopedMatchResult:
        """
        Search for the best matching student within the given scope.

        Quick-accept path (SELF_VERIFY only)
        ─────────────────────────────────────
        Set ``ScopedMatchResult.quick_accept = True`` when ALL of:
          1. ``scope.scope_type == IdentityScopeType.SELF_VERIFY``
          2. ``self._quick_accept_enabled`` is True
          3. Best prototype score ≥ effective adaptive threshold (Firestore
             variance if available, else history-based)
          4. Liveness OK: ``liveness_result.is_live`` is True, or no liveness
             result provided (treated as neutral pass)

        When ``liveness_result`` is provided and the liveness module is
        available, ``fuse_confidence()`` is used and its output replaces the
        raw prototype score as the returned ``confidence``.

        Parameters
        ----------
        query_embedding:   FaceNet embedding for the detected face.
        scope:             Identity scope controlling the candidate pool.
        threshold:         Fallback cosine distance threshold (global search).
        liveness_result:   Optional output from ``LivenessDetector.check()``.
        login_metadata:    Optional device/location metadata for fusion.

        Returns
        -------
        ScopedMatchResult
            Always includes ``quick_accept`` bool field.
        """
        # ── Normalize query ────────────────────────────────────────────────
        try:
            q = query_embedding.astype(np.float32)
            q_norm = q / (np.linalg.norm(q) + 1e-10)
        except Exception:
            q_norm = query_embedding

        if scope.scope_type == IdentityScopeType.GLOBAL or not scope.student_ids:
            return self._global_search(query_embedding, threshold, scope)

        candidates = self._load_candidates(scope.student_ids)
        if not candidates:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=0.0,
                distance=1.0,
                scope=scope,
                candidates_searched=0,
                quick_accept=False,
                message="No embeddings found for the scoped candidates.",
            )

        # ── Build prototypes and flat embedding list ───────────────────────
        prototypes: Dict[str, np.ndarray] = {}
        flat_list: List[Tuple[str, np.ndarray, str]] = []
        total_vectors = 0

        for student_id, embeddings, name in candidates:
            normed: List[np.ndarray] = []
            for emb in embeddings:
                try:
                    if emb.shape != query_embedding.shape:
                        continue
                    e = emb.astype(np.float32)
                    e = e / (np.linalg.norm(e) + 1e-10)
                    normed.append(e)
                    flat_list.append((student_id, e, name))
                    total_vectors += 1
                except Exception:
                    continue
            if normed:
                prototypes[student_id] = np.mean(np.stack(normed, axis=0), axis=0)

        if not flat_list:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=0.0,
                distance=1.0,
                scope=scope,
                candidates_searched=0,
                quick_accept=False,
                message="No valid embeddings in scope.",
            )

        # ── Prototype scores ───────────────────────────────────────────────
        proto_scores: Dict[str, float] = {
            sid: float(np.dot(q_norm, proto))
            for sid, proto in prototypes.items()
        }

        # ── Top-K softmax vote ─────────────────────────────────────────────
        sims = sorted(
            [(sid, float(np.dot(q_norm, emb))) for sid, emb, _ in flat_list],
            key=lambda x: x[1],
            reverse=True,
        )
        topk = sims[:TOP_K]
        weights: Dict[str, float] = {}
        total_w = 0.0
        for sid, sim in topk:
            w = float(np.exp(ALPHA * sim))
            weights[sid] = weights.get(sid, 0.0) + w
            total_w += w
        votes: Dict[str, float] = {
            sid: (w / total_w if total_w > 0 else 0.0)
            for sid, w in weights.items()
        }

        # ── Best candidate ─────────────────────────────────────────────────
        if proto_scores:
            best_sid, best_score = max(proto_scores.items(), key=lambda x: x[1])
        else:
            best_sid, best_score = max(votes.items(), key=lambda x: x[1])

        best_vote = votes.get(best_sid, 0.0)
        best_conf = float(best_score)
        best_distance = float(max(0.0, 1.0 - best_score))

        # ── Adaptive threshold for SELF and SELF_VERIFY ────────────────────
        is_self = scope.scope_type == IdentityScopeType.SELF
        is_self_verify = scope.scope_type == IdentityScopeType.SELF_VERIFY

        effective_t_proto = T_PROTO
        if is_self or is_self_verify:
            effective_t_proto = self._effective_adaptive_threshold(
                scope.resolved_by
            )

        # ── Decision rule ──────────────────────────────────────────────────
        if best_score < effective_t_proto or best_vote < T_VOTE:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=best_conf,
                distance=best_distance,
                scope=scope,
                candidates_searched=total_vectors,
                quick_accept=False,
                message=(
                    f"No match (proto={best_score:.2f} < {effective_t_proto:.2f} "
                    f"or vote={best_vote:.2f} < {T_VOTE:.2f}). "
                    f"Searched {total_vectors} vectors."
                ),
            )

        # ── SELF / SELF_VERIFY identity check ──────────────────────────────
        if (is_self or is_self_verify) and best_sid != scope.resolved_by:
            logger.warning(
                "%s scope mismatch: query by %s matched %s — rejecting.",
                scope.scope_type, scope.resolved_by, best_sid,
            )
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=best_conf,
                distance=best_distance,
                scope=scope,
                candidates_searched=total_vectors,
                quick_accept=False,
                message="Face did not match your registered profile.",
            )

        # ── Record score for history-based adaptive threshold ──────────────
        self._record_similarity(best_sid, best_score)

        # ── Quick-accept evaluation (SELF_VERIFY only) ─────────────────────
        quick_accept = False
        if is_self_verify and self._quick_accept_enabled:
            adaptive_thresh = self._effective_adaptive_threshold(best_sid)

            # Liveness gate: neutral pass when no result provided.
            liveness_ok = liveness_result is None or liveness_result.is_live

            if _LIVENESS_AVAILABLE and liveness_result is not None:
                # Full fusion path: fuse_confidence() decides acceptance.
                fused = fuse_confidence(
                    embedding_similarity=best_score,
                    liveness_result=liveness_result,
                    metadata=login_metadata,
                    accept_threshold=adaptive_thresh,
                )
                quick_accept = fused.accept
                best_conf = fused.final_confidence
                logger.info(
                    "SELF_VERIFY quick-accept (fused): %s | fused=%.4f "
                    "thresh=%.4f accept=%s",
                    best_sid, fused.final_confidence, adaptive_thresh, quick_accept,
                )
            else:
                # Fallback: raw prototype score vs adaptive threshold.
                quick_accept = liveness_ok and (best_score >= adaptive_thresh)
                logger.info(
                    "SELF_VERIFY quick-accept (proto): %s | proto=%.4f "
                    "thresh=%.4f liveness_ok=%s accept=%s",
                    best_sid, best_score, adaptive_thresh, liveness_ok, quick_accept,
                )

        # ── Build and return final result ──────────────────────────────────
        matched_name = next(
            (name for sid, _, name in candidates if sid == best_sid), "Unknown"
        )
        logger.info(
            "Scoped match [%s]: %s → %s "
            "(proto=%.3f, vote=%.3f, t_proto=%.3f, vectors=%d, quick_accept=%s)",
            scope.scope_type, scope.resolved_by, best_sid,
            best_score, best_vote, effective_t_proto, total_vectors, quick_accept,
        )
        return ScopedMatchResult(
            matched=True,
            student_id=best_sid,
            student_name=matched_name,
            confidence=best_conf,
            distance=best_distance,
            scope=scope,
            candidates_searched=total_vectors,
            quick_accept=quick_accept,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_embedding_variance(
        self, student_id: Optional[str]
    ) -> Optional[float]:
        """
        Retrieve pre-computed embedding variance for a student from Firestore.

        Expects the student document to carry an ``"embedding_variance"`` float
        field in cosine-distance space [0, 1] (written by ``enroll_student_multi``
        via ``firebase_service.store_enrollment()``).

        Returns ``None`` if the field is absent, the fetch fails, or no
        firebase service is configured.
        """
        if not self._fb or not student_id:
            return None
        try:
            student = self._fb.get_student(student_id)
            if not student:
                return None
            var = student.get("embedding_variance")
            return float(var) if var is not None else None
        except Exception as exc:
            logger.debug(
                "Could not fetch embedding variance for %s: %s", student_id, exc
            )
            return None

    def _load_candidates(
        self, student_ids: List[str]
    ) -> List[Tuple[str, List[np.ndarray], str]]:
        """Load embeddings for each student_id from Firestore."""
        try:
            from attendance_backend.services.firebase_service import FirebaseService
        except ImportError:  # pragma: no cover - script-mode fallback
            from services.firebase_service import FirebaseService

        results: List[Tuple[str, List[np.ndarray], str]] = []
        if not self._fb:
            return results

        for sid in student_ids:
            try:
                student = self._fb.get_student(sid)
                if not student:
                    continue
                embeddings = FirebaseService.get_all_embeddings(student)
                if embeddings:
                    results.append((sid, embeddings, student.get("name", sid)))
            except Exception as exc:
                logger.warning(
                    "Could not load embeddings for %s: %s", sid, exc
                )
        return results

    def _global_search(
        self,
        query_embedding: np.ndarray,
        threshold: float,
        scope: ScopeTarget,
    ) -> ScopedMatchResult:
        """Brute-force cosine search across all enrolled students."""
        if not self._fb:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=0.0,
                distance=1.0,
                scope=scope,
                candidates_searched=0,
                quick_accept=False,
                message="Firebase service not available.",
            )

        try:
            from attendance_backend.services.firebase_service import FirebaseService
        except ImportError:  # pragma: no cover - script-mode fallback
            from services.firebase_service import FirebaseService

        all_students = self._fb.get_all_students()
        best_distance = float("inf")
        best_student: Optional[Dict[str, Any]] = None
        total_vectors = 0

        for student in all_students:
            for emb in FirebaseService.get_all_embeddings(student):
                if emb.shape != query_embedding.shape:
                    continue
                d = float(cosine(query_embedding, emb))
                total_vectors += 1
                if d < best_distance:
                    best_distance = d
                    best_student = student

        confidence = float(1.0 - min(best_distance, 1.0))

        if best_distance > threshold or best_student is None:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=confidence,
                distance=best_distance,
                scope=scope,
                candidates_searched=total_vectors,
                quick_accept=False,
                message=f"No global match (best conf: {confidence:.2f}).",
            )

        return ScopedMatchResult(
            matched=True,
            student_id=best_student.get("student_id", ""),
            student_name=best_student.get("name", "Unknown"),
            confidence=confidence,
            distance=best_distance,
            scope=scope,
            candidates_searched=total_vectors,
            quick_accept=False,  # global path never quick-accepts
        )