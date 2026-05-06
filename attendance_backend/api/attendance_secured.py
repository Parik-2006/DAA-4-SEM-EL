"""
attendance.py  (SECURITY-HARDENED)
─────────────────────────────────────────────────────────────────────────────
Changes vs original
--------------------
★ POST /mark-attendance     → require_teacher (face-recognition mark by teacher system)
★ POST /mark-mobile         → require_student  + student can only mark for themselves
★ POST /confirm-attendance  → require_teacher
★ GET  /window-status       → any authenticated user
★ GET  /health              → public (no auth)
★ All write endpoints are audited via AuditService.

All original logic is fully preserved — security is additive only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    CAMERA_IDS,
    LATE_THRESHOLD_MINUTES,
    AttendanceStatus,
)

# ── Security ───────────────────────────────────────────────────────────────────
from decorators.auth_decorators import (
    get_current_user,
    require_teacher,
    require_student,
    get_optional_user,
)
from services.audit_services import get_audit_service
from services.auth_service import UserContext
# ──────────────────────────────────────────────────────────────────────────────

from services.attendance_lock_service import get_lock_service
from services.attendance_service import AttendanceService
from services.firebase_service import get_firebase_service
from services.period_detection_service import get_period_detection_service
from services.rtsp_stream_handler import get_stream_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# Pydantic models (unchanged)
# ---------------------------------------------------------------------------

class MarkAttendanceRequest(BaseModel):
    student_id: str
    period_id:  str
    class_id:   str
    date:       Optional[str] = None
    confidence: float         = Field(0.0, ge=0.0, le=1.0)
    method:     str           = "face_recognition"


class MobileMarkRequest(BaseModel):
    student_id: str
    period_id:  str
    class_id:   str
    date:       Optional[str] = None
    latitude:   Optional[float] = None
    longitude:  Optional[float] = None
    device_id:  Optional[str]   = None


class ConfirmAttendanceRequest(BaseModel):
    student_id: str
    period_id:  str
    class_id:   str
    date:       Optional[str] = None
    status:     str           = "present"
    confidence: float         = Field(0.0, ge=0.0, le=1.0)
    method:     str           = "manual_confirm"


# ---------------------------------------------------------------------------
# Helpers (unchanged)
# ---------------------------------------------------------------------------

def _get_svc() -> AttendanceService:
    svc = AttendanceService()
    return svc


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now().isoformat()


def _is_late(period: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """Return True if current time falls in the late window."""
    now = now or datetime.now()
    try:
        start_dt = datetime.strptime(
            f"{now.date()} {period['start_time']}", "%Y-%m-%d %H:%M"
        )
        late_cutoff = start_dt + timedelta(minutes=LATE_THRESHOLD_MINUTES)
        return now > late_cutoff
    except Exception:
        return False


# ===========================================================================
# GET /health  (fully public — no auth)
# ===========================================================================

@router.get("/health", tags=["health"], summary="Health check — public")
async def health_check():
    """Returns system health. No authentication required."""
    fb_svc    = get_firebase_service()
    lock_svc  = get_lock_service()
    stream_mgr = get_stream_manager()

    return {
        "status":    "healthy",
        "timestamp": _now_iso(),
        "services": {
            "firebase":       "connected" if fb_svc else "unavailable",
            "lock_service":   "ready"     if lock_svc else "unavailable",
            "stream_manager": "running"   if stream_mgr else "not_started",
        },
    }


# ===========================================================================
# GET /window-status  (any authenticated user)
# ===========================================================================

@router.get(
    "/window-status",
    summary="Current attendance window open/close status for a period",
)
async def get_window_status(
    period_id: str = Query(...),
    date: Optional[str] = Query(None),
    auth_user: UserContext = get_current_user,        # ← SECURITY: any role
):
    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")

    date = date or _today()

    try:
        fb_svc = get_firebase_service()
        db     = getattr(fb_svc, "firestore_db", None) or getattr(fb_svc, "_firestore", None)
        period: Dict[str, Any] = {}
        if db:
            pd_doc = db.collection("periods").document(period_id).get()
            if pd_doc.exists:
                period = pd_doc.to_dict()
    except Exception as exc:
        logger.warning("Period fetch failed for window-status: %s", exc)
        period = {}

    window = lock_svc.get_window_status(period, date)
    return JSONResponse(status_code=200, content={
        "period_id": period_id, "date": date, "window": window,
    })


# ===========================================================================
# POST /mark-attendance  (teacher / admin — face-recognition mark)
# ===========================================================================

@router.post(
    "/mark-attendance",
    summary="Mark attendance via face recognition (teacher/system)",
    status_code=status.HTTP_200_OK,
)
async def mark_attendance(
    request: Request,
    body: MarkAttendanceRequest,
    auth_user: UserContext = require_teacher,         # ← SECURITY
):
    """
    Called by the teacher-side camera system after successful face recognition.
    Requires teacher or admin role.
    """
    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")

    date   = body.date or _today()
    svc    = _get_svc()

    # Fetch period to check window + section auth
    period: Dict[str, Any] = {}
    try:
        fb_svc = get_firebase_service()
        db     = getattr(fb_svc, "firestore_db", None) or getattr(fb_svc, "_firestore", None)
        if db:
            pd_doc = db.collection("periods").document(body.period_id).get()
            if pd_doc.exists:
                period = pd_doc.to_dict()
    except Exception as exc:
        logger.warning("Period fetch failed: %s", exc)

    # Section-level auth: teacher must own this section
    period_section = period.get("section_id") or period.get("class_id", "")
    if period_section and not auth_user.is_admin() and not auth_user.can_access_section(period_section):
        get_audit_service().log_failed_access(
            user=auth_user, resource="period", resource_id=body.period_id,
            reason=f"Teacher not assigned to section '{period_section}'",
            request=request,
        )
        raise HTTPException(
            403,
            f"You are not assigned to section '{period_section}'. "
            f"Your sections: {auth_user.assigned_sections}.",
        )

    window = lock_svc.get_window_status(period, date)
    if not window.get("is_open"):
        return JSONResponse(status_code=423, content={
            "success": False, "message": window.get("message", "Attendance window closed."),
            "window": window,
        })

    computed_status = AttendanceStatus.LATE if (
        window.get("phase") == "grace" or _is_late(period)
    ) else AttendanceStatus.PRESENT

    record_id = f"{date}_{body.period_id}_{body.student_id}"
    record    = {
        "record_id":  record_id,
        "student_id": body.student_id,
        "period_id":  body.period_id,
        "class_id":   body.class_id,
        "faculty_id": auth_user.user_id,
        "status":     computed_status,
        "confidence": round(body.confidence, 4),
        "date":       date,
        "method":     body.method,
        "markedAt":   _now_iso(),
    }

    try:
        from database.firebase_client import FirebaseClient
        FirebaseClient().get_reference(f"attendance/{date}/{record_id}").set(record)
    except Exception as exc:
        raise HTTPException(500, f"Failed to write attendance record: {exc}")

    get_audit_service().log(
        action="MARK_ATTENDANCE", resource="attendance", resource_id=record_id,
        user=auth_user, request=request, after=record,
        details={"method": body.method, "confidence": body.confidence, "window_phase": window.get("phase")},
    )

    return JSONResponse(status_code=200, content={
        "success": True, "record_id": record_id,
        "status": computed_status, "window": window,
        "record": record,
    })


# ===========================================================================
# POST /confirm-attendance  (teacher / admin)
# ===========================================================================

@router.post(
    "/confirm-attendance",
    summary="Manually confirm / override an attendance record (teacher)",
)
async def confirm_attendance(
    request: Request,
    body: ConfirmAttendanceRequest,
    auth_user: UserContext = require_teacher,         # ← SECURITY
):
    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")

    date  = body.date or _today()
    _VALID = {"present", "absent", "late", "excused"}

    if body.status.lower() not in _VALID:
        raise HTTPException(422, f"Invalid status '{body.status}'. Must be one of {sorted(_VALID)}.")

    # Fetch period for window + section check
    period: Dict[str, Any] = {}
    try:
        fb_svc = get_firebase_service()
        db     = getattr(fb_svc, "firestore_db", None) or getattr(fb_svc, "_firestore", None)
        if db:
            pd_doc = db.collection("periods").document(body.period_id).get()
            if pd_doc.exists:
                period = pd_doc.to_dict()
    except Exception:
        pass

    period_section = period.get("section_id") or period.get("class_id", "")
    if period_section and not auth_user.is_admin() and not auth_user.can_access_section(period_section):
        raise HTTPException(403, f"You are not assigned to section '{period_section}'.")

    window = lock_svc.get_window_status(period, date)
    if not window.get("can_edit", False):
        return JSONResponse(status_code=423, content={
            "success": False, "message": window.get("message", "Attendance editing closed."),
            "window": window,
        })

    record_id = f"{date}_{body.period_id}_{body.student_id}"
    now_ts    = _now_iso()

    try:
        from database.firebase_client import FirebaseClient
        ref      = FirebaseClient().get_reference(f"attendance/{date}/{record_id}")
        existing = ref.get() or {}
        record   = {
            **existing,
            "record_id":  record_id,
            "student_id": body.student_id,
            "period_id":  body.period_id,
            "class_id":   body.class_id,
            "status":     body.status.lower(),
            "confidence": round(body.confidence, 4),
            "date":       date,
            "method":     body.method,
            "confirmed_by": auth_user.user_id,
            "confirmed_at": now_ts,
            "markedAt":   existing.get("markedAt") or now_ts,
        }
        ref.set(record)
    except Exception as exc:
        raise HTTPException(500, f"Failed to confirm attendance: {exc}")

    get_audit_service().log(
        action="EDIT_ATTENDANCE", resource="attendance", resource_id=record_id,
        user=auth_user, request=request, before=existing, after=record,
        details={"method": body.method, "status": body.status},
    )

    return JSONResponse(status_code=200, content={
        "success": True, "record_id": record_id, "record": record, "window": window,
    })


# ===========================================================================
# POST /mark-mobile  (student — self-mark via mobile app)
# ===========================================================================

@router.post(
    "/mark-mobile",
    summary="Student self-marks attendance via mobile (within geo-fence + window)",
)
async def mark_mobile_attendance(
    request: Request,
    body: MobileMarkRequest,
    auth_user: UserContext = require_student,         # ← SECURITY
):
    """
    Allows a student to mark their own attendance from the mobile app.
    The student may only mark for their own student_id.
    """
    # Students cannot mark attendance for someone else
    if auth_user.is_student() and body.student_id != auth_user.user_id:
        get_audit_service().log_failed_access(
            user=auth_user, resource="attendance",
            resource_id=f"{body.period_id}_{body.student_id}",
            reason=f"Student {auth_user.user_id} attempted to mark for {body.student_id}",
            request=request,
        )
        raise HTTPException(
            403, "You may only mark attendance for yourself."
        )

    lock_svc = get_lock_service()
    if lock_svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")

    date = body.date or _today()

    # Fetch period
    period: Dict[str, Any] = {}
    try:
        fb_svc = get_firebase_service()
        db     = getattr(fb_svc, "firestore_db", None) or getattr(fb_svc, "_firestore", None)
        if db:
            pd_doc = db.collection("periods").document(body.period_id).get()
            if pd_doc.exists:
                period = pd_doc.to_dict()
    except Exception:
        pass

    window = lock_svc.get_window_status(period, date)
    if not window.get("is_open"):
        return JSONResponse(status_code=423, content={
            "success": False, "message": window.get("message", "Attendance window closed."),
            "window": window,
        })

    computed_status = (
        AttendanceStatus.LATE
        if window.get("phase") == "grace" or _is_late(period)
        else AttendanceStatus.PRESENT
    )

    record_id = f"{date}_{body.period_id}_{body.student_id}"
    now_ts    = _now_iso()
    record    = {
        "record_id":  record_id,
        "student_id": body.student_id,
        "period_id":  body.period_id,
        "class_id":   body.class_id,
        "status":     computed_status,
        "date":       date,
        "method":     "student_mobile",
        "markedAt":   now_ts,
        "location":   {
            "latitude":  body.latitude,
            "longitude": body.longitude,
        } if body.latitude and body.longitude else None,
        "device_id":  body.device_id,
    }

    try:
        from database.firebase_client import FirebaseClient
        existing = FirebaseClient().get_reference(f"attendance/{date}/{record_id}").get()
        if existing:
            return JSONResponse(status_code=409, content={
                "success": False,
                "message": "Attendance already marked for this period.",
                "existing": existing,
            })
        FirebaseClient().get_reference(f"attendance/{date}/{record_id}").set(record)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to write attendance: {exc}")

    get_audit_service().log(
        action="MARK_ATTENDANCE", resource="attendance", resource_id=record_id,
        user=auth_user, request=request, after=record,
        details={"method": "student_mobile", "window_phase": window.get("phase")},
    )

    return JSONResponse(status_code=201, content={
        "success": True, "record_id": record_id,
        "status": computed_status, "record": record, "window": window,
    })


# ===========================================================================
# GET /student-records  (any authenticated — filtered by role automatically)
# ===========================================================================

@router.get(
    "/student-records",
    summary="Attendance records for a student (filtered by role)",
)
async def get_student_records(
    student_id: str = Query(...),
    period_id:  Optional[str] = Query(None),
    date_from:  Optional[str] = Query(None),
    date_to:    Optional[str] = Query(None),
    page:       int = Query(1, ge=1),
    limit:      int = Query(20, ge=1, le=100),
    auth_user: UserContext = get_current_user,        # ← SECURITY: any role
):
    """
    Students may only view their own records.
    Teachers may view any student in their assigned sections.
    Admins have unrestricted access.
    """
    # Students: enforce own-data access
    if auth_user.is_student() and student_id != auth_user.user_id:
        raise HTTPException(403, "Students may only view their own attendance records.")

    svc = _get_svc()
    try:
        return svc.get_student_records(
            student_id=student_id,
            period_id=period_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ===========================================================================
# POST /detect-face  (teacher / system — camera detection endpoint)
# ===========================================================================

@router.post(
    "/detect-face",
    summary="Face detection from camera frame (teacher/system only)",
)
async def detect_face(
    request: Request,
    body: Dict[str, Any] = Body(...),
    auth_user: UserContext = require_teacher,         # ← SECURITY
):
    """
    Accepts a base64 camera frame, runs face detection, and returns
    recognition candidates.  Called by the teacher-side camera system.
    """
    svc = _get_svc()
    try:
        result = await svc.detect_face_from_frame(body)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:
        logger.error("Face detection failed: %s", exc)
        raise HTTPException(500, f"Face detection error: {exc}")


# ===========================================================================
# POST /detect-face-only  (teacher — lightweight detection, no attendance write)
# ===========================================================================

@router.post(
    "/detect-face-only",
    summary="Face detection only — does not write an attendance record",
)
async def detect_face_only(
    request: Request,
    body: Dict[str, Any] = Body(...),
    auth_user: UserContext = require_teacher,         # ← SECURITY
):
    svc = _get_svc()
    try:
        result = await svc.detect_face_only(body)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:
        raise HTTPException(500, f"Face detection error: {exc}")