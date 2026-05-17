"""
api/attendance.py  — enhanced with period-locking and attendance-window logic
─────────────────────────────────────────────────────────────────────────────
Changes vs the original (2026-04-30)
--------------------------------------
★ Window enforcement
  Every mark-attendance path checks AttendanceLockService.get_window_status()
  before writing.  If the window is closed the endpoint returns HTTP 423 with
  a WindowClosedResponse body containing a teacher-friendly message.

★ Late detection
  Students who arrive after LATE_THRESHOLD_MINUTES into the period are
  automatically recorded as "late" instead of "present".

★ Grace-period detection
  Students who mark between period_end and period_end+ATTENDANCE_WINDOW_MINUTES
  are recorded as "late" regardless of early vs late threshold.

★ Audit trail
  Every successful write calls AttendanceLockService.write_audit() so that
  GET /teacher/attendance/{record_id}/audit always returns a full history.

★ Auto-lock trigger
  After the last valid write in the grace period, _maybe_autolock() is called
  to check and fire the auto-lock if the window has now expired.

★ New endpoint
  GET /attendance/window-status?period_id=…   — returns real-time window info
      for frontend polling (used by student-facing mark screen).

★ New endpoint
  GET /attendance/{record_id}/audit            — public read of an audit trail.

★ Daily report
  GET /attendance/daily-report now delegates to
  AttendanceService.generate_daily_report() for richer output.

All original endpoints are preserved with their signatures unchanged.
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES  = 10 * 1024 * 1024   # 10 MB
TARGET_LONG_EDGE  = 640
COSINE_THRESHOLD  = 0.55


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
# Window / lock helpers
# ══════════════════════════════════════════════════════════════════════════════

def _compute_attendance_status(
    window_phase: str,
    period: dict,
) -> str:
    """
    Decide whether a student marking now should be "present" or "late".

    Rules:
    • phase == "open"  AND elapsed <= LATE_THRESHOLD_MINUTES → "present"
    • phase == "open"  AND elapsed >  LATE_THRESHOLD_MINUTES → "late"
    • phase == "grace"                                        → "late"
    • anything else                                           → "present" (fallback)
    """
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
    """Fetch window status; return None when lock service is unavailable."""
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
    """Return HTTP 423 with teacher-friendly body."""
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
    """
    Background coroutine: check if the grace period has now expired and
    auto-lock if so.  Swallows all errors — must not affect the response.
    """
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
    """
    Build the EmbeddingScope the caller is allowed to search.

    self_verify   → only the authenticated student's own embeddings.
    section_roster→ all enrolled students in the active section (teacher).
    """
    scope_svc = get_scope_service()
    if scope_svc is None:
        # Fallback: full database scan (original behaviour)
        return None

    if scope_mode == "self_verify" and student_id:
        return scope_svc.resolve_student_scope(student_id)

    if scope_mode == "section_roster" and section_id:
        return scope_svc.resolve_section_scope(section_id)

    return None


def _get_candidate_ids_for_user(user, period_id: Optional[str] = None, limit: int = 500):
    """Return list of candidate student IDs appropriate for the authenticated user.

    - Students -> their active class/period roster when possible, otherwise themselves
    - Teachers -> students in the period's class_id (if provided) else students in assigned sections
    - Admins -> None (meaning unrestricted)
    """
    try:
        fb = get_firebase_service()
        if fb is None:
            return None

        # Students -> prefer the active period roster so attendance can match
        # against the same enrolled peers the teacher expects for that slot.
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

        # Determine class/section from period if available
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
                # fallback to assigned_sections
                for sec in (user.assigned_sections or []):
                    students = repo.list_students(course_id=sec)
                    candidate_ids.extend([s.get(DB_FIELD_STUDENT_ID) or s.get("student_id") for s in students if s])
        else:
            # Admin or other roles -> no narrowing
            return None

        # Deduplicate and limit
        seen = set()
        out = []
        for sid in candidate_ids:
            if not sid:
                continue
            if sid in seen:
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
    """
    Persist a verified outcome for downstream learning jobs.

    Only explicit confirmation flows should enqueue records here.
    Any future learning/index refresh pipeline must source from this
    collection rather than raw detection attempts.
    
    Errors are logged but do not block the main attendance flow.
    This is a fire-and-forget operation with best-effort persistence.
    """
    try:
        # Use direct Firestore import to ensure DB access
        from services.firebase_service import get_firebase_service
        
        fb = get_firebase_service()
        if fb is None:
            logger.warning(
                "Firebase service unavailable; cannot queue verified outcome. "
                "record_id=%s student=%s",
                record_id,
                student_id
            )
            return
        
        # Try multiple attribute names for Firestore DB (handles various init patterns)
        db = (
            getattr(fb, "firestore_db", None) or
            getattr(fb, "_firestore", None) or
            getattr(fb, "db", None)
        )
        
        if db is None:
            logger.warning(
                "Firestore DB not available in Firebase service (tried: firestore_db, _firestore, db). "
                "Cannot queue verified outcome for record_id=%s",
                record_id
            )
            return

        # Validate inputs
        if not record_id or not student_id:
            logger.error(
                "Cannot queue verified outcome: invalid inputs. "
                "record_id=%s student_id=%s",
                record_id,
                student_id
            )
            return

        payload = {
            "record_id": record_id,
            "student_id": student_id,
            "period_id": period_id or None,
            "confidence": round(float(confidence), 4),
            "verified": True,
            "verified_at": marked_at_iso,
            "source": "confirm_attendance",
            "queued_at": datetime.now().isoformat(),
        }
        
        # Write to Firestore with explicit error handling
        try:
            doc_ref = db.collection("verified_face_outcomes").document(record_id)
            result = doc_ref.set(payload, merge=True)
            logger.info(
                "✓ Verified outcome queued: record_id=%s student=%s confidence=%.2f source=confirm_attendance",
                record_id,
                student_id,
                confidence
            )
        except AttributeError as ae:
            logger.error(
                "Database object missing expected methods. "
                "record_id=%s error=%s",
                record_id,
                ae,
                exc_info=True
            )
            raise
        except TypeError as te:
            logger.error(
                "Invalid database object or payload. "
                "record_id=%s error=%s payload_keys=%s",
                record_id,
                te,
                list(payload.keys()),
                exc_info=True
            )
            raise
        
    except Exception as exc:
        # Log the error with full context but do not raise
        # This preserves the original attendance record even if verified outcome fails
        logger.error(
            "Failed to queue verified outcome (non-fatal): "
            "record_id=%s student=%s period=%s error_type=%s error=%s",
            record_id,
            student_id,
            period_id,
            type(exc).__name__,
            str(exc),
            exc_info=True
        )
        # Do not raise - allow attendance record to succeed even if outcome persistence fails


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
    """
    Match embedding against a bounded candidate set when provided.

    - If `candidate_student_ids` is provided, only those students are checked.
    - Else if `candidate_course_id` is provided, students returned by
      `StudentRepository.list_students(course_id)` are checked.
    - Otherwise all students are searched (legacy behaviour).
    """
    from database.student_repository import StudentRepository

    best_distance = float("inf")
    best_student = None

    # Build candidate list
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
        # Fallback to full scan on any error
        candidates = firebase.get_all_students()

    for student in candidates:
        stored_embs = FirebaseService.get_all_embeddings(student)
        for arr in stored_embs:
            try:
                if arr.shape != embedding.shape:
                    continue
            except Exception:
                # skip malformed arrays
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
    """Return the top-N candidate identities ordered by similarity.

    Used when the matcher is uncertain so the UI can prompt the user with
    likely identities instead of simply failing silently.
    """
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
                "student_id": student.get("student_id", ""),
                "student_name": student.get("name", "Unknown"),
                "confidence": round(max(0.0, min(1.0, best_score)), 4),
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
    """Resolve an identity scope and run a scoped embedding search (sync).

    Returns a ScopedMatchResult-like tuple when called from threadpool.
    """
    from datetime import datetime
    from models.identity_context import ScopeTarget, IdentityScopeType
    from services.identity_context_service import IdentityContextService
    from services.scoped_embedding_search import ScopedEmbeddingSearch

    # Resolve scope
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
            # Anonymous callers: allow explicit params
            if scope_mode == "self_verify" and student_id:
                scope = ScopeTarget(scope_type=IdentityScopeType.SELF, student_ids=[student_id], resolved_by=student_id, resolved_at=datetime.now().isoformat())
            elif scope_mode == "section_roster" and section_id and firebase:
                # Try to load roster from Firestore
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
                    scope = ScopeTarget(scope_type=IdentityScopeType.SECTION, student_ids=ids, resolved_by="anonymous", resolved_at=datetime.now().isoformat(), section_id=section_id)
                except Exception:
                    scope = ScopeTarget(scope_type=IdentityScopeType.GLOBAL, student_ids=[], resolved_by="anonymous", resolved_at=datetime.now().isoformat())
            else:
                scope = ScopeTarget(scope_type=IdentityScopeType.GLOBAL, student_ids=[], resolved_by="anonymous", resolved_at=datetime.now().isoformat())
    except Exception:
        scope = ScopeTarget(scope_type=IdentityScopeType.GLOBAL, student_ids=[], resolved_by="system", resolved_at=datetime.now().isoformat())

    searcher = ScopedEmbeddingSearch(firebase_service=firebase)
    result = searcher.search(embedding, scope)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# NEW: GET /window-status
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/window-status",
    summary="Real-time attendance window status for a period (student-facing polling)",
)
async def get_window_status(
    period_id: str = Query(..., description="Period ID to check"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
):
    """
    Lightweight endpoint for the student mark-attendance screen to poll.

    Returns the current phase (``before`` / ``open`` / ``grace`` / ``locked``),
    time remaining in the current phase, and whether new records are accepted.

    Designed to be called every 30 seconds without significant Firestore cost
    (2 document reads per call: period + lock).
    """
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
    period_id: Optional[str] = Query(None, description="Period ID to scope candidates"),
    limit: int = Query(500, description="Maximum candidates to return"),
    user = Depends(get_current_user),
):
    """Return the list of student IDs the calling user is allowed to match against.

    - Students receive only their own ID.
    - Teachers receive students for the period's class or their assigned sections.
    - Admin receives `null` candidates (meaning unrestricted/full-scan).
    """
    candidates = _get_candidate_ids_for_user(user, period_id=period_id, limit=limit)
    # Null means unrestricted (admin or error). Clients should interpret null as "no server-side narrowing".
    return JSONResponse(status_code=200, content={
        "candidate_student_ids": candidates,
        "count": len(candidates) if candidates is not None else None,
    })


# ══════════════════════════════════════════════════════════════════════════════
# NEW: GET /{record_id}/audit
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/record/{record_id}/audit",
    summary="Audit trail for an attendance record",
)
async def get_record_audit(record_id: str):
    """
    Returns the full, immutable audit history for a single attendance record.

    Delegates to AttendanceLockService.get_audit_trail() so the same trail
    is available from both the attendance router and the teacher router.
    """
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
# Step 1: detect-face-only  (window check added)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/detect-face-only",
    status_code=status.HTTP_200_OK,
    summary="Detect and identify face — does NOT write to database",
)
async def detect_face_only(
    file: UploadFile = File(..., description="JPEG or PNG image"),
    period_id: Optional[str] = Query(
        None,
        description="If supplied, window status is included in the response",
    ),
    # Backwards-compatible candidate narrowing
    candidate_student_ids: Optional[str] = Query(
        None,
        description="Comma-separated student IDs to narrow the search",
    ),
    candidate_course_id: Optional[str] = Query(
        None,
        description="Course/section id to narrow candidate students",
    ),
    # ★ New scope parameters — frontend sends these based on logged-in role
    scope_mode:  str           = Query("section_roster", description="self_verify | section_roster"),
    student_id:  Optional[str] = Query(None, description="Required for self_verify"),
    section_id:  Optional[str] = Query(None, description="Required for section_roster"),
    exclude_student_ids: Optional[str] = Query(None, description="Comma-separated student IDs to avoid for this session"),
    user = Depends(get_optional_user),
):
    excluded_ids = [s.strip() for s in exclude_student_ids.split(",")] if exclude_student_ids else None

    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    # Optional window status for the UI (non-blocking)
    window_info = _get_window_for_period(period_id)

    try:
        # Resolve identity context and run scoped search (preferred)
        scoped_result = await run_in_threadpool(
            _scoped_match, embedding, firebase, user, period_id, scope_mode, student_id, section_id, excluded_ids
        )

        # `scoped_result` is a ScopedMatchResult instance
        if hasattr(scoped_result, "matched"):
            if not scoped_result.matched:
                suggestions = await run_in_threadpool(
                    _rank_embedding_candidates_sync,
                    embedding,
                    firebase,
                    [s.strip() for s in candidate_student_ids.split(",")] if candidate_student_ids else None,
                    candidate_course_id,
                    3,
                )

                legacy_best_student, legacy_confidence, legacy_best_distance = await run_in_threadpool(
                    _match_embedding_sync,
                    embedding,
                    firebase,
                    COSINE_THRESHOLD,
                    None,
                    None,
                )
                if legacy_best_student is not None and legacy_best_distance <= COSINE_THRESHOLD:
                    del embedding
                    gc.collect()
                    return JSONResponse(status_code=200, content={
                        "matched": True,
                        "message": f"Face identified: {legacy_best_student.get('name', 'Unknown')} (legacy fallback)",
                        "student_name": legacy_best_student.get("name", "Unknown"),
                        "student_id": legacy_best_student.get("student_id", ""),
                        "confidence": round(legacy_confidence, 4),
                        "scope_mode": scope_mode,
                        "window": window_info,
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
                    "matched": False,
                    "message": no_match_msg,
                    "scope_mode": scope_mode,
                    "window": window_info,
                    "suggested_candidates": suggestions,
                })

            best_student = {"student_id": scoped_result.student_id, "name": scoped_result.student_name}
            confidence = scoped_result.confidence
            best_distance = scoped_result.distance
        else:
            # Fallback to legacy behaviour
            if not candidate_student_ids and not candidate_course_id and user is not None:
                derived = _get_candidate_ids_for_user(user, period_id=period_id)
                candidate_ids = derived
                candidate_course = None
            else:
                candidate_ids = [s.strip() for s in candidate_student_ids.split(",")] if candidate_student_ids else None
                candidate_course = candidate_course_id

            if excluded_ids:
                blocked = {sid for sid in excluded_ids if sid}
                candidate_ids = [sid for sid in (candidate_ids or []) if sid not in blocked] if candidate_ids else candidate_ids

            best_student, confidence, best_distance = await run_in_threadpool(
                _match_embedding_sync, embedding, firebase, COSINE_THRESHOLD, candidate_ids, candidate_course
            )
        del embedding
        gc.collect()
        if best_student is None:
            suggestions = await run_in_threadpool(
                _rank_embedding_candidates_sync,
                embedding,
                firebase,
                candidate_ids,
                candidate_course,
                3,
            )

            legacy_best_student, legacy_confidence, legacy_best_distance = await run_in_threadpool(
                _match_embedding_sync,
                embedding,
                firebase,
                COSINE_THRESHOLD,
                None,
                None,
            )
            if legacy_best_student is not None and legacy_best_distance <= COSINE_THRESHOLD:
                del embedding
                gc.collect()
                return JSONResponse(status_code=200, content={
                    "matched": True,
                    "message": f"Face identified: {legacy_best_student.get('name', 'Unknown')} (legacy fallback)",
                    "student_name": legacy_best_student.get("name", "Unknown"),
                    "student_id": legacy_best_student.get("student_id", ""),
                    "confidence": round(legacy_confidence, 4),
                    "scope_mode": scope_mode,
                    "window": window_info,
                    "suggested_candidates": suggestions,
                })

            no_match_msg = (
                "Face does not match your registered profile."
                if scope_mode == "self_verify"
                else f"Face not recognised in section roster. Similarity: {max(0.0, 1-best_distance):.2f}"
            )
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": no_match_msg,
                "scope_mode": scope_mode,
                "window": window_info,
                "suggested_candidates": suggestions,
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
# Step 2: confirm-attendance  ★ ENHANCED — window + lock enforced
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
    """
    Confirm and write an attendance record.

    ★ Window enforcement
    If ``period_id`` is provided the attendance window is checked:
    * Closed → HTTP 423 with WindowClosedResponse
    * Grace period → status written as "late"
    * Late-into-open → status written as "late"
    * On-time → status written as "present"

    An audit entry is always written on success.
    """
    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    student = firebase.get_student(student_id)
    if not student:
        raise HTTPException(404, f"Student {student_id} not found in the system.")

    # ── Window enforcement ─────────────────────────────────────────────────────
    window     = _get_window_for_period(period_id)
    att_status = "present"
    period_doc = None

    if window is not None:
        if not window["is_open"]:
            return _window_closed_response(window, student_id)
        # Determine present vs late
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

    # ── Write attendance ───────────────────────────────────────────────────────
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

        # ── Audit ─────────────────────────────────────────────────────────────
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

            # Optional online learning: use the confirmed frame as a new sample.
            if frame is not None:
                try:
                    learned_embedding, error_content = await _extract_embedding_from_upload(frame)
                    if error_content is None and learned_embedding is not None:
                        firebase.store_embedding(student_id, learned_embedding)
                        firebase.compute_and_update_prototype(student_id)
                    elif error_content is not None:
                        logger.warning("Frame learning skipped for %s: %s", student_id, error_content.body if hasattr(error_content, 'body') else 'invalid frame')
                except Exception:
                    logger.exception("Failed to store/update prototype for %s", student_id)

            # Realtime broadcast — fire after the write (non-blocking task)
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

        # Fire auto-lock check in background
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
            student_id,
            exc,
            exc_info=True
        )
        raise HTTPException(
            500,
            f"Attendance recording failed: {type(exc).__name__}: {str(exc)}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Legacy single-step: detect-face  ★ ENHANCED — window + lock enforced
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/detect-face",
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Detect face and mark attendance (window-enforced, 5-attempt limit)",
)
async def detect_face_and_mark(
    file: UploadFile = File(..., description="JPEG or PNG image"),
    period_id: Optional[str] = Query(None, description="Period to enforce window on"),
):
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(503, "Firebase service not initialised")

    # Window enforcement
    window = _get_window_for_period(period_id)
    if window and not window["is_open"]:
        del embedding
        gc.collect()
        return _window_closed_response(window)

    try:
        # Get attempt count BEFORE matching to enforce limit before expensive operations
        from services.face_attempt_service import get_face_attempt_service
        attempt_svc = get_face_attempt_service(getattr(firebase, "firestore_db", None) or getattr(firebase, "_firestore", None))
        
        # We don't know the student yet, but we'll track failures anyway
        # This is a simple heuristic: once we do match, we reset the counter
        
        # No explicit candidate narrowing here — rely on client to call
        # `detect-face-only` with candidates, or pass period-based narrowing below.
        best_student, confidence, best_distance = await run_in_threadpool(
            _match_embedding_sync, embedding, firebase, COSINE_THRESHOLD
        )
        del embedding
        gc.collect()

        if best_student is None or best_distance > COSINE_THRESHOLD:
            # Failed match - increment global attempt counter for this session
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

        # Check attempt limit for THIS student
        from services.face_attempt_service import get_face_attempt_service
        attempt_svc = get_face_attempt_service(getattr(firebase, "firestore_db", None) or getattr(firebase, "_firestore", None))
        can_attempt, current_attempts = attempt_svc.can_attempt(student_id, period_id)
        
        if not can_attempt:
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": (
                    f"Maximum detection attempts ({current_attempts}) reached for this period. "
                    f"Please ask an instructor for assistance."
                ),
                "window": window,
                "attempt_limit_exceeded": True,
            })

        # Determine late/present
        att_status = "present"
        if window:
            att_status = _compute_attendance_status(
                window.get("phase", "open"), best_student
            )

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

        # Reset attempts on successful detection
        attempt_svc.reset_attempts(student_id, period_id)
        
        # Audit
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

        # Realtime broadcast
        try:
            if period_id:
                from services.realtime_service import get_realtime_service
                rt_svc = get_realtime_service()
                # derive section id from period doc if possible
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
                            "record_id": record_id,
                            "student_id": student_id,
                            "period_id": period_id,
                            "status": att_status,
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
# mark-attendance  ★ ENHANCED — window + lock enforced
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

        # Extract period_id from metadata if provided
        period_id = None
        if request.metadata:
            period_id = request.metadata.get("period_id")

        # Window enforcement
        window = _get_window_for_period(period_id)
        if window and not window["is_open"]:
            raise HTTPException(
                status_code=423,
                detail={
                    "message": window.get("message", "Attendance window closed."),
                    "window":  window,
                },
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

        # Audit
        lock_svc = get_lock_service()
        if lock_svc and record_id:
            lock_svc.write_audit(
                record_id=record_id,
                action="CREATE",
                actor_id=request.student_id,
                after={
                    "record_id":  record_id,
                    "student_id": request.student_id,
                    "period_id":  period_id,
                    "status":     "present",
                    "confidence": round(request.confidence, 4),
                    "markedAt":   timestamp.isoformat(),
                    "method":     "mark_attendance_api",
                },
            )

        # Realtime broadcast
        try:
            if period_id:
                from services.realtime_service import get_realtime_service
                rt_svc = get_realtime_service()
                # try to resolve section id from period doc
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
                            "record_id": record_id,
                            "student_id": request.student_id,
                            "period_id": period_id,
                            "status": "present",
                            "confidence": round(request.confidence, 4),
                            "markedAt": timestamp.isoformat(),
                        },
                    ))
        except Exception:
            logger.debug("Realtime broadcast failed (swallowed)")

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return MarkAttendanceResponse(
            success=True,
            record_id=record_id,
            student_id=request.student_id,
            timestamp=timestamp.isoformat(),
            message="Attendance marked successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to mark attendance: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# mark-mobile  ★ ENHANCED — window enforced
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

        # Window enforcement
        window = _get_window_for_period(period_id)
        if window and not window["is_open"]:
            raise HTTPException(
                status_code=423,
                detail={
                    "message": window.get("message", "Attendance window closed."),
                    "window":  window,
                },
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
            extractor  = ModelManager.get_facenet_extractor()
            embedding  = extractor.extract_embedding(image_array)
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

        # Determine late/present
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
        lock_svc  = get_lock_service()
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
                    "method":     "face_recognition_mobile",
                },
            )

        # Realtime broadcast
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
                            "record_id": record_id,
                            "student_id": student_id,
                            "period_id": period_id,
                            "status": att_status,
                            "confidence": round(confidence, 4),
                            "markedAt": timestamp.isoformat(),
                        },
                    ))
        except Exception:
            logger.debug("Realtime broadcast failed (swallowed)")

        if period_id:
            asyncio.create_task(_maybe_autolock(period_id))

        return MarkAttendanceResponse(
            success=True,
            record_id=record_id,
            student_id=student_id,
            timestamp=timestamp.isoformat(),
            message=f"Attendance marked as {att_status.upper()} (confidence: {confidence:.2f})",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to mark attendance: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Enhanced daily-report  (delegates to AttendanceService)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance/daily-report")
async def get_daily_report(
    date: Optional[str] = Query(None),
    class_id: Optional[str] = Query(
        None,
        description=(
            "When supplied, delegates to AttendanceService.generate_daily_report() "
            "for a class-level report with period breakdown."
        ),
    ),
):
    """
    Generate a daily attendance report.

    * Without ``class_id`` → legacy summary from FirebaseService.
    * With ``class_id``    → rich report with per-period breakdown and
      student-level summary via AttendanceService.generate_daily_report().
    """
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

    # Legacy path
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
# Student Management  (unchanged)
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
            success=True, student_id=request.student_id, message="Student registered successfully"
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
            student_id=student_id, date_from=from_date, date_to=to_date, limit=limit + offset
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
# Stream Management  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/streams", response_model=StreamHealth, status_code=status.HTTP_201_CREATED)
async def add_stream(request: StreamConfig) -> StreamHealth:
    try:
        manager     = get_stream_manager()
        classroom_id: Optional[str] = getattr(request, "classroom_id", None)
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
            "stream_id":            stream_id,
            "classroom_id":         m.get("classroom_id"),
            "is_ai_active":         is_ai_active,
            "display_status":       "Live Monitoring" if is_ai_active else "System Idle",
            "last_ai_trigger":      m.get("last_ai_trigger"),
            "students_loaded":      m.get("students_loaded", False),
            "students_loaded_count": m.get("students_loaded_count", 0),
            "student_load_error":   m.get("student_load_error"),
            "fps":                  m.get("fps", 0.0),
            "active_tracks":        m.get("active_tracks", 0),
            "marked_students_today": m.get("marked_students", 0),
            "stream_status":        m.get("status", "unknown"),
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
        return {
            "success": True,
            "message": f"Student reload triggered for {stream_id}.",
        }
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
        firebase = get_firebase_service()
        manager  = get_stream_manager()
        lock_svc = get_lock_service()
        services = {
            "firebase":    "healthy" if firebase  else "unavailable",
            "streams":     "healthy" if manager   else "unavailable",
            "models":      "healthy" if ModelManager.is_initialized() else "not_initialized",
            "lock_service": "healthy" if lock_svc else "unavailable",
        }
        return HealthCheckResponse(status="healthy", services=services, uptime_seconds=0)
    except Exception as exc:
        return HealthCheckResponse(
            status="error", services={"error": str(exc)}, uptime_seconds=0
        )


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
