"""
api/courses.py — Course management endpoints (Firestore-backed)
────────────────────────────────────────────────────────────────
Manages Course documents in Firestore.

Endpoints:
  GET    /api/v1/courses             — List all courses (paginated)
  POST   /api/v1/courses             — Create a new course
  GET    /api/v1/courses/{course_id} — Get course details
  PUT    /api/v1/courses/{course_id} — Update course
  DELETE /api/v1/courses/{course_id} — Delete course

All endpoints require admin role for write operations.
Read operations are available to all authenticated users.
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

router = APIRouter(prefix="/api/v1", tags=["admin-courses"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CourseCreateRequest(BaseModel):
    """Request body for creating a course."""
    name: str = Field(..., min_length=1, max_length=255, description="Course name")
    code: str = Field(..., min_length=1, max_length=50, description="Course code")
    description: Optional[str] = Field(None, max_length=1000, description="Course description")
    credits: int = Field(default=4, ge=1, le=8, description="Course credits")
    department: Optional[str] = Field(None, description="Department name")


class CourseUpdateRequest(BaseModel):
    """Request body for updating a course."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    credits: Optional[int] = Field(None, ge=1, le=8)
    department: Optional[str] = Field(None)


class CourseResponse(BaseModel):
    """Response body for a single course."""
    course_id: str
    name: str
    code: str
    description: Optional[str] = None
    credits: int
    department: Optional[str] = None
    created_at: str
    updated_at: str


class CourseListResponse(BaseModel):
    """Response body for paginated course list."""
    data: list[CourseResponse]
    total: int
    page: int
    limit: int


def get_db() -> FirebaseClient:
    """Dependency: get FirebaseClient instance."""
    return FirebaseClient()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/courses", response_model=CourseListResponse)
async def list_courses(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    department: Optional[str] = Query(None),
    user=Depends(get_current_user),
    db: FirebaseClient = Depends(get_db),
) -> CourseListResponse:
    """
    List all courses (paginated).

    Query Parameters:
      page: Page number (default: 1)
      limit: Results per page (default: 50, max: 100)
      department: Filter by department (optional)

    Returns paginated course list.
    """
    try:
        # Get all courses
        courses = db.get_all_courses(department=department)

        # Apply pagination
        total = len(courses)
        start = (page - 1) * limit
        end = start + limit
        paginated = courses[start:end]

        # Convert to response schema
        data = [
            CourseResponse(
                course_id=c.get("course_id"),
                name=c.get("name"),
                code=c.get("code"),
                description=c.get("description"),
                credits=c.get("credits"),
                department=c.get("department"),
                created_at=c.get("created_at"),
                updated_at=c.get("updated_at"),
            )
            for c in paginated
        ]

        return CourseListResponse(
            data=data,
            total=total,
            page=page,
            limit=limit,
        )

    except Exception as exc:
        logger.error("Error listing courses: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list courses")


@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course(
    request: CourseCreateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> CourseResponse:
    """
    Create a new course.

    Request body:
      name: str (required, 1-255 chars)
      code: str (required, 1-50 chars)
      description: str (optional)
      credits: int (default 4, 1-8)
      department: str (optional)

    Returns the created course with generated course_id.
    """
    try:
        # Generate course_id from code + uuid suffix for uniqueness
        course_id = f"{request.code.upper()}_{str(uuid4())[:8]}"

        course_data = {
            "course_id": course_id,
            "name": request.name,
            "code": request.code.upper(),
            "description": request.description or "",
            "credits": request.credits,
            "department": request.department or "",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Create in Firestore
        success = db.create_course(course_data)
        if not success:
            raise Exception("Firestore write failed")

        return CourseResponse(**course_data)

    except ValueError as exc:
        logger.error("Validation error creating course: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Error creating course: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create course")


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    user=Depends(get_current_user),
    db: FirebaseClient = Depends(get_db),
) -> CourseResponse:
    """
    Get course details by ID.

    Path Parameters:
      course_id: Course identifier

    Returns the course document.
    """
    try:
        course = db.get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        return CourseResponse(**course)

    except Exception as exc:
        logger.error("Error getting course %s: %s", course_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve course")


@router.put("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    request: CourseUpdateRequest,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> CourseResponse:
    """
    Update course details.

    Path Parameters:
      course_id: Course identifier

    Request body (all fields optional):
      name, code, description, credits, department

    Returns the updated course.
    """
    try:
        # Verify course exists
        existing = db.get_course(course_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Course not found")

        # Build updates dict (only non-None fields)
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.code is not None:
            updates["code"] = request.code.upper()
        if request.description is not None:
            updates["description"] = request.description
        if request.credits is not None:
            updates["credits"] = request.credits
        if request.department is not None:
            updates["department"] = request.department

        if not updates:
            # No updates provided
            return CourseResponse(**existing)

        # Update in Firestore
        success = db.update_course(course_id, updates)
        if not success:
            raise Exception("Firestore update failed")

        # Fetch updated document
        updated = db.get_course(course_id)
        return CourseResponse(**updated)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating course %s: %s", course_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update course")


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(
    course_id: str,
    user=Depends(require_role("admin")),
    db: FirebaseClient = Depends(get_db),
) -> None:
    """
    Delete a course.

    Path Parameters:
      course_id: Course identifier

    Note: Ensure no sections are linked to this course before deletion.
    """
    try:
        # Verify course exists
        course = db.get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check if sections exist for this course
        sections = db.get_sections_by_course(course_id)
        if sections:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete course with active sections. Delete sections first.",
            )

        # Delete from Firestore
        success = db._fs_delete("courses", course_id)
        if not success:
            raise Exception("Firestore delete failed")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting course %s: %s", course_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete course")


@router.get("/courses/{course_id}/enrolled-students")
async def get_enrolled_students(
    course_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get students enrolled in a course"""
    try:
        enrollments_ref = db.get_reference("course_enrollments").child(course_id)
        enrollments = _ensure_dict(_safe_get(enrollments_ref))
        students = []
        for student_id, enrollment_data in enrollments.items():
            students.append({
                "student_id": student_id,
                "enrolled_at": (enrollment_data or {}).get("enrolled_at")
            })
        
        return {
            "course_id": course_id,
            "students": students,
            "total": len(students)
        }
    except NotFoundError:
        return {"course_id": course_id, "students": [], "total": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/courses/{course_id}/enroll/{student_id}")
async def enroll_student(
    course_id: str,
    student_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Enroll a student in a course"""
    try:
        # Check course exists
        course_ref = db.get_reference("courses").child(course_id)
        if not isinstance(_safe_get(course_ref), dict):
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Add enrollment
        enrollment_ref = db.get_reference("course_enrollments").child(course_id).child(student_id)
        enrollment_ref.set({
            "enrolled_at": datetime.now().isoformat()
        })
        
        # Update enrollment count
        enrollments = _ensure_dict(_safe_get(db.get_reference("course_enrollments").child(course_id)))
        course_ref.update({"enrolled_students": len(enrollments)})
        
        return {
            "success": True,
            "message": f"Student {student_id} enrolled in course {course_id}"
        }
    except NotFoundError:
        raise HTTPException(status_code=503, detail="Realtime database is not configured")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/courses/{course_id}/unenroll/{student_id}")
async def unenroll_student(
    course_id: str,
    student_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Remove a student from a course"""
    try:
        enrollment_ref = db.get_reference("course_enrollments").child(course_id).child(student_id)
        enrollment_ref.delete()
        
        # Update enrollment count
        course_ref = db.get_reference("courses").child(course_id)
        enrollments = _ensure_dict(_safe_get(db.get_reference("course_enrollments").child(course_id)))
        course_ref.update({"enrolled_students": len(enrollments)})
        
        return {
            "success": True,
            "message": f"Student {student_id} unenrolled from course {course_id}"
        }
    except NotFoundError:
        raise HTTPException(status_code=503, detail="Realtime database is not configured")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
