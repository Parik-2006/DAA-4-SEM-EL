from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from database.firebase_client import FirebaseClient
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin-courses"])

class CourseSchema(BaseModel):
    name: str
    code: str
    schedule: str
    room: str
    active: Optional[bool] = True

def get_db():
    return FirebaseClient()

@router.get("/courses")
async def get_all_courses(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get all courses"""
    try:
        courses_ref = db.db.reference("courses")
        courses_data = courses_ref.get()
        
        if not courses_data:
            return {
                "data": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0
            }
        
        courses = []
        for course_id, course_info in courses_data.items():
            course_info['id'] = course_id
            courses.append(course_info)
        
        # Paginate
        start = (page - 1) * limit
        end = start + limit
        paginated = courses[start:end]
        
        return {
            "data": paginated,
            "total": len(courses),
            "page": page,
            "limit": limit,
            "total_pages": (len(courses) + limit - 1) // limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/courses")
async def create_course(
    course: CourseSchema,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Create a new course"""
    try:
        course_id = str(uuid.uuid4())
        course_data = {
            "name": course.name,
            "code": course.code,
            "schedule": course.schedule,
            "room": course.room,
            "active": course.active,
            "enrolled_students": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        courses_ref = db.db.reference("courses").child(course_id)
        courses_ref.set(course_data)
        
        return {
            "success": True,
            "id": course_id,
            "message": "Course created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get specific course details"""
    try:
        course_ref = db.db.reference("courses").child(course_id)
        course = course_ref.get()
        
        if not course.val():
            raise HTTPException(status_code=404, detail="Course not found")
        
        course_data = course.val()
        course_data['id'] = course_id
        return course_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/courses/{course_id}")
async def update_course(
    course_id: str,
    course: CourseSchema,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Update course details"""
    try:
        course_ref = db.db.reference("courses").child(course_id)
        existing = course_ref.get()
        
        if not existing.val():
            raise HTTPException(status_code=404, detail="Course not found")
        
        update_data = {
            "name": course.name,
            "code": course.code,
            "schedule": course.schedule,
            "room": course.room,
            "active": course.active,
            "updated_at": datetime.now().isoformat()
        }
        
        course_ref.update(update_data)
        
        return {
            "success": True,
            "message": "Course updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/courses/{course_id}")
async def toggle_course(
    course_id: str,
    data: dict,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Toggle course active status"""
    try:
        course_ref = db.db.reference("courses").child(course_id)
        existing = course_ref.get()
        
        if not existing.val():
            raise HTTPException(status_code=404, detail="Course not found")
        
        active = data.get("active", True)
        course_ref.update({"active": active})
        
        return {
            "success": True,
            "message": f"Course {'activated' if active else 'deactivated'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Delete a course"""
    try:
        course_ref = db.db.reference("courses").child(course_id)
        existing = course_ref.get()
        
        if not existing.val():
            raise HTTPException(status_code=404, detail="Course not found")
        
        course_ref.delete()
        
        return {
            "success": True,
            "message": "Course deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/courses/{course_id}/enrolled-students")
async def get_enrolled_students(
    course_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get students enrolled in a course"""
    try:
        enrollments_ref = db.db.reference("course_enrollments").child(course_id)
        enrollments = enrollments_ref.get()
        
        students = []
        if enrollments.val():
            for student_id, enrollment_data in enrollments.val().items():
                students.append({
                    "student_id": student_id,
                    "enrolled_at": enrollment_data.get("enrolled_at")
                })
        
        return {
            "course_id": course_id,
            "students": students,
            "total": len(students)
        }
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
        course_ref = db.db.reference("courses").child(course_id)
        if not course_ref.get().val():
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Add enrollment
        enrollment_ref = db.db.reference("course_enrollments").child(course_id).child(student_id)
        enrollment_ref.set({
            "enrolled_at": datetime.now().isoformat()
        })
        
        # Update enrollment count
        course_ref.update({
            "enrolled_students": db.db.reference("course_enrollments").child(course_id).get().count()
        })
        
        return {
            "success": True,
            "message": f"Student {student_id} enrolled in course {course_id}"
        }
    except HTTPException:
        raise
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
        enrollment_ref = db.db.reference("course_enrollments").child(course_id).child(student_id)
        enrollment_ref.delete()
        
        # Update enrollment count
        course_ref = db.db.reference("courses").child(course_id)
        course_ref.update({
            "enrolled_students": db.db.reference("course_enrollments").child(course_id).get().count()
        })
        
        return {
            "success": True,
            "message": f"Student {student_id} unenrolled from course {course_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
