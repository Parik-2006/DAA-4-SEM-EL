"""
student.py  (SECURITY-HARDENED)
─────────────────────────────────────────────────────────────────────────────
Changes vs original
--------------------
★ All endpoints require "student" (or teacher/admin) role via require_student.
★ student_id parameter is now optional and defaults to authenticated user's ID.
★ Cross-student data access is blocked by explicit authorization check in handler.
★ Teachers and admins can optionally query other students' data.

Endpoints (signatures changed to optional student_id parameter)
---------
GET /api/v1/student/attendance/today
GET /api/v1/student/attendance/history
GET /api/v1/student/dashboard
GET /api/v1/student/timetable
GET /api/v1/student/attendance-summary
GET /api/v1/student/warnings
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

import logging
from fastapi import APIRouter, HTTPException, Query

from database.firebase_client import FirebaseClient

# ── firebase_admin guard for RTDB NotFound
try:
    from firebase_admin import exceptions as fb_exceptions
    _FIREBASE_NOT_FOUND = fb_exceptions.NotFoundError
except Exception:  # pragma: no cover
    _FIREBASE_NOT_FOUND = Exception

# ── Security ───────────────────────────────────────────────────────────────────
from decorators.auth_decorators import require_student
from services.auth_service import UserContext
# ──────────────────────────────────────────────────────────────────────────────

from services.student_service import StudentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/student", tags=["student"])

_svc = StudentService()


def _service() -> StudentService:
    return _svc


# ── Existing endpoints ─────────────────────────────────────────────────────────

@router.get(
    "/attendance/today",
    summary="Get today's attendance status for the student",
)
async def get_today_attendance(
    student_id: str = Query(None, description="Student ID (optional, defaults to authenticated user)"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    """
    Return the student's attendance record for today.
    Students may only view their own record; teachers/admins can view any.
    Uses authenticated user ID if student_id is not provided.
    """
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        fb    = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        ref   = fb.get_reference(f"attendance/{today}/{target_student_id}")
        data  = ref.get()
        if data and isinstance(data, dict):
            return data
        return {"status": "not_marked"}
    except _FIREBASE_NOT_FOUND:
        return {"status": "not_marked"}
    except Exception as exc:
        logger.error("student_secured.get_today_attendance | student_id=%s | exc=%s", target_student_id, exc)
        raise HTTPException(status_code=500, detail="Could not retrieve attendance record.")


@router.get(
    "/attendance/history",
    summary="Paginated attendance history with optional filters",
)
async def get_attendance_history(
    student_id:  str  = Query(None,  description="Student ID (optional, defaults to authenticated user)"),
    page:        int  = Query(1,    ge=1),
    page_size:   int  = Query(20,   ge=1, le=100),
    course_id:   Optional[str] = Query(None),
    start_date:  Optional[str] = Query(None),
    end_date:    Optional[str] = Query(None),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        return _service().get_attendance_history(
            student_id=target_student_id, page=page, page_size=page_size,
            course_id=course_id, start_date=start_date, end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── NEW endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Student dashboard — today's schedule with real-time status",
)
async def get_dashboard(
    student_id: str = Query(None, description="Student ID (optional, defaults to authenticated user)"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        return _service().build_dashboard_data(target_student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/timetable",
    summary="Full weekly timetable grid, colour-coded by course",
)
async def get_timetable(
    student_id: str = Query(None, description="Student ID (optional, defaults to authenticated user)"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        return _service().get_weekly_timetable(target_student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/attendance-summary",
    summary="Overall and course-wise attendance percentage breakdown",
)
async def get_attendance_summary(
    student_id: str = Query(None, description="Student ID (optional, defaults to authenticated user)"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        return _service().get_attendance_summary(target_student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/warnings",
    summary="Attendance warnings for courses below or near 75% threshold",
)
async def get_warnings(
    student_id: str = Query(None, description="Student ID (optional, defaults to authenticated user)"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    # Use authenticated user's ID if student_id not provided
    target_student_id = student_id or auth_user.user_id
    
    # Check authorization: students can only view their own data
    if auth_user.role == "student" and target_student_id != auth_user.user_id:
        logger.warning(
            "Cross-student access denied: authenticated=%s requested=%s",
            auth_user.user_id, target_student_id,
        )
        raise HTTPException(
            status_code=403,
            detail="You may only access your own attendance data.",
        )
    
    try:
        return _service().get_warnings(target_student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))