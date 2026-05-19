"""
Face Detection Storage Helper.

Integrates detection_id generation and storage with existing detect-face-only flow.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from database.face_profile_repository import FaceProfileRepository
from utils.face_exceptions import FaceRepositoryError


logger = logging.getLogger(__name__)


def create_detection_id() -> str:
    """Generate a unique detection identifier."""
    return f"det_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def store_pending_detection(
    session_id: str,
    predicted_student_id: str,
    candidate_scores: List[Dict[str, Any]],
    embedding: List[float],
    bbox: List[int],
    quality_metrics: Dict[str, Any],
    liveness_metrics: Dict[str, Any],
    confidence: float,
    fused_confidence: float,
    period_id: Optional[str] = None,
    retention_minutes: int = 30,
) -> Tuple[str, Dict[str, Any]]:
    """
    Store a pending face detection snapshot.
    
    This function should be called from detect-face-only after a successful
    detection and identity prediction.
    
    Args:
        session_id: Browser tab / device session ID
        predicted_student_id: Top candidate student ID
        candidate_scores: List of [{"student_id": "...", "similarity": 0.xx}, ...]
        embedding: FaceNet embedding vector
        bbox: [x, y, width, height] bounding box in image
        quality_metrics: {"tier": "HIGH", "score": 0.86, "frontality": 0.91, "sharpness": 0.82}
        liveness_metrics: {"is_live": True, "score": 0.74, "method": "blink_texture"}
        confidence: Top candidate similarity score
        fused_confidence: Fused confidence combining quality, liveness, similarity
        period_id: Optional class period ID
        retention_minutes: Retention time for pending detection (default 30 min)
    
    Returns:
        Tuple of (detection_id, detection_data)
    
    Raises:
        FaceRepositoryError: If storage fails
    """
    try:
        repo = FaceProfileRepository()
        
        detection_id = create_detection_id()
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=retention_minutes)
        
        detection_data = {
            "detection_id": detection_id,
            "session_id": session_id,
            "predicted_student_id": predicted_student_id,
            "candidate_scores": candidate_scores,
            
            "embedding": embedding,
            "embedding_model": "facenet_vggface2",
            
            "bbox": bbox,
            "quality": quality_metrics,
            "liveness": liveness_metrics,
            
            "confidence": confidence,
            "fused_confidence": fused_confidence,
            
            "period_id": period_id,
            "created_at": now.isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z",
            "used_for_learning": False,
        }
        
        repo.store_pending_detection(detection_id, detection_data)
        
        logger.info(
            f"✓ Stored pending detection {detection_id} for {predicted_student_id}"
        )
        return detection_id, detection_data
    
    except Exception as exc:
        msg = f"Failed to store pending detection: {exc}"
        logger.error(msg, exc_info=True)
        raise FaceRepositoryError(msg) from exc


def clean_expired_detections() -> int:
    """
    Remove expired pending detections (older than 30 minutes).
    
    Should be called periodically by a background task.
    
    Returns:
        Count of deleted detections
    """
    try:
        repo = FaceProfileRepository()
        count = repo.delete_expired_detections(older_than_seconds=1800)
        if count > 0:
            logger.info(f"Cleaned up {count} expired pending detections")
        return count
    except Exception as exc:
        logger.error(f"Error cleaning up detections: {exc}")
        return 0
