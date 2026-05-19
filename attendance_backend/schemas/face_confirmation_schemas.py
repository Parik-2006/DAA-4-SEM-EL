"""
Face Confirmation Learning schemas.

Pydantic schemas for face profiles, confirmations, and learning events.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════════════════════════
# Detection & Confirmation Request/Response Schemas
# ════════════════════════════════════════════════════════════════════════════════

class FaceConfirmationRequest(BaseModel):
    """Request body for POST /api/v1/attendance/face-confirmation."""
    
    session_id: str = Field(..., description="Tab/device session ID")
    period_id: str = Field(..., description="Class period ID")
    predicted_student_id: str = Field(..., description="System's predicted student ID")
    confirmed_student_id: str = Field(..., description="Student ID confirmed by user")
    detection_id: str = Field(..., description="Reference to pending detection")
    yes_this_is_me: bool = Field(default=True, description="True for positive, False for negative")
    client_timestamp: Optional[str] = Field(None, description="ISO 8601 client timestamp")


class FaceConfirmationResponse(BaseModel):
    """Response body for face-confirmation endpoint."""
    
    accepted: bool = Field(..., description="Whether confirmation was accepted")
    learning_status: str = Field(..., description="'queued', 'skipped', or 'error'")
    anchor_refreshed: bool = Field(default=False, description="Session anchor refreshed")
    message: str = Field(..., description="Human-readable message")
    error: Optional[str] = Field(None, description="Error details if applicable")


# ════════════════════════════════════════════════════════════════════════════════
# Pending Detection Schema
# ════════════════════════════════════════════════════════════════════════════════

class QualityMetrics(BaseModel):
    """Face detection quality metrics."""
    
    tier: str = Field(..., description="'HIGH', 'ACCEPTABLE', or 'LOW'")
    score: float = Field(..., ge=0.0, le=1.0, description="Quality score 0-1")
    frontality: float = Field(..., ge=0.0, le=1.0, description="Face frontality score")
    sharpness: float = Field(..., ge=0.0, le=1.0, description="Image sharpness score")


class LivenessMetrics(BaseModel):
    """Liveness detection metrics."""
    
    is_live: bool = Field(..., description="Liveness detection result")
    score: float = Field(..., ge=0.0, le=1.0, description="Liveness confidence")
    method: str = Field(..., description="Detection method e.g. 'blink_texture'")


class CandidateScore(BaseModel):
    """Ranked candidate in scoped search."""
    
    student_id: str = Field(..., description="Candidate student ID")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity")


class PendingFaceDetection(BaseModel):
    """Short-lived snapshot of face detection for confirmation."""
    
    detection_id: str = Field(..., description="Unique detection identifier")
    session_id: str = Field(..., description="Session that created this detection")
    predicted_student_id: str = Field(..., description="Top candidate student")
    candidate_scores: List[CandidateScore] = Field(default_factory=list)
    
    embedding: List[float] = Field(..., description="FaceNet embedding vector")
    embedding_model: str = Field(..., description="Model version e.g. 'facenet_vggface2'")
    
    bbox: List[int] = Field(..., description="[x, y, width, height] bounding box")
    quality: QualityMetrics = Field(..., description="Quality metrics")
    liveness: LivenessMetrics = Field(..., description="Liveness metrics")
    
    confidence: float = Field(..., ge=0.0, le=1.0)
    fused_confidence: float = Field(..., ge=0.0, le=1.0)
    
    period_id: str = Field(..., description="Class period ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Expiry timestamp")
    used_for_learning: bool = Field(default=False)


# ════════════════════════════════════════════════════════════════════════════════
# Face Confirmation Event Schema
# ════════════════════════════════════════════════════════════════════════════════

class FaceConfirmationEvent(BaseModel):
    """Immutable audit-grade record of user's face confirmation."""
    
    event_id: str = Field(..., description="Unique event ID")
    detection_id: str = Field(..., description="Reference to detection")
    session_id: str = Field(..., description="Session ID")
    
    confirmed_student_id: str = Field(..., description="Student being confirmed")
    predicted_student_id: str = Field(..., description="System's prediction")
    
    confirmed_by: str = Field(..., description="User who confirmed")
    confirmed_by_role: str = Field(..., description="'student', 'teacher', 'admin'")
    
    decision: str = Field(..., description="'positive' or 'negative'")
    
    quality_tier: str = Field(..., description="Quality of the sample")
    similarity: float = Field(..., ge=0.0, le=1.0)
    fused_confidence: float = Field(..., ge=0.0, le=1.0)
    liveness_score: float = Field(..., ge=0.0, le=1.0)
    
    learning_action: str = Field(..., description="'queued', 'skipped', 'pending_review'")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ════════════════════════════════════════════════════════════════════════════════
# Face Profile Schema
# ════════════════════════════════════════════════════════════════════════════════

class FaceProfile(BaseModel):
    """User's learned face embedding profile."""
    
    student_id: str = Field(..., description="Student ID")
    model_version: str = Field(..., description="Embedding model version")
    
    centroid: List[float] = Field(..., description="Mean embedding vector")
    variance: float = Field(..., ge=0.0, description="Embedding variance")
    
    sample_count: int = Field(default=0, description="Total samples ever added")
    trusted_sample_count: int = Field(default=0, description="Samples in current profile")
    
    last_positive_similarity: float = Field(default=0.0, description="Latest positive confirmation similarity")
    rolling_similarity_mean: float = Field(default=0.0, description="Mean similarity of recent samples")
    rolling_similarity_std: float = Field(default=0.0, description="Std dev of similarities")
    
    adaptive_threshold: float = Field(..., ge=0.62, le=0.88, description="Per-user similarity threshold")
    
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="active", description="'active' or 'inactive'")


class FaceProfileSample(BaseModel):
    """Individual trusted sample in a face profile."""
    
    sample_id: str = Field(..., description="Unique sample ID")
    source: str = Field(..., description="'enrollment' or 'yes_this_is_me'")
    
    embedding: List[float] = Field(..., description="FaceNet embedding")
    quality_score: float = Field(..., ge=0.0, le=1.0)
    quality_tier: str = Field(..., description="'HIGH', 'ACCEPTABLE', 'LOW'")
    liveness_score: float = Field(..., ge=0.0, le=1.0)
    
    similarity_to_old_centroid: float = Field(default=0.0, description="Similarity before update")
    accepted_for_profile: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FaceProfileDiagnostics(BaseModel):
    """Diagnostics response for face profile."""
    
    student_id: str = Field(..., description="Student ID")
    sample_count: int = Field(..., description="Total samples")
    trusted_sample_count: int = Field(..., description="Current profile samples")
    variance: float = Field(..., ge=0.0)
    adaptive_threshold: float = Field(..., ge=0.62, le=0.88)
    last_updated_at: datetime = Field(...)
    needs_reenrollment: bool = Field(default=False, description="Flag if profile quality is poor")


# ════════════════════════════════════════════════════════════════════════════════
# Confusable Pair Schema
# ════════════════════════════════════════════════════════════════════════════════

class ConfusablePair(BaseModel):
    """Track students who are frequently confused by the face recognition system."""
    
    student_a: str = Field(..., description="First student ID")
    student_b: str = Field(..., description="Second student ID")
    count: int = Field(default=1, description="Number of confusions")
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(default="raise_threshold", description="Recommended action")


# ════════════════════════════════════════════════════════════════════════════════
# Internal Learning Event Schema
# ════════════════════════════════════════════════════════════════════════════════

class FaceLearningGates(BaseModel):
    """Result of all learning gates for a confirmation."""
    
    auth_gate_passed: bool = Field(default=False)
    detection_gate_passed: bool = Field(default=False)
    identity_gate_passed: bool = Field(default=False)
    quality_gate_passed: bool = Field(default=False)
    liveness_gate_passed: bool = Field(default=False)
    similarity_gate_passed: bool = Field(default=False)
    anti_drift_gate_passed: bool = Field(default=False)
    
    details: Dict[str, Any] = Field(default_factory=dict, description="Gate-specific details")

    @property
    def all_passed(self) -> bool:
        """Check if all gates passed."""
        return all([
            self.auth_gate_passed,
            self.detection_gate_passed,
            self.identity_gate_passed,
            self.quality_gate_passed,
            self.liveness_gate_passed,
            self.similarity_gate_passed,
            self.anti_drift_gate_passed,
        ])
