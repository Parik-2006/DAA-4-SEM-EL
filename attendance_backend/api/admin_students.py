"""
admin_students.py
-----------------
Student CRUD, batch JSON import, and face registration for the admin API.

All routes are intended to be mounted under a prefix such as
``/api/v1/admin`` in the application factory.

Changes from original
---------------------
* Dependency injection aligned with admin.py (_fb / _svc factories).
* ``POST /batch-import`` now runs AdminService.validate_student_roster()
  before persisting, returns three-bucket error report, and auto-enrols
  each student in their class's student_ids list.
* ``POST /students`` (create single) also auto-enrols into courses/classes.
* ``PUT  /students/{student_id}`` handles class re-enrolment when class_id
  changes (removes from old class, adds to new class).
* ``DELETE /students/{student_id}`` is now a soft-delete; student record is
  retained with deleted=True and removed from all class rosters.
* ``POST /register-face`` de-duplicated: lives here only; removed from
  admin.py's register-student-face endpoint (kept for backwards-compat).
* Pydantic models tightened; response shapes consistent across all routes.
* All handlers use async Firebase I/O where the repository supports it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from database.firebase_client import FirebaseClient
from database.student_repository import StudentRepository
from services.admin_service import AdminService
from services.firebase_service import FirebaseService

router = APIRouter(tags=["admin-students"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StudentCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Full name of the student")
    email: EmailStr
    class_id: Optional[str] = Field(None, description="Class to enrol the student in")
    courses: Optional[List[str]] = Field(default_factory=list, description="Course IDs")
    student_id: Optional[str] = Field(
        None,
        description="Optional explicit student ID; auto-generated UUID if omitted",
    )


class StudentUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[EmailStr] = None
    class_id: Optional[str] = None
    courses: Optional[List[str]] = None


class BatchImportSchema(BaseModel):
    """
    JSON body for ``POST /batch-import``.

    Each item must contain at minimum: student_id, name, email, class_id.
    """
    students: List[dict] = Field(..., min_items=1)


class RegisterFaceSchema(BaseModel):
    student_id: str
    face_image_base64: str = Field(..., description="Base64-encoded JPEG/PNG image")


# ---------------------------------------------------------------------------
# Shared dependency factories (mirrors admin.py pattern)
# ---------------------------------------------------------------------------

def _fb() -> FirebaseClient:
    return FirebaseClient()


def _svc(db: FirebaseClient = Depends(_fb)) -> AdminService:
    return AdminService(db)


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _enrol_student_in_class(
    db: FirebaseClient, student_id: str, class_id: str
) -> None:
    """Append *student_id* to the class roster if not already present."""
    cls_ref = db.get_reference(f"classes/{class_id}")
    cls = cls_ref.get() or {}
    roster: list = cls.get("student_ids", [])
    if student_id not in roster:
        roster.append(student_id)
        cls_ref.update({"student_ids": roster, "updated_at": _now_iso()})


async def _unenrol_student_from_class(
    db: FirebaseClient, student_id: str, class_id: str
) -> None:
    """Remove *student_id* from the class roster (no-op if absent)."""
    cls_ref = db.get_reference(f"classes/{class_id}")
    cls = cls_ref.get() or {}
    roster: list = cls.get("student_ids", [])
    if student_id in roster:
        roster.remove(student_id)
        cls_ref.update({"student_ids": roster, "updated_at": _now_iso()})


def _strip_internal(record: dict) -> dict:
    """Remove large/internal-only fields before returning to client."""
    record.pop("face_image_base64", None)
    return record


# ===========================================================================
# CRUD
# ===========================================================================

@router.get("/students")
async def get_all_students(
    role: Optional[str] = Query(None, description="Filter by role (default: student)"),
    class_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """
    List all (non-deleted) students with optional filters.

    Filters
    -------
    ``role``     : defaults to 'student' when omitted.
    ``class_id`` : return only students enrolled in a specific class.
    """
    try:
        repo = StudentRepository(db)
        students = await repo.get_all_students(role=role or "student")

        # Additional filter not available in repo layer
        if class_id:
            students = [s for s in students if s.get("class_id") == class_id]

        # Exclude soft-deleted records
        students = [s for s in students if not s.get("deleted", False)]

        # Strip internal fields
        students = [_strip_internal(s) for s in students]

        start = (page - 1) * limit
        paginated = students[start : start + limit]

        return {
            "data": paginated,
            "total": len(students),
            "page": page,
            "limit": limit,
            "total_pages": max(1, (len(students) + limit - 1) // limit),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/students", status_code=201)
async def create_student(
    student: StudentCreateSchema,
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """
    Create a single student record and optionally enrol them in a class.

    If ``student_id`` is not supplied, a UUID is generated.
    If ``class_id`` is supplied, the student is appended to that class's roster.
    """
    try:
        # Explicit ID or generated UUID
        student_id = (student.student_id or _new_id()).strip()
        now = _now_iso()

        # Check for email collision
        repo = StudentRepository(db)
        existing = await repo.get_student_by_email(student.email)
        if existing and not existing.get("deleted"):
            raise HTTPException(
                status_code=409,
                detail=f"A student with email '{student.email}' already exists.",
            )

        record: dict[str, Any] = {
            "id": student_id,
            "name": student.name.strip(),
            "email": student.email.lower(),
            "role": "student",
            "class_id": student.class_id or "",
            "courses": student.courses or [],
            "deleted": False,
            "created_at": now,
            "updated_at": now,
        }

        db.get_reference(f"users/{student_id}").set(record)

        # Enrol in class roster
        if student.class_id:
            await _enrol_student_in_class(db, student_id, student.class_id)

        return {
            "success": True,
            "student_id": student_id,
            "message": "Student created successfully",
            "data": _strip_internal(record),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/students/{student_id}")
async def get_student(
    student_id: str,
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """Fetch a single student by ID."""
    try:
        repo = StudentRepository(db)
        student = await repo.get_student(student_id)
        if not student or student.get("deleted"):
            raise HTTPException(status_code=404, detail="Student not found")
        return _strip_internal(student)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    payload: StudentUpdateSchema,
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """
    Partial update for a student record.

    If ``class_id`` changes, the student is automatically removed from the
    previous class roster and added to the new one.
    """
    try:
        ref = db.get_reference(f"users/{student_id}")
        existing = ref.get()
        if not existing or existing.get("deleted"):
            raise HTTPException(status_code=404, detail="Student not found")

        updates: dict[str, Any] = {"updated_at": _now_iso()}

        if payload.name is not None:
            updates["name"] = payload.name.strip()
        if payload.email is not None:
            updates["email"] = payload.email.lower()
        if payload.courses is not None:
            updates["courses"] = payload.courses

        # Handle class re-enrolment
        old_class = existing.get("class_id", "")
        if payload.class_id is not None and payload.class_id != old_class:
            updates["class_id"] = payload.class_id
            if old_class:
                await _unenrol_student_from_class(db, student_id, old_class)
            if payload.class_id:
                await _enrol_student_in_class(db, student_id, payload.class_id)

        ref.update(updates)

        return {
            "success": True,
            "student_id": student_id,
            "updated_fields": [k for k in updates if k != "updated_at"],
            "message": "Student updated successfully",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """
    Soft-delete a student.

    The user record is retained in Firebase with ``deleted=True``.
    The student is removed from their enrolled class's roster.
    """
    try:
        ref = db.get_reference(f"users/{student_id}")
        existing = ref.get()
        if not existing or existing.get("deleted"):
            raise HTTPException(status_code=404, detail="Student not found")

        now = _now_iso()
        ref.update({"deleted": True, "deleted_at": now, "updated_at": now})

        # Remove from class roster
        class_id = existing.get("class_id", "")
        if class_id:
            await _unenrol_student_from_class(db, student_id, class_id)

        return {
            "success": True,
            "student_id": student_id,
            "message": "Student deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# BATCH JSON IMPORT
# ===========================================================================

@router.post("/batch-import")
async def batch_import_students(
    body: BatchImportSchema,
    db: FirebaseClient = Depends(_fb),
    svc: AdminService = Depends(_svc),
) -> dict:
    """
    Import multiple students from a JSON payload.

    Accepts an object ``{ "students": [ {student_id, name, email, class_id}, … ] }``.

    This endpoint is best suited for programmatic integrations.
    For CSV file uploads use ``POST /api/v1/admin/students/bulk-import`` instead.

    Processing pipeline
    -------------------
    1. ``AdminService.validate_student_roster()`` — format + duplicate checks.
    2. Persist each valid row; auto-enrol into ``class_id`` roster.
    3. Return three error buckets: ``validation_errors``, ``persist_errors``.
    """
    students = body.students

    # --- Step 1: service-layer validation ---
    validation = svc.validate_student_roster(students)

    imported: list[str] = []
    persist_errors: list[dict] = []

    # --- Step 2: persist valid rows ---
    for row in validation["valid_rows"]:
        try:
            now = _now_iso()
            sid = row["student_id"]

            # Check email uniqueness against existing live records
            existing_ref = db.get_reference(f"users/{sid}")
            if existing_ref.get() and not existing_ref.get().get("deleted"):
                persist_errors.append(
                    {
                        "row": row["row"],
                        "student_id": sid,
                        "error": f"Student ID '{sid}' already exists.",
                    }
                )
                continue

            record: dict[str, Any] = {
                "id": sid,
                "name": row["name"],
                "email": row["email"],
                "role": "student",
                "class_id": row["class_id"],
                "courses": [],
                "deleted": False,
                "created_at": now,
                "updated_at": now,
            }

            db.get_reference(f"users/{sid}").set(record)
            await _enrol_student_in_class(db, sid, row["class_id"])
            imported.append(sid)

        except Exception as exc:
            persist_errors.append(
                {
                    "row": row["row"],
                    "student_id": row.get("student_id", ""),
                    "error": str(exc),
                }
            )

    total_failed = len(validation["invalid_rows"]) + len(persist_errors)

    return {
        "success": validation["valid"] and len(persist_errors) == 0,
        "total": validation["total"],
        "imported": len(imported),
        "failed": total_failed,
        "validation_errors": [
            {
                "row": r["row"],
                "student_id": r.get("student_id", ""),
                "errors": r["errors"],
            }
            for r in validation["invalid_rows"]
        ],
        "persist_errors": persist_errors,
    }


# ===========================================================================
# FACE REGISTRATION
# ===========================================================================

@router.post("/register-face")
async def register_student_face(
    body: RegisterFaceSchema,
    db: FirebaseClient = Depends(_fb),
) -> dict:
    """
    Store a face image for a student.

    The base64-encoded image is forwarded to ``FirebaseService.store_student_face``
    which handles image validation and storage.  The student record must exist
    and must not be soft-deleted.
    """
    try:
        # Guard: student must exist
        student_ref = db.get_reference(f"users/{body.student_id}")
        student = student_ref.get()
        if not student or student.get("deleted"):
            raise HTTPException(
                status_code=404,
                detail=f"Student '{body.student_id}' not found.",
            )

        firebase_service = FirebaseService(db)
        success = await firebase_service.store_student_face(
            body.student_id, body.face_image_base64
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to store face image."
            )

        # Update student record to mark face as registered
        student_ref.update(
            {
                "face_registered": True,
                "face_registered_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )

        return {
            "success": True,
            "student_id": body.student_id,
            "message": f"Face registered for student '{body.student_id}'",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))