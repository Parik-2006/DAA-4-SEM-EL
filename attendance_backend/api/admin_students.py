from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from schemas.attendance_schemas import StudentCreateSchema
from database.student_repository import StudentRepository
from database.firebase_client import FirebaseClient
from services.firebase_service import FirebaseService

router = APIRouter(tags=["admin-students"])

def get_db():
    return FirebaseClient()

@router.get("/students")
async def get_all_students(
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get all students with optional role filtering"""
    try:
        repo = StudentRepository(db)
        students = await repo.get_all_students(role=role)
        
        # Paginate
        start = (page - 1) * limit
        end = start + limit
        paginated = students[start:end]
        
        return {
            "data": paginated,
            "total": len(students),
            "page": page,
            "limit": limit,
            "total_pages": (len(students) + limit - 1) // limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/students")
async def create_student(
    student: StudentCreateSchema,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Create a new student"""
    try:
        repo = StudentRepository(db)
        user_id = await repo.create_student(
            name=student.name,
            email=student.email,
            courses=student.courses or []
        )
        return {
            "success": True,
            "user_id": user_id,
            "message": "Student created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/students/{student_id}")
async def get_student(
    student_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get specific student details"""
    try:
        repo = StudentRepository(db)
        student = await repo.get_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    student: StudentCreateSchema,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Update student details"""
    try:
        repo = StudentRepository(db)
        success = await repo.update_student(
            student_id=student_id,
            name=student.name,
            email=student.email,
            courses=student.courses or []
        )
        if not success:
            raise HTTPException(status_code=404, detail="Student not found")
        return {
            "success": True,
            "message": "Student updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Delete a student"""
    try:
        repo = StudentRepository(db)
        success = await repo.delete_student(student_id)
        if not success:
            raise HTTPException(status_code=404, detail="Student not found")
        return {
            "success": True,
            "message": "Student deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-import")
async def batch_import_students(
    data: dict,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Import multiple students from CSV"""
    try:
        students = data.get("students", [])
        success_count = 0
        failed_count = 0
        errors = []
        
        repo = StudentRepository(db)
        
        for student_data in students:
            try:
                await repo.create_student(
                    name=student_data.get("name"),
                    email=student_data.get("email"),
                    courses=student_data.get("courses", [])
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "email": student_data.get("email"),
                    "error": str(e)
                })
        
        return {
            "success": True,
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(students),
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register-face")
async def register_student_face(
    data: dict,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Register face image for a student"""
    try:
        student_id = data.get("student_id")
        face_image_base64 = data.get("face_image_base64")
        
        if not student_id or not face_image_base64:
            raise HTTPException(status_code=400, detail="Missing student_id or face_image_base64")
        
        # Store face image in Firebase
        firebase_service = FirebaseService(db)
        success = await firebase_service.store_student_face(student_id, face_image_base64)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register face")
        
        return {
            "success": True,
            "message": f"Face registered for student {student_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
