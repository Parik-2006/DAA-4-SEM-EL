"""
Student-facing API endpoints.

All routes require a ``student_id`` query parameter.  Authentication /
JWT validation is expected to be handled by a middleware layer upstream;
these handlers trust the student_id they receive.

Endpoints
---------
GET /api/v1/student/attendance/today          (existing — kept unchanged)
GET /api/v1/student/attendance/history        (existing — enhanced with pagination
                                               + date-range + course filter)
GET /api/v1/student/dashboard                 (NEW)
GET /api/v1/student/timetable                 (NEW)
GET /api/v1/student/attendance-summary        (NEW)
GET /api/v1/student/warnings                  (NEW)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from database.firebase_client import FirebaseClient
from services.student_service import StudentService

router = APIRouter(prefix="/api/v1/student", tags=["student"])

# Singleton-style service (stateless — safe to share across requests)
_svc = StudentService()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _service() -> StudentService:
    """Return the module-level StudentService instance."""
    return _svc


# ── Existing endpoints (kept, history enhanced) ────────────────────────────────

@router.get(
    "/attendance/today",
    summary="Get today's attendance status for the student",
    response_description="Attendance record for today, or {status: not_marked}",
)
async def get_today_attendance(student_id: str = Query(..., description="Student ID")):
    """
    Return the student's attendance record for today.

    Returns ``{"status": "not_marked"}`` when no record exists yet.
    """
    try:
        fb = FirebaseClient()
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
    response_description="Paginated list of attendance records",
)
async def get_attendance_history(
    student_id: str  = Query(...,  description="Student ID"),
    page:       int  = Query(1,    ge=1,   description="Page number (1-based)"),
    page_size:  int  = Query(20,   ge=1,   le=100, description="Records per page"),
    course_id:  Optional[str] = Query(None, description="Filter by course code"),
    start_date: Optional[str] = Query(None, description="Filter from date YYYY-MM-DD (inclusive)"),
    end_date:   Optional[str] = Query(None, description="Filter to date YYYY-MM-DD (inclusive)"),
):
    """
    Return paginated attendance history for the student.

    Supports filtering by course code and/or date range.
    Each record includes ``marked_by_name`` (faculty display name) and
    a ``status_color`` hex string for the frontend.
    """
    try:
        return _service().get_attendance_history(
            student_id=student_id,
            page=page,
            page_size=page_size,
            course_id=course_id,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── NEW endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Student dashboard — today's schedule with real-time status",
    response_description="Today's periods with status, active period countdown, and summary",
)
async def get_dashboard(
    student_id: str = Query(..., description="Student ID"),
):
    """
    Return everything the student dashboard needs in a single call.

    **Period status values**

    | status    | meaning                                       | colour   |
    |-----------|-----------------------------------------------|----------|
    | `present` | Attendance recorded, on time                  | #22C55E  |
    | `late`    | Attendance recorded, arrived late             | #F59E0B  |
    | `absent`  | Period ended, no attendance recorded          | #EF4444  |
    | `pending` | Period in progress or not yet started         | #94A3B8  |

    The ``active_period`` field contains the currently running period with a
    ``countdown_seconds`` field indicating seconds left in the class.

    **Response shape**
    ```json
    {
      "today_date": "2026-04-30",
      "day_name": "Thursday",
      "active_period": { ...period card... },
      "periods_today": [ ...period cards... ],
      "summary": { "total": 5, "present": 2, "absent": 1, "late": 0, "pending": 2 },
      "overall_attendance": { "percentage": 82.5, "band": "warning", "color": "#F59E0B" }
    }
    ```
    """
    try:
        return _service().build_dashboard_data(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/timetable",
    summary="Full weekly timetable grid, colour-coded by course",
    response_description="Timetable organised by day with course colours",
)
async def get_timetable(
    student_id: str = Query(..., description="Student ID"),
):
    """
    Return the student's full weekly timetable.

    Each period card includes:
    - `color` — a deterministic hex colour assigned to the course code
      (consistent across views so the same course always appears the same colour).
    - `faculty_name` — resolved display name of the faculty member.

    **Response shape**
    ```json
    {
      "class_id": "CS-A-SEM6",
      "days": {
        "Monday": [ { "period_id": "...", "start_time": "09:00", "color": "#6366F1", ... } ],
        ...
      },
      "all_courses": {
        "CS401": { "name": "Machine Learning", "color": "#6366F1" }
      }
    }
    ```
    """
    try:
        return _service().get_weekly_timetable(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/attendance-summary",
    summary="Overall and course-wise attendance percentage breakdown",
    response_description="Attendance summary with colour-coded course breakdown",
)
async def get_attendance_summary(
    student_id: str = Query(..., description="Student ID"),
):
    """
    Return the student's overall attendance percentage plus a per-course
    breakdown.

    **Band thresholds**

    | band      | condition | colour  |
    |-----------|-----------|---------|
    | `safe`    | ≥ 85 %    | #22C55E |
    | `warning` | 75–85 %   | #F59E0B |
    | `danger`  | < 75 %    | #EF4444 |

    Each course entry also contains ``required_consecutive_to_reach_75`` —
    the minimum number of consecutive classes the student must attend to
    bring the course percentage back above 75 %.

    **Response shape**
    ```json
    {
      "overall": { "percentage": 78.4, "present": 45, "absent": 12, ... },
      "course_breakdown": [
        { "course_code": "CS401", "percentage": 65.0, "band": "danger", ... }
      ],
      "has_critical": true,
      "critical_courses": [ ... ]
    }
    ```
    """
    try:
        return _service().get_attendance_summary(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/warnings",
    summary="Attendance warnings for courses below or near 75% threshold",
    response_description="List of at-risk courses with colour coding and human-readable messages",
)
async def get_warnings(
    student_id: str = Query(..., description="Student ID"),
):
    """
    Return attendance warnings for courses below or near the 75 % threshold.

    - ``has_critical_warning`` is ``true`` if **any** course is below 75 %.
    - ``messages`` contains human-readable warning strings ready to display.
    - Each course entry is colour-coded via ``band_color`` (see legend below).

    **Legend**
    ```json
    {
      "safe":    { "label": "> 85%",  "color": "#22C55E" },
      "warning": { "label": "75–85%", "color": "#F59E0B" },
      "danger":  { "label": "< 75%",  "color": "#EF4444" }
    }
    ```
    """
    try:
        return _service().get_warnings(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
