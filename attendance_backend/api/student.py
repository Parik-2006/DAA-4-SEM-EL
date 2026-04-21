from fastapi import APIRouter, Query
from datetime import datetime
from ..database.firebase_client import FirebaseClient
from ..database.student_repository import StudentRepository

router = APIRouter(prefix="/api/v1/student", tags=["student"])


@router.get("/attendance/today")
async def get_today_attendance(student_id: str):
    """Get student's attendance status for today"""
    try:
        fb = FirebaseClient()
        today = datetime.now().strftime("%Y-%m-%d")
        
        ref = fb.db.reference(f"attendance/{today}/{student_id}")
        data = ref.get()
        
        if data and isinstance(data, dict):
            return data
        return {"status": "not_marked"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/attendance/history")
async def get_attendance_history(student_id: str, limit: int = Query(30, le=100)):
    """Get student's attendance history"""
    try:
        fb = FirebaseClient()
        ref = fb.db.reference("attendance")
        all_dates = ref.get() or {}
        
        records = []
        for date in sorted(all_dates.keys(), reverse=True):
            if isinstance(all_dates[date], dict) and student_id in all_dates[date]:
                record = all_dates[date][student_id].copy() if isinstance(all_dates[date][student_id], dict) else {}
                record['date'] = date
                records.append(record)
                if len(records) >= limit:
                    break
        
        return {"records": records}
    except Exception as e:
        return {"records": [], "error": str(e)}
