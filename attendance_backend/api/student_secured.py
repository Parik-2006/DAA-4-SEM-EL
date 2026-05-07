"""
student.py  (SECURITY-HARDENED)
─────────────────────────────────────────────────────────────────────────────
Changes vs original
--------------------
★ All endpoints require "student" (or teacher/admin) role via require_student.
★ require_own_student_data enforces that students can only query their own
  student_id — cross-student data access is blocked at the dependency level.
★ Teachers and admins bypass the own-data check (they need class-wide access).

Endpoints (signatures unchanged, security is additive)
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
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database.firebase_client import FirebaseClient

# ── Security ───────────────────────────────────────────────────────────────────
from decorators.auth_decorators import (
    require_student,
    require_own_student_data,
)
from services.auth_service import UserContext
# ──────────────────────────────────────────────────────────────────────────────

from services.student_service import StudentService

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
    student_id: str = Query(..., description="Student ID"),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    """
    Return the student's attendance record for today.
    Students may only view their own record; teachers/admins can view any.
    """
    try:
        fb    = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        ref   = fb.get_reference(f"attendance/{today}/{student_id}")
        data  = ref.get()
        if data and isinstance(data, dict):
            return data
        return {"status": "not_marked"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get(
    "/attendance/history",
    summary="Paginated attendance history with optional filters",
)
async def get_attendance_history(
    student_id:  str  = Query(...,  description="Student ID"),
    page:        int  = Query(1,    ge=1),
    page_size:   int  = Query(20,   ge=1, le=100),
    course_id:   Optional[str] = Query(None),
    start_date:  Optional[str] = Query(None),
    end_date:    Optional[str] = Query(None),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    try:
        return _service().get_attendance_history(
            student_id=student_id, page=page, page_size=page_size,
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
    student_id: str = Query(..., description="Student ID"),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    try:
        return _service().build_dashboard_data(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/timetable",
    summary="Full weekly timetable grid, colour-coded by course",
)
async def get_timetable(
    student_id: str = Query(..., description="Student ID"),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    try:
        return _service().get_weekly_timetable(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/attendance-summary",
    summary="Overall and course-wise attendance percentage breakdown",
)
async def get_attendance_summary(
    student_id: str = Query(..., description="Student ID"),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    try:
        return _service().get_attendance_summary(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/warnings",
    summary="Attendance warnings for courses below or near 75% threshold",
)
async def get_warnings(
    student_id: str = Query(..., description="Student ID"),
    auth_user: UserContext = require_student,                    # ← SECURITY
    _own: None = require_own_student_data("student_id"),        # ← SECURITY
):
    try:
        return _service().get_warnings(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))