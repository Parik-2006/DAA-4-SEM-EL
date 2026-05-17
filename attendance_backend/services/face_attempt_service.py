"""
face_attempt_service.py — Track face detection attempts per student per period
════════════════════════════════════════════════════════════════════════════════
Enforces a maximum of 5 face detection attempts per student per period.
After 5 failed attempts, no more attempts are allowed until the period closes.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Maximum attempts per student per period
MAX_FACE_DETECTION_ATTEMPTS = 5


class FaceAttemptService:
    """Track face detection attempts in Firestore."""
    
    def __init__(self, firestore_db: Any = None):
        self.db = firestore_db
    
    def get_attempt_count(self, student_id: str, period_id: Optional[str] = None) -> int:
        """Get the current attempt count for a student in a period."""
        if not self.db or not student_id:
            return 0
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Create a unique key for this student+period+day
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            
            # Store attempts in a lightweight collection
            doc = self.db.collection("face_attempts").document(attempt_key).get()
            
            if doc.exists:
                return doc.to_dict().get("count", 0)
            return 0
            
        except Exception as e:
            logger.warning(f"Could not retrieve attempt count: {e}")
            return 0
    
    def increment_attempt(self, student_id: str, period_id: Optional[str] = None) -> int:
        """
        Increment the attempt count and return the new count.
        Returns the new count after incrementing.
        """
        if not self.db or not student_id:
            return 1
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            
            doc_ref = self.db.collection("face_attempts").document(attempt_key)
            doc = doc_ref.get()
            
            if doc.exists:
                new_count = doc.to_dict().get("count", 0) + 1
            else:
                new_count = 1
            
            # Set with timestamp for TTL/cleanup later
            doc_ref.set({
                "student_id": student_id,
                "period_id": period_id or "unknown",
                "date": today,
                "count": new_count,
                "last_attempt": datetime.now().isoformat(),
            })
            
            return new_count
            
        except Exception as e:
            logger.warning(f"Could not increment attempt count: {e}")
            return 1
    
    def can_attempt(self, student_id: str, period_id: Optional[str] = None) -> Tuple[bool, int]:
        """
        Check if a student can attempt face detection.
        Returns (can_attempt, current_count).
        """
        current_count = self.get_attempt_count(student_id, period_id)
        can_attempt = current_count < MAX_FACE_DETECTION_ATTEMPTS
        return can_attempt, current_count
    
    def reset_attempts(self, student_id: str, period_id: Optional[str] = None) -> None:
        """Reset attempts for a student in a period (usually on successful detection)."""
        if not self.db or not student_id:
            return
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            
            self.db.collection("face_attempts").document(attempt_key).delete()
            logger.info(f"Reset attempts for {student_id} in period {period_id}")
            
        except Exception as e:
            logger.warning(f"Could not reset attempts: {e}")


def get_face_attempt_service(firestore_db: Any = None) -> FaceAttemptService:
    """Get or create a face attempt service instance."""
    if firestore_db is None:
        try:
            from services.firebase_service import get_firebase_service
            fb = get_firebase_service()
            firestore_db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
        except Exception:
            pass
    
    return FaceAttemptService(firestore_db)
