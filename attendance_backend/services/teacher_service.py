"""
Teacher Service - Business logic for teacher portal operations.

Handles:
- Dashboard data (today's classes, current period)
- Attendance marking and editing
- Attendance history and reports
- Period status and locking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from firebase_admin.exceptions import NotFoundError

from database.firebase_client import FirebaseClient
from config.constants import (
    STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_EXCUSED,
    PERIOD_OPEN, PERIOD_CLOSED, PERIOD_LOCKED,
    ATTENDANCE_WINDOW_AFTER_PERIOD_MINUTES,
    LATE_THRESHOLD_MINUTES,
    COLLECTION_TIMETABLE, COLLECTION_ATTENDANCE, COLLECTION_CLASSES
)

logger = logging.getLogger(__name__)


class TeacherService:
    """Service class for teacher-related operations."""
    
    def __init__(self, db: FirebaseClient = None):
        """Initialize teacher service with database client."""
        self.db = db or FirebaseClient()
    
    def get_teacher_dashboard(self, teacher_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get teacher dashboard data for a specific date.
        
        Args:
            teacher_id: Faculty ID
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Dashboard data with today's classes, current period, stats
        """
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # Get day of week
            day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A").lower()
            
            # Get all periods for this teacher on this day
            teacher_periods = self._get_teacher_periods_by_day(teacher_id, day_name)
            
            # Get current period
            current_period = self._get_current_active_period(teacher_id, day_name)
            
            # Get attendance stats for today
            today_stats = self._get_today_attendance_stats(teacher_id, date)
            
            return {
                "success": True,
                "date": date,
                "day": day_name,
                "teacher_id": teacher_id,
                "periods": teacher_periods,
                "current_period": current_period,
                "today_stats": today_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting teacher dashboard: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_active_class(self, teacher_id: str) -> Dict[str, Any]:
        """
        Get currently active class period for teacher with student roster.
        
        Args:
            teacher_id: Faculty ID
            
        Returns:
            Active class details with student roster and face photos
        """
        try:
            # Get current day and time
            now = datetime.now()
            day_name = now.strftime("%A").lower()
            current_time = now.strftime("%H:%M")
            
            # Find matching period
            periods = self._get_periods_by_day_and_time(teacher_id, day_name, current_time)
            
            if not periods:
                return {
                    "success": False,
                    "message": "No active class right now",
                    "active": False,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            period = periods[0]
            class_id = period.get("class_id")
            period_id = period.get("period_id")
            
            # Get student roster
            roster = self._get_class_roster_with_faces(class_id)
            
            # Get period status
            period_status = self._check_period_attendance_status(period_id)
            
            return {
                "success": True,
                "active": True,
                "period_id": period_id,
                "class_id": class_id,
                "course_name": period.get("course_name"),
                "course_code": period.get("course_code"),
                "start_time": period.get("start_time"),
                "end_time": period.get("end_time"),
                "is_lab_class": period.get("is_lab_class", False),
                "roster": roster,
                "roster_count": len(roster),
                "period_status": period_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting active class: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_class_roster(self, class_id: str, include_faces: bool = True) -> Dict[str, Any]:
        """
        Get student roster for a class.
        
        Args:
            class_id: Class ID
            include_faces: Include face photo URLs
            
        Returns:
            Student list with optional face photos
        """
        try:
            roster = self._get_class_roster_with_faces(class_id) if include_faces else \
                     self._get_class_roster_without_faces(class_id)
            
            return {
                "success": True,
                "class_id": class_id,
                "roster": roster,
                "total_students": len(roster),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting class roster: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_attendance_window_status(self, period_id: str) -> Dict[str, Any]:
        """
        Check if attendance window is open for marking.
        
        Args:
            period_id: Period/Timetable ID
            
        Returns:
            Status dict with is_open, time_remaining, can_edit flags
        """
        try:
            period = self._get_period_by_id(period_id)
            
            if not period:
                return {"success": False, "error": "Period not found"}
            
            now = datetime.now()
            start_time = datetime.strptime(period.get("start_time"), "%H:%M").time()
            end_time = datetime.strptime(period.get("end_time"), "%H:%M").time()
            
            # Calculate attendance window
            current_time = now.time()
            window_end = (datetime.combine(datetime.today(), end_time) + 
                         timedelta(minutes=ATTENDANCE_WINDOW_AFTER_PERIOD_MINUTES)).time()
            
            is_open = start_time <= current_time <= window_end
            can_edit = current_time <= window_end
            
            # Calculate time remaining
            if is_open and can_edit:
                window_end_dt = datetime.combine(datetime.today(), window_end)
                time_remaining = int((window_end_dt - now).total_seconds() / 60)
            else:
                time_remaining = 0
            
            is_locked = period.get("status") == PERIOD_LOCKED
            
            return {
                "success": True,
                "period_id": period_id,
                "is_open": is_open,
                "can_edit": can_edit and not is_locked,
                "is_locked": is_locked,
                "time_remaining_minutes": max(0, time_remaining),
                "period_start": period.get("start_time"),
                "period_end": period.get("end_time"),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error checking attendance window: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def mark_attendance_bulk(self, period_id: str, attendance_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Mark attendance for multiple students in a period.
        
        Args:
            period_id: Period ID
            attendance_list: List of dicts with student_id, status, confidence
            
        Returns:
            Result with success count and errors
        """
        try:
            # Check if attendance window is open
            window_status = self.get_attendance_window_status(period_id)
            if not window_status.get("is_open"):
                return {
                    "success": False,
                    "error": "Attendance window is closed",
                    "window_status": window_status
                }
            
            # Validate all entries
            validated = []
            errors = []
            
            for idx, entry in enumerate(attendance_list):
                try:
                    student_id = entry.get("student_id")
                    status = entry.get("status")
                    confidence = entry.get("confidence", 0.0)
                    
                    if not student_id or not status:
                        errors.append({
                            "index": idx,
                            "error": "Missing student_id or status"
                        })
                        continue
                    
                    if status not in [STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_EXCUSED]:
                        errors.append({
                            "index": idx,
                            "error": f"Invalid status: {status}"
                        })
                        continue
                    
                    validated.append({
                        "student_id": student_id,
                        "status": status,
                        "confidence": confidence
                    })
                
                except Exception as e:
                    errors.append({"index": idx, "error": str(e)})
            
            # Batch insert attendance records
            success_count = 0
            for entry in validated:
                try:
                    record = {
                        "period_id": period_id,
                        "student_id": entry["student_id"],
                        "status": entry["status"],
                        "confidence": entry["confidence"],
                        "marked_by": "teacher",
                        "timestamp": datetime.utcnow().isoformat(),
                        "is_locked": False
                    }
                    
                    self.db.add_document(COLLECTION_ATTENDANCE, record)
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Error marking attendance for student {entry['student_id']}: {e}")
                    errors.append({
                        "student_id": entry["student_id"],
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "period_id": period_id,
                "marked_count": success_count,
                "total_submitted": len(attendance_list),
                "errors": errors,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error bulk marking attendance: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def edit_attendance(self, record_id: str, new_status: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Edit a single attendance record before lock.
        
        Args:
            record_id: Attendance record ID
            new_status: New status (present/absent/late/excused)
            reason: Reason for edit
            
        Returns:
            Updated record or error
        """
        try:
            # Get record
            record = self.db.get_document(COLLECTION_ATTENDANCE, record_id)
            
            if not record:
                return {"success": False, "error": "Record not found"}
            
            # Check if locked
            if record.get("is_locked"):
                return {
                    "success": False,
                    "error": "Cannot edit locked record"
                }
            
            # Validate new status
            if new_status not in [STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_EXCUSED]:
                return {
                    "success": False,
                    "error": f"Invalid status: {new_status}"
                }
            
            # Update record
            update_data = {
                "status": new_status,
                "edited_at": datetime.utcnow().isoformat(),
                "previous_status": record.get("status"),
                "edit_reason": reason
            }
            
            self.db.update_document(COLLECTION_ATTENDANCE, record_id, update_data)
            
            logger.info(f"Attendance record {record_id} updated from {record.get('status')} to {new_status}")
            
            return {
                "success": True,
                "record_id": record_id,
                "old_status": record.get("status"),
                "new_status": new_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error editing attendance record: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_attendance_history(self, teacher_id: str, class_id: Optional[str] = None,
                              date_from: Optional[str] = None, date_to: Optional[str] = None,
                              limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get attendance history for teacher's classes.
        
        Args:
            teacher_id: Faculty ID
            class_id: Optional class filter
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Pagination limit
            offset: Pagination offset
            
        Returns:
            Paginated attendance history
        """
        try:
            # Query attendance records
            records = self._query_attendance_history(
                teacher_id, class_id, date_from, date_to, limit, offset
            )
            
            return {
                "success": True,
                "teacher_id": teacher_id,
                "records": records,
                "total": len(records),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting attendance history: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_daily_report(self, class_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get attendance report for a class on a specific date.
        
        Args:
            class_id: Class ID
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Daily attendance summary with stats
        """
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # Get all periods for this class on this date
            day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A").lower()
            periods = self._get_class_periods_by_day(class_id, day_name)
            
            # Get attendance for each period
            period_attendance = []
            total_present = 0
            total_absent = 0
            total_late = 0
            
            for period in periods:
                period_id = period.get("period_id")
                attendance = self._get_period_attendance(period_id)
                
                present_count = sum(1 for a in attendance if a.get("status") == STATUS_PRESENT)
                absent_count = sum(1 for a in attendance if a.get("status") == STATUS_ABSENT)
                late_count = sum(1 for a in attendance if a.get("status") == STATUS_LATE)
                
                total_present += present_count
                total_absent += absent_count
                total_late += late_count
                
                period_attendance.append({
                    "period_id": period_id,
                    "course_name": period.get("course_name"),
                    "time": f"{period.get('start_time')} - {period.get('end_time')}",
                    "present": present_count,
                    "absent": absent_count,
                    "late": late_count,
                    "total": len(attendance)
                })
            
            return {
                "success": True,
                "class_id": class_id,
                "date": date,
                "period_attendance": period_attendance,
                "summary": {
                    "total_present": total_present,
                    "total_absent": total_absent,
                    "total_late": total_late
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting daily report: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_teacher_by_id(self, teacher_id: str) -> Dict[str, Any]:
        """
        Get teacher information.
        
        Args:
            teacher_id: Faculty ID
            
        Returns:
            Teacher details
        """
        try:
            # Query from Firebase (assumes Faculty collection exists)
            # This is a placeholder - adjust based on your actual structure
            teacher = self.db.get_document("faculty", teacher_id)
            
            if not teacher:
                return {
                    "success": False,
                    "error": "Teacher not found"
                }
            
            return {
                "success": True,
                "teacher_id": teacher_id,
                "name": teacher.get("name"),
                "email": teacher.get("email"),
                "department": teacher.get("department"),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting teacher: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== Private Helper Methods ====================
    
    def _get_teacher_periods_by_day(self, teacher_id: str, day_name: str) -> List[Dict[str, Any]]:
        """Get all periods taught by teacher on a specific day."""
        # Implement based on your Firestore structure
        try:
            # Query timetable for this teacher and day
            periods = self.db.query_documents(
                COLLECTION_TIMETABLE,
                [("faculty_id", "==", teacher_id), ("day_of_week", "==", day_name)]
            )
            return periods or []
        except Exception as e:
            logger.error(f"Error getting teacher periods: {e}")
            return []
    
    def _get_current_active_period(self, teacher_id: str, day_name: str) -> Optional[Dict[str, Any]]:
        """Get currently active period for teacher."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        periods = self._get_periods_by_day_and_time(teacher_id, day_name, current_time)
        return periods[0] if periods else None
    
    def _get_periods_by_day_and_time(self, teacher_id: str, day_name: str, current_time: str) -> List[Dict]:
        """Get periods matching day and time."""
        try:
            all_periods = self._get_teacher_periods_by_day(teacher_id, day_name)
            matching = []
            
            for period in all_periods:
                start = period.get("start_time")
                end = period.get("end_time")
                
                if start <= current_time <= end:
                    matching.append(period)
            
            return matching
        except Exception as e:
            logger.error(f"Error getting periods by time: {e}")
            return []
    
    def _get_class_roster_with_faces(self, class_id: str) -> List[Dict[str, Any]]:
        """Get student roster with face photos."""
        try:
            students = self.db.query_documents(
                "students",
                [("class_id", "==", class_id)]
            )
            
            roster = []
            for student in students:
                roster.append({
                    "student_id": student.get("student_id"),
                    "name": student.get("name"),
                    "roll_no": student.get("roll_no"),
                    "email": student.get("email"),
                    "face_photo_url": student.get("face_photo_url"),
                    "face_embedding": student.get("face_embedding")
                })
            
            return roster
        except Exception as e:
            logger.error(f"Error getting roster: {e}")
            return []
    
    def _get_class_roster_without_faces(self, class_id: str) -> List[Dict[str, str]]:
        """Get student roster without face data."""
        try:
            students = self.db.query_documents(
                "students",
                [("class_id", "==", class_id)]
            )
            
            return [
                {
                    "student_id": s.get("student_id"),
                    "name": s.get("name"),
                    "roll_no": s.get("roll_no"),
                    "email": s.get("email")
                }
                for s in students
            ]
        except Exception as e:
            logger.error(f"Error getting roster: {e}")
            return []
    
    def _check_period_attendance_status(self, period_id: str) -> Dict[str, Any]:
        """Check attendance marking status for a period."""
        try:
            window_status = self.get_attendance_window_status(period_id)
            return window_status
        except Exception as e:
            logger.error(f"Error checking period status: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_period_by_id(self, period_id: str) -> Optional[Dict]:
        """Get period details by ID."""
        try:
            return self.db.get_document(COLLECTION_TIMETABLE, period_id)
        except Exception as e:
            logger.error(f"Error getting period: {e}")
            return None
    
    def _get_today_attendance_stats(self, teacher_id: str, date: str) -> Dict[str, int]:
        """Get attendance statistics for today."""
        try:
            day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A").lower()
            periods = self._get_teacher_periods_by_day(teacher_id, day_name)
            
            marked_count = 0
            for period in periods:
                attendance = self._get_period_attendance(period.get("period_id"))
                if attendance:
                    marked_count += len(attendance)
            
            return {
                "total_classes": len(periods),
                "marked_attendance": marked_count
            }
        except Exception as e:
            logger.error(f"Error getting attendance stats: {e}")
            return {"total_classes": 0, "marked_attendance": 0}
    
    def _get_class_periods_by_day(self, class_id: str, day_name: str) -> List[Dict]:
        """Get all periods for a class on a day."""
        try:
            periods = self.db.query_documents(
                COLLECTION_TIMETABLE,
                [("class_id", "==", class_id), ("day_of_week", "==", day_name)]
            )
            return periods or []
        except Exception as e:
            logger.error(f"Error getting class periods: {e}")
            return []
    
    def _get_period_attendance(self, period_id: str) -> List[Dict]:
        """Get all attendance records for a period."""
        try:
            records = self.db.query_documents(
                COLLECTION_ATTENDANCE,
                [("period_id", "==", period_id)]
            )
            return records or []
        except Exception as e:
            logger.error(f"Error getting period attendance: {e}")
            return []
    
    def _query_attendance_history(self, teacher_id: str, class_id: Optional[str],
                                 date_from: Optional[str], date_to: Optional[str],
                                 limit: int, offset: int) -> List[Dict]:
        """Query attendance history with filters."""
        try:
            # Build query conditions
            conditions = []
            
            if class_id:
                # Get periods for this class first
                periods = self.db.query_documents(
                    COLLECTION_TIMETABLE,
                    [("class_id", "==", class_id)]
                )
                period_ids = [p.get("period_id") for p in periods]
            
            # Query attendance records
            records = self.db.query_documents(COLLECTION_ATTENDANCE, conditions)
            
            # Filter by period if class_id specified
            if class_id:
                records = [r for r in records if r.get("period_id") in period_ids]
            
            # Filter by date range
            if date_from or date_to:
                records = self._filter_by_date_range(records, date_from, date_to)
            
            # Apply pagination
            return records[offset:offset+limit]
        
        except Exception as e:
            logger.error(f"Error querying attendance history: {e}")
            return []
    
    def _filter_by_date_range(self, records: List[Dict], date_from: Optional[str],
                             date_to: Optional[str]) -> List[Dict]:
        """Filter records by date range."""
        filtered = records
        
        if date_from:
            filtered = [r for r in filtered if r.get("timestamp", "") >= date_from]
        
        if date_to:
            filtered = [r for r in filtered if r.get("timestamp", "") <= date_to]
        
        return filtered
