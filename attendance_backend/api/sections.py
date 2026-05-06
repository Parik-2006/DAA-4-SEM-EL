"""
api/sections.py — Section, Enrollment, and CourseAssignment management
──────────────────────────────────────────────────────────────────────
Manages the multi-tenant section structure for the attendance system.

Sections are the primary isolation boundary: all attendance, timetable, and
assignments are scoped by section_id at the database level.

Endpoints:
  GET    /api/v1/sections             — List sections (filtered by course, semester)
  POST   /api/v1/sections             — Create a new section
  GET    /api/v1/sections/{section_id} — Get section details
  PUT    /api/v1/sections/{section_id} — Update section
  DELETE /api/v1/sections/{section_id} — Delete section

  GET    /api/v1/enrollments         — List enrollments (admin only)
  POST   /api/v1/enrollments         — Enroll a student in a section
  DELETE /api/v1/enrollments/{enrollment_id} — Unenroll student

  GET    /api/v1/assignments         — List course assignments
  POST   /api/v1/assignments         — Assign teacher to section
  DELETE /api/v1/assignments/{assignment_id} — Remove assignment

All write endpoints require admin role.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database.firebase_client import FirebaseClient
from middleware.auth_middleware import require_role, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["admin-sections"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class SectionCreateRequest(BaseModel):
    """Request to create a section."""
    course_id: str = Field(..., description="Parent course ID")
    section_name: str = Field(..., min_length=1, max_length=10, description="Section name (e.g., CSE C)")
    semester: int = Field(..., ge=1, le=8, description="Semester number")
    year: int = Field(..., ge=2000, le=2100, description="Academic year")
    capacity: Optional[int] = Field(default=60, ge=1, le=200)


class SectionResponse(BaseModel):
    """Response for a section document."""
    section_id: str
    course_id: str
    section_name: str
    semester: int
    year: int
    capacity: int
    created_at: str
    updated_at: str


class SectionListResponse(BaseModel):
    """Paginated section list."""
    data: list[SectionResponse]
    total: int
    page: int
    limit: int


class EnrollmentCreateRequest(BaseModel):
    """Request to enroll a student in a section."""
    student_id: str = Field(..., description="Student ID")
    section_id: str = Field(..., description="Section ID")


class EnrollmentResponse(BaseModel):
    """Response for an enrollment document."""
    enrollment_id: str
    student_id: str
    section_id: str
    enrollment_date: str
    created_at: str


class CourseAssignmentCreateRequest(BaseModel):
    """Request to assign a teacher to a section."""
    teacher_id: str = Field(..., description="Teacher ID")
    section_id: str = Field(..., description="Section ID")
    courses: list[str] = Field(default_factory=list, description="Course IDs taught in this section")
    is_primary: Optional[bool] = Field(default=True, description="Primary assignment indicator")


class CourseAssignmentResponse(BaseModel):
    """Response for a course assignment document."""
    assignment_id: str
    teacher_id: str
    section_id: str
    courses: list[str]
    is_primary: bool
    created_at: str
    updated_at: str


def get_db() -> FirebaseClient:
    """Dependency: get FirebaseClient instance."""
    return FirebaseClient()


# ── SECTIONS ENDPOINTS ─────────────────────────────────────────────────────────

@router.get("/sections", response_model=SectionListResponse)
async def list_sections(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    course_id: Optional[str] = Query(None),
    semester: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    user=Depends(get_current_user),
    db: FirebaseClient = Depends(get_db),
) -> SectionListResponse:
    """
    List sections with optional filters.

    Query Parameters:
      course_id: Filter by parent course (optional)
      semester: Filter by semester (optional)
      year: Filter by academic year (optional)
      page: Page number (default: 1)
      limit: Results per page (default: 50, max: 100)

    Returns paginated section list.
    """
    try:
        sections: list = []

        # Simple filter logic: course_id takes priority, then semester+year
        if course_id:
            sections = db.get_sections_by_course(course_id)
        elif semester is not None and year is not None:
            sections = db.get_sections_by_semester_year(semester, year)
        else:
            # Fallback: get all sections from all courses
            # (This is less efficient; typically filter by course_id or semester+year)
            courses = db.get_all_courses()
            for course in courses:
                cid = course.get("course_id")
                if cid:
                    sections.extend(db.get_sections_by_course(cid))

        # Apply pagination
        total = len(sections)
        start = (page - 1) * limit
        end = start + limit
        paginated = sections[start:end]

        data = [
            SectionResponse(
                section_id=s.get("section_id"),
                course_id=s.get("course_id"),
                section_name=s.get("section_name"),
                semester=s.get("semester"),
                year=s.get("year"),
                capacity=s.get("capacity", 60),
                created_at=s.get("created_at"),
                updated_at=s.get("updated_at"),
            )
            for s in paginated
        ]

        return SectionListResponse(
            data=data,
            total=total,
            page=page,
            limit=limit,
        )

    except Exception as exc:
        logger.error("Error listing sections: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list sections")


@router.post("/sections", response_model=SectionResponse, status_code=201)
async def create_section(
    request: SectionCreateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> SectionResponse:
    """
    Create a new section.

    Request body:
      course_id: str (required) — parent course ID
      section_name: str (required) — e.g., "CSE C"
      semester: int (required, 1-8)
      year: int (required, 2000-2100)
      capacity: int (optional, default 60)

    Returns the created section.
    """
    try:
        # Verify parent course exists
        course = db.get_course(request.course_id)
        if not course:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")

        # Generate section_id
        section_id = f"{request.section_name}_SEM{request.semester}_{request.year}"

        section_data = {
            "section_id": section_id,
            "course_id": request.course_id,
            "section_name": request.section_name,
            "semester": request.semester,
            "year": request.year,
            "capacity": request.capacity or 60,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        success = db.create_section(section_data)
        if not success:
            raise Exception("Firestore write failed")

        return SectionResponse(**section_data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating section: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create section")


@router.get("/sections/{section_id}", response_model=SectionResponse)
async def get_section(
    section_id: str,
    user=Depends(get_current_user),
    db: FirebaseClient = Depends(get_db),
) -> SectionResponse:
    """
    Get section details.

    Path Parameters:
      section_id: Section identifier

    Returns the section document.
    """
    try:
        section = db.get_section(section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        return SectionResponse(**section)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting section %s: %s", section_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve section")


@router.put("/sections/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: str,
    request: SectionCreateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> SectionResponse:
    """
    Update section details.

    Path Parameters:
      section_id: Section identifier

    Request body: same as create (overwrites all fields)

    Returns the updated section.
    """
    try:
        # Verify section exists
        existing = db.get_section(section_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Section not found")

        updates = {
            "course_id": request.course_id,
            "section_name": request.section_name,
            "semester": request.semester,
            "year": request.year,
            "capacity": request.capacity or 60,
            "updated_at": datetime.utcnow().isoformat(),
        }

        success = db.update_section(section_id, updates)
        if not success:
            raise Exception("Firestore update failed")

        updated = db.get_section(section_id)
        return SectionResponse(**updated)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating section %s: %s", section_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update section")


@router.delete("/sections/{section_id}", status_code=204)
async def delete_section(
    section_id: str,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> None:
    """
    Delete a section.

    Path Parameters:
      section_id: Section identifier

    Note: Ensure no enrollments or assignments exist before deletion.
    """
    try:
        # Verify section exists
        section = db.get_section(section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Check for enrollments
        enrollments = db.get_section_students(section_id)
        if enrollments:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete section with active enrollments",
            )

        # Check for assignments
        assignments = db.get_section_teachers(section_id)
        if assignments:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete section with active teacher assignments",
            )

        # Delete from Firestore
        success = db._fs_delete("sections", section_id)
        if not success:
            raise Exception("Firestore delete failed")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting section %s: %s", section_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete section")


# ── ENROLLMENTS ENDPOINTS ──────────────────────────────────────────────────────

@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201)
async def enroll_student(
    request: EnrollmentCreateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> EnrollmentResponse:
    """
    Enroll a student in a section.

    Request body:
      student_id: str (required)
      section_id: str (required)

    Returns the created enrollment document.
    """
    try:
        # Verify section exists
        section = db.get_section(request.section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Generate enrollment_id
        enrollment_id = f"{request.student_id}_{request.section_id}"

        # Check if already enrolled
        existing = db.get_enrollment(enrollment_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Student is already enrolled in this section",
            )

        enrollment_data = {
            "enrollment_id": enrollment_id,
            "student_id": request.student_id,
            "section_id": request.section_id,
            "enrollment_date": datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }

        success = db.enroll_student(enrollment_data)
        if not success:
            raise Exception("Firestore write failed")

        return EnrollmentResponse(**enrollment_data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error enrolling student: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to enroll student")


@router.delete("/enrollments/{enrollment_id}", status_code=204)
async def unenroll_student(
    enrollment_id: str,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> None:
    """
    Unenroll a student from a section.

    Path Parameters:
      enrollment_id: Enrollment document ID (format: {student_id}_{section_id})

    Returns 204 No Content on success.
    """
    try:
        # Verify enrollment exists
        enrollment = db.get_enrollment(enrollment_id)
        if not enrollment:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        # Delete from Firestore
        success = db._fs_delete("enrollments", enrollment_id)
        if not success:
            raise Exception("Firestore delete failed")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error unenrolling student %s: %s", enrollment_id, exc)
        raise HTTPException(status_code=500, detail="Failed to unenroll student")


# ── COURSE ASSIGNMENTS ENDPOINTS ───────────────────────────────────────────────

@router.post("/assignments", response_model=CourseAssignmentResponse, status_code=201)
async def create_assignment(
    request: CourseAssignmentCreateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> CourseAssignmentResponse:
    """
    Assign a teacher to a section.

    Request body:
      teacher_id: str (required)
      section_id: str (required)
      courses: list[str] (optional, default [])
      is_primary: bool (optional, default True)

    Returns the created assignment document.
    """
    try:
        # Verify section exists
        section = db.get_section(request.section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Generate assignment_id
        assignment_id = f"{request.teacher_id}_{request.section_id}"

        # Check if already assigned
        existing = db.get_course_assignment(assignment_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Teacher is already assigned to this section",
            )

        assignment_data = {
            "assignment_id": assignment_id,
            "teacher_id": request.teacher_id,
            "faculty_id": request.teacher_id,  # backward compat alias
            "section_id": request.section_id,
            "courses": request.courses,
            "is_primary": request.is_primary if request.is_primary is not None else True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        success = db.create_course_assignment(assignment_data)
        if not success:
            raise Exception("Firestore write failed")

        return CourseAssignmentResponse(
            assignment_id=assignment_data["assignment_id"],
            teacher_id=assignment_data["teacher_id"],
            section_id=assignment_data["section_id"],
            courses=assignment_data["courses"],
            is_primary=assignment_data["is_primary"],
            created_at=assignment_data["created_at"],
            updated_at=assignment_data["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating assignment: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create assignment")


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: str,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> None:
    """
    Remove a teacher's assignment to a section.

    Path Parameters:
      assignment_id: Assignment document ID (format: {teacher_id}_{section_id})

    Returns 204 No Content on success.
    """
    try:
        # Verify assignment exists
        assignment = db.get_course_assignment(assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Delete from Firestore
        success = db.delete_course_assignment(assignment_id)
        if not success:
            raise Exception("Firestore delete failed")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting assignment %s: %s", assignment_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete assignment")
