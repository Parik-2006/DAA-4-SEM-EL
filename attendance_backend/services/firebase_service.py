"""
Firebase service for storing embeddings and attendance records.

Integrates with Firestore and Realtime Database.
Handles student registration, embedding storage, and attendance logging.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import numpy as np

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, db, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Service for Firebase database operations.
    
    Supports both Firestore (NoSQL) and Realtime Database.
    Stores embeddings, student info, and attendance records.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Firebase service."""
        if not self._initialized:
            self.db = None
            self.firebase_db = None
            self.storage_bucket = None
            self._initialized = True
    
    @classmethod
    def initialize(
        cls,
        credentials_path: str,
        database_url: Optional[str] = None,
        storage_bucket: Optional[str] = None,
        use_firestore: bool = True
    ) -> 'FirebaseService':
        """
        Initialize Firebase with credentials.
        
        Args:
            credentials_path: Path to Firebase JSON credentials file
            database_url: Firebase Realtime Database URL (if using RTDB)
            storage_bucket: Firebase Storage bucket
            use_firestore: Use Firestore (True) or Realtime DB (False)
        
        Returns:
            FirebaseService instance
        
        Raises:
            Exception: If Firebase initialization fails
        """
        if not FIREBASE_AVAILABLE:
            raise RuntimeError(
                "Firebase SDK not installed. Install with: "
                "pip install firebase-admin"
            )
        
        service = cls()
        
        try:
            # Initialize Firebase
            if not firebase_admin._apps:  # Check if already initialized
                cred = credentials.Certificate(credentials_path)
                options = {}
                
                if database_url:
                    options['databaseURL'] = database_url
                
                firebase_admin.initialize_app(cred, options)
                logger.info("Firebase initialized successfully")
            
            # Initialize services
            if use_firestore:
                service.db = firestore.client()
                logger.info("Firestore initialized")
            else:
                service.firebase_db = db.reference()
                logger.info("Realtime Database initialized")
            
            if storage_bucket:
                service.storage_bucket = storage.bucket(storage_bucket)
                logger.info("Storage bucket initialized")
            
            return service
        
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    # ==================== Student Registration ====================
    
    def register_student(
        self,
        student_id: str,
        name: str,
        email: str,
        embeddings: np.ndarray,
        phone: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Register a new student with embeddings.
        
        Args:
            student_id: Unique student ID
            name: Student name
            email: Student email
            embeddings: Face embedding array (128-dim)
            phone: Optional phone number
            metadata: Optional metadata dictionary
        
        Returns:
            Response with student ID and status
        
        Raises:
            Exception: If registration fails
        """
        try:
            # Serialize embeddings (numpy array → list)
            embedding_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings
            
            student_data = {
                "student_id": student_id,
                "name": name,
                "email": email,
                "phone": phone or "",
                "embedding": embedding_list,
                "registered_at": datetime.now().isoformat(),
                "last_seen": None,
                "attendance_count": 0,
                "status": "active",
                "metadata": metadata or {}
            }
            
            if self.db:  # Firestore
                self.db.collection("students").document(student_id).set(student_data)
                logger.info(f"Student registered in Firestore: {student_id}")
            
            elif self.firebase_db:  # Realtime DB
                self.firebase_db.child("students").child(student_id).set(student_data)
                logger.info(f"Student registered in RTDB: {student_id}")
            
            return {
                "success": True,
                "student_id": student_id,
                "message": "Student registered successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to register student {student_id}: {e}")
            raise
    
    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve student data.
        
        Args:
            student_id: Student ID
        
        Returns:
            Student data or None if not found
        """
        try:
            if self.db:  # Firestore
                doc = self.db.collection("students").document(student_id).get()
                return doc.to_dict() if doc.exists else None
            
            elif self.firebase_db:  # Realtime DB
                data = self.firebase_db.child("students").child(student_id).get()
                return data.val() if data.val() else None
        
        except Exception as e:
            logger.error(f"Failed to get student {student_id}: {e}")
            return None
    
    def get_all_students(self) -> List[Dict[str, Any]]:
        """
        Retrieve all registered students.
        
        Returns:
            List of student dictionaries
        """
        try:
            students = []
            
            if self.db:  # Firestore
                docs = self.db.collection("students").stream()
                students = [doc.to_dict() for doc in docs]
            
            elif self.firebase_db:  # Realtime DB
                data = self.firebase_db.child("students").get()
                if data.val():
                    students = [v for v in data.val().values()]
            
            logger.info(f"Retrieved {len(students)} students")
            return students
        
        except Exception as e:
            logger.error(f"Failed to retrieve students: {e}")
            return []
    
    def update_student(
        self,
        student_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update student record.
        
        Args:
            student_id: Student ID
            updates: Dictionary of fields to update
        
        Returns:
            True if successful
        """
        try:
            if self.db:  # Firestore
                self.db.collection("students").document(student_id).update(updates)
            
            elif self.firebase_db:  # Realtime DB
                self.firebase_db.child("students").child(student_id).update(updates)
            
            logger.info(f"Updated student: {student_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update student {student_id}: {e}")
            return False
    
    # ==================== Attendance Logging ====================
    
    def mark_attendance(
        self,
        student_id: str,
        timestamp: Optional[datetime] = None,
        confidence: float = 0.0,
        track_id: Optional[int] = None,
        camera_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Mark attendance for a student.
        
        Args:
            student_id: Student ID
            timestamp: Attendance timestamp (default: now)
            confidence: Recognition confidence (0-1)
            track_id: Track ID from tracking system
            camera_id: Camera ID for multi-camera systems
            metadata: Additional metadata
        
        Returns:
            Response with attendance record ID
        """
        try:
            timestamp = timestamp or datetime.now()
            
            attendance_record = {
                "student_id": student_id,
                "timestamp": timestamp.isoformat(),
                "date": timestamp.date().isoformat(),
                "time": timestamp.time().isoformat(),
                "confidence": confidence,
                "track_id": track_id,
                "camera_id": camera_id or "default",
                "status": "present",
                "metadata": metadata or {}
            }
            
            if self.db:  # Firestore
                # Add to attendance collection
                doc_ref = self.db.collection("attendance").add(attendance_record)
                record_id = doc_ref[1].id
                
                # Update student's last_seen and count
                self.db.collection("students").document(student_id).update({
                    "last_seen": timestamp.isoformat(),
                    "attendance_count": firestore.Increment(1)
                })
                
                logger.info(f"Attendance marked for {student_id}: {record_id}")
            
            elif self.firebase_db:  # Realtime DB
                # Generate timestamp-based ID for ordering
                record_id = timestamp.timestamp()
                self.firebase_db.child("attendance").child(str(record_id)).set(attendance_record)
                
                # Update student
                self.firebase_db.child("students").child(student_id).update({
                    "last_seen": timestamp.isoformat(),
                    "attendance_count": 1  # Increment manually in RTDB
                })
                
                logger.info(f"Attendance marked for {student_id}: {record_id}")
            
            return {
                "success": True,
                "record_id": str(record_id),
                "student_id": student_id,
                "timestamp": timestamp.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to mark attendance for {student_id}: {e}")
            raise
    
    def get_attendance_records(
        self,
        student_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve attendance records.
        
        Args:
            student_id: Filter by student ID (optional)
            date_from: Start date (optional)
            date_to: End date (optional)
            limit: Maximum records to return
        
        Returns:
            List of attendance records
        """
        try:
            records = []
            
            if self.db:  # Firestore
                query = self.db.collection("attendance")
                
                if student_id:
                    query = query.where("student_id", "==", student_id)
                
                if date_from:
                    query = query.where(
                        "timestamp", ">=",
                        date_from.isoformat()
                    )
                
                if date_to:
                    query = query.where(
                        "timestamp", "<=",
                        date_to.isoformat()
                    )
                
                docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
                records = [doc.to_dict() for doc in docs]
            
            elif self.firebase_db:  # Realtime DB
                data = self.firebase_db.child("attendance").get()
                if data.val():
                    records = list(data.val().values())
                    
                    if student_id:
                        records = [r for r in records if r.get("student_id") == student_id]
                    
                    # Sort by timestamp descending
                    records = sorted(
                        records,
                        key=lambda r: r.get("timestamp", ""),
                        reverse=True
                    )[:limit]
            
            logger.info(f"Retrieved {len(records)} attendance records")
            return records
        
        except Exception as e:
            logger.error(f"Failed to retrieve attendance records: {e}")
            return []
    
    def get_daily_report(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get attendance report for a specific date.
        
        Args:
            date: Date for report (default: today)
        
        Returns:
            Attendance report
        """
        date = date or datetime.now()
        date_str = date.date().isoformat()
        
        try:
            records = self.get_attendance_records(
                date_from=datetime.fromisoformat(f"{date_str}T00:00:00"),
                date_to=datetime.fromisoformat(f"{date_str}T23:59:59")
            )
            
            # Group by student
            by_student = {}
            for record in records:
                student_id = record.get("student_id")
                if student_id not in by_student:
                    by_student[student_id] = []
                by_student[student_id].append(record)
            
            return {
                "date": date_str,
                "total_records": len(records),
                "unique_students": len(by_student),
                "records_by_student": by_student
            }
        
        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")
            return {"error": str(e)}
    
    # ==================== Session Management ====================
    
    def create_session(
        self,
        session_id: str,
        camera_id: str,
        start_time: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create an attendance session for a camera.
        
        Args:
            session_id: Unique session ID
            camera_id: Camera ID
            start_time: Session start time
            metadata: Additional metadata
        
        Returns:
            Session information
        """
        try:
            start_time = start_time or datetime.now()
            
            session_data = {
                "session_id": session_id,
                "camera_id": camera_id,
                "start_time": start_time.isoformat(),
                "end_time": None,
                "status": "active",
                "attendance_count": 0,
                "metadata": metadata or {}
            }
            
            if self.db:  # Firestore
                self.db.collection("sessions").document(session_id).set(session_data)
            elif self.firebase_db:
                self.firebase_db.child("sessions").child(session_id).set(session_data)
            
            logger.info(f"Session created: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "start_time": start_time.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def end_session(self, session_id: str) -> bool:
        """
        End an attendance session.
        
        Args:
            session_id: Session ID
        
        Returns:
            True if successful
        """
        try:
            end_time = datetime.now()
            
            if self.db:  # Firestore
                self.db.collection("sessions").document(session_id).update({
                    "end_time": end_time.isoformat(),
                    "status": "closed"
                })
            
            elif self.firebase_db:
                self.firebase_db.child("sessions").child(session_id).update({
                    "end_time": end_time.isoformat(),
                    "status": "closed"
                })
            
            logger.info(f"Session ended: {session_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    # ==================== Embedding Management ====================
    
    def store_embedding(
        self,
        student_id: str,
        embedding: np.ndarray,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Store embedding for student.
        
        Args:
            student_id: Student ID
            embedding: Face embedding (128-dim)
            timestamp: Embedding timestamp
        
        Returns:
            True if successful
        """
        try:
            timestamp = timestamp or datetime.now()
            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            
            embedding_data = {
                "student_id": student_id,
                "embedding": embedding_list,
                "timestamp": timestamp.isoformat()
            }
            
            if self.db:  # Firestore
                self.db.collection("embeddings").document(
                    f"{student_id}_{timestamp.timestamp()}"
                ).set(embedding_data)
            
            elif self.firebase_db:
                self.firebase_db.child("embeddings").child(student_id).set(embedding_data)
            
            logger.info(f"Embedding stored for {student_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to store embedding for {student_id}: {e}")
            return False
    
    def get_embeddings(self, student_id: str) -> List[np.ndarray]:
        """
        Retrieve embeddings for a student.
        
        Args:
            student_id: Student ID
        
        Returns:
            List of numpy embedding arrays
        """
        try:
            embeddings = []
            
            if self.db:  # Firestore
                docs = self.db.collection("embeddings").where(
                    "student_id", "==", student_id
                ).stream()
                
                for doc in docs:
                    data = doc.to_dict()
                    embedding_list = data.get("embedding", [])
                    if embedding_list:
                        embeddings.append(np.array(embedding_list))
            
            elif self.firebase_db:
                data = self.firebase_db.child("embeddings").child(student_id).get()
                if data.val() and "embedding" in data.val():
                    embeddings.append(np.array(data.val()["embedding"]))
            
            logger.info(f"Retrieved {len(embeddings)} embeddings for {student_id}")
            return embeddings
        
        except Exception as e:
            logger.error(f"Failed to retrieve embeddings for {student_id}: {e}")
            return []


# Singleton instance
firebase_service: Optional[FirebaseService] = None


def get_firebase_service() -> Optional[FirebaseService]:
    """Get Firebase service singleton."""
    return firebase_service


def initialize_firebase(
    credentials_path: str,
    database_url: Optional[str] = None,
    storage_bucket: Optional[str] = None,
    use_firestore: bool = True
) -> FirebaseService:
    """Initialize Firebase service."""
    global firebase_service
    firebase_service = FirebaseService.initialize(
        credentials_path=credentials_path,
        database_url=database_url,
        storage_bucket=storage_bucket,
        use_firestore=use_firestore
    )
    return firebase_service
