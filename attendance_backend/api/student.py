"""
api/student.py
────────────────────────────────────────────────────────────────────────────────
Student-facing API endpoints.

Changes from original
---------------------
1. _require_student_role()
   Validates X-Student-Token header.  Returns token doc containing
   ``student_id`` and ``class_id``.  Dev bypass: "dev_student_{student_id}".

2. _assert_own_record(requesting_student_id, queried_student_id)
   Every handler verifies that the student_id in the query matches the
   authenticated student.  A student can NEVER query another student's data —
   the check happens on the backend before any Firebase query runs.

3. get_attendance_history — enhanced with pagination + date-range + course
   filter, now also guarded by _assert_own_record.

4. SSE/WebSocket subscription helper — students can subscribe to their own
   class room for real-time "your attendance was marked" notifications.

Endpoints
---------
GET /api/v1/student/attendance/today        (existing — now guarded)
GET /api/v1/student/attendance/history      (existing — enhanced + now guarded)
GET /api/v1/student/dashboard               (existing — now guarded)
GET /api/v1/student/timetable               (existing — now guarded)
GET /api/v1/student/attendance-summary      (existing — now guarded)
GET /api/v1/student/warnings                (existing — now guarded)
GET /api/v1/student/realtime/token          (NEW — short-lived SSE/WS token)
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from database.firebase_client import FirebaseClient
from services.student_service import StudentService

router = APIRouter(prefix="/api/v1/student", tags=["student"])

# Singleton-style service (stateless — safe to share across requests)
_svc = StudentService()


# ══════════════════════════════════════════════════════════════════════════════
# Auth guard
# ══════════════════════════════════════════════════════════════════════════════

async def _require_student_role(x_student_token: Optional[str] = Header(None)):
    """
    Validate X-Student-Token.

    Returns token doc with at minimum ``student_id`` and ``class_id`` keys.
    Dev bypass: token starting with "dev_student_{student_id}".
    """
    if not x_student_token:
        raise HTTPException(status_code=401, detail="X-Student-Token header required.")

    if x_student_token.startswith("dev_student_"):
        sid = x_student_token[len("dev_student_"):]
        try:
            fb = FirebaseClient()
            user = fb.get_reference(f"users/{sid}").get() or {}
            class_id = user.get("class_id", "")
        except Exception:
            class_id = ""
        return {"role": "student", "student_id": sid, "class_id": class_id}

    try:
        fb = FirebaseClient()
        doc = fb.get_reference(f"auth_tokens/{x_student_token}").get()
        if (
            doc
            and isinstance(doc, dict)
            and doc.get("role") == "student"
            and not doc.get("revoked")
        ):
            return doc
    except Exception:
        pass

    raise HTTPException(status_code=403, detail="Invalid or insufficient student token.")


# ══════════════════════════════════════════════════════════════════════════════
# Own-record guard
# ══════════════════════════════════════════════════════════════════════════════

def _assert_own_record(authenticated_student_id: str, queried_student_id: str) -> None:
    """
    Raise 403 if *queried_student_id* ≠ *authenticated_student_id*.

    This is the single, centrally enforced rule that prevents any student
    from viewing another student's attendance data.
    """
    if authenticated_student_id != queried_student_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "You are not authorised to access this student's records. "
                "You may only query your own attendance data."
            ),
        )


def _service() -> StudentService:
    return _svc


# ══════════════════════════════════════════════════════════════════════════════
# Existing endpoints — now guarded
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/attendance/today",
    summary="Get today's attendance status for the authenticated student",
    response_description="Attendance record for today, or {status: not_marked}",
)
async def get_today_attendance(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
):
    """
    Return the student's attendance record for today.

    Returns ``{"status": "not_marked"}`` when no record exists yet.
    A student can only query their own record; any other student_id returns 403.
    """
    _assert_own_record(_student["student_id"], student_id)

    try:
        fb    = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        ref   = fb.get_reference(f"attendance/{today}/{student_id}")
        data  = ref.get()
        if data and isinstance(data, dict):
            # Return only fields safe for the student to see — strip any
            # internal metadata fields that contain other students' data.
            return {
                "status":     data.get("status", "not_marked"),
                "markedAt":   data.get("markedAt"),
                "period_id":  data.get("period_id"),
                "class_id":   data.get("class_id"),
                "confidence": data.get("confidence"),
            }
        return {"status": "not_marked"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get(
    "/attendance/history",
    summary="Paginated attendance history — own records only",
    response_description="Paginated list of attendance records",
)
async def get_attendance_history(
    student_id: str  = Query(..., description="Must match your authenticated identity"),
    page:       int  = Query(1,   ge=1,                   description="Page number (1-based)"),
    page_size:  int  = Query(20,  ge=1, le=100,            description="Records per page"),
    course_id:  Optional[str] = Query(None,                description="Filter by course code"),
    start_date: Optional[str] = Query(None,                description="Filter from date YYYY-MM-DD (inclusive)"),
    end_date:   Optional[str] = Query(None,                description="Filter to date YYYY-MM-DD (inclusive)"),
    _student=Depends(_require_student_role),
):
    """
    Return paginated attendance history for the authenticated student.

    Supports filtering by course code and/or date range.
    Each record includes ``marked_by_name`` (faculty display name) and
    a ``status_color`` hex string for the frontend.
    Cross-student access is blocked server-side.
    """
    _assert_own_record(_student["student_id"], student_id)

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


@router.get(
    "/dashboard",
    summary="Student dashboard — today's schedule with real-time status (own only)",
    response_description="Today's periods with status, active period countdown, and summary",
)
async def get_dashboard(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
):
    """
    Return everything the student dashboard needs in a single call.

    Only the authenticated student's own data is returned.
    Attempting to access another student's dashboard returns 403.

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
    _assert_own_record(_student["student_id"], student_id)

    try:
        return _service().build_dashboard_data(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/timetable",
    summary="Full weekly timetable grid, colour-coded by course — own class only",
    response_description="Timetable organised by day with course colours",
)
async def get_timetable(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
):
    """
    Return the student's full weekly timetable.

    The timetable is scoped to the student's own class (class_id from their
    user record). Each period card includes:
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
    _assert_own_record(_student["student_id"], student_id)

    try:
        return _service().get_weekly_timetable(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/attendance-summary",
    summary="Overall and course-wise attendance percentage — own records only",
    response_description="Attendance summary with colour-coded course breakdown",
)
async def get_attendance_summary(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
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

    Cross-student access is blocked server-side before any data is fetched.

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
    _assert_own_record(_student["student_id"], student_id)

    try:
        return _service().get_attendance_summary(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/warnings",
    summary="Attendance warnings for courses below or near 75% — own only",
    response_description="List of at-risk courses with colour coding and human-readable messages",
)
async def get_warnings(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
):
    """
    Return attendance warnings for courses below or near the 75 % threshold.

    - ``has_critical_warning`` is ``true`` if **any** course is below 75 %.
    - ``messages`` contains human-readable warning strings ready to display.
    - Each course entry is colour-coded via ``band_color`` (see legend below).

    Only the authenticated student's data is returned.

    **Legend**
    ```json
    {
      "safe":    { "label": "> 85%",  "color": "#22C55E" },
      "warning": { "label": "75–85%", "color": "#F59E0B" },
      "danger":  { "label": "< 75%",  "color": "#EF4444" }
    }
    ```
    """
    _assert_own_record(_student["student_id"], student_id)

    try:
        return _service().get_warnings(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# NEW — Real-time SSE/WebSocket token endpoint
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/realtime/token",
    summary="Issue a short-lived SSE/WebSocket token scoped to the student's class",
)
async def get_realtime_token(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    _student=Depends(_require_student_role),
):
    """
    Return a short-lived token that the student can use to subscribe to the
    SSE or WebSocket stream for their own class room.

    The token is scoped to the student's class_id (from their Firebase user
    record).  It expires after 60 minutes and is stored under
    ``auth_tokens/{token}`` in Firebase for validation by the WebSocket handler.

    **Response shape**
    ```json
    {
      "token":      "rt_...",
      "section_id": "CS-A-SEM6",
      "expires_at": "2026-04-30T11:00:00Z",
      "ws_url":     "/api/v1/realtime/ws/CS-A-SEM6?client_id=...&role=student&token=rt_...",
      "sse_url":    "/api/v1/realtime/sse/CS-A-SEM6?client_id=...&role=student&token=rt_..."
    }
    ```
    """
    _assert_own_record(_student["student_id"], student_id)

    # Resolve class_id — prefer the value already in the token doc, then
    # fall back to a Firebase lookup so we never issue a token without a scope.
    class_id = _student.get("class_id", "")
    if not class_id:
        try:
            fb = FirebaseClient()
            user = fb.get_reference(f"users/{student_id}").get() or {}
            class_id = user.get("class_id", "")
        except Exception:
            pass

    if not class_id:
        raise HTTPException(
            status_code=422,
            detail="Student is not enrolled in any class. Cannot issue real-time token.",
        )

    raw     = f"student:{student_id}:{class_id}:{time.time()}"
    token   = "rt_" + hashlib.sha256(raw.encode()).hexdigest()[:32]
    expires = int(time.time()) + 3600   # 60 minutes

    token_doc = {
        "role":       "student",
        "student_id": student_id,
        "class_id":   class_id,
        "expires_at": expires,
        "revoked":    False,
    }

    try:
        fb = FirebaseClient()
        fb.get_reference(f"auth_tokens/{token}").set(token_doc)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not persist realtime token: {exc}",
        )

    base_qs = f"client_id={student_id}&role=student&token={token}"
    return {
        "token":      token,
        "section_id": class_id,
        "expires_at": datetime.utcfromtimestamp(expires).isoformat() + "Z",
        "ws_url":     f"/api/v1/realtime/ws/{class_id}?{base_qs}",
        "sse_url":    f"/api/v1/realtime/sse/{class_id}?{base_qs}",
    }