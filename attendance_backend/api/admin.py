"""
api/admin.py  –  Production admin API router
═════════════════════════════════════════════════════════════════════════════
Auth
----
Every endpoint requires a valid JWT access token whose role == "admin".
The ``Depends(require_role("admin"))`` guard replaces the previous
``X-Admin-Token`` header approach, giving us full JWT-based RBAC.

Endpoints
---------
Core data (preserved from v1):
  GET  /api/v1/admin/students
  GET  /api/v1/admin/attendance/today
  GET  /api/v1/admin/attendance
  POST /api/v1/admin/register-student-face

Analytics (new from v2):
  GET  /api/v1/admin/analytics/overview
  GET  /api/v1/admin/analytics/sections
  GET  /api/v1/admin/analytics/trends

User management (new – pairs with auth system):
  GET    /api/v1/admin/users
  PATCH  /api/v1/admin/users/{user_id}
  DELETE /api/v1/admin/users/{user_id}
  GET    /api/v1/admin/roles

CIE Management (from v1 + v2):
  POST   /api/v1/admin/cie
  GET    /api/v1/admin/cies
  PUT    /api/v1/admin/cie/{cie_id}
  DELETE /api/v1/admin/cie/{cie_id}

Class Management (from v1 + v2):
  POST /api/v1/admin/class
  GET  /api/v1/admin/classes
  PUT  /api/v1/admin/class/{class_id}

Bulk Import (from v1 + v2):
  POST /api/v1/admin/timetable/bulk-import
  POST /api/v1/admin/students/bulk-import

Reporting (from v1 + v2):
  GET /api/v1/admin/reports/cie/{cie_id}/summary
  GET /api/v1/admin/reports/class/{class_id}/attendance

System Config (from v1 + v2):
  POST /api/v1/admin/config
"""

from __future__ import annotations

import base64
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from database.firebase_client import FirebaseClient
from database.student_repository import StudentRepository
from database.user_repository import UserRepository
from middleware.auth_middleware import require_role, TokenPayload
from services.admin_service import AdminService
from services.auth_service import ROLE_PERMISSIONS
from utils.csv_parser import parse_roster_csv, parse_timetable_csv

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# ── Shared singletons ─────────────────────────────────────────────────────────
user_repo = UserRepository()
student_repo = StudentRepository()

# ── JWT guard: every route requires role == "admin" ───────────────────────────
_admin = Depends(require_role("admin"))


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class CIECreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    academic_year: str = Field(..., description="e.g. '2024-25'")
    department: Optional[str] = None


class CIEUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    academic_year: Optional[str] = None
    department: Optional[str] = None


class ClassCreateSchema(BaseModel):
    cie_id: str
    name: str = Field(..., min_length=1, description="e.g. 'CS301-A'")
    course_code: str
    course_name: str
    semester: str = Field(..., description="e.g. '5'")
    section: str = Field(..., description="e.g. 'A'")
    faculty_id: Optional[str] = None
    student_ids: Optional[List[str]] = []


class ClassUpdateSchema(BaseModel):
    name: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    semester: Optional[str] = None
    section: Optional[str] = None
    faculty_id: Optional[str] = None
    student_ids: Optional[List[str]] = None


class SystemConfigSchema(BaseModel):
    attendance_window_minutes: Optional[int] = Field(None, ge=1, le=120)
    late_threshold_minutes: Optional[int] = Field(None, ge=1, le=60)
    low_attendance_warning_threshold: Optional[float] = Field(None, ge=1.0, le=100.0)


class UserPatchSchema(BaseModel):
    """Admin can update role, active status, and section assignments."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    assigned_sections: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fb() -> FirebaseClient:
    return FirebaseClient()


def _svc() -> AdminService:
    return AdminService(_fb())


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _new_id() -> str:
    return str(uuid.uuid4())


def _strip_sensitive(user: dict) -> dict:
    """Remove fields that must never leave the server."""
    return {k: v for k, v in user.items() if k not in ("password_hash", "reset_token", "reset_expires")}


# ═════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT  (new — pairs with the JWT auth system)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_all_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: TokenPayload = _admin,
):
    """List all users with optional filters. Sensitive fields are stripped."""
    users = user_repo.search_users(
        role=role,
        is_active=is_active,
    )
    users = [_strip_sensitive(u) for u in users]
    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
    start = (page - 1) * limit
    return {
        "data": users[start: start + limit],
        "total": len(users),
        "page": page,
        "limit": limit,
        "total_pages": max(1, (len(users) + limit - 1) // limit),
    }


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: str,
    payload: UserPatchSchema,
    _: TokenPayload = _admin,
):
    """
    Update a user's role, active status, name, or assigned sections.

    Role changes take effect on the user's NEXT login (the JWT is not
    invalidated immediately — add a token blocklist for hard real-time
    revocation).
    """
    from schemas.user_schemas import VALID_ROLES

    existing = user_repo.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found.")

    updates: Dict[str, Any] = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'.")
        updates["role"] = payload.role
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active
    if payload.assigned_sections is not None:
        updates["assigned_sections"] = payload.assigned_sections

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    updates["updated_at"] = _now_iso()
    success = user_repo.update_user(user_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Update failed.")

    logger.info("Admin patched user %s: %s", user_id, list(updates))
    return {"success": True, "user_id": user_id, "updated_fields": list(updates)}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    hard_delete: bool = Query(False, description="Permanently remove the user record"),
    _: TokenPayload = _admin,
):
    """
    Deactivate (soft) or permanently delete a user.

    Default is soft-deactivation (``is_active=False``) which preserves
    audit history. Pass ``?hard_delete=true`` only when GDPR erasure is
    required.
    """
    existing = user_repo.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found.")

    if hard_delete:
        ok = user_repo.delete_user(user_id)
        action = "deleted"
    else:
        ok = user_repo.update_user(user_id, {"is_active": False, "updated_at": _now_iso()})
        action = "deactivated"

    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to {action} user.")

    logger.info("Admin %s user %s", action, user_id)
    return {"success": True, "user_id": user_id, "action": action}


@router.get("/roles")
async def list_roles(_: TokenPayload = _admin):
    """Return all roles and their associated permissions."""
    return {
        "roles": [
            {"role": role, "permissions": perms}
            for role, perms in ROLE_PERMISSIONS.items()
        ]
    }


# ═════════════════════════════════════════════════════════════════════════════
# CORE DATA ENDPOINTS  (v1, now JWT-guarded)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/students", response_model=List[dict])
async def get_all_students(_: TokenPayload = _admin):
    """Return all student accounts (password_hash stripped)."""
    try:
        students = user_repo.list_users_by_role("student")
        return [_strip_sensitive(s) for s in students]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/attendance/today")
async def get_today_attendance_stats(_: TokenPayload = _admin):
    """System-wide today attendance statistics."""
    try:
        fb = _fb()
        if not fb.fs:
            return {
                "totalStudents": 0, "presentToday": 0, "absentToday": 0,
                "lateToday": 0, "attendanceRate": 0.0,
                "error": "Firestore not initialized",
            }

        today = datetime.now().strftime("%Y-%m-%d")

        try:
            docs = fb.fs.collection("attendance").where("date", "==", today).stream()
            today_records = [d.to_dict() for d in docs]
        except Exception as qe:
            logger.warning("Attendance query failed: %s", qe)
            today_records = []

        present = sum(1 for r in today_records if r.get("status") == "present")
        late    = sum(1 for r in today_records if r.get("status") == "late")
        absent  = sum(1 for r in today_records if r.get("status") == "absent")

        all_students = user_repo.list_users_by_role("student")
        total = len(all_students)
        if total == 0:
            try:
                total = sum(1 for _ in fb.fs.collection("students").stream())
            except Exception:
                total = 0

        rate = round((present + late) / total * 100, 1) if total else 0.0
        present_ids = [r.get("student_id") for r in today_records if r.get("status") in ("present", "late")]

        return {
            "totalStudents": total,
            "presentToday": present,
            "absentToday": absent,
            "lateToday": late,
            "attendanceRate": rate,
            "pendingRecords": max(0, total - present - late - absent),
            "presentStudentIds": present_ids,
        }
    except Exception as exc:
        logger.error("get_today_attendance_stats error: %s", exc)
        return {"totalStudents": 0, "presentToday": 0, "absentToday": 0,
                "lateToday": 0, "attendanceRate": 0.0, "error": str(exc)}


@router.get("/attendance")
async def get_attendance_records(
    date: str,
    course_id: Optional[str] = None,
    section_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: TokenPayload = _admin,
):
    """
    Paginated attendance records for a given date.
    Optional filters: ``course_id``, ``section_id``.
    """
    try:
        fb = _fb()
        if not fb.fs:
            return {"data": [], "total": 0, "page": page, "limit": limit,
                    "error": "Firestore not available"}

        query = fb.fs.collection("attendance").where("date", "==", date)
        docs = list(query.stream())

        records = []
        for doc in docs:
            v = doc.to_dict()
            records.append({
                "id":          doc.id,
                "studentId":   v.get("student_id"),
                "studentName": (v.get("studentName")
                                or v.get("metadata", {}).get("student_name")
                                or "Unknown"),
                "status":      v.get("status") or v.get("metadata", {}).get("attendance_status", "present"),
                "markedAt":    v.get("timestamp"),
                "confidence":  v.get("confidence", 0.0),
                "sectionId":   v.get("class_id", ""),
                "metadata":    v.get("metadata", {}),
            })

        # Client-side filters (move to Firestore composite index in production)
        if section_id:
            records = [r for r in records if r["sectionId"] == section_id]

        # Enrich missing names
        for r in records:
            if r["studentName"] == "Unknown" and r["studentId"]:
                try:
                    sd = fb.fs.collection("students").document(r["studentId"]).get()
                    if sd.exists:
                        r["studentName"] = sd.to_dict().get("name", "Unknown")
                except Exception:
                    pass

        records.sort(key=lambda x: x.get("markedAt") or "", reverse=True)
        start = (page - 1) * limit
        return {
            "data": records[start: start + limit],
            "total": len(records),
            "page": page,
            "limit": limit,
        }
    except Exception as exc:
        logger.error("get_attendance_records error: %s", exc)
        return {"data": [], "total": 0, "page": page, "limit": limit, "error": str(exc)}


@router.post("/register-student-face")
async def register_student_face(
    student_id: str,
    face_image_base64: str,
    _: TokenPayload = _admin,
):
    """Register or update a student's face embedding."""
    try:
        base64.b64decode(face_image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")
    try:
        _fb().get_reference(f"students/{student_id}").update({
            "face_image_base64": face_image_base64[:100],
            "registered_at": _now_iso(),
            "embedding_version": "facenet_v1",
        })
        return {"success": True, "message": "Face registered successfully."}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ═════════════════════════════════════════════════════════════════════════════
# ANALYTICS  (new in v2, fully integrated)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/overview")
async def admin_analytics_overview(_: TokenPayload = _admin):
    """
    System-wide KPIs for the admin dashboard.

    Returns total students, total active sections, overall attendance rate
    for today, today's present/late/absent/pending breakdown, and a count
    of periods currently running.
    """
    fb = _fb()
    today = datetime.now().strftime("%Y-%m-%d")

    # ── Student total ─────────────────────────────────────────────────────────
    try:
        total_students = len(user_repo.list_users_by_role("student") or [])
        if total_students == 0 and fb.fs:
            total_students = sum(1 for _ in fb.fs.collection("students").stream())
    except Exception:
        total_students = 0

    # ── Active sections ───────────────────────────────────────────────────────
    try:
        raw_classes: dict = fb.get_reference("classes").get() or {}
        active_sections = [
            v for v in raw_classes.values()
            if isinstance(v, dict) and not v.get("deleted", False)
        ]
        total_sections = len(active_sections)
    except Exception:
        active_sections = []
        total_sections = 0

    # ── Today's attendance ────────────────────────────────────────────────────
    present = late = absent = 0
    try:
        if fb.fs:
            for doc in fb.fs.collection("attendance").where("date", "==", today).stream():
                s = doc.to_dict().get("status", "")
                if s == "present":  present += 1
                elif s == "late":   late    += 1
                elif s == "absent": absent  += 1
    except Exception as exc:
        logger.warning("analytics/overview attendance query: %s", exc)

    total_marked = present + late + absent
    pending = max(0, total_students - total_marked)
    rate = round((present + late) / total_students * 100, 1) if total_students else 0.0

    # ── Active periods right now ──────────────────────────────────────────────
    active_periods_count = 0
    try:
        now_str  = datetime.now().strftime("%H:%M")
        today_dow = datetime.now().weekday()
        if fb.fs:
            docs = (
                fb.fs.collection("periods")
                .where("day_of_week", "==", today_dow)
                .where("active_status", "==", True)
                .where("start_time", "<=", now_str)
                .stream()
            )
            for d in docs:
                if d.to_dict().get("end_time", "00:00") >= now_str:
                    active_periods_count += 1
    except Exception:
        pass

    return {
        "total_students":        total_students,
        "total_sections":        total_sections,
        "overall_attendance_rate": rate,
        "today_breakdown": {
            "present":        present,
            "late":           late,
            "absent":         absent,
            "pending":        pending,
            "total_expected": total_students,
            "total_marked":   total_marked,
        },
        "active_periods_now": active_periods_count,
        "generated_at":       _now_iso(),
    }


@router.get("/analytics/sections")
async def admin_section_breakdown(
    date: Optional[str] = Query(None, description="YYYY-MM-DD (defaults to today)"),
    _: TokenPayload = _admin,
):
    """
    Per-section attendance breakdown.

    Each entry: section_id, name, course_code, semester, present, late,
    absent, pending, total_students, attendance_rate.
    Sorted by attendance_rate ascending so at-risk sections appear first.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    fb = _fb()

    try:
        raw_classes: dict = fb.get_reference("classes").get() or {}
    except Exception:
        raw_classes = {}

    sections = [
        v for v in raw_classes.values()
        if isinstance(v, dict) and not v.get("deleted", False)
    ]

    # Collect attendance status per section → student
    records_by_section: Dict[str, Dict[str, str]] = defaultdict(dict)
    try:
        day_records = fb.get_reference(f"attendance/{target_date}").get() or {}
        for rec in day_records.values():
            if isinstance(rec, dict):
                sec = rec.get("class_id", "")
                stu = rec.get("student_id", "")
                if sec and stu:
                    records_by_section[sec][stu] = rec.get("status", "present")
    except Exception:
        pass

    # Fallback: Firestore
    if not records_by_section and fb.fs:
        try:
            for doc in fb.fs.collection("attendance").where("date", "==", target_date).stream():
                v = doc.to_dict()
                sec = v.get("class_id", "")
                stu = v.get("student_id", "")
                if sec and stu:
                    records_by_section[sec][stu] = v.get("status", "present")
        except Exception as exc:
            logger.warning("analytics/sections Firestore fallback: %s", exc)

    breakdown = []
    for sec in sections:
        sid  = sec.get("id", "")
        sids = sec.get("student_ids", [])
        total = len(sids)
        sm = records_by_section.get(sid, {})

        present = sum(1 for s in sids if sm.get(s) == "present")
        late    = sum(1 for s in sids if sm.get(s) == "late")
        absent  = sum(1 for s in sids if sm.get(s) == "absent")
        rate    = round((present + late) / total * 100, 1) if total else 0.0

        breakdown.append({
            "section_id":      sid,
            "section_name":    sec.get("name", ""),
            "course_code":     sec.get("course_code", ""),
            "course_name":     sec.get("course_name", ""),
            "semester":        sec.get("semester", ""),
            "section_label":   sec.get("section", ""),
            "faculty_id":      sec.get("faculty_id", ""),
            "total_students":  total,
            "present":         present,
            "late":            late,
            "absent":          absent,
            "pending":         max(0, total - present - late - absent),
            "attendance_rate": rate,
        })

    breakdown.sort(key=lambda x: x["attendance_rate"])
    return {
        "date":           target_date,
        "total_sections": len(breakdown),
        "sections":       breakdown,
        "generated_at":   _now_iso(),
    }


@router.get("/analytics/trends")
async def admin_attendance_trends(
    days: int = Query(7, ge=2, le=90, description="Past days to include"),
    _: TokenPayload = _admin,
):
    """
    Day-by-day attendance rate trend for the whole institution.

    Returns a list of ``{date, present, late, absent, total_marked, rate}``
    ordered oldest → newest.
    """
    fb = _fb()
    today = datetime.now().date()

    try:
        total_students = len(user_repo.list_users_by_role("student") or []) or 1
    except Exception:
        total_students = 1

    trend = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        d_str = d.strftime("%Y-%m-%d")
        present = late = absent = 0

        try:
            day_data = fb.get_reference(f"attendance/{d_str}").get() or {}
            for rec in day_data.values():
                if isinstance(rec, dict):
                    s = rec.get("status", "")
                    if s == "present":  present += 1
                    elif s == "late":   late    += 1
                    elif s == "absent": absent  += 1
        except Exception:
            pass

        trend.append({
            "date":         d_str,
            "present":      present,
            "late":         late,
            "absent":       absent,
            "total_marked": present + late + absent,
            "rate":         round((present + late) / total_students * 100, 1),
        })

    return {
        "days":           days,
        "total_students": total_students,
        "trend":          trend,
        "generated_at":   _now_iso(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/cie", status_code=201)
async def create_cie(payload: CIECreateSchema, _: TokenPayload = _admin):
    """Create a new CIE block. Returns the generated ``cie_id``."""
    fb = _fb()
    cie_id = _new_id()
    record = {
        "id": cie_id,
        "name": payload.name.strip(),
        "description": payload.description or "",
        "academic_year": payload.academic_year.strip(),
        "department": payload.department or "",
        "class_ids": [],
        "deleted": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    fb.get_reference(f"cies/{cie_id}").set(record)
    return {"success": True, "cie_id": cie_id, "data": record}


@router.get("/cies")
async def list_cies(
    department: Optional[str] = None,
    academic_year: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: TokenPayload = _admin,
):
    """List all active CIEs. Supports filtering by department and academic year."""
    fb = _fb()
    raw: dict = fb.get_reference("cies").get() or {}
    cies = [v for v in raw.values() if isinstance(v, dict) and not v.get("deleted", False)]

    if department:
        cies = [c for c in cies if c.get("department", "").lower() == department.lower()]
    if academic_year:
        cies = [c for c in cies if c.get("academic_year") == academic_year]

    for cie in cies:
        cie["class_count"] = len(cie.get("class_ids", []))

    cies.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    start = (page - 1) * limit
    return {
        "data":        cies[start: start + limit],
        "total":       len(cies),
        "page":        page,
        "limit":       limit,
        "total_pages": max(1, (len(cies) + limit - 1) // limit),
    }


@router.put("/cie/{cie_id}")
async def update_cie(cie_id: str, payload: CIEUpdateSchema, _: TokenPayload = _admin):
    """Update mutable fields of an existing CIE."""
    fb = _fb()
    ref = fb.get_reference(f"cies/{cie_id}")
    existing = ref.get()
    if not existing or existing.get("deleted"):
        raise HTTPException(status_code=404, detail=f"CIE '{cie_id}' not found.")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    for field, val in payload.model_dump(exclude_none=True).items():
        updates[field] = val.strip() if isinstance(val, str) else val

    ref.update(updates)
    return {"success": True, "cie_id": cie_id, "updated_fields": list(updates)}


@router.delete("/cie/{cie_id}")
async def delete_cie(cie_id: str, _: TokenPayload = _admin):
    """
    Soft-delete a CIE and cascade to all child classes.
    Records are retained with ``deleted=True`` for audit purposes.
    """
    fb = _fb()
    ref = fb.get_reference(f"cies/{cie_id}")
    cie = ref.get()
    if not cie or cie.get("deleted"):
        raise HTTPException(status_code=404, detail=f"CIE '{cie_id}' not found.")

    now = _now_iso()
    ref.update({"deleted": True, "deleted_at": now, "updated_at": now})

    class_ids: List[str] = cie.get("class_ids", [])
    for cid in class_ids:
        cls_ref = fb.get_reference(f"classes/{cid}")
        cls = cls_ref.get()
        if cls and not cls.get("deleted"):
            cls_ref.update({"deleted": True, "deleted_at": now, "updated_at": now})

    logger.info("Admin soft-deleted CIE %s and %d class(es)", cie_id, len(class_ids))
    return {
        "success":        True,
        "cie_id":         cie_id,
        "deleted_classes": len(class_ids),
        "message":        f"CIE '{cie_id}' and {len(class_ids)} class(es) soft-deleted.",
    }


# ═════════════════════════════════════════════════════════════════════════════
# CLASS MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/class", status_code=201)
async def create_class(payload: ClassCreateSchema, _: TokenPayload = _admin):
    """Create a class under an existing CIE. Validates that the parent CIE exists."""
    fb = _fb()
    cie_ref = fb.get_reference(f"cies/{payload.cie_id}")
    cie = cie_ref.get()
    if not cie or cie.get("deleted"):
        raise HTTPException(status_code=404, detail=f"CIE '{payload.cie_id}' not found.")

    class_id = _new_id()
    now = _now_iso()
    record = {
        "id":          class_id,
        "cie_id":      payload.cie_id,
        "name":        payload.name.strip(),
        "course_code": payload.course_code.strip().upper(),
        "course_name": payload.course_name.strip(),
        "semester":    payload.semester.strip(),
        "section":     payload.section.strip(),
        "faculty_id":  payload.faculty_id or "",
        "student_ids": payload.student_ids or [],
        "deleted":     False,
        "created_at":  now,
        "updated_at":  now,
    }
    fb.get_reference(f"classes/{class_id}").set(record)

    existing_ids: List[str] = cie.get("class_ids", [])
    existing_ids.append(class_id)
    cie_ref.update({"class_ids": existing_ids, "updated_at": now})

    return {"success": True, "class_id": class_id, "data": record}


@router.get("/classes")
async def list_classes(
    cie_id:     Optional[str] = None,
    semester:   Optional[str] = None,
    section:    Optional[str] = None,
    faculty_id: Optional[str] = None,
    page:  int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: TokenPayload = _admin,
):
    """List classes with optional filters. Includes computed ``student_count``."""
    fb = _fb()
    raw: dict = fb.get_reference("classes").get() or {}
    classes = [v for v in raw.values() if isinstance(v, dict) and not v.get("deleted", False)]

    if cie_id:     classes = [c for c in classes if c.get("cie_id") == cie_id]
    if semester:   classes = [c for c in classes if c.get("semester") == semester]
    if section:    classes = [c for c in classes if c.get("section", "").lower() == section.lower()]
    if faculty_id: classes = [c for c in classes if c.get("faculty_id") == faculty_id]

    for cls in classes:
        cls["student_count"] = len(cls.get("student_ids", []))

    classes.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    start = (page - 1) * limit
    return {
        "data":        classes[start: start + limit],
        "total":       len(classes),
        "page":        page,
        "limit":       limit,
        "total_pages": max(1, (len(classes) + limit - 1) // limit),
    }


@router.put("/class/{class_id}")
async def update_class(class_id: str, payload: ClassUpdateSchema, _: TokenPayload = _admin):
    """Update mutable fields of an existing class."""
    fb = _fb()
    ref = fb.get_reference(f"classes/{class_id}")
    existing = ref.get()
    if not existing or existing.get("deleted"):
        raise HTTPException(status_code=404, detail=f"Class '{class_id}' not found.")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    for attr in ("name", "course_code", "course_name", "semester", "section", "faculty_id"):
        val = getattr(payload, attr)
        if val is not None:
            updates[attr] = val.strip().upper() if attr == "course_code" else val.strip()
    if payload.student_ids is not None:
        updates["student_ids"] = payload.student_ids

    ref.update(updates)
    return {"success": True, "class_id": class_id, "updated_fields": list(updates)}


# ═════════════════════════════════════════════════════════════════════════════
# BULK IMPORT
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/timetable/bulk-import")
async def bulk_import_timetable(
    file: UploadFile = File(...),
    _: TokenPayload = _admin,
):
    """
    Import timetable periods from a CSV.

    Expected columns: ``day``, ``start_time``, ``end_time``, ``course_code``,
    ``course_name``, ``faculty_id``, ``class_id``.

    Conflict detection prevents double-booking of faculty. Returns a detailed
    per-row error report.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    parse_result = parse_timetable_csv(await file.read())

    if not parse_result.rows and not parse_result.ok:
        return {
            "success": False, "total_rows": parse_result.total_rows,
            "imported": 0, "failed": parse_result.total_rows,
            "parse_errors": [e.to_dict() for e in parse_result.errors],
            "conflict_errors": [],
        }

    svc = _svc()
    try:
        conflicts = svc.check_timetable_conflicts(parse_result.rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    conflicting_rows: set = {c["period_a"]["row"] for c in conflicts} | {c["period_b"]["row"] for c in conflicts}
    safe_rows = [r for r in parse_result.rows if r["row"] not in conflicting_rows]

    fb = _fb()
    imported_ids: List[str] = []
    persist_errors: List[dict] = []

    for row in safe_rows:
        try:
            pid = _new_id()
            fb.get_reference(f"timetable/{row['class_id']}/{pid}").set({
                "id": pid, "day": row["day"],
                "start_time": row["start_time"], "end_time": row["end_time"],
                "course_code": row["course_code"], "course_name": row["course_name"],
                "faculty_id": row["faculty_id"], "class_id": row["class_id"],
                "created_at": _now_iso(),
            })
            imported_ids.append(pid)
        except Exception as exc:
            persist_errors.append({"row": row["row"], "error": str(exc)})

    return {
        "success": not conflicts and not parse_result.errors,
        "total_rows": parse_result.total_rows,
        "imported": len(imported_ids),
        "failed": parse_result.invalid_row_count + len(conflicting_rows) + len(persist_errors),
        "parse_errors": [e.to_dict() for e in parse_result.errors],
        "conflict_errors": [
            {"rows": [c["period_a"]["row"], c["period_b"]["row"]], "message": c["message"]}
            for c in conflicts
        ],
        "persist_errors": persist_errors,
    }


@router.post("/students/bulk-import")
async def bulk_import_students(
    file: UploadFile = File(...),
    _: TokenPayload = _admin,
):
    """
    Import a student roster from a CSV.

    Expected columns: ``student_id``, ``name``, ``email``, ``class_id``.
    Valid students are persisted and enrolled in their class.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    parse_result = parse_roster_csv(await file.read())

    if not parse_result.rows and not parse_result.ok:
        return {
            "success": False, "total_rows": parse_result.total_rows,
            "imported": 0, "failed": parse_result.total_rows,
            "parse_errors": [e.to_dict() for e in parse_result.errors],
            "validation_errors": [], "persist_errors": [],
        }

    svc = _svc()
    validation = svc.validate_student_roster(parse_result.rows)
    fb = _fb()
    imported: List[str] = []
    persist_errors: List[dict] = []

    for row in validation["valid_rows"]:
        try:
            now = _now_iso()
            fb.get_reference(f"users/{row['student_id']}").set({
                "id": row["student_id"], "name": row["name"],
                "email": row["email"], "role": "student",
                "class_id": row["class_id"], "assigned_sections": [],
                "is_active": True, "created_at": now, "updated_at": now,
            })
            cls_ref = fb.get_reference(f"classes/{row['class_id']}")
            cls = cls_ref.get() or {}
            sids: List[str] = cls.get("student_ids", [])
            if row["student_id"] not in sids:
                sids.append(row["student_id"])
                cls_ref.update({"student_ids": sids, "updated_at": now})
            imported.append(row["student_id"])
        except Exception as exc:
            persist_errors.append({"row": row["row"], "student_id": row["student_id"], "error": str(exc)})

    return {
        "success": parse_result.ok and validation["valid"] and not persist_errors,
        "total_rows": parse_result.total_rows,
        "imported": len(imported),
        "failed": parse_result.invalid_row_count + len(validation["invalid_rows"]) + len(persist_errors),
        "parse_errors": [e.to_dict() for e in parse_result.errors],
        "validation_errors": [
            {"row": r["row"], "student_id": r.get("student_id"), "errors": r["errors"]}
            for r in validation["invalid_rows"]
        ],
        "persist_errors": persist_errors,
    }


# ═════════════════════════════════════════════════════════════════════════════
# REPORTING
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/reports/cie/{cie_id}/summary")
async def cie_summary_report(cie_id: str, _: TokenPayload = _admin):
    """CIE-wide attendance summary with per-class breakdown."""
    svc = _svc()
    try:
        return await svc.get_cie_summary(cie_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reports/class/{class_id}/attendance")
async def class_attendance_report(class_id: str, _: TokenPayload = _admin):
    """
    Student-wise attendance breakdown for a class.
    Students sorted by attendance percentage ascending (at-risk first).
    """
    svc = _svc()
    try:
        return await svc.get_class_attendance_detail(class_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/config")
async def set_system_config(payload: SystemConfigSchema, _: TokenPayload = _admin):
    """
    Persist system-wide attendance configuration.
    Only supplied fields are updated; omitted fields retain their current values.
    """
    updates: Dict[str, Any] = {}
    if payload.attendance_window_minutes is not None:
        updates["attendance_window_minutes"] = payload.attendance_window_minutes
    if payload.late_threshold_minutes is not None:
        updates["late_threshold_minutes"] = payload.late_threshold_minutes
    if payload.low_attendance_warning_threshold is not None:
        updates["low_attendance_warning_threshold"] = payload.low_attendance_warning_threshold

    if not updates:
        raise HTTPException(status_code=400, detail="No configuration fields provided.")

    updates["updated_at"] = _now_iso()
    _fb().get_reference("system_config").update(updates)

    return {
        "success":        True,
        "updated_fields": [k for k in updates if k != "updated_at"],
        "config":         updates,
    }