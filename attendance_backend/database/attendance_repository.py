"""
Attendance Data Repository.

Provides operations for recording and querying attendance records.
"""

from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, date, timedelta

from database.firebase_client import FirebaseClient
from config.constants import (
    FIREBASE_COLLECTIONS,
    AttendanceStatus,
    DB_FIELD_STUDENT_ID,
    DB_FIELD_COURSE_ID,
    DB_FIELD_TIMESTAMP,
    DB_FIELD_ATTENDANCE_DATE,
    DB_FIELD_ATTENDANCE_TIME,
    DB_FIELD_CONFIDENCE_SCORE,
    ATTENDANCE_RETENTION_DAYS,
)


logger = logging.getLogger(__name__)


class AttendanceRepository:
    """
    Repository for attendance record operations.
    
    Handles recording and querying attendance data in Firebase.
    """
    
    def __init__(self):
        """Initialize repository with Firebase client."""
        self.db = FirebaseClient()
        self.collection = FIREBASE_COLLECTIONS['attendance']
    
    def mark_attendance(
        self,
        student_id: str,
        course_id: str,
        confidence_score: float,
        status: str = AttendanceStatus.PRESENT,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record attendance for student.
        
        Args:
            student_id: Student identifier
            course_id: Course identifier
            confidence_score: Face recognition confidence (0-1)
            status: Attendance status (present, absent, late, etc.)
            timestamp: Record timestamp (uses current time if None)
            metadata: Additional metadata
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            # Create unique record ID
            record_id = f"{student_id}_{timestamp.isoformat()}"
            
            data = {
                DB_FIELD_STUDENT_ID: student_id,
                DB_FIELD_COURSE_ID: course_id,
                DB_FIELD_ATTENDANCE_DATE: timestamp.strftime("%Y-%m-%d"),
                DB_FIELD_ATTENDANCE_TIME: timestamp.strftime("%H:%M:%S"),
                DB_FIELD_TIMESTAMP: timestamp.isoformat(),
                'status': status,
                DB_FIELD_CONFIDENCE_SCORE: confidence_score,
            }
            
            if metadata:
                data.update(metadata)
            
            path = f"{self.collection}/{record_id}"
            success = self.db.write_data(path, data)
            
            if success:
                logger.info(f"Marked attendance for {student_id} in {course_id}")
            else:
                logger.error(f"Failed to mark attendance for {student_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error marking attendance: {e}")
            return False
    
    def get_student_attendance(
        self,
        student_id: str,
        course_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records for student.
        
        Args:
            student_id: Student identifier
            course_id: Filter by course (optional)
            start_date: Start date (optional)
            end_date: End date (optional)
        
        Returns:
            List of attendance records
        """
        try:
            path = self.collection
            data = self.db.read_data(path)
            
            if not data:
                return []
            
            # Filter to current student
            records = [
                r for r in data.values()
                if isinstance(r, dict) and r.get(DB_FIELD_STUDENT_ID) == student_id
            ]
            
            # Filter by course if specified
            if course_id:
                records = [r for r in records if r.get(DB_FIELD_COURSE_ID) == course_id]
            
            # Filter by date range
            if start_date or end_date:
                records = self._filter_by_date_range(records, start_date, end_date)
            
            logger.debug(f"Retrieved {len(records)} attendance records for {student_id}")
            return records
        
        except Exception as e:
            logger.error(f"Error retrieving attendance for {student_id}: {e}")
            return []
    
    def get_course_attendance(
        self,
        course_id: str,
        date_filter: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all attendance records for a course.
        
        Args:
            course_id: Course identifier
            date_filter: Filter to specific date (optional)
        
        Returns:
            List of attendance records
        """
        try:
            path = self.collection
            data = self.db.read_data(path)
            
            if not data:
                return []
            
            # Filter to current course
            records = [
                r for r in data.values()
                if isinstance(r, dict) and r.get(DB_FIELD_COURSE_ID) == course_id
            ]
            
            # Filter by date if specified
            if date_filter:
                date_str = date_filter.strftime("%Y-%m-%d")
                records = [
                    r for r in records
                    if r.get(DB_FIELD_ATTENDANCE_DATE) == date_str
                ]
            
            logger.debug(f"Retrieved {len(records)} attendance records for {course_id}")
            return records
        
        except Exception as e:
            logger.error(f"Error retrieving course attendance: {e}")
            return []
    
    def get_attendance_statistics(
        self,
        student_id: str,
        course_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get attendance statistics for student.
        
        Args:
            student_id: Student identifier
            course_id: Course identifier
            start_date: Start date (optional)
            end_date: End date (optional)
        
        Returns:
            Dictionary with attendance stats
        """
        try:
            records = self.get_student_attendance(
                student_id,
                course_id,
                start_date,
                end_date
            )
            
            # Count by status
            status_counts = {}
            for status in AttendanceStatus:
                status_counts[status.value] = sum(
                    1 for r in records if r.get('status') == status.value
                )
            
            total = len(records)
            present = status_counts.get(AttendanceStatus.PRESENT.value, 0)
            
            # Calculate attendance percentage
            attendance_percent = (present / total * 100) if total > 0 else 0
            
            return {
                'student_id': student_id,
                'course_id': course_id,
                'total_records': total,
                'status_counts': status_counts,
                'attendance_percent': round(attendance_percent, 2),
                'average_confidence': self._calculate_avg_confidence(records),
            }
        
        except Exception as e:
            logger.error(f"Error calculating attendance statistics: {e}")
            return {}
    
    def delete_old_records(self, days_to_keep: int = ATTENDANCE_RETENTION_DAYS) -> int:
        """
        Delete old attendance records (archival cleanup).
        
        Args:
            days_to_keep: Number of days of records to keep
        
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).date()
            
            path = self.collection
            data = self.db.read_data(path)
            
            if not data:
                return 0
            
            deleted_count = 0
            for record_id, record in data.items():
                if isinstance(record, dict):
                    record_date_str = record.get(DB_FIELD_ATTENDANCE_DATE)
                    if record_date_str:
                        try:
                            record_date = datetime.strptime(
                                record_date_str,
                                "%Y-%m-%d"
                            ).date()
                            
                            if record_date < cutoff_date:
                                delete_path = f"{path}/{record_id}"
                                if self.db.delete_data(delete_path):
                                    deleted_count += 1
                        except ValueError:
                            logger.warning(f"Invalid date format in record: {record_id}")
            
            logger.info(f"Deleted {deleted_count} old attendance records")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error deleting old records: {e}")
            return 0
    
    def _filter_by_date_range(
        self,
        records: List[Dict[str, Any]],
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> List[Dict[str, Any]]:
        """Filter records by date range."""
        if not start_date and not end_date:
            return records
        
        filtered = []
        for record in records:
            date_str = record.get(DB_FIELD_ATTENDANCE_DATE)
            if not date_str:
                continue
            
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if start_date and record_date < start_date:
                    continue
                if end_date and record_date > end_date:
                    continue
                
                filtered.append(record)
            except ValueError:
                logger.warning(f"Invalid date format in record: {date_str}")
        
        return filtered
    
    def _calculate_avg_confidence(self, records: List[Dict[str, Any]]) -> float:
        """Calculate average confidence score from records."""
        if not records:
            return 0.0
        
        scores = [
            r.get(DB_FIELD_CONFIDENCE_SCORE, 0.0)
            for r in records
            if DB_FIELD_CONFIDENCE_SCORE in r
        ]
        
        if not scores:
            return 0.0
        
        return round(sum(scores) / len(scores), 3)
