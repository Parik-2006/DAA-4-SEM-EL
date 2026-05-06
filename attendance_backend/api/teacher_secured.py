"""
teacher.py  (SECURITY-HARDENED)
─────────────────────────────────────────────────────────────────────────────
Changes vs original
--------------------
★ All endpoints require "teacher" or "admin" role (require_teacher dep).
★ faculty_id parameter is validated against the authenticated user's user_id
  (require_faculty_access) — a teacher cannot impersonate another teacher.
★ mark_bulk_attendance validates that the teacher is assigned to the period's
  section before writing any records.
★ Audit logging on bulk mark, edit, lock, and unlock operations.

All original endpoint signatures and behaviour are preserved.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from google.cloud.firestore_v1 import FieldFilter

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    DAY_OF_WEEK_MAP,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
    AttendanceStatus,
)

# ── Security ───────────────────────────────────────────────────────────────────
from decorators.auth_decorators import (
    get_current_user,
    require_teacher,
    require_faculty_access,
)
from services.audit_service import get_audit_service
from services.auth_service import UserContext
# ──────────────────────────────────────────────────────────────────────────────

from services.attendance_lock_service import get_lock_service
from services.period_detection_service import get_period_detection_service
from services.timetable_service import get_timetable_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])

_LOCK_REASON_MANUAL = "manual"
_VALID_STATUSES = {"present", "absent", "late", "excused"}


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers  (unchanged)
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
    from services.firebase_service import get_firebase_service
    svc = get_firebase_service()
    if svc is None:
        raise HTTPException(503, "FirebaseService not initialised")
    return svc


def _get_firestore():
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


def _attendance_status_for_student(student_id: str, today_records: Dict[str, Any]) -> Optional[str]:
    for rec in today_records.values():
        if isinstance(rec, dict) and rec.get("student_id") == student_id:
            return rec.get("status", "present")
    return None


def _build_period_summary(period, lock_svc, today_records, date):
    window  = lock_svc.get_window_status(period, date)
    present = sum(1 for r in today_records.values()
                  if isinstance(r, dict) and r.get("period_id") == period.get("period_id") and r.get("status") == "present")
    late    = sum(1 for r in today_records.values()
                  if isinstance(r, dict) and r.get("period_id") == period.get("period_id") and r.get("status") == "late")
    absent  = sum(1 for r in today_records.values()
                  if isinstance(r, dict) and r.get("period_id") == period.get("period_id") and r.get("status") == "absent")
    return {**period, "window": window,
            "attendance_counts": {"present": present, "late": late, "absent": absent,
                                  "total_marked": present + late + absent}}


# ══════════════════════════════════════════════════════════════════════════════
# GET /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", summary="Teacher dashboard — today's full schedule")
async def get_teacher_dashboard(
    faculty_id: str = Query(..., description="Faculty/teacher identifier"),
    date: Optional[str] = Query(None),
    auth_user: UserContext = require_teacher,           # ← SECURITY
    _faculty: None = require_faculty_access("faculty_id"),  # ← SECURITY: own ID only
):
    lock_svc      = _require_lock_svc()
    timetable_svc = _require_timetable_svc()
    date          = date or _today()
    today_dow     = datetime.strptime(date, "%Y-%m-%d").weekday()

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
        raise HTTPException(500, f"Could not fetch periods: {exc}")

    try:
        from database.firebase_client import FirebaseClient
        fb_rt         = FirebaseClient()
        today_records = fb_rt.get_reference(f"attendance/{date}").get() or {}
    except Exception as exc:
        logger.warning("Could not fetch today's attendance: %s", exc)
        today_records = {}

    detection_svc    = get_period_detection_service()
    current_period_id: Optional[str] = None
    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload and payload.get("primary_period"):
            current_period_id = payload["primary_period"].get("period_id")

    schedule = []
    active_period_summary = None
    for p in periods:
        summary = _build_period_summary(p, lock_svc, today_records, date)
        summary["is_current"] = (p.get("period_id") == current_period_id)
        schedule.append(summary)
        if summary["is_current"]:
            active_period_summary = summary

    for p in periods:
        try:
            lock_svc.auto_lock_if_expired(p, date)
        except Exception:
            pass

    return JSONResponse(status_code=200, content={
        "faculty_id": faculty_id, "date": date,
        "day": DAY_OF_WEEK_MAP.get(today_dow, "?"),
        "total_periods": len(schedule), "schedule": schedule,
        "active_period": active_period_summary,
        "generated_at": datetime.now().isoformat(),
        "config": {"attendance_window_minutes": ATTENDANCE_WINDOW_MINUTES,
                   "late_threshold_minutes": LATE_THRESHOLD_MINUTES},
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /active-class
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/active-class", summary="Currently active class with roster")
async def get_active_class(
    faculty_id: str = Query(...),
    auth_user: UserContext = require_teacher,           # ← SECURITY
    _faculty: None = require_faculty_access("faculty_id"),  # ← SECURITY
):
    lock_svc = _require_lock_svc()
    date     = _today()

    detection_svc  = get_period_detection_service()
    active_period: Optional[Dict[str, Any]] = None

    if detection_svc:
        payload = detection_svc.get_active_period()
        if payload:
            for p in payload.get("active_periods", []):
                if p.get("faculty_id") == faculty_id:
                    active_period = p
                    break

    if active_period is None:
        try:
            now     = datetime.now()
            now_str = now.strftime(TIME_FORMAT_HM)
            db      = _get_firestore()
            docs    = (
                db.collection("periods")
                .where(filter=FieldFilter("faculty_id", "==", faculty_id))
                .where(filter=FieldFilter("day_of_week", "==", now.weekday()))
                .where(filter=FieldFilter("active_status", "==", True))
                .where(filter=FieldFilter("start_time", "<=", now_str))
                .stream()
            )
            for c in [d.to_dict() for d in docs]:
                end_dt = _parse_hhmm(c["end_time"]) + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
                if now <= end_dt:
                    active_period = c
                    break
        except Exception as exc:
            logger.error("Active-class fallback failed: %s", exc)

    if active_period is None:
        return JSONResponse(status_code=404, content={
            "is_active": False,
            "message": "No active class period found for this teacher right now.",
            "faculty_id": faculty_id, "checked_at": datetime.now().isoformat(),
        })

    class_id  = active_period.get("class_id", "")
    period_id = active_period.get("period_id", "")
    window    = lock_svc.get_window_status(active_period, date)

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

    try:
        from database.firebase_client import FirebaseClient
        fb_rt         = FirebaseClient()
        today_records = fb_rt.get_reference(f"attendance/{date}").get() or {}
    except Exception:
        today_records = {}

    roster = [{
        "student_id":        stu.get("student_id", ""),
        "name":              stu.get("name", ""),
        "email":             stu.get("email", ""),
        "roll_number":       stu.get("roll_number") or stu.get("metadata", {}).get("roll_number"),
        "face_thumbnail":    stu.get("face_thumbnail_url") or stu.get("face_image_preview"),
        "attendance_status": _attendance_status_for_student(stu.get("student_id", ""), today_records),
        "is_marked":         _attendance_status_for_student(stu.get("student_id", ""), today_records) is not None,
    } for stu in students_raw]

    return JSONResponse(status_code=200, content={
        "is_active": True, "period": active_period, "window": window, "date": date,
        "class_id": class_id, "roster": roster,
        "summary": {
            "total_students": len(roster),
            "present":   sum(1 for s in roster if s["attendance_status"] == "present"),
            "late":      sum(1 for s in roster if s["attendance_status"] == "late"),
            "absent":    sum(1 for s in roster if s["attendance_status"] == "absent"),
            "not_marked": sum(1 for s in roster if not s["is_marked"]),
        },
        "checked_at": datetime.now().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# POST /mark-bulk
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/mark-bulk", summary="Bulk attendance marking (enforces window/lock + section auth)")
async def mark_bulk_attendance(
    request: Request,
    faculty_id: str = Query(...),
    body: Dict[str, Any] = Body(...),
    auth_user: UserContext = require_teacher,           # ← SECURITY
    _faculty: None = require_faculty_access("faculty_id"),  # ← SECURITY
):
    lock_svc = _require_lock_svc()

    period_id       = body.get("period_id", "")
    class_id        = body.get("class_id", "")
    date            = body.get("date") or _today()
    attendance_list = body.get("attendance_list", [])

    if not period_id:
        raise HTTPException(400, "period_id is required")
    if not attendance_list:
        raise HTTPException(400, "attendance_list must not be empty")

    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        if not pd_doc.exists:
            raise HTTPException(404, f"Period '{period_id}' not found")
        period = pd_doc.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Could not fetch period: {exc}")

    # ── Section authorization: teacher must be assigned to this section ────────
    period_section_id = period.get("section_id") or period.get("class_id", "")
    if not auth_user.is_admin() and not auth_user.can_access_section(period_section_id):
        get_audit_service().log_failed_access(
            user=auth_user, resource="period", resource_id=period_id,
            reason=f"Teacher not assigned to section '{period_section_id}'",
            request=request,
        )
        raise HTTPException(
            403,
            f"You are not assigned to the section for period '{period_id}'. "
            f"Your sections: {auth_user.assigned_sections}.",
        )

    window = lock_svc.get_window_status(period, date)
    if not window["is_open"]:
        return JSONResponse(status_code=423, content={
            "success": False, "message": window["message"], "window": window,
            "accepted": 0, "rejected": len(attendance_list), "results": [],
        })

    try:
        from database.firebase_client import FirebaseClient
        fb_rt    = FirebaseClient()
        base_ref = fb_rt.get_reference(f"attendance/{date}")
    except Exception as exc:
        raise HTTPException(500, f"Firebase not available: {exc}")

    now     = datetime.now()
    now_ts  = now.isoformat()
    results = []
    accepted = 0
    rejected = 0

    for item in attendance_list:
        stu_id     = item.get("student_id", "").strip()
        stu_status = item.get("status", "present").strip().lower()
        confidence = float(item.get("confidence", 0.0))

        if not stu_id:
            results.append({"student_id": stu_id, "success": False, "error": "student_id is required"})
            rejected += 1
            continue

        if stu_status not in _VALID_STATUSES:
            results.append({"student_id": stu_id, "success": False,
                            "error": f"Invalid status '{stu_status}'. Must be one of {sorted(_VALID_STATUSES)}"})
            rejected += 1
            continue

        if window["phase"] == "grace" and stu_status == "present":
            stu_status = "late"

        record_id = f"{date}_{period_id}_{stu_id}"
        record = {
            "record_id": record_id, "student_id": stu_id, "period_id": period_id,
            "class_id": class_id, "faculty_id": faculty_id, "status": stu_status,
            "confidence": round(confidence, 4), "markedAt": now_ts, "date": date,
            "method": "bulk_teacher",
        }

        try:
            base_ref.child(record_id).set(record)
            lock_svc.write_audit(
                record_id=record_id, action="BULK_MARK", actor_id=faculty_id, after=record,
                reason=f"Bulk mark by teacher during {window['phase']} phase",
            )
            results.append({"student_id": stu_id, "success": True,
                            "record_id": record_id, "status": stu_status})
            accepted += 1
        except Exception as exc:
            results.append({"student_id": stu_id, "success": False, "error": str(exc)})
            rejected += 1

    # ── Audit ──────────────────────────────────────────────────────────────────
    get_audit_service().log(
        action="BULK_MARK_ATTENDANCE", resource="attendance", user=auth_user,
        resource_id=period_id, request=request,
        details={"period_id": period_id, "date": date, "accepted": accepted,
                 "rejected": rejected, "class_id": class_id},
    )

    return JSONResponse(status_code=200, content={
        "success": accepted > 0, "period_id": period_id, "date": date,
        "accepted": accepted, "rejected": rejected, "window": window,
        "results": results, "marked_at": now_ts,
        "message": f"Marked {accepted} records successfully." + (f" {rejected} failed." if rejected else ""),
    })


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /attendance/{record_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.patch("/attendance/{record_id}", summary="Edit a single attendance record")
async def edit_attendance_record(
    request: Request,
    record_id: str = Path(...),
    faculty_id: str = Query(...),
    body: Dict[str, Any] = Body(...),
    auth_user: UserContext = require_teacher,           # ← SECURITY
    _faculty: None = require_faculty_access("faculty_id"),  # ← SECURITY
):
    lock_svc   = _require_lock_svc()
    new_status = body.get("status", "").strip().lower()
    confidence = body.get("confidence")
    reason     = body.get("reason")

    if new_status and new_status not in _VALID_STATUSES:
        raise HTTPException(422, f"Invalid status '{new_status}'. Must be one of {sorted(_VALID_STATUSES)}.")

    try:
        from database.firebase_client import FirebaseClient
        fb_rt    = FirebaseClient()
        parts    = record_id.split("_", 1)
        date_str = parts[0] if len(parts) > 1 else _today()
        rec_ref  = fb_rt.get_reference(f"attendance/{date_str}/{record_id}")
        existing = rec_ref.get()
    except Exception as exc:
        raise HTTPException(500, f"Could not read attendance record: {exc}")

    if not existing:
        raise HTTPException(404, f"Attendance record '{record_id}' not found.")

    # Validate that the teacher owns this section
    record_section = existing.get("section_id") or existing.get("class_id", "")
    if record_section and not auth_user.is_admin() and not auth_user.can_access_section(record_section):
        raise HTTPException(403, "You can only edit records for your assigned sections.")

    period_id = existing.get("period_id", "")
    if not period_id:
        raise HTTPException(422, "Record has no period_id; cannot check lock state.")

    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        period = pd_doc.to_dict() if pd_doc.exists else {}
    except Exception:
        period = {}

    window   = lock_svc.get_window_status(period, date_str) if period else {}
    can_edit = window.get("can_edit", False)

    if not can_edit:
        return JSONResponse(status_code=423, content={
            "success": False, "message": window.get("message", "Attendance window closed."),
            "window": window, "record": existing,
        })

    updated = dict(existing)
    if new_status:
        updated["status"] = new_status
    if confidence is not None:
        updated["confidence"] = round(float(confidence), 4)
    updated["last_edited_by"] = faculty_id
    updated["last_edited_at"] = datetime.now().isoformat()
    if reason:
        updated["edit_reason"] = reason

    rec_ref.set(updated)

    changes = {
        k: {"before": existing.get(k), "after": updated[k]}
        for k in ("status", "confidence") if existing.get(k) != updated.get(k)
    }
    lock_svc.write_audit(
        record_id=record_id, action="UPDATE", actor_id=faculty_id,
        before=existing, after=updated, reason=reason,
    )

    # ── Audit ──────────────────────────────────────────────────────────────────
    get_audit_service().log(
        action="EDIT_ATTENDANCE", resource="attendance", resource_id=record_id,
        user=auth_user, request=request, before=existing, after=updated,
        details={"changes": changes, "reason": reason},
    )

    try:
        audit_trail = lock_svc.get_audit_trail(record_id)
    except Exception:
        audit_trail = []

    return JSONResponse(status_code=200, content={
        "success": True, "record_id": record_id, "record": updated,
        "changes": changes, "window": window, "audit_trail": audit_trail,
        "message": "Attendance record updated successfully.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /attendance/{record_id}/audit  (unchanged — no auth change needed beyond teacher)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance/{record_id}/audit", summary="Full audit trail for an attendance record")
async def get_attendance_audit(
    record_id: str = Path(...),
    auth_user: UserContext = require_teacher,           # ← SECURITY
):
    lock_svc = _require_lock_svc()
    try:
        trail = lock_svc.get_audit_trail(record_id)
    except Exception as exc:
        raise HTTPException(500, f"Could not retrieve audit trail: {exc}")

    return JSONResponse(status_code=200, content={
        "record_id": record_id, "entry_count": len(trail), "audit_trail": trail,
    })


# ══════════════════════════════════════════════════════════════════════════════
# Lock / Unlock
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/period/{period_id}/lock", summary="Manually lock a period")
async def lock_period(
    request: Request,
    period_id: str = Path(...),
    faculty_id: str = Query(...),
    date: Optional[str] = Query(None),
    reason: Optional[str] = Query("manual"),
    auth_user: UserContext = require_teacher,           # ← SECURITY
    _faculty: None = require_faculty_access("faculty_id"),  # ← SECURITY
):
    lock_svc = _require_lock_svc()
    date     = date or _today()
    try:
        db     = _get_firestore()
        pd_doc = db.collection("periods").document(period_id).get()
        class_id = pd_doc.to_dict().get("class_id", "") if pd_doc.exists else ""
    except Exception:
        class_id = ""

    lock_doc = lock_svc.lock_period(
        period_id=period_id, class_id=class_id, date=date,
        actor_id=faculty_id, reason=reason or _LOCK_REASON_MANUAL,
    )

    get_audit_service().log(
        action="LOCK_PERIOD", resource="period", resource_id=period_id,
        user=auth_user, request=request, details={"date": date, "reason": reason},
    )

    return JSONResponse(status_code=200, content={
        "success": True, "period_id": period_id, "date": date, "lock": lock_doc,
        "message": f"Period '{period_id}' is now locked.",
    })


@router.post("/period/{period_id}/unlock", summary="Admin-only: force-unlock a locked period")
async def unlock_period(
    request: Request,
    period_id: str = Path(...),
    actor_id: str = Query("admin"),
    date: Optional[str] = Query(None),
    force: bool = Query(False),
    auth_user: UserContext = require_teacher,           # ← SECURITY (admin handled by route rules)
):
    # Unlock / force-unlock is admin-only in practice (PermissionMiddleware
    # allows teacher role here, but force=True should be admin; add explicit check)
    if force and not auth_user.is_admin():
        raise HTTPException(403, "Force-unlock requires admin role.")

    lock_svc = _require_lock_svc()
    date     = date or _today()

    result = lock_svc.unlock_period(period_id=period_id, date=date, actor_id=actor_id, force=force)

    get_audit_service().log(
        action="UNLOCK_PERIOD", resource="period", resource_id=period_id,
        user=auth_user, request=request,
        details={"date": date, "force": force, "actor_id": actor_id},
    )

    return JSONResponse(status_code=200, content={
        "success": True, "period_id": period_id, "date": date, "result": result,
        "message": (f"Period '{period_id}' force-opened by admin." if force
                    else f"Period '{period_id}' unlocked."),
    })