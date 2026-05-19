"""
Face Confirmation Learning API endpoints.

Provides endpoints for:
- POST /api/v1/attendance/face-confirmation
- GET /api/v1/attendance/face-profile/{student_id}/diagnostics
"""

import logging
import uuid
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from decorators.auth import get_user, UserRole
from services.face_confirmation_service import FaceConfirmationService
from services.face_profile_learning_service import FaceProfileLearningService
from database.face_profile_repository import FaceProfileRepository
from schemas.face_confirmation_schemas import (
    FaceConfirmationRequest,
    FaceConfirmationResponse,
    FaceProfileDiagnostics,
)
from utils.face_exceptions import (
    FaceConfirmationError,
    FaceAuthorizationError,
    FaceIdentityMismatchError,
    FaceDetectionNotFoundError,
    FaceDetectionExpiredError,
    FaceProfileNotFoundError,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/attendance", tags=["Face Confirmation Learning"])


# ════════════════════════════════════════════════════════════════════════════════
# Service Dependencies
# ════════════════════════════════════════════════════════════════════════════════

def get_confirmation_service() -> FaceConfirmationService:
    """Get face confirmation service instance."""
    return FaceConfirmationService()


def get_learning_service() -> FaceProfileLearningService:
    """Get face profile learning service instance."""
    return FaceProfileLearningService()


def get_profile_repo() -> FaceProfileRepository:
    """Get face profile repository instance."""
    return FaceProfileRepository()


# ════════════════════════════════════════════════════════════════════════════════
# Face Confirmation Endpoint
# ════════════════════════════════════════════════════════════════════════════════

@router.post(
    "/face-confirmation",
    response_model=FaceConfirmationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit face confirmation ('Yes, this is me' / 'No, this is not me')",
    responses={
        200: {"description": "Confirmation accepted and learning queued"},
        400: {"description": "Invalid confirmation request"},
        401: {"description": "Unauthorized"},
        404: {"description": "Detection not found or expired"},
    }
)
async def submit_face_confirmation(
    body: FaceConfirmationRequest,
    user = Depends(get_user),
    svc: FaceConfirmationService = Depends(get_confirmation_service),
    learning_svc: FaceProfileLearningService = Depends(get_learning_service),
    repo: FaceProfileRepository = Depends(get_profile_repo),
):
    """
    Submit a face confirmation event.
    
    When a student clicks "Yes, this is me" or "No, this is not me", this endpoint:
    1. Validates the confirmation request
    2. Stores an immutable confirmation event
    3. For positive confirmations: queues a learning task
    4. Refreshes the session anchor
    
    **Request Body**:
    - `session_id`: Tab/device session ID (from camera session)
    - `period_id`: Class period ID
    - `predicted_student_id`: System's face recognition prediction
    - `confirmed_student_id`: Student ID being confirmed
    - `detection_id`: Reference to the pending face detection
    - `yes_this_is_me`: true for positive confirmation, false for negative
    - `client_timestamp`: ISO 8601 client timestamp (optional)
    
    **Response**:
    - `accepted`: Whether confirmation was accepted
    - `learning_status`: 'queued', 'skipped', or 'logged_negative'
    - `anchor_refreshed`: Whether session anchor was refreshed
    - `message`: Human-readable status message
    """
    try:
        # Process the confirmation
        success, learning_status, result = svc.process_confirmation(
            session_id=body.session_id,
            period_id=body.period_id,
            predicted_student_id=body.predicted_student_id,
            confirmed_student_id=body.confirmed_student_id,
            detection_id=body.detection_id,
            yes_this_is_me=body.yes_this_is_me,
            authenticated_user_id=user.user_id,
            authenticated_user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            client_timestamp=body.client_timestamp,
        )
        
        # If positive confirmation, apply learning
        if body.yes_this_is_me:
            try:
                # Fetch the detection to get embedding and metrics
                detection = repo.get_pending_detection(body.detection_id)
                
                # Run gated learning
                sample_accepted, gates = learning_svc.apply_positive_confirmation(
                    event_id=result.get("event_id", ""),
                    confirmed_student_id=body.confirmed_student_id,
                    detection_id=body.detection_id,
                    embedding=detection.get("embedding", []),
                    quality_tier=detection.get("quality", {}).get("tier", "LOW"),
                    quality_score=detection.get("quality", {}).get("score", 0.0),
                    liveness_score=detection.get("liveness", {}).get("score", 0.0),
                    fused_confidence=detection.get("fused_confidence", 0.0),
                    similarity=detection.get("candidate_scores", [{}])[0].get("similarity", 0.0),
                )
                
                if sample_accepted:
                    learning_status = "learning_applied"
                else:
                    learning_status = "learning_gated_out"
                    logger.info(f"Learning gates rejected: {gates.details}")
            
            except FaceDetectionNotFoundError as exc:
                logger.warning(f"Detection not found for learning: {exc}")
                learning_status = "detection_not_found"
            except Exception as exc:
                logger.error(f"Error applying learning: {exc}", exc_info=True)
                learning_status = "learning_error"
        
        return FaceConfirmationResponse(
            accepted=True,
            learning_status=learning_status,
            anchor_refreshed=result.get("anchor_refreshed", False),
            message=f"Face confirmation saved. Status: {learning_status}",
        )
    
    except FaceAuthorizationError as exc:
        logger.warning(f"Authorization error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    
    except (FaceDetectionNotFoundError, FaceDetectionExpiredError) as exc:
        logger.warning(f"Detection error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    
    except FaceIdentityMismatchError as exc:
        logger.warning(f"Identity mismatch: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    
    except FaceConfirmationError as exc:
        logger.error(f"Confirmation error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    
    except Exception as exc:
        logger.error(f"Unexpected error in face confirmation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing face confirmation",
        )


# ════════════════════════════════════════════════════════════════════════════════
# Face Profile Diagnostics Endpoint
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/face-profile/{student_id}/diagnostics",
    response_model=FaceProfileDiagnostics,
    status_code=status.HTTP_200_OK,
    summary="Get face profile diagnostics",
    responses={
        200: {"description": "Profile diagnostics retrieved"},
        403: {"description": "Unauthorized to view this student's profile"},
        404: {"description": "Profile not found"},
    }
)
async def get_face_profile_diagnostics(
    student_id: str,
    user = Depends(get_user),
    repo: FaceProfileRepository = Depends(get_profile_repo),
):
    """
    Get diagnostics for a student's face profile.
    
    **Authorization**:
    - Students can view only their own profile
    - Teachers/admins can view any student's profile
    
    **Response Fields**:
    - `student_id`: Student identifier
    - `sample_count`: Total samples ever added to profile
    - `trusted_sample_count`: Current samples in the profile
    - `variance`: Embedding variance (stability metric)
    - `adaptive_threshold`: Per-student similarity threshold
    - `last_updated_at`: Last profile update timestamp
    - `needs_reenrollment`: Flag if profile quality is poor
    """
    try:
        # Authorization check
        if user.role == UserRole.STUDENT and user.user_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own profile",
            )
        
        # Get profile
        profile = repo.get_profile(student_id)
        
        # Get samples
        samples = repo.get_profile_samples(student_id, limit=100)
        
        # Determine if re-enrollment is needed
        needs_reenrollment = False
        if profile.get("variance", 0.0) > 0.1:  # High variance indicates instability
            needs_reenrollment = True
        if profile.get("trusted_sample_count", 0) < 3:
            needs_reenrollment = True
        
        return FaceProfileDiagnostics(
            student_id=student_id,
            sample_count=profile.get("sample_count", len(samples)),
            trusted_sample_count=profile.get("trusted_sample_count", len(samples)),
            variance=profile.get("variance", 0.0),
            adaptive_threshold=profile.get("adaptive_threshold", 0.70),
            last_updated_at=profile.get("last_updated_at", datetime.utcnow()),
            needs_reenrollment=needs_reenrollment,
        )
    
    except FaceProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No face profile found for student {student_id}",
        )
    
    except Exception as exc:
        logger.error(f"Error getting profile diagnostics: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving profile diagnostics",
        )
