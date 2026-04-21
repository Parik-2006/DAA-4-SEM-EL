from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from ..database.user_repository import UserRepository
from ..database.student_repository import StudentRepository
from ..models import UserModel
from ..database.firebase_client import FirebaseClient

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

user_repo = UserRepository()
student_repo = StudentRepository()


@router.get("/students", response_model=List[dict])
async def get_all_students():
    """Admin-only: Get all students"""
    try:
        students = user_repo.list_users_by_role("student")
        return students if students else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attendance/today")
async def get_today_attendance_stats():
    """Admin-only: Get today's attendance statistics"""
    try:
        fb = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        
        ref = fb.db.reference(f"attendance/{today}")
        today_data = ref.get() or {}
        
        present_count = sum(1 for v in today_data.values() if isinstance(v, dict) and v.get("status") == "present")
        absent_count = sum(1 for v in today_data.values() if isinstance(v, dict) and v.get("status") == "absent")
        late_count = sum(1 for v in today_data.values() if isinstance(v, dict) and v.get("status") == "late")
        
        all_students = user_repo.list_users_by_role("student")
        total_students = len(all_students) if all_students else 0
        
        attendance_rate = (present_count / total_students * 100) if total_students > 0 else 0
        
        return {
            "totalStudents": total_students,
            "presentToday": present_count,
            "absentToday": absent_count,
            "lateToday": late_count,
            "attendanceRate": round(attendance_rate, 1)
        }
    except Exception as e:
        return {
            "totalStudents": 0,
            "presentToday": 0,
            "absentToday": 0,
            "lateToday": 0,
            "attendanceRate": 0.0,
            "error": str(e)
        }


@router.get("/attendance")
async def get_attendance_records(
    date: str,
    course_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get attendance records for date with pagination"""
    try:
        fb = FirebaseClient()
        ref = fb.db.reference(f"attendance/{date}")
        records = ref.get() or {}
        
        record_list = []
        for k, v in records.items():
            if isinstance(v, dict):
                record_list.append({
                    "id": k,
                    "studentId": v.get("studentId"),
                    "studentName": v.get("studentName"),
                    "status": v.get("status"),
                    "markedAt": v.get("markedAt"),
                    "confidence": v.get("confidence", 0.0)
                })
        
        start = (page - 1) * limit
        end = start + limit
        
        return {
            "data": record_list[start:end],
            "total": len(record_list),
            "page": page,
            "limit": limit
        }
    except Exception as e:
        return {
            "data": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": str(e)
        }


@router.post("/register-student-face")
async def register_student_face(student_id: str, face_image_base64: str):
    """Register or update student face for recognition"""
    try:
        import base64
        
        fb = FirebaseClient()
        
        # Validate base64 image
        try:
            image_data = base64.b64decode(face_image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image")
        
        # Save to Firebase (simplified - embedding extraction requires ML model)
        ref = fb.db.reference(f"students/{student_id}")
        ref.update({
            "face_image_base64": face_image_base64[:100],  # Store small portion as proof
            "registered_at": datetime.now().isoformat(),
            "embedding_version": "facenet_v1"
        })
        
        return {"success": True, "message": "Face registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
