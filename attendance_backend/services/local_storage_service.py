import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class LocalStorageService:
    """
    A local fallback for FirebaseService that stores data in JSON files.
    Ensures the system works even when Firebase is unavailable.
    """
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Use a path relative to this file's parent's parent (attendance_backend/data/local_db)
            base_path = Path(__file__).parent.parent
            self.data_dir = base_path / "data" / "local_db"
        else:
            self.data_dir = Path(data_dir)
            
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.students_file = self.data_dir / "students.json"
        self.attendance_file = self.data_dir / "attendance.json"
        
        self._load_data()

    def _load_data(self):
        if self.students_file.exists():
            with open(self.students_file, 'r') as f:
                self.students = json.load(f)
        else:
            self.students = {}
            self._save_students()

        if self.attendance_file.exists():
            with open(self.attendance_file, 'r') as f:
                self.attendance = json.load(f)
        else:
            self.attendance = {}
            self._save_attendance()

    def _save_students(self):
        with open(self.students_file, 'w') as f:
            json.dump(self.students, f, indent=2)

    def _save_attendance(self):
        with open(self.attendance_file, 'w') as f:
            json.dump(self.attendance, f, indent=2)

    def register_student(self, student_id: str, name: str, email: str, embeddings: np.ndarray, phone: str = "", metadata: dict = None):
        embedding_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings
        student_data = {
            "student_id": student_id,
            "name": name,
            "email": email,
            "phone": phone,
            "embedding": embedding_list,
            "embeddings": [embedding_list],
            "registered_at": datetime.now().isoformat(),
            "last_seen": None,
            "attendance_count": 0,
            "status": "active",
            "metadata": metadata or {}
        }
        self.students[student_id] = student_data
        self._save_students()
        return {"success": True, "student_id": student_id}

    def get_student(self, student_id: str):
        return self.students.get(student_id)

    def get_all_students(self):
        return list(self.students.values())

    def update_student(self, student_id: str, updates: dict):
        if student_id in self.students:
            self.students[student_id].update(updates)
            self._save_students()
            return True
        return False

    def mark_attendance(self, student_id: str, timestamp=None, confidence=0.0, track_id=None, camera_id=None, metadata=None):
        timestamp = timestamp or datetime.now()
        record_id = str(timestamp.timestamp())
        record = {
            "student_id": student_id,
            "timestamp": timestamp.isoformat(),
            "date": timestamp.date().isoformat(),
            "time": timestamp.time().isoformat(),
            "confidence": confidence,
            "track_id": track_id,
            "camera_id": camera_id or "local",
            "status": "present",
            "metadata": metadata or {}
        }
        self.attendance[record_id] = record
        self._save_attendance()
        
        if student_id in self.students:
            self.students[student_id]["last_seen"] = timestamp.isoformat()
            self.students[student_id]["attendance_count"] = self.students[student_id].get("attendance_count", 0) + 1
            self._save_students()
            
        return {"success": True, "record_id": record_id}

    def get_attendance_records(self, student_id=None, limit=100):
        records = list(self.attendance.values())
        if student_id:
            records = [r for r in records if r.get("student_id") == student_id]
        return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]

    def store_embedding(self, student_id: str, embedding: np.ndarray):
        if student_id in self.students:
            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            current_list = self.students[student_id].get("embeddings", [])
            current_list.append(embedding_list)
            self.students[student_id]["embeddings"] = current_list
            self.students[student_id]["embedding"] = embedding_list
            self._save_students()
            return True
        return False
