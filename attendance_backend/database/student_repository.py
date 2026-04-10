"""
Student Data Repository.

Provides CRUD operations for student records in Firebase.
"""

from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from database.firebase_client import FirebaseClient
from config.constants import (
    FIREBASE_COLLECTIONS,
    DB_FIELD_STUDENT_ID,
    DB_FIELD_STUDENT_NAME,
    DB_FIELD_STUDENT_EMAIL,
    DB_FIELD_TIMESTAMP,
)


logger = logging.getLogger(__name__)


class StudentRepository:
    """
    Repository for student data operations.
    
    Handles CRUD operations for student records in Firebase Realtime Database.
    """
    
    def __init__(self):
        """Initialize repository with Firebase client."""
        self.db = FirebaseClient()
        self.collection = FIREBASE_COLLECTIONS['students']
    
    def create_student(
        self,
        student_id: str,
        name: str,
        email: str,
        course_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create new student record.
        
        Args:
            student_id: Unique student identifier
            name: Student full name
            email: Student email address
            course_id: Associated course ID
            metadata: Additional metadata
        
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                DB_FIELD_STUDENT_ID: student_id,
                DB_FIELD_STUDENT_NAME: name,
                DB_FIELD_STUDENT_EMAIL: email,
                'course_id': course_id,
                DB_FIELD_TIMESTAMP: datetime.utcnow().isoformat(),
                'active': True,
            }
            
            if metadata:
                data.update(metadata)
            
            path = f"{self.collection}/{student_id}"
            success = self.db.write_data(path, data)
            
            if success:
                logger.info(f"Created student record: {student_id}")
            else:
                logger.error(f"Failed to create student: {student_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error creating student {student_id}: {e}")
            return False
    
    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Get student record by ID.
        
        Args:
            student_id: Student identifier
        
        Returns:
            Student data dictionary or None if not found
        """
        try:
            path = f"{self.collection}/{student_id}"
            student_data = self.db.read_data(path)
            
            if student_data:
                logger.debug(f"Retrieved student: {student_id}")
            else:
                logger.debug(f"Student not found: {student_id}")
            
            return student_data
        
        except Exception as e:
            logger.error(f"Error retrieving student {student_id}: {e}")
            return None
    
    def update_student(
        self,
        student_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """
        Update student record.
        
        Args:
            student_id: Student identifier
            update_data: Data to update
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add timestamp
            update_data[DB_FIELD_TIMESTAMP] = datetime.utcnow().isoformat()
            
            path = f"{self.collection}/{student_id}"
            success = self.db.update_data(path, update_data)
            
            if success:
                logger.info(f"Updated student: {student_id}")
            else:
                logger.error(f"Failed to update student: {student_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error updating student {student_id}: {e}")
            return False
    
    def delete_student(self, student_id: str) -> bool:
        """
        Delete student record.
        
        Args:
            student_id: Student identifier
        
        Returns:
            True if successful, False otherwise
        """
        try:
            path = f"{self.collection}/{student_id}"
            success = self.db.delete_data(path)
            
            if success:
                logger.info(f"Deleted student: {student_id}")
            else:
                logger.error(f"Failed to delete student: {student_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error deleting student {student_id}: {e}")
            return False
    
    def list_students(self, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all students, optionally filtered by course.
        
        Args:
            course_id: Filter by course ID (optional)
        
        Returns:
            List of student records
        """
        try:
            path = self.collection
            data = self.db.read_data(path)
            
            if not data:
                return []
            
            students = list(data.values()) if isinstance(data, dict) else []
            
            # Filter by course if specified
            if course_id:
                students = [s for s in students if s.get('course_id') == course_id]
            
            logger.debug(f"Retrieved {len(students)} students")
            return students
        
        except Exception as e:
            logger.error(f"Error listing students: {e}")
            return []
    
    def search_students(self, query: str) -> List[Dict[str, Any]]:
        """
        Search students by name or email.
        
        Args:
            query: Search query
        
        Returns:
            List of matching student records
        """
        try:
            students = self.list_students()
            query = query.lower()
            
            # Search in name and email
            results = [
                s for s in students
                if query in s.get(DB_FIELD_STUDENT_NAME, '').lower()
                or query in s.get(DB_FIELD_STUDENT_EMAIL, '').lower()
            ]
            
            logger.debug(f"Search found {len(results)} students for query: {query}")
            return results
        
        except Exception as e:
            logger.error(f"Error searching students: {e}")
            return []
    
    def get_student_count(self, course_id: Optional[str] = None) -> int:
        """
        Get total student count.
        
        Args:
            course_id: Count for specific course (optional)
        
        Returns:
            Number of students
        """
        try:
            students = self.list_students(course_id)
            return len(students)
        except Exception as e:
            logger.error(f"Error counting students: {e}")
            return 0
    
    def activate_student(self, student_id: str) -> bool:
        """
        Activate student account.
        
        Args:
            student_id: Student identifier
        
        Returns:
            True if successful, False otherwise
        """
        return self.update_student(student_id, {'active': True})
    
    def deactivate_student(self, student_id: str) -> bool:
        """
        Deactivate student account.
        
        Args:
            student_id: Student identifier
        
        Returns:
            True if successful, False otherwise
        """
        return self.update_student(student_id, {'active': False})
    
    def bulk_create_students(
        self,
        students: List[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """
        Create multiple student records.
        
        Args:
            students: List of student data dictionaries
        
        Returns:
            Dictionary mapping student_id to success status
        """
        results = {}
        
        for student_data in students:
            student_id = student_data.get(DB_FIELD_STUDENT_ID)
            if not student_id:
                logger.warning("Skipping student without ID")
                continue
            
            # Extract required fields
            name = student_data.get(DB_FIELD_STUDENT_NAME, '')
            email = student_data.get(DB_FIELD_STUDENT_EMAIL, '')
            course_id = student_data.get('course_id')
            
            # Keep other fields as metadata
            metadata = {
                k: v for k, v in student_data.items()
                if k not in [DB_FIELD_STUDENT_ID, DB_FIELD_STUDENT_NAME,
                             DB_FIELD_STUDENT_EMAIL, 'course_id']
            }
            
            success = self.create_student(
                student_id,
                name,
                email,
                course_id,
                metadata
            )
            results[student_id] = success
        
        return results
