"""
admin.py  –  Enhanced admin API router
=======================================
Endpoints
---------
Existing (preserved):
  GET  /api/v1/admin/students
  GET  /api/v1/admin/attendance/today
  GET  /api/v1/admin/attendance
  POST /api/v1/admin/register-student-face

CIE Management:
  POST   /api/v1/admin/cie
  GET    /api/v1/admin/cies
  PUT    /api/v1/admin/cie/{cie_id}
  DELETE /api/v1/admin/cie/{cie_id}

Class Management:
  POST /api/v1/admin/class
  GET  /api/v1/admin/classes
  PUT  /api/v1/admin/class/{class_id}

Bulk Import:
  POST /api/v1/admin/timetable/bulk-import
  POST /api/v1/admin/students/bulk-import

Reporting:
  GET /api/v1/admin/reports/cie/{cie_id}/summary
  GET /api/v1/admin/reports/class/{class_id}/attendance

System Config:
  POST /api/v1/admin/config
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from database.firebase_client import FirebaseClient
from database.student_repository import StudentRepository
from database.user_repository import UserRepository
from services.admin_service import AdminService
from utils.csv_parser import parse_roster_csv, parse_timetable_csv

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Shared singletons (stateless wrappers – safe to reuse)
user_repo = UserRepository()
student_repo = StudentRepository()


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class CIECreateSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Human-readable CIE name")
    description: Optional[str] = None
    academic_year: str = Field(..., description="e.g. '2024-25'")
    department: Optional[str] = None


class CIEUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    academic_year: Optional[str] = None
    department: Optional[str] = None


class ClassCreateSchema(BaseModel):
    cie_id: str = Field(..., description="Parent CIE identifier")
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
    attendance_window_minutes: Optional[int] = Field(
        None, ge=1, le=120,
        description="Window in minutes during which attendance can be marked"
    )
    late_threshold_minutes: Optional[int] = Field(
        None, ge=1, le=60,
        description="Minutes after session start at which a student is marked late"
    )
    low_attendance_warning_threshold: Optional[float] = Field(
        None, ge=1.0, le=100.0,
        description="Percentage below which a low-attendance warning is triggered"
    )


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _fb() -> FirebaseClient:
    return FirebaseClient()


def _svc() -> AdminService:
    return AdminService(_fb())


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _new_id() -> str:
    return str(uuid.uuid4())


# ===========================================================================
# EXISTING ENDPOINTS (preserved)
# ===========================================================================

@router.get("/students", response_model=List[dict])
async def get_all_students():
    """Admin-only: Get all students."""
    try:
        students = user_repo.list_users_by_role("student")
        return students if students else []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/attendance/today")
async def get_today_attendance_stats():
    """Admin-only: Get today's attendance statistics."""
    try:
        fb = _fb()
        # Ensure we have Firestore
        if not fb.fs:
            return {
                "totalStudents": 0,
                "presentToday": 0,
                "absentToday": 0,
                "lateToday": 0,
                "attendanceRate": 0.0,
                "error": "Firestore not initialized"
            }

        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            # Query Firestore attendance collection for today
            docs = fb.fs.collection("attendance").where("date", "==", today).stream()
            today_records = [doc.to_dict() for doc in docs]
        except Exception as query_err:
            logger.warning("Failed to query attendance: %s. Returning empty data.", query_err)
            today_records = []

        present_count = sum(1 for r in today_records if r.get("status") == "present")
        late_count = sum(1 for r in today_records if r.get("status") == "late")
        absent_count = sum(1 for r in today_records if r.get("status") == "absent")

        # Get total students
        all_students = user_repo.list_users_by_role("student")
        total_students = len(all_students) if all_students else 0
        
        # In case students are not in 'users' but in 'students' collection
        if total_students == 0:
            try:
                student_docs = fb.fs.collection("students").stream()
                total_students = sum(1 for _ in student_docs)
            except Exception as student_err:
                logger.warning("Failed to query students: %s. Using 0.", student_err)
                total_students = 0

        attendance_rate = (
            ((present_count + late_count) / total_students * 100) if total_students > 0 else 0
        )

        present_student_ids = [r.get("student_id") for r in today_records if r.get("status") in ["present", "late"]]

        return {
            "totalStudents": total_students,
            "presentToday": present_count,
            "absentToday": absent_count,
            "lateToday": late_count,
            "attendanceRate": round(attendance_rate, 1),
            "pendingRecords": max(0, total_students - (present_count + late_count)),
            "presentStudentIds": present_student_ids
        }
    except Exception as exc:
        logger.error("Error in get_today_attendance_stats: %s", exc)
        return {
            "totalStudents": 0,
            "presentToday": 0,
            "absentToday": 0,
            "lateToday": 0,
            "attendanceRate": 0.0,
            "error": str(exc),
        }


@router.get("/attendance")
async def get_attendance_records(
    date: str,
    course_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Get attendance records for a date from Firestore with optional filters."""
    try:
        fb = _fb()
        if not fb.fs:
            return {"data": [], "total": 0, "page": page, "limit": limit, "error": "Firestore not available"}

        # Query Firestore
        query = fb.fs.collection("attendance").where("date", "==", date)
        
        # Stream and convert to list (pagination handled manually for simplicity in this small set)
        docs = query.stream()
        
        record_list = []
        for doc in docs:
            v = doc.to_dict()
            record_list.append({
                "id": doc.id,
                "studentId": v.get("student_id"),
                "studentName": v.get("studentName") or v.get("metadata", {}).get("student_name") or "Unknown",
                "status": v.get("status") or v.get("metadata", {}).get("attendance_status", "present"),
                "markedAt": v.get("timestamp"),
                "confidence": v.get("confidence", 0.0),
                "metadata": v.get("metadata", {})
            })

        # Enrich with real names if missing
        for r in record_list:
            if not r["studentName"] or r["studentName"] == "Unknown":
                student_doc = fb.fs.collection("students").document(r["studentId"]).get()
                if student_doc.exists:
                    r["studentName"] = student_doc.to_dict().get("name", "Unknown")

        # Sort by markedAt descending
        record_list.sort(key=lambda x: x.get("markedAt", ""), reverse=True)

        start = (page - 1) * limit
        return {
            "data": record_list[start : start + limit],
            "total": len(record_list),
            "page": page,
            "limit": limit,
        }
    except Exception as exc:
        logger.error("Error in get_attendance_records: %s", exc)
        return {"data": [], "total": 0, "page": page, "limit": limit, "error": str(exc)}


@router.post("/register-student-face")
async def register_student_face(student_id: str, face_image_base64: str):
    """Register or update a student's face for recognition."""
    try:
        try:
            base64.b64decode(face_image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image")

        fb = _fb()
        ref = fb.get_reference(f"students/{student_id}")
        ref.update(
            {
                "face_image_base64": face_image_base64[:100],
                "registered_at": _now_iso(),
                "embedding_version": "facenet_v1",
            }
        )
        return {"success": True, "message": "Face registered successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# CIE MANAGEMENT
# ===========================================================================

@router.post("/cie", status_code=201)
async def create_cie(payload: CIECreateSchema):
    """
    Create a new CIE (Continuous Internal Evaluation) block.

    Returns the generated ``cie_id``.
    """
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
):
    """
    List all active CIEs with class counts.

    Optional filters: ``department``, ``academic_year``.
    """
    fb = _fb()
    raw: dict = fb.get_reference("cies").get() or {}

    cies = [v for v in raw.values() if isinstance(v, dict) and not v.get("deleted", False)]

    if department:
        cies = [c for c in cies if c.get("department", "").lower() == department.lower()]
    if academic_year:
        cies = [c for c in cies if c.get("academic_year") == academic_year]

    # Attach class count
    for cie in cies:
        cie["class_count"] = len(cie.get("class_ids", []))

    cies.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    start = (page - 1) * limit

    return {
        "data": cies[start : start + limit],
        "total": len(cies),
        "page": page,
        "limit": limit,
        "total_pages": max(1, (len(cies) + limit - 1) // limit),
    }


@router.put("/cie/{cie_id}")
async def update_cie(cie_id: str, payload: CIEUpdateSchema):
    """Update mutable fields of an existing CIE."""
    fb = _fb()
    ref = fb.get_reference(f"cies/{cie_id}")
    existing = ref.get()
    if not existing or existing.get("deleted"):
        raise HTTPException(status_code=404, detail=f"CIE '{cie_id}' not found.")

    updates: dict[str, Any] = {"updated_at": _now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.academic_year is not None:
        updates["academic_year"] = payload.academic_year.strip()
    if payload.department is not None:
        updates["department"] = payload.department

    ref.update(updates)
    return {"success": True, "cie_id": cie_id, "updated_fields": list(updates.keys())}


@router.delete("/cie/{cie_id}")
async def delete_cie(cie_id: str):
    """
    Soft-delete a CIE.

    The record is retained in Firebase with ``deleted=True`` and a
    ``deleted_at`` timestamp.  All associated classes are also soft-deleted.
    """
    fb = _fb()
    ref = fb.get_reference(f"cies/{cie_id}")
    cie = ref.get()
    if not cie or cie.get("deleted"):
        raise HTTPException(status_code=404, detail=f"CIE '{cie_id}' not found.")

    now = _now_iso()
    ref.update({"deleted": True, "deleted_at": now, "updated_at": now})

    # Cascade soft-delete to child classes
    class_ids: list[str] = cie.get("class_ids", [])
    for cid in class_ids:
        cls_ref = fb.get_reference(f"classes/{cid}")
        cls = cls_ref.get()
        if cls and not cls.get("deleted"):
            cls_ref.update({"deleted": True, "deleted_at": now, "updated_at": now})

    return {
        "success": True,
        "cie_id": cie_id,
        "deleted_classes": len(class_ids),
        "message": f"CIE '{cie_id}' and {len(class_ids)} class(es) soft-deleted.",
    }


# ===========================================================================
# CLASS MANAGEMENT
# ===========================================================================

@router.post("/class", status_code=201)
async def create_class(payload: ClassCreateSchema):
    """
    Create a new class under an existing CIE.

    Validates that the parent CIE exists and is not deleted.
    """
    fb = _fb()

    # Validate parent CIE
    cie_ref = fb.get_reference(f"cies/{payload.cie_id}")
    cie = cie_ref.get()
    if not cie or cie.get("deleted"):
        raise HTTPException(
            status_code=404, detail=f"CIE '{payload.cie_id}' not found."
        )

    class_id = _new_id()
    now = _now_iso()

    record = {
        "id": class_id,
        "cie_id": payload.cie_id,
        "name": payload.name.strip(),
        "course_code": payload.course_code.strip().upper(),
        "course_name": payload.course_name.strip(),
        "semester": payload.semester.strip(),
        "section": payload.section.strip(),
        "faculty_id": payload.faculty_id or "",
        "student_ids": payload.student_ids or [],
        "deleted": False,
        "created_at": now,
        "updated_at": now,
    }

    # Persist class
    fb.get_reference(f"classes/{class_id}").set(record)

    # Add class_id to parent CIE
    existing_class_ids: list = cie.get("class_ids", [])
    existing_class_ids.append(class_id)
    cie_ref.update({"class_ids": existing_class_ids, "updated_at": now})

    return {"success": True, "class_id": class_id, "data": record}


@router.get("/classes")
async def list_classes(
    cie_id: Optional[str] = None,
    semester: Optional[str] = None,
    section: Optional[str] = None,
    faculty_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List classes with optional filters.

    Filters: ``cie_id``, ``semester``, ``section``, ``faculty_id``.
    """
    fb = _fb()
    raw: dict = fb.get_reference("classes").get() or {}

    classes = [
        v for v in raw.values()
        if isinstance(v, dict) and not v.get("deleted", False)
    ]

    if cie_id:
        classes = [c for c in classes if c.get("cie_id") == cie_id]
    if semester:
        classes = [c for c in classes if c.get("semester") == semester]
    if section:
        classes = [c for c in classes if c.get("section", "").lower() == section.lower()]
    if faculty_id:
        classes = [c for c in classes if c.get("faculty_id") == faculty_id]

    # Enrich with student count
    for cls in classes:
        cls["student_count"] = len(cls.get("student_ids", []))

    classes.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    start = (page - 1) * limit

    return {
        "data": classes[start : start + limit],
        "total": len(classes),
        "page": page,
        "limit": limit,
        "total_pages": max(1, (len(classes) + limit - 1) // limit),
    }


@router.put("/class/{class_id}")
async def update_class(class_id: str, payload: ClassUpdateSchema):
    """Update mutable fields of an existing class."""
    fb = _fb()
    ref = fb.get_reference(f"classes/{class_id}")
    existing = ref.get()
    if not existing or existing.get("deleted"):
        raise HTTPException(status_code=404, detail=f"Class '{class_id}' not found.")

    updates: dict[str, Any] = {"updated_at": _now_iso()}
    for attr in ("name", "course_code", "course_name", "semester", "section", "faculty_id"):
        val = getattr(payload, attr)
        if val is not None:
            updates[attr] = val.strip().upper() if attr == "course_code" else val.strip()
    if payload.student_ids is not None:
        updates["student_ids"] = payload.student_ids

    ref.update(updates)
    return {"success": True, "class_id": class_id, "updated_fields": list(updates.keys())}


# ===========================================================================
# BULK IMPORT – TIMETABLE
# ===========================================================================

@router.post("/timetable/bulk-import")
async def bulk_import_timetable(file: UploadFile = File(...)):
    """
    Import timetable periods from a CSV file.

    **Expected columns:** ``day``, ``start_time``, ``end_time``,
    ``course_code``, ``course_name``, ``faculty_id``, ``class_id``

    Processing steps:
    1. Parse and validate every row in the CSV.
    2. Check for faculty scheduling conflicts across all valid rows.
    3. Persist only non-conflicting, valid rows to Firebase.

    Returns a detailed report with success/failure counts and per-row
    error messages.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    content = await file.read()
    parse_result = parse_timetable_csv(content)

    if not parse_result.rows and not parse_result.ok:
        # Header-level errors – bail early
        return {
            "success": False,
            "total_rows": parse_result.total_rows,
            "imported": 0,
            "failed": parse_result.total_rows,
            "parse_errors": [e.to_dict() for e in parse_result.errors],
            "conflict_errors": [],
        }

    # Conflict detection on all valid rows
    svc = _svc()
    try:
        conflicts = svc.check_timetable_conflicts(parse_result.rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Build a set of conflicting row numbers
    conflicting_rows: set[int] = set()
    for c in conflicts:
        conflicting_rows.add(c["period_a"]["row"])
        conflicting_rows.add(c["period_b"]["row"])

    safe_rows = [r for r in parse_result.rows if r["row"] not in conflicting_rows]

    # Persist safe rows
    fb = _fb()
    imported_ids: list[str] = []
    persist_errors: list[dict] = []

    for row in safe_rows:
        try:
            period_id = _new_id()
            now = _now_iso()
            fb.get_reference(f"timetable/{row['class_id']}/{period_id}").set(
                {
                    "id": period_id,
                    "day": row["day"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "course_code": row["course_code"],
                    "course_name": row["course_name"],
                    "faculty_id": row["faculty_id"],
                    "class_id": row["class_id"],
                    "created_at": now,
                }
            )
            imported_ids.append(period_id)
        except Exception as exc:
            persist_errors.append({"row": row["row"], "error": str(exc)})

    total_failed = parse_result.invalid_row_count + len(conflicting_rows) + len(persist_errors)

    return {
        "success": len(conflicts) == 0 and len(parse_result.errors) == 0,
        "total_rows": parse_result.total_rows,
        "imported": len(imported_ids),
        "failed": total_failed,
        "parse_errors": [e.to_dict() for e in parse_result.errors],
        "conflict_errors": [
            {
                "rows": [c["period_a"]["row"], c["period_b"]["row"]],
                "message": c["message"],
            }
            for c in conflicts
        ],
        "persist_errors": persist_errors,
    }


# ===========================================================================
# BULK IMPORT – STUDENT ROSTER
# ===========================================================================

@router.post("/students/bulk-import")
async def bulk_import_students(file: UploadFile = File(...)):
    """
    Import a student roster from a CSV file.

    **Expected columns:** ``student_id``, ``name``, ``email``, ``class_id``

    Processing steps:
    1. Parse and validate every row (format + duplicates).
    2. Run domain-level roster validation via ``AdminService``.
    3. Persist valid students to Firebase and enrol them in their class.

    Returns success/failure counts and detailed per-row error messages.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    content = await file.read()
    parse_result = parse_roster_csv(content)

    if not parse_result.rows and not parse_result.ok:
        return {
            "success": False,
            "total_rows": parse_result.total_rows,
            "imported": 0,
            "failed": parse_result.total_rows,
            "parse_errors": [e.to_dict() for e in parse_result.errors],
            "validation_errors": [],
            "persist_errors": [],
        }

    svc = _svc()
    validation = svc.validate_student_roster(parse_result.rows)

    fb = _fb()
    imported: list[str] = []
    persist_errors: list[dict] = []

    for row in validation["valid_rows"]:
        try:
            now = _now_iso()
            fb.get_reference(f"users/{row['student_id']}").set(
                {
                    "id": row["student_id"],
                    "name": row["name"],
                    "email": row["email"],
                    "role": "student",
                    "class_id": row["class_id"],
                    "created_at": now,
                    "updated_at": now,
                }
            )
            # Enrol student in class
            cls_ref = fb.get_reference(f"classes/{row['class_id']}")
            cls = cls_ref.get() or {}
            student_ids: list = cls.get("student_ids", [])
            if row["student_id"] not in student_ids:
                student_ids.append(row["student_id"])
                cls_ref.update({"student_ids": student_ids, "updated_at": now})

            imported.append(row["student_id"])
        except Exception as exc:
            persist_errors.append({"row": row["row"], "student_id": row["student_id"], "error": str(exc)})

    total_failed = parse_result.invalid_row_count + len(validation["invalid_rows"]) + len(persist_errors)

    return {
        "success": parse_result.ok and validation["valid"] and len(persist_errors) == 0,
        "total_rows": parse_result.total_rows,
        "imported": len(imported),
        "failed": total_failed,
        "parse_errors": [e.to_dict() for e in parse_result.errors],
        "validation_errors": [
            {"row": r["row"], "student_id": r.get("student_id"), "errors": r["errors"]}
            for r in validation["invalid_rows"]
        ],
        "persist_errors": persist_errors,
    }


# ===========================================================================
# REPORTING
# ===========================================================================

@router.get("/reports/cie/{cie_id}/summary")
async def cie_summary_report(cie_id: str):
    """
    CIE-wide attendance summary.

    Returns overall stats (total classes, students, attendance average)
    and a per-class breakdown with session counts and per-class averages.
    """
    svc = _svc()
    try:
        summary = await svc.get_cie_summary(cie_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return summary


@router.get("/reports/class/{class_id}/attendance")
async def class_attendance_report(class_id: str):
    """
    Detailed student-wise attendance breakdown for a class.

    Each student entry includes present/late/absent counts, overall
    attendance percentage, and an ``at_risk`` flag (< 75 % by default).
    Students are returned sorted by attendance percentage ascending so
    at-risk students appear first.
    """
    svc = _svc()
    try:
        detail = await svc.get_class_attendance_detail(class_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return detail


# ===========================================================================
# SYSTEM CONFIGURATION
# ===========================================================================

@router.post("/config")
async def set_system_config(payload: SystemConfigSchema):
    """
    Persist system-wide attendance configuration.

    | Field                              | Meaning                                                          |
    |------------------------------------|------------------------------------------------------------------|
    | ``attendance_window_minutes``      | How long after a session starts attendance can be marked         |
    | ``late_threshold_minutes``         | Minutes after start at which check-in is recorded as *late*     |
    | ``low_attendance_warning_threshold``| Percentage below which a student receives a low-attendance alert |

    Only supplied fields are updated; omitted fields retain their current values.
    """
    updates: dict[str, Any] = {}
    if payload.attendance_window_minutes is not None:
        updates["attendance_window_minutes"] = payload.attendance_window_minutes
    if payload.late_threshold_minutes is not None:
        updates["late_threshold_minutes"] = payload.late_threshold_minutes
    if payload.low_attendance_warning_threshold is not None:
        updates["low_attendance_warning_threshold"] = payload.low_attendance_warning_threshold

    if not updates:
        raise HTTPException(status_code=400, detail="No configuration fields provided.")

    updates["updated_at"] = _now_iso()

    fb = _fb()
    fb.get_reference("system_config").update(updates)

    return {
        "success": True,
        "updated_fields": [k for k in updates if k != "updated_at"],
        "config": updates,
    }
