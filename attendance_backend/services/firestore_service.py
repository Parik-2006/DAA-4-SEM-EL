"""
Enhanced Firestore service for Smart Attendance System.

Handles student data, embeddings, and attendance records in Firestore.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import numpy as np

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class FirestoreService:
    """Enhanced Firestore service for NoSQL database operations."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.db = None
        self.storage_bucket = None
    
    @classmethod
    def initialize(
        cls,
        credentials_path: str,
        storage_bucket: Optional[str] = None
    ) -> 'FirestoreService':
        """
        Initialize Firestore service.
        
        Args:
            credentials_path: Path to Firebase credentials JSON
            storage_bucket: Firebase Storage bucket name
        
        Returns:
            FirestoreService instance
        """
        if not FIREBASE_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")
        
        service = cls()
        
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
            
            service.db = firestore.client()
            if storage_bucket:
                service.storage_bucket = storage.bucket(storage_bucket)
            
            logger.info("Firestore service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            raise
        
        return service
    
    # ============ Student Operations ============
    
    def create_student(self, student_data: Dict[str, Any]) -> str:
        """Create a new student record."""
        try:
            doc_ref = self.db.collection('students').add(
                {
                    **student_data,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                }
            )
            logger.info(f"Student created: {doc_ref[1].id}")
            return doc_ref[1].id
        except Exception as e:
            logger.error(f"Error creating student: {e}")
            raise
    
    def get_student(self, student_id: str) -> Optional[Dict]:
        """Get student by ID."""
        try:
            doc = self.db.collection('students').document(student_id).get()
            if doc.exists:
                return {**doc.to_dict(), 'id': doc.id}
            return None
        except Exception as e:
            logger.error(f"Error getting student: {e}")
            raise
    
    def get_students_by_course(self, course_id: str) -> List[Dict]:
        """Get all students enrolled in a course."""
        try:
            docs = self.db.collection('students').where(
                'course_id', '==', course_id
            ).stream()
            return [{**doc.to_dict(), 'id': doc.id} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting students by course: {e}")
            raise
    
    def update_student(self, student_id: str, data: Dict[str, Any]) -> None:
        """Update student record."""
        try:
            self.db.collection('students').document(student_id).update({
                **data,
                'updated_at': datetime.utcnow(),
            })
            logger.info(f"Student updated: {student_id}")
        except Exception as e:
            logger.error(f"Error updating student: {e}")
            raise
    
    # ============ Course Operations ============
    
    def create_course(self, course_data: Dict[str, Any]) -> str:
        """Create a new course."""
        try:
            doc_ref = self.db.collection('courses').add({
                **course_data,
                'created_at': datetime.utcnow(),
            })
            logger.info(f"Course created: {doc_ref[1].id}")
            return doc_ref[1].id
        except Exception as e:
            logger.error(f"Error creating course: {e}")
            raise
    
    def get_course(self, course_id: str) -> Optional[Dict]:
        """Get course by ID."""
        try:
            doc = self.db.collection('courses').document(course_id).get()
            if doc.exists:
                return {**doc.to_dict(), 'id': doc.id}
            return None
        except Exception as e:
            logger.error(f"Error getting course: {e}")
            raise
    
    def get_all_courses(self) -> List[Dict]:
        """Get all courses."""
        try:
            docs = self.db.collection('courses').stream()
            return [{**doc.to_dict(), 'id': doc.id} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting courses: {e}")
            raise
    
    # ============ Attendance Operations ============
    
    def record_attendance(self, attendance_data: Dict[str, Any]) -> str:
        """Record attendance for a student."""
        try:
            doc_ref = self.db.collection('attendance').add({
                **attendance_data,
                'marked_at': datetime.utcnow(),
            })
            logger.info(f"Attendance recorded: {doc_ref[1].id}")
            return doc_ref[1].id
        except Exception as e:
            logger.error(f"Error recording attendance: {e}")
            raise
    
    def get_attendance_records(
        self,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
        days_back: int = 30
    ) -> List[Dict]:
        """Get attendance records with optional filtering."""
        try:
            query = self.db.collection('attendance')
            
            if student_id:
                query = query.where('student_id', '==', student_id)
            if course_id:
                query = query.where('course_id', '==', course_id)
            
            # Filter by date
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            query = query.where('marked_at', '>=', cutoff_date)
            query = query.order_by('marked_at', direction=firestore.Query.DESCENDING)
            
            docs = query.stream()
            return [{**doc.to_dict(), 'id': doc.id} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting attendance records: {e}")
            raise
    
    def get_attendance_statistics(
        self,
        student_id: str,
        course_id: str
    ) -> Dict[str, int]:
        """Get attendance statistics for a student in a course."""
        try:
            records = self.db.collection('attendance').where(
                'student_id', '==', student_id
            ).where('course_id', '==', course_id).stream()
            
            stats = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0}
            for doc in records:
                data = doc.to_dict()
                status = data.get('status', 'absent')
                if status in stats:
                    stats[status] += 1
            
            return stats
        except Exception as e:
            logger.error(f"Error getting attendance statistics: {e}")
            raise
    
    # ============ Embedding Operations ============
    
    def store_embedding(
        self,
        student_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict] = None
    ) -> str:
        """Store face embedding for a student."""
        try:
            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            
            doc_ref = self.db.collection('embeddings').add({
                'student_id': student_id,
                'embedding': embedding_list,
                'metadata': metadata or {},
                'created_at': datetime.utcnow(),
            })
            logger.info(f"Embedding stored for student {student_id}")
            return doc_ref[1].id
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            raise
    
    def get_student_embeddings(self, student_id: str) -> List[Dict]:
        """Get all embeddings for a student."""
        try:
            docs = self.db.collection('embeddings').where(
                'student_id', '==', student_id
            ).stream()
            
            embeddings = []
            for doc in docs:
                data = doc.to_dict()
                data['embedding'] = np.array(data['embedding'])
                embeddings.append({**data, 'id': doc.id})
            
            return embeddings
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise
    
    # ============ Batch Operations ============
    
    def batch_record_attendance(
        self,
        attendance_records: List[Dict[str, Any]]
    ) -> List[str]:
        """Record multiple attendance records in a batch."""
        try:
            batch = self.db.batch()
            ids = []
            
            for record in attendance_records:
                doc_ref = self.db.collection('attendance').document()
                batch.set(doc_ref, {
                    **record,
                    'marked_at': datetime.utcnow(),
                })
                ids.append(doc_ref.id)
            
            batch.commit()
            logger.info(f"Batch recorded {len(attendance_records)} attendance records")
            return ids
        except Exception as e:
            logger.error(f"Error in batch attendance recording: {e}")
            raise
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        try:
            stats = {
                'students': len(list(self.db.collection('students').stream())),
                'courses': len(list(self.db.collection('courses').stream())),
                'attendance': len(list(self.db.collection('attendance').stream())),
                'embeddings': len(list(self.db.collection('embeddings').stream())),
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            raise
