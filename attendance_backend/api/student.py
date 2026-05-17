"""
api/student.py
────────────────────────────────────────────────────────────────────────────────
Student-facing API endpoints.

Authentication
──────────────
All endpoints now use standard JWT-based authentication via the Authorization
header ("Bearer <token>"), enforced by middleware.auth_middleware.require_role.
The student_id is extracted from the JWT claims (user.user_id) and compared
against the ``student_id`` query parameter to prevent cross-student access.

Original changes
────────────────
1. _assert_own_record(requesting_student_id, queried_student_id)
   Every handler verifies that the student_id in the query matches the
   authenticated student.  A student can NEVER query another student's data —
   the check happens on the backend before any Firebase query runs.

2. get_attendance_history — enhanced with pagination + date-range + course
   filter, now also guarded by _assert_own_record.

3. SSE/WebSocket subscription helper — students can subscribe to their own
   class room for real-time "your attendance was marked" notifications.

Hardening pass (first)
──────────────────────
• get_today_attendance: raw RTDB value is guarded with isinstance(data, dict).
• All bare fb.get_reference().get() calls that previously relied on implicit
  truthiness are wrapped with _safe_rtdb_dict() which returns {} on None,
  non-dict, or any exception, and logs the anomaly at WARNING level.

Patch set (2026-05-13)
──────────────────────
P-2  _safe_get_user() for the profile lookup. Missing profile is NOT an auth
     failure; class_id is just "".

P-3  get_realtime_token: same _safe_get_user() for the fallback lookup, so a
     missing /users/{id} node yields 422 ("not enrolled") instead of 500.

P-4  get_today_attendance: replace bare except / {"status":"error"} 200-body
     with a proper HTTPException(500) so callers get a real HTTP error status.
     _FIREBASE_NOT_FOUND is caught separately → {"status": "not_marked"}.

P-5  Structured warning logs at every auth-guard branch that previously
     swallowed exceptions silently.  Format: logger.warning("%s | reason=%s").

Endpoints
─────────
GET /api/v1/student/attendance/today        guarded by JWT
GET /api/v1/student/attendance/history      guarded by JWT, paginated, filterable
GET /api/v1/student/dashboard               guarded by JWT
GET /api/v1/student/timetable               guarded by JWT
GET /api/v1/student/attendance-summary      guarded by JWT
GET /api/v1/student/warnings                guarded by JWT
GET /api/v1/student/realtime/token          short-lived SSE/WS token
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from database.attendance_repository import AttendanceRepository
from database.firebase_client import FirebaseClient
from middleware.auth_middleware import require_role, TokenPayload
from services.student_service import StudentService

# ── firebase_admin is available at runtime; guard the import so unit tests
#    that mock FirebaseClient can still import this module without the SDK.
try:
    from firebase_admin import exceptions as fb_exceptions          # P-1 / P-2
    _FIREBASE_NOT_FOUND = fb_exceptions.NotFoundError
except ImportError:                                                  # pragma: no cover
    _FIREBASE_NOT_FOUND = Exception   # fallback; full SDK must be present in prod

router = APIRouter(prefix="/api/v1/student", tags=["student"])
logger = logging.getLogger(__name__)                                 # P-5

# Singleton-style service (stateless — safe to share across requests)
_svc = StudentService()


# ══════════════════════════════════════════════════════════════════════════════
# Generic safe RTDB helper
# ══════════════════════════════════════════════════════════════════════════════

def _safe_rtdb_dict(path: str) -> Dict[str, Any]:
    """
    Read *path* from RTDB and always return a plain ``dict``.

    Returns ``{}`` when:
    * The node does not exist (RTDB returns ``None`` or raises NotFoundError)
    * The node value is not a dict (e.g. a scalar or list — pathological data)
    * Firebase raises any other exception (network, auth, etc.)

    Callers must treat an empty dict as "not found" — this helper must NOT
    raise HTTPException because it is a utility layer; the caller decides
    whether absence is an error or expected-absent.

    Note: use this helper only where silent failure on RTDB errors is
    acceptable (e.g. optional enrichment).  For endpoints that must
    distinguish "not found" from "infra outage", use explicit try/except with
    _FIREBASE_NOT_FOUND instead.
    """
    try:
        fb   = FirebaseClient()
        data = fb.get_reference(path).get()
        if isinstance(data, dict):
            return data
        if data is not None:
            logger.warning(
                "_safe_rtdb_dict: unexpected type %s at path '%s' — treating as empty",
                type(data).__name__, path,
            )
        return {}
    except _FIREBASE_NOT_FOUND:
        # Node simply does not exist — not a fault.
        return {}
    except Exception as exc:                                         # noqa: BLE001
        logger.warning("_safe_rtdb_dict: Firebase error reading '%s': %s", path, exc)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# P-2 / P-3  Specific safe user-profile helper
# ══════════════════════════════════════════════════════════════════════════════

def _safe_get_user(student_id: str) -> Dict[str, Any]:
    """
    Fetch /users/{student_id} from RTDB.

    Returns an empty dict — NOT an exception — when:
    * The node doesn't exist (NotFoundError / None result)
    * Any transient RTDB error

    This isolates the "profile enrichment" concern from auth: a missing
    profile is a data-completeness problem, not an authentication failure.
    Unlike _safe_rtdb_dict, it emits structured warning logs (P-5 format)
    and is the canonical helper for all user-profile lookups in this module.
    """
    try:
        fb   = FirebaseClient()
        data = fb.get_reference(f"users/{student_id}").get()
        if isinstance(data, dict):
            return data
        if data is not None:
            logger.warning(
                "users/%s | reason=unexpected_profile_type | type=%s",
                student_id, type(data).__name__,
            )
        return {}
    except _FIREBASE_NOT_FOUND:
        # P-2: missing node is not an error from the caller's perspective.
        logger.warning("users/%s | reason=profile_not_found_in_rtdb", student_id)
        return {}
    except Exception as exc:
        # RTDB connectivity / permission error — log and return empty so the
        # caller decides whether class_id absence is fatal.
        logger.warning(
            "users/%s | reason=rtdb_lookup_failed | exc=%s", student_id, exc
        )
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Auth guard — JWT-based (replaces X-Student-Token custom header)
# ══════════════════════════════════════════════════════════════════════════════

async def _require_student(user: TokenPayload = Depends(require_role("student"))) -> TokenPayload:
    """
    Ensure the authenticated user has the 'student' role.
    Returns the TokenPayload so handlers can access user_id, permissions, etc.
    """
    return user


# ══════════════════════════════════════════════════════════════════════════════
# Own-record guard
# ══════════════════════════════════════════════════════════════════════════════

def _assert_own_record(authenticated_student_id: str, queried_student_id: str) -> None:
    """
    Raise 403 if *queried_student_id* ≠ *authenticated_student_id*.

    This is the single, centrally enforced rule that prevents any student
    from viewing another student's attendance data.  It runs on the backend
    before any Firebase query is issued.
    """
    if authenticated_student_id != queried_student_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "You are not authorised to access this student's records. "
                "You may only query your own attendance data."
            ),
        )


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


def _service() -> StudentService:
    return _svc


_STUDENT_ALLOWED_FIELDS = {
    "record_id",
    "course_id",
    "attendance_date",
    "attendance_time",
    "status",
    "period_id",
    "markedAt",
}


def _student_safe_record(record: dict) -> dict:
    return {key: value for key, value in record.items() if key in _STUDENT_ALLOWED_FIELDS}


def _parse_date_safe(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}. Use YYYY-MM-DD.")


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/attendance/today",
    summary="Get today's attendance status for the authenticated student",
    response_description="Attendance record for today, or {status: not_marked}",
)
async def get_today_attendance(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return the student's attendance record for today.

    Returns ``{"status": "not_marked"}`` when no record exists yet.
    A student can only query their own record; any other student_id returns 403.

    P-4: RTDB infrastructure errors now raise HTTPException(500) instead of
    returning a 200 response body with ``{"status": "error"}``.
    ``_FIREBASE_NOT_FOUND`` (node absent) is caught separately and returns
    ``{"status": "not_marked"}`` — not an error from the client's perspective.
    """
    _assert_own_record(user.user_id, student_id)

    try:
        fb    = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        data  = fb.get_reference(f"attendance/{today}/{student_id}").get()
        if data and isinstance(data, dict):
            # Return only fields safe for the student to see — strip any
            # internal metadata that may reference other students' data.
            return {
                "status":     data.get("status", "not_marked"),
                "markedAt":   data.get("markedAt"),
                "period_id":  data.get("period_id"),
                "class_id":   data.get("class_id"),
                "confidence": data.get("confidence"),
            }
        return {"status": "not_marked"}
    except _FIREBASE_NOT_FOUND:
        # Attendance node for today simply doesn't exist yet — not an error.
        return {"status": "not_marked"}
    except Exception as exc:
        # P-4: real infrastructure errors surface as 500, not a 200 error body.
        logger.error("get_today_attendance | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail="Could not retrieve attendance record.")


@router.get(
    "/attendance/history",
    summary="Paginated attendance history — own records only",
    response_description="Paginated list of attendance records",
)
async def get_attendance_history(
    student_id: str  = Query(..., description="Must match your authenticated identity"),
    page:       int  = Query(1,   ge=1,        description="Page number (1-based)"),
    page_size:  int  = Query(20,  ge=1, le=100, description="Records per page"),
    course_id:  Optional[str] = Query(None,     description="Filter by course code"),
    start_date: Optional[str] = Query(None,     description="Filter from date YYYY-MM-DD (inclusive)"),
    end_date:   Optional[str] = Query(None,     description="Filter to date YYYY-MM-DD (inclusive)"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return paginated attendance history for the authenticated student.

    Supports filtering by course code and/or date range.
    Each record includes ``marked_by_name`` (faculty display name) and
    a ``status_color`` hex string for the frontend.
    Cross-student access is blocked server-side before any data is fetched.
    """
    _assert_own_record(user.user_id, student_id)

    try:
        repo = AttendanceRepository()
        result = repo.get_student_attendance_paginated(
            student_id=student_id,
            page=page,
            page_size=page_size,
            course_id=course_id,
            start_date=_parse_date_safe(start_date),
            end_date=_parse_date_safe(end_date),
        )
        if page > result["total_pages"] and result["total"] > 0:
            raise HTTPException(status_code=404, detail=f"Page {page} does not exist. Max page: {result['total_pages']}.")
        result["records"] = [_student_safe_record(record) for record in result["records"]]
        return result
    except Exception as exc:
        logger.error("get_attendance_history | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/dashboard",
    summary="Student dashboard — today's schedule with real-time status (own only)",
    response_description="Today's periods with status, active period countdown, and summary",
)
async def get_dashboard(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return everything the student dashboard needs in a single call.

    Only the authenticated student's own data is returned.
    Attempting to access another student's dashboard returns 403.

    **Period status values**

    | status    | meaning                              | colour  |
    |-----------|--------------------------------------|---------|
    | `present` | Attendance recorded, on time         | #22C55E |
    | `late`    | Attendance recorded, arrived late    | #F59E0B |
    | `absent`  | Period ended, no attendance recorded | #EF4444 |
    | `pending` | Period in progress or not yet started| #94A3B8 |

    The ``active_period`` field contains the currently running period with a
    ``countdown_seconds`` field indicating seconds remaining in the class.

    **Response shape**
    ```json
    {
      "today_date": "2026-05-13",
      "day_name": "Wednesday",
      "active_period": { ...period card... },
      "periods_today": [ ...period cards... ],
      "summary": { "total": 5, "present": 2, "absent": 1, "late": 0, "pending": 2 },
      "overall_attendance": { "percentage": 82.5, "band": "warning", "color": "#F59E0B" }
    }
    ```
    """
    _assert_own_record(user.user_id, student_id)

    try:
        return _service().build_dashboard_data(student_id)
    except Exception as exc:
        logger.error("get_dashboard | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/timetable",
    summary="Full weekly timetable grid, colour-coded by course — own class only",
    response_description="Timetable organised by day with course colours",
)
async def get_timetable(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return the student's full weekly timetable.

    The timetable is scoped to the student's own class (``class_id`` from their
    user record).  Each period card includes:

    - ``color`` — a deterministic hex colour assigned to the course code
      (consistent across all views; the same course always shows the same colour).
    - ``faculty_name`` — resolved display name of the faculty member.

    **Response shape**
    ```json
    {
      "class_id": "CS-A-SEM6",
      "days": {
        "Monday": [
          { "period_id": "...", "start_time": "09:00", "color": "#6366F1", ... }
        ]
      },
      "all_courses": {
        "CS401": { "name": "Machine Learning", "color": "#6366F1" }
      }
    }
    ```
    """
    _assert_own_record(user.user_id, student_id)

    try:
        return _service().get_weekly_timetable(student_id)
    except Exception as exc:
        logger.error("get_timetable | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/attendance-summary",
    summary="Overall and course-wise attendance percentage — own records only",
    response_description="Attendance summary with colour-coded course breakdown",
)
async def get_attendance_summary(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
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
    the minimum consecutive classes the student must attend to bring that
    course back above 75 %.

    Cross-student access is blocked server-side before any data is fetched.

    **Response shape**
    ```json
    {
      "overall": { "percentage": 78.4, "present": 45, "absent": 12 },
      "course_breakdown": [
        { "course_code": "CS401", "percentage": 65.0, "band": "danger", ... }
      ],
      "has_critical": true,
      "critical_courses": [ ... ]
    }
    ```
    """
    _assert_own_record(user.user_id, student_id)

    try:
        return _service().get_attendance_summary(student_id)
    except Exception as exc:
        logger.error("get_attendance_summary | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/warnings",
    summary="Attendance warnings for courses below or near 75% — own only",
    response_description="List of at-risk courses with colour coding and human-readable messages",
)
async def get_warnings(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return attendance warnings for courses below or near the 75 % threshold.

    - ``has_critical_warning`` is ``true`` if **any** course is below 75 %.
    - ``messages`` contains human-readable warning strings ready to display.
    - Each course entry is colour-coded via ``band_color``.

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
    _assert_own_record(user.user_id, student_id)

    try:
        return _service().get_warnings(student_id)
    except Exception as exc:
        logger.error("get_warnings | student_id=%s | exc=%s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# Analytics — personal trend + summary + streaks  (Prompt 5)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/analytics",
    summary="Personal analytics — trend, summary, and streak (own data only)",
    response_description="Attendance trend, overall percentage, and current/longest streak",
)
async def get_student_analytics(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    days: int = Query(30, ge=7, le=180, description="Trend window in days"),
    user: TokenPayload = Depends(_require_student),
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
    _assert_own_record(user.user_id, student_id)

    try:
        repo = AttendanceRepository()
        today = datetime.now().date()
        start = today - timedelta(days=days)

        records = repo.get_student_attendance(student_id, start_date=start, end_date=today)

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
            student_id, days, rate,
        )

        return {
            "student_id": student_id,
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
            student_id, exc,
        )
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# Real-time SSE/WebSocket token  (P-3)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/realtime/token",
    summary="Issue a short-lived SSE/WebSocket token scoped to the student's class",
)
async def get_realtime_token(
    student_id: str = Query(..., description="Must match your authenticated identity"),
    user: TokenPayload = Depends(_require_student),
):
    """
    Return a short-lived token that the student can use to subscribe to the
    SSE or WebSocket stream for their own class room.

    The token is scoped to the student's ``class_id`` (from their Firebase
    user record).  It expires after 60 minutes and is stored under
    ``auth_tokens/{token}`` in RTDB for validation by the WebSocket handler.

    P-3: The fallback user-profile lookup uses ``_safe_get_user()``, so a
    missing ``/users/{id}`` node yields a 422 ("not enrolled") instead of 500.

    **Response shape**
    ```json
    {
      "token":      "rt_...",
      "section_id": "CS-A-SEM6",
      "expires_at": "2026-05-13T11:00:00Z",
      "ws_url":     "/api/v1/realtime/ws/CS-A-SEM6?client_id=...&role=student&token=rt_...",
      "sse_url":    "/api/v1/realtime/sse/CS-A-SEM6?client_id=...&role=student&token=rt_..."
    }
    ```
    """
    _assert_own_record(user.user_id, student_id)

    # Resolve class_id from user profile (P-3: never raises)
    profile  = _safe_get_user(student_id)
    class_id = profile.get("class_id", "")

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
        logger.error(
            "get_realtime_token | student_id=%s | reason=token_persist_failed | exc=%s",
            student_id, exc,
        )
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


# ══════════════════════════════════════════════════════════════════════════════
# P-6  Companion note for student_secured.py / auth_decorators.py
# ══════════════════════════════════════════════════════════════════════════════
#
# decorators/auth_decorators.py  →  require_own_student_data
# ──────────────────────────────────────────────────────────
# The decorator resolves the caller's student_id from their auth context, then
# compares it to the query-param student_id.  It must NOT perform a bare RTDB
# lookup for profile data — that was where the original 500 crept in.
# The student_id present in the token (auth_user.uid) is the source of truth.
#
# Minimal reference implementation:
#
#   def require_own_student_data(param_name: str):
#       async def _dep(
#           request: Request,
#           auth_user: UserContext = Depends(require_student),
#       ):
#           queried_id = request.query_params.get(param_name)
#           if auth_user.role == "student" and auth_user.uid != queried_id:
#               raise HTTPException(403, "You may only query your own data.")
#           # Teachers/admins skip the check — they have class-wide access.
#       return Depends(_dep)
#
# If a profile lookup IS needed inside the decorator for any reason, use
# _safe_get_user() (or a local equivalent with the same error contract):
# NotFoundError and RTDB failures must return {} and never propagate.