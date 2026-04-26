"""
Firebase service for storing embeddings and attendance records.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
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
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
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
        if not FIREBASE_AVAILABLE:
            raise RuntimeError("Firebase SDK not installed.")

        service = cls()

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(credentials_path)
                options = {}
                if database_url:
                    options['databaseURL'] = database_url
                firebase_admin.initialize_app(cred, options)

            if use_firestore:
                service.db = firestore.client()
                logger.info("Firestore initialized")
            else:
                service.firebase_db = db.reference()
                logger.info("Realtime Database initialized")

            if storage_bucket:
                service.storage_bucket = storage.bucket(storage_bucket)

            return service
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise

    # ── NEW: canonical embeddings helper ─────────────────────────────────────

    @staticmethod
    def get_all_embeddings(student: Dict[str, Any]) -> List[np.ndarray]:
        """
        Return all face embeddings for *student* as a list of numpy arrays.

        Handles three storage layouts that exist in the wild:
          1. {"embeddings": [[…], […]]}     ← multi-shot (new)
          2. {"embedding": […]}             ← single-shot (legacy)
          3. both keys present

        Deduplicates: if 'embeddings' list is non-empty it is used exclusively;
        the legacy 'embedding' key is only consulted when 'embeddings' is absent
        or empty.
        """
        embs: List[np.ndarray] = []

        # Multi-shot list (new format)
        raw_list = student.get("embeddings") or []
        for item in raw_list:
            if item is not None:
                try:
                    embs.append(np.array(item, dtype=np.float32))
                except Exception:
                    pass

        # Legacy single vector — only add when embeddings list was empty
        if not embs:
            raw_single = student.get("embedding")
            if raw_single is not None:
                try:
                    embs.append(np.array(raw_single, dtype=np.float32))
                except Exception:
                    pass

        return embs

    # ── Student Registration ──────────────────────────────────────────────────

    def register_student(
        self,
        student_id: str,
        name: str,
        email: str,
        embeddings: np.ndarray,
        phone: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        try:
            embedding_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings

            student_data = {
                "student_id": student_id,
                "name": name,
                "email": email,
                "phone": phone or "",
                # Write BOTH keys so old and new consumers both work:
                # • embedding  → single vector (legacy consumers)
                # • embeddings → list of vectors (multi-shot / new)
                "embedding": embedding_list,
                "embeddings": [embedding_list],
                "registered_at": datetime.now().isoformat(),
                "last_seen": None,
                "attendance_count": 0,
                "status": "active",
                "metadata": metadata or {}
            }

            if self.db:
                self.db.collection("students").document(student_id).set(student_data)
                logger.info(f"Student registered in Firestore: {student_id}")
            elif self.firebase_db:
                self.firebase_db.child("students").child(student_id).set(student_data)
                logger.info(f"Student registered in RTDB: {student_id}")

            return {"success": True, "student_id": student_id, "message": "Student registered successfully"}
        except Exception as e:
            logger.error(f"Failed to register student {student_id}: {e}")
            raise

    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        try:
            if self.db:
                doc = self.db.collection("students").document(student_id).get()
                return doc.to_dict() if doc.exists else None
            elif self.firebase_db:
                data = self.firebase_db.child("students").child(student_id).get()
                return data if data else None
        except Exception as e:
            logger.error(f"Failed to get student {student_id}: {e}")
            return None

    def get_all_students(self) -> List[Dict[str, Any]]:
        try:
            students = []
            if self.db:
                docs = self.db.collection("students").stream()
                students = [doc.to_dict() for doc in docs]
            elif self.firebase_db:
                data = self.firebase_db.child("students").get()
                if data:
                    students = [v for v in data.values()]
            return students
        except Exception as e:
            logger.error(f"Failed to retrieve students: {e}")
            return []

    def update_student(self, student_id: str, updates: Dict[str, Any]) -> bool:
        try:
            if self.db:
                self.db.collection("students").document(student_id).update(updates)
            elif self.firebase_db:
                self.firebase_db.child("students").child(student_id).update(updates)
            return True
        except Exception as e:
            logger.error(f"Failed to update student {student_id}: {e}")
            return False

    # ── Attendance Logging ────────────────────────────────────────────────────

    def mark_attendance(
        self,
        student_id: str,
        timestamp: Optional[datetime] = None,
        confidence: float = 0.0,
        track_id: Optional[int] = None,
        camera_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
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

            if self.db:
                doc_ref = self.db.collection("attendance").add(attendance_record)
                record_id = doc_ref[1].id
                self.db.collection("students").document(student_id).update({
                    "last_seen": timestamp.isoformat(),
                    "attendance_count": firestore.Increment(1)
                })
            elif self.firebase_db:
                record_id = str(timestamp.timestamp())
                self.firebase_db.child("attendance").child(str(record_id)).set(attendance_record)
                self.firebase_db.child("students").child(student_id).update({
                    "last_seen": timestamp.isoformat(),
                })

            logger.info(f"Attendance marked for {student_id}: {record_id}")
            return {"success": True, "record_id": str(record_id), "student_id": student_id, "timestamp": timestamp.isoformat()}
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
        try:
            records = []
            if self.db:
                query = self.db.collection("attendance")
                if student_id:
                    query = query.where("student_id", "==", student_id)
                if date_from:
                    query = query.where("timestamp", ">=", date_from.isoformat())
                if date_to:
                    query = query.where("timestamp", "<=", date_to.isoformat())
                docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
                records = [doc.to_dict() for doc in docs]
            elif self.firebase_db:
                data = self.firebase_db.child("attendance").get()
                if data:
                    records = list(data.values())
                    if student_id:
                        records = [r for r in records if r.get("student_id") == student_id]
                    records = sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
            return records
        except Exception as e:
            logger.error(f"Failed to retrieve attendance records: {e}")
            return []

    def get_daily_report(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        date = date or datetime.now()
        date_str = date.date().isoformat()
        try:
            records = self.get_attendance_records(
                date_from=datetime.fromisoformat(f"{date_str}T00:00:00"),
                date_to=datetime.fromisoformat(f"{date_str}T23:59:59")
            )
            by_student = {}
            for record in records:
                sid = record.get("student_id")
                if sid not in by_student:
                    by_student[sid] = []
                by_student[sid].append(record)
            return {"date": date_str, "total_records": len(records), "unique_students": len(by_student), "records_by_student": by_student}
        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")
            return {"error": str(e)}

    # ── Embedding Management ──────────────────────────────────────────────────

    def store_embedding(
        self,
        student_id: str,
        embedding: np.ndarray,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Append *embedding* to the student's embeddings list and update the
        legacy ``embedding`` field so both storage layouts stay in sync.
        """
        timestamp = timestamp or datetime.now()
        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding

        try:
            if self.db:  # Firestore
                student_ref = self.db.collection("students").document(student_id)
                doc = student_ref.get()
                if doc.exists:
                    existing = doc.to_dict() or {}
                    current_list: list = existing.get("embeddings") or []
                    if not isinstance(current_list, list):
                        current_list = [current_list]
                    current_list.append(embedding_list)
                    student_ref.update({
                        "embedding": embedding_list,   # keep legacy field current
                        "embeddings": current_list,
                    })
                    logger.info(f"Embedding appended for {student_id} (total: {len(current_list)})")
                    return True

            elif self.firebase_db:  # Realtime DB
                path = f"students/{student_id}"
                existing = self.firebase_db.child(path).get() or {}
                current_list = existing.get("embeddings") or []
                if not isinstance(current_list, list):
                    current_list = [current_list]
                current_list.append(embedding_list)
                self.firebase_db.child(path).update({
                    "embedding": embedding_list,
                    "embeddings": current_list,
                })
                logger.info(f"Embedding appended for {student_id} (total: {len(current_list)})")
                return True

        except Exception as e:
            logger.error(f"Failed to store embedding for {student_id}: {e}")
            return False

        return False

    def get_embeddings(self, student_id: str) -> List[np.ndarray]:
        try:
            student = self.get_student(student_id)
            if student is None:
                return []
            return self.get_all_embeddings(student)
        except Exception as e:
            logger.error(f"Failed to retrieve embeddings for {student_id}: {e}")
            return []


# Singleton instance
firebase_service: Optional[FirebaseService] = None


def get_firebase_service() -> Optional[FirebaseService]:
    return firebase_service


def initialize_firebase(
    credentials_path: str,
    database_url: Optional[str] = None,
    storage_bucket: Optional[str] = None,
    use_firestore: bool = True
) -> FirebaseService:
    global firebase_service
    firebase_service = FirebaseService.initialize(
        credentials_path=credentials_path,
        database_url=database_url,
        storage_bucket=storage_bucket,
        use_firestore=use_firestore
    )
    return firebase_service
