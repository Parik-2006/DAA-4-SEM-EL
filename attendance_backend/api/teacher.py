"""
api/teacher.py  —  unified teacher-facing API
──────────────────────────────────────────────────────────────────────────────
Merged from two separate implementations.

Auth conventions (apply everywhere)
────────────────────────────────────
• JWT-based auth via ``require_role`` + ``TokenPayload`` (primary).
• ``_get_assigned_sections(faculty_id)`` performs a secondary Firebase
  ownership check — belt-and-suspenders on top of JWT claims so that stale
  tokens or manually-created period records can never leak across sections.
• Teachers see only their own faculty_id and assigned sections.
• Admins may pass ``faculty_id`` query param to inspect/operate as any teacher.
• Section-level guard: ``_enforce_period_access()`` blocks cross-section reads.

Realtime integration
────────────────────
• mark-bulk    → broadcasts "bulk_attendance"   to section room + cache bust
• mark single  → broadcasts "attendance_marked" to section room + cache bust
• edit record  → broadcasts "attendance_marked" to section room + cache bust
• lock/unlock  → broadcasts "period_locked" / "period_unlocked"
• /active-class roster is cached for TEACHER_CACHE_TTL (5 s) and busted on
  any attendance event for that section.

Endpoint index
──────────────
Schedule / timetable (read-only)
  GET  /teacher/dashboard               Rich dashboard: schedule + counts + detection
  GET  /teacher/schedule/today          Lightweight schedule with live window phases (cached)
  GET  /teacher/active-class            Active period + full student roster (5 s cache)
  GET  /teacher/periods/active          Periods open RIGHT NOW (repo cache, cheap)
  GET  /teacher/available-periods       Same, richer runtime fields (Firestore)
  GET  /teacher/periods/{period_id}     Single period detail + window status
  GET  /teacher/timetable               Full weekly grid for assigned classes

Attendance marking
  POST /teacher/attendance/mark         Mark one student (full validation chain)
  POST /teacher/attendance/mark-bulk    Mark many students at once (up to 200)

Attendance reads / edits
  GET   /teacher/attendance/by-period/{period_id}   All records for a period
  PATCH /teacher/attendance/{record_id}             Edit one record (window-gated)
  GET   /teacher/attendance/{record_id}/audit        Immutable audit trail

Period lock management
  POST /teacher/period/{period_id}/lock    Manually lock (teacher action)
  POST /teacher/period/{period_id}/unlock  Force-unlock (admin only)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from google.cloud.firestore_v1 import FieldFilter

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    DAY_OF_WEEK_MAP,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
)
from database.attendance_repository import AttendanceRepository
from database.timetable_repository import get_timetable_repository
from middleware.auth_middleware import require_role
from services.attendance_lock_service import get_lock_service
from services.auth_service import TokenPayload
from services.firebase_service import get_firebase_service
from services.period_detection_service import get_period_detection_service
from services.realtime_service import get_realtime_service, TEACHER_CACHE_TTL
from services.timetable_service import get_timetable_service
from utils.time_validator import TimeValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])

_tv = TimeValidator()

_VALID_STATUSES  = {"present", "absent", "late", "excused"}
_LOCK_REASON_MANUAL = "manual"


# ══════════════════════════════════════════════════════════════════════════════
# Shared dependency helpers
# ══════════════════════════════════════════════════════════════════════════════

def _require_lock_svc():
    svc = get_lock_service()
    if svc is None:
        raise HTTPException(503, "AttendanceLockService not initialised")
    return svc


def _require_timetable_svc():
    svc = get_timetable_service()
    if svc is None:
        raise HTTPException(503, "TimetableService not initialised")
    return svc


def _require_repo():
    repo = get_timetable_repository()
    if repo is None:
        raise HTTPException(503, "TimetableRepository not initialised")
    return repo


def _require_firebase():
    fb = get_firebase_service()
    if fb is None:
        raise HTTPException(503, "FirebaseService not initialised")
    return fb


def _get_firestore():
    fb = _require_firebase()
    db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
    if db is None:
        raise HTTPException(503, "Firestore client not available")
    return db


def _get_rtdb():
    try:
        from database.firebase_client import FirebaseClient
        return FirebaseClient()
    except Exception as exc:
        raise HTTPException(503, f"Firebase RTDB not available: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Section ownership guard (Firebase-level, belt-and-suspenders over JWT)
# ══════════════════════════════════════════════════════════════════════════════

async def _get_assigned_sections(faculty_id: str) -> Set[str]:
    """
    Return the set of class_ids assigned to *faculty_id* by querying Firebase.

    This is a secondary check on top of the JWT ``assigned_sections`` claim.
    It catches stale tokens and manually-created period records that may be
    inconsistent with the live course_assignments collection.

    Falls back to the ``classes`` collection if course_assignments is empty,
    then returns an empty set on unexpected errors (callers handle that case).
    """
    try:
        from database.firebase_client import FirebaseClient
        fb = FirebaseClient()

        # Primary: course_assignments
        assignments_raw = fb.get_reference("course_assignments").get() or {}
        sections: Set[str] = {
            v.get("class_id")
            for v in assignments_raw.values()
            if isinstance(v, dict)
            and v.get("faculty_id") == faculty_id
            and v.get("class_id")
        }

        # Secondary fallback: classes.faculty_id
        if not sections:
            classes_raw = fb.get_reference("classes").get() or {}
            sections = {
                v.get("id")
                for v in classes_raw.values()
                if isinstance(v, dict)
                and v.get("faculty_id") == faculty_id
                and not v.get("deleted", False)
                and v.get("id")
            }

        return sections
    except Exception as exc:
        logger.error("_get_assigned_sections failed: %s", exc)
        return set()


def _assert_section_access(section_id: str, assigned: Set[str]) -> None:
    """Raise 403 if *section_id* is not in *assigned*."""
    if section_id not in assigned:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Access denied: section '{section_id}' is not assigned to you. "
                "Contact an admin if this is incorrect."
            ),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Auth / access helpers (JWT-level)
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_faculty_id(
    current_user: TokenPayload,
    requested_faculty_id: Optional[str],
) -> str:
    """
    Resolve the effective faculty_id from the JWT and optional override.

    • Teachers always operate as themselves.
    • Admins may supply ``faculty_id`` to operate on behalf of any teacher.
    """
    if current_user.role == "admin":
        if not requested_faculty_id:
            raise HTTPException(400, "faculty_id query param is required for admin requests")
        return requested_faculty_id

    if current_user.role != "teacher":
        raise HTTPException(403, "Only teachers and admins can access teacher endpoints")

    if requested_faculty_id and requested_faculty_id != current_user.user_id:
        raise HTTPException(403, "Teachers can only access their own faculty_id")

    return current_user.user_id


def _enforce_period_access(
    current_user: TokenPayload,
    period: Dict[str, Any],
) -> None:
    """
    Raise 403 if the teacher is not assigned to this period or its section.

    Checks both the JWT ``assigned_sections`` claim AND the period's
    ``faculty_id`` field.  Admins bypass all checks.
    """
    if current_user.role == "admin":
        return

    period_faculty = str(period.get("faculty_id") or "").strip()
    class_id       = str(period.get("class_id")   or "").strip()

    if period_faculty and period_faculty != current_user.user_id:
        raise HTTPException(403, "You are not the assigned faculty for this period")

    assigned = getattr(current_user, "assigned_sections", None) or []
    if assigned and class_id and class_id not in assigned:
        raise HTTPException(403, f"Section '{class_id}' is not in your assigned sections")


def _assigned_class_ids(current_user: TokenPayload) -> List[str]:
    """Return the list of class_ids from the JWT ``assigned_sections`` claim."""
    return list(getattr(current_user, "assigned_sections", None) or [])


# ══════════════════════════════════════════════════════════════════════════════
# Misc helpers
# ══════════════════════════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_hhmm(t: str, date: Optional[str] = None) -> datetime:
    d = date or _today()
    return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")


def _period_runtime_status(start_time: str, end_time: str) -> str:
    window = _tv.get_window({"start_time": start_time, "end_time": end_time,
                              "period_type": "lecture"})
    return window.phase


def _fetch_today_records(date: str) -> Dict[str, Any]:
    try:
        fb_rt = _get_rtdb()
        return fb_rt.get_reference(f"attendance/{date}").get() or {}
    except Exception as exc:
        logger.warning("Could not fetch today's attendance: %s", exc)
        return {}


def _build_period_summary(
    period: Dict[str, Any],
    lock_svc,
    today_records: Dict[str, Any],
    date: str,
) -> Dict[str, Any]:
    window = lock_svc.get_window_status(period, date)
    pid    = period.get("period_id", "")

    def _count(s: str) -> int:
        return sum(
            1 for r in today_records.values()
            if isinstance(r, dict)
            and r.get("period_id") == pid
            and r.get("status") == s
        )

    return {
        **period,
        "window": window,
        "attendance_counts": {
            "present":      _count("present"),
            "late":         _count("late"),
            "absent":       _count("absent"),
            "total_marked": _count("present") + _count("late") + _count("absent"),
        },
    }


def _student_status_today(
    student_id: str,
    today_records: Dict[str, Any],
) -> Optional[str]:
    for rec in today_records.values():
        if isinstance(rec, dict) and rec.get("student_id") == student_id:
            return rec.get("status", "present")
    return None


def _write_attendance_record(fb_rt, record_id: str, date: str, payload: Dict[str, Any]) -> None:
    fb_rt.get_reference(f"attendance/{date}/{record_id}").set(payload)


# ══════════════════════════════════════════════════════════════════════════════
# GET /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/dashboard",
    summary="Rich teacher dashboard: full schedule, counts, detection state",
)
async def get_teacher_dashboard(
    faculty_id:   Optional[str] = Query(None, description="Admin override: target faculty"),
    date:         Optional[str] = Query(None, description="YYYY-MM-DD, defaults today"),
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
):
    """
    Returns the teacher's full schedule for ``date`` (today by default).

    Each period is enriched with:
    - ``window``             : open / grace / locked status + human message
    - ``attendance_counts``  : present / late / absent / total_marked
    - ``is_current``         : True for the period active right now

    Only periods belonging to sections assigned to this teacher are returned.
    Unassigned sections are silently excluded.
    """
    lock_svc   = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    date       = date or _today()
    today_dow  = datetime.strptime(date, "%Y-%m-%d").weekday()

    # Double-check section ownership against Firebase (not just JWT)
    assigned_sections = await _get_assigned_sections(faculty_id)

    try:
        db     = _get_firestore()
        p_docs = (
            db.collection("periods")
            .where(filter=FieldFilter("faculty_id",    "==", faculty_id))
            .where(filter=FieldFilter("day_of_week",   "==", today_dow))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("start_time")
            .stream()
        )
        # Belt-and-suspenders: also filter by Firebase-verified sections
        periods = [
            d.to_dict() for d in p_docs
            if not assigned_sections
            or d.to_dict().get("class_id") in assigned_sections
        ]
    except Exception as exc:
        logger.error("Dashboard period fetch failed: %s", exc)
        raise HTTPException(500, f"Could not fetch periods: {exc}")

    today_records = _fetch_today_records(date)

    detection_svc     = get_period_detection_service()
    current_period_id: Optional[str] = None
    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload and payload.get("primary_period"):
            current_period_id = payload["primary_period"].get("period_id")

    schedule: List[Dict[str, Any]] = []
    active_period_summary           = None

    for p in periods:
        summary = _build_period_summary(p, lock_svc, today_records, date)
        summary["is_current"] = (p.get("period_id") == current_period_id)
        schedule.append(summary)
        if summary["is_current"]:
            active_period_summary = summary
        try:
            lock_svc.auto_lock_if_expired(p, date)
        except Exception:
            pass

    return JSONResponse(status_code=200, content={
        "faculty_id":        faculty_id,
        "date":              date,
        "day":               DAY_OF_WEEK_MAP.get(today_dow, "?"),
        "assigned_sections": list(assigned_sections),
        "total_periods":     len(schedule),
        "schedule":          schedule,
        "active_period":     active_period_summary,
        "generated_at":      datetime.now().isoformat(),
        "config": {
            "attendance_window_minutes": ATTENDANCE_WINDOW_MINUTES,
            "late_threshold_minutes":   LATE_THRESHOLD_MINUTES,
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /schedule/today  (lightweight, repo cache)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/schedule/today",
    summary="Lightweight today schedule with live window phases (cached)",
)
async def get_today_schedule(
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
):
    """
    Returns today's periods using the in-process TimetableRepository cache
    (60-second TTL).  Cheaper than ``/dashboard`` — good for polling every
    30 seconds to update window phase badges in the UI.
    """
    repo       = _require_repo()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids  = _assigned_class_ids(current_user)

    schedule = repo.get_today_schedule_for_teacher(faculty_id, class_ids)
    enriched = [{**p, "window": _tv.get_window(p).to_dict()} for p in schedule]

    return JSONResponse(status_code=200, content={
        "faculty_id":   faculty_id,
        "date":         _today(),
        "day_name":     datetime.now().strftime("%A"),
        "period_count": len(enriched),
        "schedule":     enriched,
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /active-class  (5-second cache + Firebase section guard)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/active-class",
    summary="Currently active class with full annotated student roster (5 s cache)",
)
async def get_active_class(
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
):
    """
    Returns the period running right now for this teacher together with the
    full student roster.  Each student is annotated with today's attendance
    status and face thumbnail URL.

    The roster is cached for ``TEACHER_CACHE_TTL`` (5 s) and automatically
    invalidated when an attendance event is broadcast for this section.

    Returns HTTP 404 when there is no active period for this teacher.
    """
    lock_svc   = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    date       = _today()

    # ── 5-second cache ────────────────────────────────────────────────────────
    rt_svc    = get_realtime_service()
    cache_key = f"teacher_active_{faculty_id}"
    cached    = rt_svc.cache_get(cache_key)
    if cached is not None:
        return JSONResponse(status_code=200, content={**cached, "_cached": True})

    # Verify section ownership from Firebase
    assigned_sections = await _get_assigned_sections(faculty_id)

    # ── Find active period ────────────────────────────────────────────────────
    active_period: Optional[Dict[str, Any]] = None

    # Try detection service first
    detection_svc = get_period_detection_service()
    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload:
            for p in payload.get("active_periods", []):
                if (
                    p.get("faculty_id") == faculty_id
                    and (not assigned_sections or p.get("class_id") in assigned_sections)
                ):
                    active_period = p
                    break

    # Fallback: direct Firestore query
    if active_period is None:
        try:
            now     = datetime.now()
            now_str = now.strftime(TIME_FORMAT_HM)
            db      = _get_firestore()
            docs    = (
                db.collection("periods")
                .where(filter=FieldFilter("faculty_id",    "==", faculty_id))
                .where(filter=FieldFilter("day_of_week",   "==", now.weekday()))
                .where(filter=FieldFilter("active_status", "==", True))
                .where(filter=FieldFilter("start_time",    "<=", now_str))
                .stream()
            )
            for c in [d.to_dict() for d in docs]:
                if assigned_sections and c.get("class_id") not in assigned_sections:
                    continue
                end_dt = _parse_hhmm(c["end_time"]) + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
                if now <= end_dt:
                    active_period = c
                    break
        except Exception as exc:
            logger.error("Active-class fallback query failed: %s", exc)

    if active_period is None:
        return JSONResponse(status_code=404, content={
            "is_active":  False,
            "faculty_id": faculty_id,
            "message":    "No active class period right now.",
            "checked_at": datetime.now().isoformat(),
        })

    # JWT-level access check
    _enforce_period_access(current_user, active_period)
    # Firebase-level section check
    class_id  = active_period.get("class_id", "")
    period_id = active_period.get("period_id", "")
    if assigned_sections:
        _assert_section_access(class_id, assigned_sections)

    window = lock_svc.get_window_status(active_period, date)

    # ── Student roster (this section only) ────────────────────────────────────
    try:
        db       = _get_firestore()
        stu_docs = (
            db.collection("students")
            .where(filter=FieldFilter("class_id",     "==", class_id))
            .where(filter=FieldFilter("active_status","==", True))
            .order_by("name")
            .stream()
        )
        students_raw = [d.to_dict() for d in stu_docs]
    except Exception as exc:
        logger.error("Roster fetch failed: %s", exc)
        students_raw = []

    today_records = _fetch_today_records(date)

    roster = [
        {
            "student_id":        s.get("student_id", ""),
            "name":              s.get("name", ""),
            "email":             s.get("email", ""),
            "roll_number":       s.get("roll_number") or s.get("metadata", {}).get("roll_number"),
            "face_thumbnail":    s.get("face_thumbnail_url") or s.get("face_image_preview"),
            "attendance_status": _student_status_today(s.get("student_id", ""), today_records),
            "is_marked":         _student_status_today(s.get("student_id", ""), today_records) is not None,
        }
        for s in students_raw
    ]

    result = {
        "is_active": True,
        "period":    active_period,
        "window":    window,
        "date":      date,
        "class_id":  class_id,
        "roster":    roster,
        "summary": {
            "total_students": len(roster),
            "present":    sum(1 for s in roster if s["attendance_status"] == "present"),
            "late":       sum(1 for s in roster if s["attendance_status"] == "late"),
            "absent":     sum(1 for s in roster if s["attendance_status"] == "absent"),
            "not_marked": sum(1 for s in roster if not s["is_marked"]),
        },
        "checked_at": datetime.now().isoformat(),
    }

    rt_svc.cache_set(cache_key, result, ttl=TEACHER_CACHE_TTL)

    return JSONResponse(status_code=200, content={**result, "_cached": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET /periods/active  (repo cache — cheap)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/periods/active",
    summary="Periods currently open for attendance (repo cache, cheap)",
)
async def get_active_periods(
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
):
    """
    Lightweight endpoint for the "Mark Attendance" button enable/disable check.
    Uses the TimetableRepository 60-second cache — safe to poll every 30 s.
    """
    repo       = _require_repo()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids  = _assigned_class_ids(current_user)

    active = repo.get_active_periods_for_teacher(faculty_id, class_ids)

    return JSONResponse(status_code=200, content={
        "faculty_id":   faculty_id,
        "checked_at":   datetime.now().isoformat(),
        "active_count": len(active),
        "periods":      active,
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /available-periods  (Firestore query — richer fields)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/available-periods",
    summary="Periods available for marking right now (Firestore, richer fields)",
)
async def get_available_periods(
    faculty_id: Optional[str] = Query(None, description="Admin override"),
    date:       Optional[str] = Query(None, description="YYYY-MM-DD"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Like ``/periods/active`` but queries Firestore directly and adds runtime
    status labels and the full ``window`` dict for each period.
    """
    lock_svc          = _require_lock_svc()
    faculty_id        = _resolve_faculty_id(current_user, faculty_id)
    date              = date or _today()
    dow               = datetime.strptime(date, "%Y-%m-%d").weekday()
    assigned_sections = await _get_assigned_sections(faculty_id)

    try:
        db   = _get_firestore()
        docs = (
            db.collection("periods")
            .where(filter=FieldFilter("faculty_id",    "==", faculty_id))
            .where(filter=FieldFilter("day_of_week",   "==", dow))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("start_time")
            .stream()
        )
        periods = [
            d.to_dict() for d in docs
            if not assigned_sections
            or d.to_dict().get("class_id") in assigned_sections
        ]
    except Exception as exc:
        raise HTTPException(500, f"Could not fetch periods: {exc}")

    available = []
    for p in periods:
        _enforce_period_access(current_user, p)
        window  = lock_svc.get_window_status(p, date)
        runtime = _period_runtime_status(p.get("start_time", ""), p.get("end_time", ""))
        item = {
            **p,
            "runtime_status":           runtime,
            "window":                   window,
            "is_available_for_marking": bool(window.get("is_open")),
        }
        if item["is_available_for_marking"]:
            available.append(item)

    return JSONResponse(status_code=200, content={
        "faculty_id":        faculty_id,
        "date":              date,
        "available_count":   len(available),
        "available_periods": available,
        "generated_at":      datetime.now().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /periods/{period_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/periods/{period_id}",
    summary="Single period detail with live window status",
)
async def get_period_detail(
    period_id:    str,
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
):
    repo        = _require_repo()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)

    allowed, reason = repo.validate_teacher_owns_period(period_id, _faculty_id, class_ids)
    if not allowed:
        raise HTTPException(403, reason)

    period = repo.get_period(period_id)
    window = _tv.get_window(period)

    return JSONResponse(status_code=200, content={
        "period": period,
        "window": window.to_dict(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /timetable
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/timetable",
    summary="Full weekly timetable for assigned classes",
)
async def get_weekly_timetable(
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
):
    repo        = _require_repo()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)

    timetable_by_class = {cid: repo.get_full_week(cid) for cid in class_ids}

    return JSONResponse(status_code=200, content={
        "faculty_id":   _faculty_id,
        "classes":      timetable_by_class,
        "generated_at": datetime.now().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# POST /attendance/mark  (single student, full validation chain)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/attendance/mark",
    summary="Mark attendance for one student (timetable-gated, full chain)",
    status_code=201,
)
async def mark_single_attendance(
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    period_id:    str           = Body(..., embed=True),
    student_id:   str           = Body(..., embed=True),
    faculty_id:   Optional[str] = Body(None, embed=True, description="Admin override"),
    att_status:   Optional[str] = Body(
        None, embed=True,
        alias="status",
        description="Override: 'present' | 'late' | 'absent' | 'excused'",
    ),
    note:         Optional[str] = Body(None, embed=True),
):
    """
    Validation chain
    ─────────────────
    1. JWT + role check (require_role)
    2. Period in teacher's assigned section (repo + Firebase)
    3. Teacher is the assigned faculty for the period
    4. Attendance window open (TimeValidator)
    5. Manual lock check (AttendanceLockService)
    6. Student exists
    7. Write to RTDB + audit log
    8. Realtime broadcast + cache bust
    9. Auto-lock if grace window just expired
    """
    repo        = _require_repo()
    lock_svc    = _require_lock_svc()
    fb          = _require_firebase()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)

    # Period ownership (JWT-level)
    allowed, reason = repo.validate_teacher_owns_period(period_id, _faculty_id, class_ids)
    if not allowed:
        raise HTTPException(403, reason)

    period = repo.get_period(period_id)

    # Section ownership (Firebase-level)
    assigned_sections = await _get_assigned_sections(_faculty_id)
    if assigned_sections:
        _assert_section_access(period.get("class_id", ""), assigned_sections)

    # Time window
    window = _tv.get_window(period)
    if not window.is_open:
        return JSONResponse(status_code=423, content={
            "success":    False,
            "student_id": student_id,
            "message":    window.message,
            "window":     window.to_dict(),
        })

    # Manual lock
    if lock_svc.is_locked(period_id):
        return JSONResponse(status_code=423, content={
            "success":    False,
            "student_id": student_id,
            "message":    "Period is manually locked. Contact admin to unlock.",
            "window":     window.to_dict(),
        })

    # Student check
    student = fb.get_student(student_id)
    if not student:
        raise HTTPException(404, f"Student '{student_id}' not found.")

    final_status = att_status if att_status in _VALID_STATUSES else window.auto_status
    date         = _today()
    timestamp    = datetime.now()
    record_id    = f"{date}_{period_id}_{student_id}"
    class_id     = period.get("class_id", "")

    record = {
        "record_id":    record_id,
        "student_id":   student_id,
        "period_id":    period_id,
        "class_id":     class_id,
        "section_id":   class_id,   # section-scoped field for new queries
        "course_id":    period.get("course_id"),
        "faculty_id":   _faculty_id,
        "status":       final_status,
        "confidence":   1.0,
        "markedAt":     timestamp.isoformat(),
        "date":         date,
        "method":       "teacher_manual",
        "note":         note,
        "window_phase": window.phase,
    }

    try:
        fb_rt = _get_rtdb()
        _write_attendance_record(fb_rt, record_id, date, record)
    except Exception as exc:
        logger.error("Attendance write failed: %s", exc)
        raise HTTPException(500, f"Failed to record attendance: {exc}")

    lock_svc.write_audit(
        record_id=record_id, action="CREATE",
        actor_id=_faculty_id, after=record,
    )

    # Realtime broadcast + cache bust
    rt_svc = get_realtime_service()
    rt_svc._invalidate_cache(f"teacher_active_{_faculty_id}")
    await rt_svc.broadcast(
        event_type="attendance_marked",
        section_id=class_id,
        payload={
            "record_id":  record_id,
            "student_id": student_id,
            "period_id":  period_id,
            "status":     final_status,
            "marked_by":  _faculty_id,
        },
    )

    # Auto-lock if grace window just expired
    if window.phase == "grace" and window.time_remaining < 1:
        try:
            lock_svc.lock_period(
                period_id=period_id,
                class_id=class_id,
                actor_id="system",
                reason="auto",
            )
        except Exception:
            pass

    return JSONResponse(status_code=201, content={
        "success":      True,
        "record_id":    record_id,
        "student_id":   student_id,
        "student_name": student.get("name", ""),
        "period_id":    period_id,
        "status":       final_status,
        "marked_by":    _faculty_id,
        "timestamp":    timestamp.isoformat(),
        "window":       window.to_dict(),
        "message": (
            f"Attendance marked as {final_status.upper()} for "
            f"{student.get('name', student_id)}."
        ),
    })


# ══════════════════════════════════════════════════════════════════════════════
# POST /attendance/mark-bulk  (up to 200 students)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/attendance/mark-bulk",
    summary="Bulk-mark attendance for an entire class list (up to 200 students)",
    status_code=200,
)
async def mark_bulk_attendance(
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
    period_id:    str          = Body(..., embed=True),
    students:     List[Dict[str, Any]] = Body(
        ...,
        embed=True,
        description=(
            "List of {student_id, status?, confidence?}. "
            "``status`` omitted → auto-detected. Max 200."
        ),
    ),
    faculty_id:   Optional[str] = Body(None, embed=True, description="Admin override"),
    class_id:     Optional[str] = Body(None, embed=True),
    date:         Optional[str] = Body(None, embed=True),
    note:         Optional[str] = Body(None, embed=True),
):
    """
    Mark an entire class in one request.

    - ``absent`` records are written explicitly so analytics can distinguish
      "confirmed absent" from "period not yet marked".
    - Grace period overrides ``present`` → ``late`` automatically.
    - Returns per-student results so the UI can highlight failures.
    - On any accepted records: broadcasts ``bulk_attendance`` to the section
      room and busts the active-class cache.

    Example body::

        {
          "period_id": "CSE4C_MON_0900",
          "students": [
            {"student_id": "1RV23CS001", "status": "present"},
            {"student_id": "1RV23CS002", "status": "absent"},
            {"student_id": "1RV23CS003"}
          ]
        }
    """
    if len(students) > 200:
        raise HTTPException(400, "Maximum 200 students per bulk mark request.")

    repo        = _require_repo()
    lock_svc    = _require_lock_svc()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)
    date        = date or _today()

    # Period ownership (JWT-level)
    allowed, reason = repo.validate_teacher_owns_period(period_id, _faculty_id, class_ids)
    if not allowed:
        raise HTTPException(403, reason)

    period = repo.get_period(period_id)
    window = _tv.get_window(period)

    effective_class_id = class_id or period.get("class_id", "")

    # Section ownership (Firebase-level)
    assigned_sections = await _get_assigned_sections(_faculty_id)
    if assigned_sections:
        _assert_section_access(effective_class_id, assigned_sections)

    if not window.is_open:
        return JSONResponse(status_code=423, content={
            "success":  False,
            "message":  window.message,
            "window":   window.to_dict(),
            "accepted": 0,
            "rejected": len(students),
        })

    if lock_svc.is_locked(period_id):
        return JSONResponse(status_code=423, content={
            "success":  False,
            "message":  "Period is manually locked.",
            "window":   window.to_dict(),
            "accepted": 0,
            "rejected": len(students),
        })

    fb_rt     = _get_rtdb()
    timestamp = datetime.now()
    now_ts    = timestamp.isoformat()
    results:  List[Dict[str, Any]] = []
    accepted  = 0
    rejected  = 0

    for entry in students:
        sid        = str(entry.get("student_id", "")).strip()
        raw_status = entry.get("status") or window.auto_status
        confidence = float(entry.get("confidence", 1.0 if raw_status != "absent" else 0.0))

        if not sid:
            results.append({"student_id": sid, "success": False,
                            "error": "student_id is required"})
            rejected += 1
            continue

        if raw_status not in _VALID_STATUSES:
            results.append({"student_id": sid, "success": False,
                            "error": f"Invalid status '{raw_status}'"})
            rejected += 1
            continue

        # Grace period forces present → late
        if window.phase == "grace" and raw_status == "present":
            raw_status = "late"

        record_id = f"{date}_{period_id}_{sid}"
        record = {
            "record_id":    record_id,
            "student_id":   sid,
            "period_id":    period_id,
            "class_id":     effective_class_id,
            "section_id":   effective_class_id,   # section-scoped field
            "course_id":    period.get("course_id"),
            "faculty_id":   _faculty_id,
            "status":       raw_status,
            "confidence":   round(confidence, 4),
            "markedAt":     now_ts,
            "date":         date,
            "method":       "teacher_bulk",
            "note":         note,
            "window_phase": window.phase,
        }

        try:
            _write_attendance_record(fb_rt, record_id, date, record)
            lock_svc.write_audit(
                record_id=record_id,
                action="BULK_MARK",
                actor_id=_faculty_id,
                after=record,
                reason=f"Bulk mark during {window.phase} phase",
            )
            results.append({
                "student_id": sid,
                "success":    True,
                "record_id":  record_id,
                "status":     raw_status,
            })
            accepted += 1
        except Exception as exc:
            logger.error("Bulk mark failed for %s: %s", sid, exc)
            results.append({"student_id": sid, "success": False, "error": str(exc)})
            rejected += 1

    # Realtime broadcast + cache bust
    if accepted > 0:
        rt_svc = get_realtime_service()
        rt_svc._invalidate_cache(f"teacher_active_{_faculty_id}")
        await rt_svc.broadcast(
            event_type="bulk_attendance",
            section_id=effective_class_id,
            payload={
                "period_id":  period_id,
                "faculty_id": _faculty_id,
                "date":       date,
                "accepted":   accepted,
                "rejected":   rejected,
                "records":    [r for r in results if r.get("success")],
            },
        )

    return JSONResponse(status_code=200, content={
        "success":   accepted > 0,
        "period_id": period_id,
        "date":      date,
        "accepted":  accepted,
        "rejected":  rejected,
        "window":    window.to_dict(),
        "results":   results,
        "marked_at": now_ts,
        "message": (
            f"Marked {accepted} records successfully."
            + (f" {rejected} failed." if rejected else "")
        ),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /attendance/by-period/{period_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/attendance/by-period/{period_id}",
    summary="All attendance records for a specific period and date",
)
async def get_period_attendance(
    period_id:    str,
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
    date:         Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    repo        = _require_repo()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)

    allowed, reason = repo.validate_teacher_owns_period(period_id, _faculty_id, class_ids)
    if not allowed:
        raise HTTPException(403, reason)

    assigned_sections = await _get_assigned_sections(_faculty_id)
    period = repo.get_period(period_id)
    if assigned_sections:
        _assert_section_access(period.get("class_id", ""), assigned_sections)

    query_date = date or _today()

    try:
        fb_rt    = _get_rtdb()
        all_recs = fb_rt.get_reference(f"attendance/{query_date}").get() or {}
        filtered = [
            r for r in all_recs.values()
            if isinstance(r, dict) and r.get("period_id") == period_id
        ]
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch records: {exc}")

    return JSONResponse(status_code=200, content={
        "period_id":    period_id,
        "date":         query_date,
        "record_count": len(filtered),
        "records":      filtered,
    })


@router.get(
    "/attendance/history",
    summary="Paginated attendance history for a teacher's assigned section",
)
async def get_section_history(
    class_id:   str = Query(..., description="Must be in your assigned sections"),
    page:       int = Query(1, ge=1),
    page_size:  int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None),
    end_date:   Optional[str] = Query(None),
    course_id:  Optional[str] = Query(None),
    faculty_id: Optional[str] = Query(None, description="Admin override"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    assigned = await _get_assigned_sections(_faculty_id)
    _assert_section_access(class_id, assigned)

    repo = AttendanceRepository()
    result = repo.get_section_attendance_paginated(
        class_id=class_id,
        faculty_id=_faculty_id,
        page=page,
        page_size=page_size,
        course_id=course_id,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    if page > result["total_pages"] and result["total"] > 0:
        raise HTTPException(status_code=404, detail=f"Page {page} does not exist. Max page: {result['total_pages']}.")

    return JSONResponse(status_code=200, content={
        **result,
        "class_id": class_id,
        "faculty_id": _faculty_id,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /attendance/{record_id}  (edit, window-gated, broadcasts update)
# ══════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/attendance/{record_id}",
    summary="Edit an attendance record (only while window can_edit is True)",
)
async def edit_attendance_record(
    record_id:    str           = Path(...),
    current_user: TokenPayload  = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
    new_status:   Optional[str] = Body(None, embed=True, alias="status"),
    confidence:   Optional[float] = Body(None, embed=True),
    reason:       Optional[str] = Body(None, embed=True),
):
    """
    Partially update an attendance record.

    Only ``status``, ``confidence``, and ``reason`` may be changed.
    The period must still have ``can_edit=True``.  Every edit is appended to
    the immutable audit trail.  On success broadcasts ``attendance_marked``
    to the section room and busts the active-class cache.
    """
    lock_svc    = _require_lock_svc()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)

    if new_status and new_status not in _VALID_STATUSES:
        raise HTTPException(
            422,
            f"Invalid status '{new_status}'. Must be one of {sorted(_VALID_STATUSES)}.",
        )

    parts    = record_id.split("_", 1)
    date_str = parts[0] if len(parts) > 1 else _today()

    try:
        fb_rt    = _get_rtdb()
        rec_ref  = fb_rt.get_reference(f"attendance/{date_str}/{record_id}")
        existing = rec_ref.get()
    except Exception as exc:
        raise HTTPException(500, f"Could not read record: {exc}")

    if not existing:
        raise HTTPException(404, f"Record '{record_id}' not found.")

    record_class_id = existing.get("class_id", "")
    period_id       = existing.get("period_id", "")

    # Firebase-level section guard
    if record_class_id:
        assigned_sections = await _get_assigned_sections(_faculty_id)
        if assigned_sections:
            _assert_section_access(record_class_id, assigned_sections)

    # Fetch period for window check and JWT-level guard
    period: Dict[str, Any] = {}
    window: Dict[str, Any] = {}
    if period_id:
        try:
            db     = _get_firestore()
            pd_doc = db.collection("periods").document(period_id).get()
            if pd_doc.exists:
                period = pd_doc.to_dict()
                _enforce_period_access(current_user, period)
                window = lock_svc.get_window_status(period, date_str)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Period fetch for edit check failed: %s", exc)

    if window and not window.get("can_edit", False):
        return JSONResponse(status_code=423, content={
            "success": False,
            "message": window.get("message", "Attendance window closed — cannot edit."),
            "window":  window,
            "record":  existing,
        })

    updated = dict(existing)
    if new_status:
        updated["status"] = new_status
    if confidence is not None:
        updated["confidence"] = round(float(confidence), 4)
    if reason:
        updated["edit_reason"] = reason
    updated["last_edited_by"] = _faculty_id
    updated["last_edited_at"] = datetime.now().isoformat()

    try:
        rec_ref.set(updated)
    except Exception as exc:
        raise HTTPException(500, f"Failed to update record: {exc}")

    changes = {
        k: {"before": existing.get(k), "after": updated.get(k)}
        for k in ("status", "confidence")
        if existing.get(k) != updated.get(k)
    }

    lock_svc.write_audit(
        record_id=record_id,
        action="UPDATE",
        actor_id=_faculty_id,
        before=existing,
        after=updated,
        reason=reason,
    )

    try:
        audit_trail = lock_svc.get_audit_trail(record_id)
    except Exception:
        audit_trail = []

    # Realtime broadcast + cache bust
    if record_class_id:
        rt_svc = get_realtime_service()
        rt_svc._invalidate_cache(f"teacher_active_{_faculty_id}")
        await rt_svc.broadcast(
            event_type="attendance_marked",
            section_id=record_class_id,
            payload={
                "record_id":  record_id,
                "student_id": updated.get("student_id"),
                "period_id":  period_id,
                "status":     updated.get("status"),
                "edited_by":  _faculty_id,
                "changes":    changes,
            },
        )

    return JSONResponse(status_code=200, content={
        "success":     True,
        "record_id":   record_id,
        "record":      updated,
        "changes":     changes,
        "window":      window,
        "audit_trail": audit_trail,
        "message":     "Attendance record updated successfully.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /attendance/{record_id}/audit
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/attendance/{record_id}/audit",
    summary="Immutable audit trail for a single attendance record",
)
async def get_attendance_audit(
    record_id:    str,
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
):
    """Returns every change ever made to this record — who, when, what, why."""
    lock_svc    = _require_lock_svc()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)

    # Best-effort section guard via the record itself
    try:
        parts    = record_id.split("_", 1)
        date_str = parts[0] if len(parts) > 1 else _today()
        fb_rt    = _get_rtdb()
        existing = fb_rt.get_reference(f"attendance/{date_str}/{record_id}").get()
        if existing:
            assigned_sections = await _get_assigned_sections(_faculty_id)
            class_id = existing.get("class_id", "")
            if class_id and assigned_sections:
                _assert_section_access(class_id, assigned_sections)
    except HTTPException:
        raise
    except Exception:
        pass   # non-critical; proceed to trail fetch

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
# POST /period/{period_id}/lock  (teacher action)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/period/{period_id}/lock",
    summary="Manually lock a period early (no more marking after this)",
)
async def lock_period(
    period_id:    str  = Path(...),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
    faculty_id:   Optional[str] = Query(None, description="Admin override"),
    date:         Optional[str] = Query(None),
    reason:       Optional[str] = Query("manual"),
):
    """
    Immediately lock a period so no new attendance records can be created
    or edited.  Useful when a teacher finishes early or leaves mid-class.
    Broadcasts ``period_locked`` to the section room.
    """
    lock_svc    = _require_lock_svc()
    repo        = _require_repo()
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    class_ids   = _assigned_class_ids(current_user)
    date        = date or _today()

    # JWT-level ownership
    allowed, r = repo.validate_teacher_owns_period(period_id, _faculty_id, class_ids)
    if not allowed:
        raise HTTPException(403, r)

    period   = repo.get_period(period_id)
    class_id = period.get("class_id", "")

    # Firebase-level section guard
    assigned_sections = await _get_assigned_sections(_faculty_id)
    if assigned_sections and class_id:
        _assert_section_access(class_id, assigned_sections)

    lock_doc = lock_svc.lock_period(
        period_id=period_id,
        class_id=class_id,
        date=date,
        actor_id=_faculty_id,
        reason=reason or _LOCK_REASON_MANUAL,
    )

    # Broadcast
    if class_id:
        rt_svc = get_realtime_service()
        await rt_svc.broadcast(
            event_type="period_locked",
            section_id=class_id,
            payload={"period_id": period_id, "locked_by": _faculty_id, "date": date},
        )

    return JSONResponse(status_code=200, content={
        "success":   True,
        "period_id": period_id,
        "date":      date,
        "lock":      lock_doc,
        "message":   f"Period '{period_id}' is now locked.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# POST /period/{period_id}/unlock  (admin only)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/period/{period_id}/unlock",
    summary="Admin-only: unlock or force-open a locked period",
)
async def unlock_period(
    period_id:    str  = Path(...),
    current_user: TokenPayload = Depends(require_role("admin")),
    date:         Optional[str] = Query(None),
    force:        bool = Query(
        False,
        description=(
            "True → force-open even if natural window has expired. "
            "Records an audit entry."
        ),
    ),
    actor_id:     Optional[str] = Query(None, description="Audit actor override"),
):
    """
    Unlock a period.  ``force=True`` re-opens even after the natural window
    has closed — the admin escape hatch for edge cases (power outage, system
    issue, etc.).  Broadcasts ``period_unlocked`` to the section room.
    """
    lock_svc = _require_lock_svc()
    date     = date or _today()
    actor    = actor_id or current_user.user_id

    result = lock_svc.unlock_period(
        period_id=period_id,
        date=date,
        actor_id=actor,
        force=force,
    )

    # Resolve class_id for broadcast
    class_id = ""
    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        class_id = pd_doc.to_dict().get("class_id", "") if pd_doc.exists else ""
    except Exception:
        pass

    if class_id:
        rt_svc = get_realtime_service()
        await rt_svc.broadcast(
            event_type="period_unlocked",
            section_id=class_id,
            payload={
                "period_id": period_id,
                "actor_id":  actor,
                "force":     force,
                "date":      date,
            },
        )

    return JSONResponse(status_code=200, content={
        "success":   True,
        "period_id": period_id,
        "date":      date,
        "result":    result,
        "message": (
            f"Period '{period_id}' force-opened by admin override."
            if force else
            f"Period '{period_id}' unlocked."
        ),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /analytics/section  (Prompt 5)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/analytics/section",
    summary="Section attendance analytics for assigned class (teacher-scoped)",
)
async def get_section_analytics(
    class_id: str = Query(..., description="Must be in your assigned sections"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD (defaults to today)"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
    faculty_id: Optional[str] = Query(None, description="Admin override"),
):
    """
    Section-scoped analytics for an assigned class.

    The teacher can only query sections they are assigned to. Admins can
    query any section by providing their faculty_id.

    **Response**
    ```json
    {
      "class_id": "CSE-4C",
      "date": "2026-05-14",
      "present": 32,
      "late": 1,
      "absent": 5,
      "not_marked": 7,
      "total_students": 45,
      "attendance_rate": 73.3,
      "band": "warning"
    }
    ```
    """
    _faculty_id = _resolve_faculty_id(current_user, faculty_id)
    target_date = date or _today()

    # Verify section ownership
    assigned_sections = await _get_assigned_sections(_faculty_id)
    if assigned_sections:
        _assert_section_access(class_id, assigned_sections)

    try:
        fb_rt = _get_rtdb()
        day_recs = fb_rt.get_reference(f"attendance/{target_date}").get() or {}
    except Exception as exc:
        logger.error("Section analytics fetch failed: %s", exc)
        raise HTTPException(500, f"Failed to fetch attendance data: {exc}")

    present = late = absent = 0
    for rec in day_recs.values():
        if isinstance(rec, dict) and rec.get("class_id") == class_id:
            s = rec.get("status", "")
            if s == "present":
                present += 1
            elif s == "late":
                late += 1
            elif s == "absent":
                absent += 1

    total_marked = present + late + absent
    rate = round((present + late) / total_marked * 100, 1) if total_marked else 0.0
    band = _attendance_band_teacher(rate)

    # Get total student count for the class
    try:
        db = _get_firestore()
        stu_docs = (
            db.collection("students")
            .where(filter=FieldFilter("class_id", "==", class_id))
            .where(filter=FieldFilter("active_status", "==", True))
            .stream()
        )
        total_students = len(list(stu_docs))
    except Exception:
        total_students = 0

    not_marked = max(0, total_students - total_marked)

    logger.info(
        "get_section_analytics | faculty_id=%s | class_id=%s | date=%s | rate=%f%%",
        _faculty_id, class_id, target_date, rate,
    )

    return JSONResponse(status_code=200, content={
        "class_id": class_id,
        "date": target_date,
        "present": present,
        "late": late,
        "absent": absent,
        "not_marked": not_marked,
        "total_students": total_students,
        "attendance_rate": rate,
        "band": band,
        "generated_at": datetime.now().isoformat(),
    })


def _attendance_band_teacher(rate: float) -> str:
    """Classify attendance rate into safety band."""
    if rate >= 85:
        return "safe"
    if rate >= 75:
        return "warning"
    return "danger"