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

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

import logging
from fastapi import APIRouter, HTTPException, Query

from database.attendance_repository import AttendanceRepository
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


# ── Helper functions ───────────────────────────────────────────────────────────

def _attendance_band_student(rate: float) -> str:
    """Classify attendance rate into safety band."""
    if rate >= 85:
        return "safe"
    if rate >= 75:
        return "warning"
    return "danger"


_BAND_COLORS_STUDENT = {
    "safe": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}


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


@router.get(
    "/analytics",
    summary="Personal analytics — trend, summary, and streak (own data only)",
)
async def get_student_analytics(
    student_id: Optional[str] = Query(None, description="Optional; defaults to authenticated user"),
    days: int = Query(30, ge=7, le=180, description="Trend window in days"),
    auth_user: UserContext = require_student,                    # ← SECURITY
):
    """
    Return personal analytics for the authenticated student only.

    The student_id parameter must match the authenticated token — no
    cross-student access is possible regardless of client input.

    The ``days`` parameter controls the trend window (7–180 days).

    **Band thresholds**

    | band      | condition | colour  |
    |-----------|-----------|---------|
    | safe      | ≥ 85 %    | #22C55E |
    | warning   | 75–85 %   | #F59E0B |
    | danger    | < 75 %    | #EF4444 |

    **Response shape**
    ```json
    {
      "student_id": "1RV23CS001",
      "days": 30,
      "trend": [
        { "date": "2026-04-14", "present": 3, "late": 0, "absent": 1, "rate": 75.0 }
      ],
      "overall": {
        "percentage": 78.4,
        "present": 45,
        "late": 2,
        "absent": 12,
        "total": 59,
        "band": "warning",
        "color": "#F59E0B"
      },
      "streak": {
        "current_present_streak": 5,
        "longest_streak": 12
      },
      "generated_at": "2026-05-14T10:30:00Z"
    }
    ```
    """
    # Use provided student_id or fall back to authenticated user
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
        repo = AttendanceRepository()
        today = datetime.now().date()
        start = today - timedelta(days=days)

        records = repo.get_student_attendance(target_student_id, start_date=start, end_date=today)

        by_date: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"present": 0, "late": 0, "absent": 0}
        )
        for r in records:
            d = r.get("attendance_date", "") or r.get("date", "")
            s = r.get("status", "")
            if d and s in ("present", "late", "absent"):
                by_date[d][s] += 1

        trend = []
        for offset in range(days - 1, -1, -1):
            d_str = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
            day = by_date.get(d_str, {"present": 0, "late": 0, "absent": 0})
            total_day = day["present"] + day["late"] + day["absent"]
            if total_day == 0:
                trend.append({
                    "date": d_str,
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "rate": None,
                })
            else:
                trend.append({
                    "date": d_str,
                    "present": day["present"],
                    "late": day["late"],
                    "absent": day["absent"],
                    "rate": round((day["present"] + day["late"]) / total_day * 100, 1),
                })

        total_r = len(records)
        present_r = sum(1 for r in records if r.get("status") == "present")
        late_r = sum(1 for r in records if r.get("status") == "late")
        absent_r = sum(1 for r in records if r.get("status") == "absent")
        rate = round((present_r + late_r) / total_r * 100, 1) if total_r else 0.0
        band = _attendance_band_student(rate)

        current_streak = 0
        longest_streak = 0
        for entry in reversed(trend):
            if entry["rate"] is None or entry["rate"] == 0.0:
                current_streak = 0
            else:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)

        logger.info(
            "get_student_analytics | student_id=%s | days=%d | rate=%f%%",
            target_student_id, days, rate,
        )

        return {
            "student_id": target_student_id,
            "days": days,
            "trend": trend,
            "overall": {
                "percentage": rate,
                "present": present_r,
                "late": late_r,
                "absent": absent_r,
                "total": total_r,
                "band": band,
                "color": _BAND_COLORS_STUDENT.get(band, "#94A3B8"),
            },
            "streak": {
                "current_present_streak": current_streak,
                "longest_streak": longest_streak,
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "get_student_analytics | student_id=%s | exc=%s",
            target_student_id, exc,
        )
        raise HTTPException(status_code=500, detail=str(exc))