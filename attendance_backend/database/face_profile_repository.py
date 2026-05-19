"""
Face Profile Repository.

Provides CRUD operations for face profiles, samples, detections, and confirmation events.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from database.firebase_client import FirebaseClient
from config.constants import FIREBASE_COLLECTIONS
from utils.face_exceptions import (
    FaceRepositoryError,
    FaceProfileNotFoundError,
    FaceDetectionNotFoundError,
    FaceDetectionExpiredError,
)


logger = logging.getLogger(__name__)


class FaceProfileRepository:
    """
    Repository for face profile and related data operations.
    
    Manages:
    - face_profiles/{student_id} — learning profile
    - face_profile_samples/{student_id}/samples/{sample_id} — trusted samples
    - pending_face_detections/{detection_id} — short-lived detection snapshots
    - face_confirmation_events/{event_id} — immutable confirmation audit trail
    - face_confusion_pairs/{pair_id} — confusable student pairs
    """
    
    def __init__(self):
        """Initialize repository with Firebase client."""
        self.db = FirebaseClient()
        candidates = (
            getattr(self.db, "firestore_db", None),
            getattr(self.db, "fs", None),
            getattr(self.db, "_firestore", None),
        )
        self.fs_db = next((client for client in candidates if hasattr(client, "collection")), None)
        if not self.fs_db:
            raise FaceRepositoryError("Firestore client not available")
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Face Profile Operations
    # ══════════════════════════════════════════════════════════════════════════════
    
    def create_or_update_profile(
        self,
        student_id: str,
        centroid: List[float],
        variance: float,
        adaptive_threshold: float,
        model_version: str = "facenet_vggface2",
        trusted_sample_count: int = 0,
        sample_count: int = 0,
        last_positive_similarity: float = 0.0,
        rolling_similarity_mean: float = 0.0,
        rolling_similarity_std: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Create or update a face profile for a student.
        
        Args:
            student_id: Student identifier
            centroid: Embedding centroid vector
            variance: Embedding variance
            adaptive_threshold: Per-student similarity threshold
            model_version: Embedding model version
            trusted_sample_count: Count of trusted samples in profile
            sample_count: Total count of samples ever added
        
        Returns:
            Profile document data
        
        Raises:
            FaceRepositoryError: If update fails
        """
        try:
            profile = {
                "student_id": student_id,
                "model_version": model_version,
                "centroid": centroid,
                "variance": variance,
                "sample_count": sample_count,
                "trusted_sample_count": trusted_sample_count,
                "last_positive_similarity": float(last_positive_similarity),
                "rolling_similarity_mean": float(rolling_similarity_mean),
                "rolling_similarity_std": float(rolling_similarity_std),
                "adaptive_threshold": adaptive_threshold,
                "last_updated_at": datetime.utcnow().isoformat() + "Z",
                "status": "active",
            }
            
            doc_ref = self.fs_db.collection("face_profiles").document(student_id)
            doc_ref.set(profile, merge=True)
            
            logger.info(f"✓ Face profile created/updated for {student_id}")
            return profile
        
        except Exception as exc:
            msg = f"Failed to create/update face profile for {student_id}: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def get_profile(self, student_id: str) -> Dict[str, Any]:
        """
        Retrieve face profile for a student.
        
        Args:
            student_id: Student identifier
        
        Returns:
            Profile document data
        
        Raises:
            FaceProfileNotFoundError: If profile does not exist
            FaceRepositoryError: If retrieval fails
        """
        try:
            doc = self.fs_db.collection("face_profiles").document(student_id).get()
            if not doc.exists:
                raise FaceProfileNotFoundError(f"No profile for {student_id}")
            return doc.to_dict()
        except FaceProfileNotFoundError:
            raise
        except Exception as exc:
            msg = f"Failed to retrieve face profile for {student_id}: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def profile_exists(self, student_id: str) -> bool:
        """Check if a face profile exists."""
        try:
            doc = self.fs_db.collection("face_profiles").document(student_id).get()
            return doc.exists
        except Exception as exc:
            logger.error(f"Error checking profile existence for {student_id}: {exc}")
            return False
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Profile Sample Operations
    # ══════════════════════════════════════════════════════════════════════════════
    
    def add_profile_sample(
        self,
        student_id: str,
        sample_id: str,
        embedding: List[float],
        quality_score: float,
        quality_tier: str,
        liveness_score: float,
        source: str = "yes_this_is_me",
        similarity_to_centroid: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Add a trusted sample to a student's profile.
        
        Args:
            student_id: Student identifier
            sample_id: Unique sample identifier
            embedding: Embedding vector
            quality_score: Quality metric 0-1
            quality_tier: 'HIGH', 'ACCEPTABLE', 'LOW'
            liveness_score: Liveness metric 0-1
            source: 'enrollment' or 'yes_this_is_me'
            similarity_to_centroid: Similarity before centroid update
        
        Returns:
            Sample document data
        
        Raises:
            FaceRepositoryError: If operation fails
        """
        try:
            sample = {
                "sample_id": sample_id,
                "source": source,
                "embedding": embedding,
                "quality_score": quality_score,
                "quality_tier": quality_tier,
                "liveness_score": liveness_score,
                "similarity_to_old_centroid": similarity_to_centroid,
                "accepted_for_profile": True,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            
            doc_ref = (
                self.fs_db.collection("face_profile_samples")
                .document(student_id)
                .collection("samples")
                .document(sample_id)
            )
            doc_ref.set(sample)
            
            logger.info(f"✓ Added profile sample {sample_id} for {student_id}")
            return sample
        
        except Exception as exc:
            msg = f"Failed to add profile sample for {student_id}: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def get_profile_samples(
        self,
        student_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve trusted samples for a student's profile.
        
        Args:
            student_id: Student identifier
            limit: Maximum samples to return
        
        Returns:
            List of sample documents
        """
        try:
            samples = (
                self.fs_db.collection("face_profile_samples")
                .document(student_id)
                .collection("samples")
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [doc.to_dict() for doc in samples]
        except Exception as exc:
            logger.error(f"Failed to retrieve profile samples for {student_id}: {exc}")
            return []
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Pending Detection Operations
    # ══════════════════════════════════════════════════════════════════════════════
    
    def store_pending_detection(
        self,
        detection_id: str,
        detection_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Store a short-lived pending detection snapshot.
        
        Args:
            detection_id: Unique detection identifier
            detection_data: Detection document data
        
        Returns:
            Stored detection data
        
        Raises:
            FaceRepositoryError: If operation fails
        """
        try:
            doc_ref = self.fs_db.collection("pending_face_detections").document(detection_id)
            doc_ref.set(detection_data)
            
            logger.info(f"✓ Stored pending detection {detection_id}")
            return detection_data
        
        except Exception as exc:
            msg = f"Failed to store pending detection {detection_id}: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def get_pending_detection(self, detection_id: str) -> Dict[str, Any]:
        """
        Retrieve a pending detection by ID.
        
        Args:
            detection_id: Unique detection identifier
        
        Returns:
            Detection document data
        
        Raises:
            FaceDetectionNotFoundError: If not found
            FaceDetectionExpiredError: If expired
            FaceRepositoryError: If retrieval fails
        """
        try:
            doc = self.fs_db.collection("pending_face_detections").document(detection_id).get()
            
            if not doc.exists:
                raise FaceDetectionNotFoundError(f"Detection {detection_id} not found")
            
            detection = doc.to_dict()
            
            # Check expiry
            if "expires_at" in detection:
                expires_at = detection["expires_at"]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                
                now = datetime.now(expires_at.tzinfo) if getattr(expires_at, "tzinfo", None) else datetime.utcnow()
                if now > expires_at:
                    raise FaceDetectionExpiredError(f"Detection {detection_id} expired")
            
            return detection
        
        except (FaceDetectionNotFoundError, FaceDetectionExpiredError):
            raise
        except Exception as exc:
            msg = f"Failed to retrieve detection {detection_id}: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def mark_detection_used(self, detection_id: str) -> None:
        """Mark a detection as used for learning."""
        try:
            self.fs_db.collection("pending_face_detections").document(detection_id).update({
                "used_for_learning": True,
            })
            logger.info(f"✓ Marked detection {detection_id} as used")
        except Exception as exc:
            logger.warning(f"Failed to mark detection {detection_id} as used: {exc}")
    
    def delete_expired_detections(self, older_than_seconds: int = 1800) -> int:
        """
        Delete pending detections older than threshold (default 30 min).
        
        Args:
            older_than_seconds: Age threshold in seconds
        
        Returns:
            Count of deleted documents
        """
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=older_than_seconds)
            cutoff_iso = cutoff.isoformat() + "Z"
            
            docs = (
                self.fs_db.collection("pending_face_detections")
                .where("expires_at", "<", cutoff_iso)
                .stream()
            )
            
            count = 0
            for doc in docs:
                doc.reference.delete()
                count += 1
            
            logger.info(f"Deleted {count} expired pending detections")
            return count
        
        except Exception as exc:
            logger.error(f"Error deleting expired detections: {exc}")
            return 0
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Confirmation Event Operations
    # ══════════════════════════════════════════════════════════════════════════════
    
    def store_confirmation_event(
        self,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Store an immutable confirmation event.
        
        Args:
            event_id: Unique event identifier
            event_data: Confirmation event data
        
        Returns:
            Stored event data
        
        Raises:
            FaceRepositoryError: If operation fails
        """
        try:
            doc_ref = self.fs_db.collection("face_confirmation_events").document(event_id)
            doc_ref.set(event_data)
            
            logger.info(f"✓ Stored confirmation event {event_id}")
            return event_data
        
        except Exception as exc:
            msg = f"Failed to store confirmation event: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceRepositoryError(msg) from exc
    
    def get_confirmation_events(
        self,
        student_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent confirmation events for a student.
        
        Args:
            student_id: Student identifier
            limit: Maximum events to return
        
        Returns:
            List of confirmation event documents
        """
        try:
            events = (
                self.fs_db.collection("face_confirmation_events")
                .where("confirmed_student_id", "==", student_id)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [doc.to_dict() for doc in events]
        except Exception as exc:
            logger.error(f"Failed to retrieve confirmation events for {student_id}: {exc}")
            return []
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Confusable Pair Operations
    # ══════════════════════════════════════════════════════════════════════════════
    
    def track_confusable_pair(
        self,
        student_a: str,
        student_b: str,
    ) -> Dict[str, Any]:
        """
        Track or update a confusable student pair.
        
        Args:
            student_a: First student ID
            student_b: Second student ID
        
        Returns:
            Pair document data
        """
        try:
            # Canonical ordering to avoid duplicates
            pair_id = "_".join(sorted([student_a, student_b]))
            
            doc_ref = self.fs_db.collection("face_confusion_pairs").document(pair_id)
            
            pair_data = {
                "student_a": student_a,
                "student_b": student_b,
                "count": 1,
                "last_seen": datetime.utcnow().isoformat() + "Z",
                "action": "raise_threshold",
            }
            
            doc_ref.set(pair_data, merge=True)
            logger.info(f"✓ Tracked confusable pair: {student_a} <-> {student_b}")
            return pair_data
        
        except Exception as exc:
            logger.error(f"Failed to track confusable pair: {exc}")
            return {}
    
    def get_confusable_pairs(self, student_id: str) -> List[Dict[str, Any]]:
        """
        Get confusable pairs for a student.
        
        Args:
            student_id: Student identifier
        
        Returns:
            List of confusable pair documents
        """
        try:
            pairs_a = (
                self.fs_db.collection("face_confusion_pairs")
                .where("student_a", "==", student_id)
                .stream()
            )
            pairs_b = (
                self.fs_db.collection("face_confusion_pairs")
                .where("student_b", "==", student_id)
                .stream()
            )
            
            return [doc.to_dict() for doc in list(pairs_a) + list(pairs_b)]
        except Exception as exc:
            logger.error(f"Failed to retrieve confusable pairs for {student_id}: {exc}")
            return []
