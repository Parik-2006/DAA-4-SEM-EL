"""
api/teacher.py
─────────────────────────────────────────────────────────────────────────────
Teacher-facing REST endpoints.

All routes sit under /api/v1/teacher and are designed for the teacher
dashboard UI.  Authentication is assumed to happen at the gateway/middleware
layer; endpoints receive ``faculty_id`` either from a JWT sub-claim or as a
query parameter during development.

Endpoints
---------
GET  /api/v1/teacher/dashboard
    Today's full schedule for a teacher with live period status, attendance
    counts, and window open/closed/locked state per period.

GET  /api/v1/teacher/active-class
    The currently active period for this teacher, including the full student
    roster annotated with today's attendance status and face thumbnail URLs.

POST /api/v1/teacher/mark-bulk
    Bulk attendance marking for a period.  Enforces window / lock rules.
    Body: { period_id, date?, attendance_list: [{student_id, status, confidence}] }

PATCH /api/v1/teacher/attendance/{record_id}
    Edit a single attendance record before the lock timestamp.
    Returns the updated record with its full audit trail.

GET  /api/v1/teacher/attendance/{record_id}/audit
    Full immutable audit trail for a specific attendance record.

POST /api/v1/teacher/period/{period_id}/lock
    Manually lock a period early (teacher action).

POST /api/v1/teacher/period/{period_id}/unlock
    Admin-only force-unlock of a locked period.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from google.cloud.firestore_v1 import FieldFilter

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    DAY_OF_WEEK_MAP,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
    AttendanceStatus,
)
from services.attendance_lock_service import get_lock_service
from services.period_detection_service import get_period_detection_service
from services.timetable_service import get_timetable_service
from middleware.auth_middleware import require_role
from services.auth_service import TokenPayload
from utils.time_validator import get_period_runtime_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])

# ── Constants ──────────────────────────────────────────────────────────────────
_LOCK_REASON_MANUAL = "manual"
_VALID_STATUSES = {"present", "absent", "late", "excused"}


# ══════════════════════════════════════════════════════════════════════════════
# Dependency / shared helpers
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


def _get_firebase():
    """Return the FirebaseService singleton (lazy import to avoid circular deps)."""
    from services.firebase_service import get_firebase_service
    svc = get_firebase_service()
    if svc is None:
        raise HTTPException(503, "FirebaseService not initialised")
    return svc


def _get_firestore():
    """Return raw Firestore client from the Firebase service."""
    fb = _get_firebase()
    db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
    if db is None:
        raise HTTPException(503, "Firestore client not available")
    return db


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_hhmm(t: str, date: Optional[str] = None) -> datetime:
    d = date or _today()
    return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")


def _attendance_status_for_student(
    student_id: str,
    today_records: Dict[str, Any],
) -> Optional[str]:
    """Scan today_records (keyed by record_id) for this student."""
    for rec in today_records.values():
        if isinstance(rec, dict) and rec.get("student_id") == student_id:
            return rec.get("status", "present")
    return None


def _resolve_faculty_id(
    current_user: TokenPayload,
    requested_faculty_id: Optional[str],
) -> str:
    """
    Resolve teacher identity from JWT while preserving admin override support.

    Teachers always operate as themselves. Admins may pass ``faculty_id``
    to inspect/operate on behalf of a teacher.
    """
    if current_user.role == "admin":
        if not requested_faculty_id:
            raise HTTPException(400, "faculty_id is required for admin requests")
        return requested_faculty_id

    if current_user.role != "teacher":
        raise HTTPException(403, "Only teachers/admins can access this endpoint")

    if requested_faculty_id and requested_faculty_id != current_user.user_id:
        raise HTTPException(403, "Teachers can only access their own faculty_id")

    return current_user.user_id


def _enforce_period_access(
    current_user: TokenPayload,
    period: Dict[str, Any],
) -> None:
    """Restrict teachers to assigned sections and their own periods."""
    if current_user.role == "admin":
        return

    period_faculty = str(period.get("faculty_id") or "").strip()
    class_id = str(period.get("class_id") or "").strip()

    if period_faculty and period_faculty != current_user.user_id:
        raise HTTPException(403, "You are not assigned to this period")

    # If section assignments are present in JWT, enforce them strictly.
    if current_user.assigned_sections and class_id not in current_user.assigned_sections:
        raise HTTPException(403, "You are not assigned to this section")


def _build_period_summary(
    period: Dict[str, Any],
    lock_svc,
    today_records: Dict[str, Any],
    date: str,
) -> Dict[str, Any]:
    """
    Annotate a period dict with window status and today's attendance counts.
    """
    window = lock_svc.get_window_status(period, date)

    present = sum(
        1 for r in today_records.values()
        if isinstance(r, dict)
        and r.get("period_id") == period.get("period_id")
        and r.get("status") == "present"
    )
    late = sum(
        1 for r in today_records.values()
        if isinstance(r, dict)
        and r.get("period_id") == period.get("period_id")
        and r.get("status") == "late"
    )
    absent = sum(
        1 for r in today_records.values()
        if isinstance(r, dict)
        and r.get("period_id") == period.get("period_id")
        and r.get("status") == "absent"
    )

    return {
        **period,
        "window": window,
        "attendance_counts": {
            "present": present,
            "late":    late,
            "absent":  absent,
            "total_marked": present + late + absent,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/dashboard",
    summary="Teacher dashboard — today's full schedule with attendance status",
)
async def get_teacher_dashboard(
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Returns the teacher's full schedule for the requested date.

    Each period entry includes:
    - Full period details (course, time, room)
    - ``window`` : open/grace/locked status with human-readable message
    - ``attendance_counts`` : present / late / absent counts
    - ``is_current`` : True for the period active right now

    The currently active period (if any) is also returned under
    ``active_period`` for quick access.
    """
    lock_svc      = _require_lock_svc()
    timetable_svc = _require_timetable_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)

    date = date or _today()
    today_dow = datetime.strptime(date, "%Y-%m-%d").weekday()

    # Fetch all periods for this faculty
    try:
        db = _get_firestore()
        period_docs = (
            db.collection("periods")
            .where(filter=FieldFilter("faculty_id", "==", faculty_id))
            .where(filter=FieldFilter("day_of_week", "==", today_dow))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("start_time")
            .stream()
        )
        periods = [d.to_dict() for d in period_docs]
    except Exception as exc:
        logger.error("Dashboard period fetch failed: %s", exc)
        raise HTTPException(500, f"Could not fetch periods: {exc}")

    # Fetch today's attendance from Realtime DB
    try:
        from database.firebase_client import FirebaseClient
        fb_rt   = FirebaseClient()
        rt_ref  = fb_rt.get_reference(f"attendance/{date}")
        today_records: Dict[str, Any] = rt_ref.get() or {}
    except Exception as exc:
        logger.warning("Could not fetch today's attendance: %s", exc)
        today_records = {}

    # Identify current period from detection service
    detection_svc = get_period_detection_service()
    current_period_id: Optional[str] = None
    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload and payload.get("primary_period"):
            current_period_id = payload["primary_period"].get("period_id")

    # Build annotated schedule
    schedule = []
    active_period_summary = None

    for p in periods:
        summary = _build_period_summary(p, lock_svc, today_records, date)
        summary["is_current"] = (p.get("period_id") == current_period_id)
        schedule.append(summary)
        if summary["is_current"]:
            active_period_summary = summary

    # Auto-lock expired periods (fire-and-forget; don't block response)
    for p in periods:
        try:
            lock_svc.auto_lock_if_expired(p, date)
        except Exception:
            pass

    return JSONResponse(status_code=200, content={
        "faculty_id":    faculty_id,
        "date":          date,
        "day":           DAY_OF_WEEK_MAP.get(today_dow, "?"),
        "total_periods": len(schedule),
        "schedule":      schedule,
        "active_period": active_period_summary,
        "generated_at":  datetime.now().isoformat(),
        "config": {
            "attendance_window_minutes": ATTENDANCE_WINDOW_MINUTES,
            "late_threshold_minutes":   LATE_THRESHOLD_MINUTES,
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /active-class
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/active-class",
    summary="Currently active class with full student roster and attendance state",
)
async def get_active_class(
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Returns the period currently running for this teacher together with:
    - Full student roster for the class
    - Per-student attendance status for today (present / absent / not_marked)
    - Face thumbnail URL or base64 snippet from Firebase
    - Live window status (open / grace / locked)

    Returns 404 if the teacher has no active period right now.
    """
    lock_svc = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    date     = _today()

    # Find active period for this faculty
    detection_svc = get_period_detection_service()
    active_period: Optional[Dict[str, Any]] = None

    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload:
            for p in payload.get("active_periods", []):
                if p.get("faculty_id") == faculty_id:
                    active_period = p
                    break

    # Fallback: query Firestore directly for current time
    if active_period is None:
        try:
            now = datetime.now()
            now_str = now.strftime(TIME_FORMAT_HM)
            db = _get_firestore()
            docs = (
                db.collection("periods")
                .where(filter=FieldFilter("faculty_id", "==", faculty_id))
                .where(filter=FieldFilter("day_of_week", "==", now.weekday()))
                .where(filter=FieldFilter("active_status", "==", True))
                .where(filter=FieldFilter("start_time", "<=", now_str))
                .stream()
            )
            candidates = [d.to_dict() for d in docs]
            # Filter end_time >= now
            for c in candidates:
                end_dt = _parse_hhmm(c["end_time"]) + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
                if now <= end_dt:
                    active_period = c
                    break
        except Exception as exc:
            logger.error("Active-class fallback query failed: %s", exc)

    if active_period is None:
        return JSONResponse(status_code=404, content={
            "is_active":  False,
            "message":    "No active class period found for this teacher right now.",
            "faculty_id": faculty_id,
            "checked_at": datetime.now().isoformat(),
        })

    _enforce_period_access(current_user, active_period)

    class_id   = active_period.get("class_id", "")
    period_id  = active_period.get("period_id", "")

    # Window status
    window = lock_svc.get_window_status(active_period, date)

    # Fetch student roster
    try:
        db       = _get_firestore()
        stu_docs = (
            db.collection("students")
            .where(filter=FieldFilter("class_id", "==", class_id))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("name")
            .stream()
        )
        students_raw = [d.to_dict() for d in stu_docs]
    except Exception as exc:
        logger.error("Student roster fetch failed: %s", exc)
        students_raw = []

    # Today's attendance for this period
    try:
        from database.firebase_client import FirebaseClient
        fb_rt = FirebaseClient()
        rt_ref = fb_rt.get_reference(f"attendance/{date}")
        today_records: Dict[str, Any] = rt_ref.get() or {}
    except Exception:
        today_records = {}

    # Build annotated roster
    roster = []
    for stu in students_raw:
        stu_id = stu.get("student_id", "")
        att_status = _attendance_status_for_student(stu_id, today_records)
        roster.append({
            "student_id":       stu_id,
            "name":             stu.get("name", ""),
            "email":            stu.get("email", ""),
            "roll_number":      stu.get("roll_number") or stu.get("metadata", {}).get("roll_number"),
            "face_thumbnail":   stu.get("face_thumbnail_url") or stu.get("face_image_preview"),
            "attendance_status": att_status,        # None = not yet marked
            "is_marked":        att_status is not None,
        })

    not_marked   = sum(1 for s in roster if not s["is_marked"])
    present_count = sum(1 for s in roster if s["attendance_status"] == "present")
    late_count    = sum(1 for s in roster if s["attendance_status"] == "late")
    absent_count  = sum(1 for s in roster if s["attendance_status"] == "absent")

    return JSONResponse(status_code=200, content={
        "is_active":   True,
        "period":      active_period,
        "window":      window,
        "date":        date,
        "class_id":    class_id,
        "roster":      roster,
        "summary": {
            "total_students": len(roster),
            "present":        present_count,
            "late":           late_count,
            "absent":         absent_count,
            "not_marked":     not_marked,
        },
        "checked_at": datetime.now().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# POST /mark-bulk
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/mark-bulk",
    summary="Bulk attendance marking for a period (enforces window/lock rules)",
    status_code=status.HTTP_200_OK,
)
async def mark_bulk_attendance(
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    body: Dict[str, Any] = Body(
        ...,
        examples={
            "default": {
                "summary": "Bulk mark attendance",
                "value": {
                    "period_id": "CS-A-SEM6_MON_0900",
                    "class_id":  "CS-A-SEM6",
                    "date":      "2026-04-30",
                    "attendance_list": [
                        {"student_id": "STU001", "status": "present", "confidence": 1.0},
                        {"student_id": "STU002", "status": "absent",  "confidence": 0.0},
                        {"student_id": "STU003", "status": "late",    "confidence": 0.85},
                    ],
                },
            }
        },
    ),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Mark attendance for multiple students in a single request.

    Rules enforced
    --------------
    * The period window must be open (or in grace period).
    * Individual records with invalid ``status`` values are rejected per-row;
      the rest are committed.
    * Each written record gets an audit entry with ``action="BULK_MARK"``.
    * Returns a per-student result list so the frontend can show which
      records succeeded and which failed.
    """
    lock_svc = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)

    period_id       = body.get("period_id", "")
    class_id        = body.get("class_id", "")
    date            = body.get("date") or _today()
    attendance_list = body.get("attendance_list", [])

    if not period_id:
        raise HTTPException(400, "period_id is required")
    if not attendance_list:
        raise HTTPException(400, "attendance_list must not be empty")

    # Fetch period to check window
    try:
        db       = _get_firestore()
        pd_doc   = db.collection("periods").document(period_id).get()
        if not pd_doc.exists:
            raise HTTPException(404, f"Period '{period_id}' not found")
        period = pd_doc.to_dict()
        _enforce_period_access(current_user, period)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Could not fetch period: {exc}")

    period_class_id = period.get("class_id", "")
    if class_id and period_class_id and class_id != period_class_id:
        raise HTTPException(422, "class_id does not match period class_id")
    if not class_id:
        class_id = period_class_id

    # Enforce window
    window = lock_svc.get_window_status(period, date)
    if not window["is_open"]:
        return JSONResponse(status_code=423, content={
            "success":  False,
            "message":  window["message"],
            "window":   window,
            "accepted": 0,
            "rejected": len(attendance_list),
            "results":  [],
        })

    # Fetch Firebase service for writing records
    try:
        from database.firebase_client import FirebaseClient
        fb_rt = FirebaseClient()
        base_ref = fb_rt.get_reference(f"attendance/{date}")
    except Exception as exc:
        raise HTTPException(500, f"Firebase not available: {exc}")

    now        = datetime.now()
    now_ts     = now.isoformat()
    results    = []
    accepted   = 0
    rejected   = 0

    for item in attendance_list:
        stu_id  = item.get("student_id", "").strip()
        stu_status = item.get("status", "present").strip().lower()
        confidence = float(item.get("confidence", 0.0))

        # Validate
        if not stu_id:
            results.append({"student_id": stu_id, "success": False,
                            "error": "student_id is required"})
            rejected += 1
            continue

        if stu_status not in _VALID_STATUSES:
            results.append({"student_id": stu_id, "success": False,
                            "error": f"Invalid status '{stu_status}'. "
                                     f"Must be one of {sorted(_VALID_STATUSES)}"})
            rejected += 1
            continue

        # Late detection: if in grace period, override to 'late' unless already absent/excused
        if window["phase"] == "grace" and stu_status == "present":
            stu_status = "late"

        record_id = f"{date}_{period_id}_{stu_id}"
        record = {
            "record_id":   record_id,
            "student_id":  stu_id,
            "period_id":   period_id,
            "class_id":    class_id,
            "faculty_id":  faculty_id,
            "status":      stu_status,
            "confidence":  round(confidence, 4),
            "markedAt":    now_ts,
            "date":        date,
            "method":      "bulk_teacher",
        }

        try:
            base_ref.child(record_id).set(record)
            # Write audit
            lock_svc.write_audit(
                record_id=record_id,
                action="BULK_MARK",
                actor_id=faculty_id,
                after=record,
                before=None,
                reason=f"Bulk mark by teacher during {window['phase']} phase",
            )
            results.append({"student_id": stu_id, "success": True,
                            "record_id": record_id, "status": stu_status})
            accepted += 1

        except Exception as exc:
            logger.error("Bulk mark failed for %s: %s", stu_id, exc)
            results.append({"student_id": stu_id, "success": False,
                            "error": str(exc)})
            rejected += 1

    return JSONResponse(status_code=200, content={
        "success":   accepted > 0,
        "period_id": period_id,
        "date":      date,
        "accepted":  accepted,
        "rejected":  rejected,
        "window":    window,
        "results":   results,
        "marked_at": now_ts,
        "message": (
            f"Marked {accepted} records successfully. "
            + (f"{rejected} failed." if rejected else "")
        ),
    })


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /attendance/{record_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/attendance/{record_id}",
    summary="Edit a single attendance record (only before period lock)",
)
async def edit_attendance_record(
    record_id: str = Path(..., description="Attendance record ID"),
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    body: Dict[str, Any] = Body(
        ...,
        examples={
            "default": {
                "summary": "Edit attendance",
                "value": {
                    "status":     "excused",
                    "confidence": 0.0,
                    "reason":     "Medical certificate submitted",
                },
            }
        },
    ),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Edit a single attendance record.

    Rules
    -----
    * The period the record belongs to must not be locked.
    * Only ``status``, ``confidence``, and ``reason`` fields may be changed.
    * The ``status`` value must be one of: present, absent, late, excused.
    * Every edit is written to the immutable audit trail.

    Returns the updated record with its full audit trail appended.
    """
    lock_svc = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)

    new_status  = body.get("status", "").strip().lower()
    confidence  = body.get("confidence")
    reason      = body.get("reason")

    if new_status and new_status not in _VALID_STATUSES:
        raise HTTPException(
            422,
            f"Invalid status '{new_status}'. Must be one of {sorted(_VALID_STATUSES)}.",
        )

    # Fetch existing record
    try:
        from database.firebase_client import FirebaseClient
        fb_rt    = FirebaseClient()
        # record_id convention: YYYY-MM-DD_{period_id}_{student_id}
        parts    = record_id.split("_", 1)
        date_str = parts[0] if len(parts) > 1 else _today()
        rec_ref  = fb_rt.get_reference(f"attendance/{date_str}/{record_id}")
        existing = rec_ref.get()
    except Exception as exc:
        raise HTTPException(500, f"Could not read attendance record: {exc}")

    if not existing:
        raise HTTPException(404, f"Attendance record '{record_id}' not found.")

    # Determine period_id from record
    period_id = existing.get("period_id", "")
    if not period_id:
        raise HTTPException(422, "Record has no period_id; cannot check lock state.")

    # Fetch period to check window
    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        period = pd_doc.to_dict() if pd_doc.exists else {}
        if period:
            _enforce_period_access(current_user, period)
    except Exception as exc:
        period = {}

    # Enforce window for editing
    window = lock_svc.get_window_status(period, date_str) if period else {}
    can_edit = window.get("can_edit", False)

    if not can_edit:
        msg = window.get("message", "Attendance window closed — cannot edit.")
        return JSONResponse(status_code=423, content={
            "success": False,
            "message": msg,
            "window":  window,
            "record":  existing,
        })

    # Apply changes
    updated = dict(existing)
    if new_status:
        updated["status"] = new_status
    if confidence is not None:
        updated["confidence"] = round(float(confidence), 4)

    updated["last_edited_by"] = faculty_id
    updated["last_edited_at"] = datetime.now().isoformat()
    if reason:
        updated["edit_reason"] = reason

    try:
        rec_ref.set(updated)
    except Exception as exc:
        raise HTTPException(500, f"Failed to update record: {exc}")

    # Audit
    changes = {
        k: {"before": existing.get(k), "after": updated[k]}
        for k in ("status", "confidence")
        if existing.get(k) != updated.get(k)
    }
    lock_svc.write_audit(
        record_id=record_id,
        action="UPDATE",
        actor_id=faculty_id,
        before=existing,
        after=updated,
        reason=reason,
    )

    # Fetch audit trail
    try:
        audit_trail = lock_svc.get_audit_trail(record_id)
    except Exception:
        audit_trail = []

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
    summary="Full audit trail for an attendance record",
)
async def get_attendance_audit(
    record_id: str = Path(..., description="Attendance record ID"),
):
    """
    Returns the complete, immutable audit history for a record:
    who marked it, when, what was changed, and why.
    """
    lock_svc = _require_lock_svc()

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
# POST /period/{period_id}/lock  and  /unlock
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/period/{period_id}/lock",
    summary="Manually lock a period to prevent further attendance marking",
)
async def lock_period(
    period_id: str = Path(...),
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    date: Optional[str] = Query(None),
    reason: Optional[str] = Query("manual", description="Reason for early lock"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """
    Immediately lock a period.

    After locking:
    * No new attendance records can be created for this period.
    * Existing records cannot be edited.
    * The lock is visible to students on the attendance confirmation screen.
    """
    lock_svc = _require_lock_svc()
    faculty_id = _resolve_faculty_id(current_user, faculty_id)
    date = date or _today()

    # Fetch class_id for the period
    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        period = pd_doc.to_dict() if pd_doc.exists else {}
        if period:
            _enforce_period_access(current_user, period)
        class_id = period.get("class_id", "")
    except Exception:
        class_id = ""

    lock_doc = lock_svc.lock_period(
        period_id=period_id,
        class_id=class_id,
        date=date,
        actor_id=faculty_id,
        reason=reason or _LOCK_REASON_MANUAL,
    )

    return JSONResponse(status_code=200, content={
        "success":   True,
        "period_id": period_id,
        "date":      date,
        "lock":      lock_doc,
        "message":   f"Period '{period_id}' is now locked. No further attendance changes allowed.",
    })


@router.post(
    "/period/{period_id}/unlock",
    summary="Admin-only: force-unlock a locked period",
)
async def unlock_period(
    period_id: str = Path(...),
    actor_id: Optional[str] = Query(None, description="Optional audit actor override"),
    date: Optional[str] = Query(None),
    force: bool = Query(
        False,
        description=(
            "If True, opens the period even if its natural window has expired. "
            "Use with caution — creates an audit record."
        ),
    ),
    current_user: TokenPayload = Depends(require_role("admin")),
):
    """
    Unlock or force-open a period.

    ``force=True`` overrides the natural attendance window and allows marking
    even after the grace period has expired.  This action is recorded in the
    lock document and flagged in all subsequent audit entries.
    """
    lock_svc = _require_lock_svc()
    date = date or _today()
    actor = actor_id or current_user.user_id

    result = lock_svc.unlock_period(
        period_id=period_id,
        date=date,
        actor_id=actor,
        force=force,
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
# GET /available-periods
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/available-periods",
    summary="Periods available right now for the logged-in teacher",
)
async def get_available_periods(
    faculty_id: Optional[str] = Query(None, description="Admin-only teacher override"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
    current_user: TokenPayload = Depends(require_role("teacher", "admin")),
):
    """Return current teacher periods with real-time status and markability."""
    lock_svc = _require_lock_svc()
    faculty = _resolve_faculty_id(current_user, faculty_id)
    date = date or _today()
    dow = datetime.strptime(date, "%Y-%m-%d").weekday()

    try:
        db = _get_firestore()
        docs = (
            db.collection("periods")
            .where(filter=FieldFilter("faculty_id", "==", faculty))
            .where(filter=FieldFilter("day_of_week", "==", dow))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("start_time")
            .stream()
        )
        periods = [d.to_dict() for d in docs]
    except Exception as exc:
        raise HTTPException(500, f"Could not fetch periods: {exc}")

    available: List[Dict[str, Any]] = []
    for p in periods:
        _enforce_period_access(current_user, p)
        window = lock_svc.get_window_status(p, date)
        runtime_status = get_period_runtime_status(
            p.get("start_time", "00:00"),
            p.get("end_time", "00:00"),
        )
        item = {
            **p,
            "runtime_status": runtime_status,
            "window": window,
            "is_available_for_marking": bool(window.get("is_open")),
        }
        if item["is_available_for_marking"]:
            available.append(item)

    return JSONResponse(
        status_code=200,
        content={
            "faculty_id": faculty,
            "date": date,
            "available_count": len(available),
            "available_periods": available,
            "generated_at": datetime.now().isoformat(),
        },
    )
