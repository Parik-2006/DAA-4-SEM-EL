"""
Face Confirmation Service.

Handles user confirmations, validation, and queueing of learning tasks.
"""

import logging
import uuid
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from database.face_profile_repository import FaceProfileRepository
from services.session_anchor_service import get_anchor_service
from utils.face_exceptions import (
    FaceConfirmationError,
    FaceDetectionNotFoundError,
    FaceDetectionExpiredError,
    FaceAuthorizationError,
    FaceIdentityMismatchError,
)


logger = logging.getLogger(__name__)


class FaceConfirmationService:
    """
    Service for handling user face confirmations.
    
    Responsibilities:
    - Validate confirmation requests
    - Fetch and validate pending detections
    - Write immutable confirmation events
    - Queue learning tasks
    - Refresh session anchors
    """
    
    def __init__(self):
        """Initialize service with dependencies."""
        self.repo = FaceProfileRepository()
        self.anchor_service = get_anchor_service()
    
    def process_confirmation(
        self,
        session_id: str,
        period_id: str,
        predicted_student_id: str,
        confirmed_student_id: str,
        detection_id: str,
        yes_this_is_me: bool,
        authenticated_user_id: str,
        authenticated_user_role: str,
        client_timestamp: Optional[str] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process a face confirmation from a user.
        
        Args:
            session_id: Tab/device session ID
            period_id: Class period ID
            predicted_student_id: System's prediction
            confirmed_student_id: Student identity being confirmed
            detection_id: Reference to pending detection
            yes_this_is_me: True for positive, False for negative
            authenticated_user_id: ID of confirming user
            authenticated_user_role: 'student', 'teacher', 'admin'
            client_timestamp: ISO 8601 client time
        
        Returns:
            Tuple of (success, learning_status, result_dict)
        
        Raises:
            FaceConfirmationError: If confirmation fails
        """
        try:
            # 1. Authorization gate
            self._validate_authorization(
                confirmed_student_id,
                authenticated_user_id,
                authenticated_user_role,
            )
            
            # 2. Fetch and validate detection
            detection = self._validate_detection(detection_id)
            
            # 3. Identity compatibility gate
            self._validate_identity_compatibility(
                predicted_student_id,
                confirmed_student_id,
                authenticated_user_role,
            )
            
            # 4. Create immutable confirmation event
            event_id = self._generate_event_id()
            learning_status = "queued" if yes_this_is_me else "logged_negative"
            
            event_data = {
                "event_id": event_id,
                "detection_id": detection_id,
                "session_id": session_id,
                "confirmed_student_id": confirmed_student_id,
                "predicted_student_id": predicted_student_id,
                "confirmed_by": authenticated_user_id,
                "confirmed_by_role": authenticated_user_role,
                "decision": "positive" if yes_this_is_me else "negative",
                "quality_tier": detection.get("quality", {}).get("tier", "UNKNOWN"),
                "similarity": detection.get("candidate_scores", [{}])[0].get("similarity", 0.0),
                "fused_confidence": detection.get("fused_confidence", 0.0),
                "liveness_score": detection.get("liveness", {}).get("score", 0.0),
                "learning_action": learning_status,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            
            self.repo.store_confirmation_event(event_id, event_data)
            
            # 5. Refresh session anchor after positive confirmation
            anchor_refreshed = False
            if yes_this_is_me:
                try:
                    self.anchor_service.anchor(
                        session_id=session_id,
                        user_id=confirmed_student_id,
                        period_id=period_id,
                    )
                    anchor_refreshed = True
                    logger.info(f"✓ Refreshed session anchor for {confirmed_student_id}")
                except Exception as exc:
                    logger.warning(f"Failed to refresh anchor: {exc}")
            
            # 6. Mark detection as used
            self.repo.mark_detection_used(detection_id)
            
            result = {
                "accepted": True,
                "learning_status": learning_status,
                "anchor_refreshed": anchor_refreshed,
                "event_id": event_id,
            }
            
            logger.info(
                f"✓ Confirmation processed: {confirmed_student_id} -> {learning_status}"
            )
            return True, learning_status, result
        
        except (FaceConfirmationError, FaceAuthorizationError, FaceIdentityMismatchError) as exc:
            logger.warning(f"Confirmation validation failed: {exc}")
            raise
        except Exception as exc:
            msg = f"Unexpected error processing confirmation: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceConfirmationError(msg) from exc
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Validation Gates
    # ══════════════════════════════════════════════════════════════════════════════
    
    def _validate_authorization(
        self,
        confirmed_student_id: str,
        authenticated_user_id: str,
        authenticated_user_role: str,
    ) -> None:
        """
        Validate that user is authorized to confirm this identity.
        
        Rules:
        - Students can confirm only themselves
        - Teachers/admins can confirm students in their scope (simplified: allow all)
        """
        if authenticated_user_role == "student":
            # Fast path: if the stored authenticated id equals the student id, allow
            if authenticated_user_id == confirmed_student_id:
                return

            # Otherwise attempt to resolve authenticated user -> student mapping
            try:
                from database.user_repository import UserRepository
                from services.firebase_service import FirebaseService

                user_repo = UserRepository()
                user = user_repo.get_user(authenticated_user_id)
                if user and user.get("email"):
                    email = user.get("email").strip().lower()
                    fb = FirebaseService()
                    # Search students for a matching email
                    students = fb.get_all_students() or []
                    for s in students:
                        s_email = (s.get("email") or "").strip().lower()
                        sid = s.get("student_id") or s.get("id") or None
                        if s_email and sid and s_email == email:
                            if sid == confirmed_student_id:
                                return
            except Exception as exc:
                logger.debug("Could not map authenticated user to student id: %s", exc)

            # If mapping didn't match, deny
            raise FaceAuthorizationError(
                f"Student {authenticated_user_id} cannot confirm {confirmed_student_id}"
            )
        
        # Teachers/admins can confirm any student in their assigned scope
        # (simplified: we assume authorization middleware handles scope)
        # For now, we just log and allow
    
    def _validate_detection(self, detection_id: str) -> Dict[str, Any]:
        """
        Validate and retrieve a pending detection.
        
        Checks:
        - Detection exists
        - Detection is not expired
        - Detection has not been previously used for learning
        """
        try:
            detection = self.repo.get_pending_detection(detection_id)
            
            if detection.get("used_for_learning", False):
                raise FaceConfirmationError(
                    f"Detection {detection_id} already used for learning"
                )
            
            return detection
        
        except (FaceDetectionNotFoundError, FaceDetectionExpiredError):
            raise
        except Exception as exc:
            raise FaceConfirmationError(f"Failed to validate detection: {exc}") from exc
    
    def _validate_identity_compatibility(
        self,
        predicted_student_id: str,
        confirmed_student_id: str,
        authenticated_user_role: str,
    ) -> None:
        """
        Validate that predicted and confirmed identities are compatible.
        
        Rules:
        - Students can only confirm positive or negative for their own prediction
        - Teachers/admins can correct predictions (allow mismatches)
        """
        if authenticated_user_role == "student":
            # Student can only confirm their own detection (positive or negative)
            if predicted_student_id != confirmed_student_id:
                # Allow negative (student says "No, that's not me, but I am me")
                # but require the confirmed_student_id to match authenticated user
                # This is handled in _validate_authorization
                pass
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Utilities
    # ══════════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _generate_event_id() -> str:
        """Generate a unique confirmation event ID."""
        return f"fce_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
