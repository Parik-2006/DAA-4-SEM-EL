"""
Face Profile Learning Service.

Applies gated learning algorithm to update user profiles from confirmed samples.
"""

import logging
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from database.face_profile_repository import FaceProfileRepository
from schemas.face_confirmation_schemas import FaceLearningGates
from utils.face_exceptions import (
    FaceLearningError,
    FaceLearningGateError,
    FaceAntiDriftError,
    FaceProfileNotFoundError,
)


logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# Learning Configuration
# ════════════════════════════════════════════════════════════════════════════════

class LearningGateConfig:
    """Configuration for learning gates."""
    
    # Quality gate
    QUALITY_SCORE_MIN = 0.70
    QUALITY_SCORE_MIN_NEW = 0.80  # Stricter for new profiles
    
    # Liveness gate
    LIVENESS_SCORE_MIN = 0.55
    LIVENESS_SCORE_MIN_NEW = 0.65  # Stricter for new profiles
    
    # Fused confidence gate
    FUSED_CONFIDENCE_MIN = 0.68
    
    # Similarity gate
    SIMILARITY_MIN = 0.62
    SIMILARITY_MARGIN_FROM_THRESHOLD = -0.08  # Allow slightly below threshold
    
    # Anti-drift gate
    OUTLIER_THRESHOLD_STD = 2.5  # Reject samples > 2.5 sigma from mean
    
    # Profile configuration
    MAX_TRUSTED_SAMPLES = 50  # Cap samples to prevent drift
    MIN_INITIAL_SAMPLES = 3  # Require 3 samples before updating profile


class FaceProfileLearningService:
    """
    Service for applying gated learning to face profiles.
    
    Responsibilities:
    - Validate sample quality through multiple gates
    - Apply anti-drift checks
    - Update or create profile prototypes
    - Manage sample capping
    - Refresh search indexes
    """
    
    def __init__(self):
        """Initialize service with dependencies."""
        self.repo = FaceProfileRepository()
        self.config = LearningGateConfig()
    
    def apply_positive_confirmation(
        self,
        event_id: str,
        confirmed_student_id: str,
        detection_id: str,
        embedding: List[float],
        quality_tier: str,
        quality_score: float,
        liveness_score: float,
        fused_confidence: float,
        similarity: float,
    ) -> Tuple[bool, FaceLearningGates]:
        """
        Apply a positive confirmation to update or create a face profile.
        
        Args:
            event_id: Confirmation event ID
            confirmed_student_id: Student being confirmed
            detection_id: Reference to detection
            embedding: FaceNet embedding vector
            quality_tier: 'HIGH', 'ACCEPTABLE', 'LOW'
            quality_score: Quality score 0-1
            liveness_score: Liveness score 0-1
            fused_confidence: Fused confidence 0-1
            similarity: Similarity to existing centroid (or new centroid)
        
        Returns:
            Tuple of (sample_accepted, gates_result)
        
        Raises:
            FaceLearningError: If learning fails
        """
        try:
            # Run all gates
            gates = self._run_learning_gates(
                confirmed_student_id,
                quality_tier,
                quality_score,
                liveness_score,
                fused_confidence,
                similarity,
                embedding,
            )
            
            # Check if all gates passed
            if not gates.all_passed:
                logger.info(
                    f"Learning gates rejected sample for {confirmed_student_id}: "
                    f"gates={gates.details}"
                )
                return False, gates
            
            # Get or create profile
            try:
                profile = self.repo.get_profile(confirmed_student_id)
                is_new_profile = False
            except FaceProfileNotFoundError:
                profile = self._create_initial_profile(confirmed_student_id, embedding)
                is_new_profile = True
            
            # Store the sample
            sample_id = self._generate_sample_id()
            centroid = profile.get("centroid", [])
            
            self.repo.add_profile_sample(
                student_id=confirmed_student_id,
                sample_id=sample_id,
                embedding=embedding,
                quality_score=quality_score,
                quality_tier=quality_tier,
                liveness_score=liveness_score,
                source="yes_this_is_me",
                similarity_to_centroid=similarity if not is_new_profile else 0.0,
            )
            
            # Update profile (centroid, variance, threshold)
            samples = self.repo.get_profile_samples(confirmed_student_id)
            if len(samples) >= self.config.MIN_INITIAL_SAMPLES or is_new_profile:
                self._update_profile_prototype(
                    confirmed_student_id,
                    profile,
                    samples,
                )
            
            logger.info(f"✓ Profile updated for {confirmed_student_id}")
            return True, gates
        
        except FaceLearningGateError:
            gates = FaceLearningGates()
            gates.details = {"error": "Gate validation failed"}
            return False, gates
        except Exception as exc:
            msg = f"Error applying positive confirmation: {exc}"
            logger.error(msg, exc_info=True)
            raise FaceLearningError(msg) from exc
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Learning Gates
    # ══════════════════════════════════════════════════════════════════════════════
    
    def _run_learning_gates(
        self,
        confirmed_student_id: str,
        quality_tier: str,
        quality_score: float,
        liveness_score: float,
        fused_confidence: float,
        similarity: float,
        embedding: List[float],
    ) -> FaceLearningGates:
        """Run all learning gates for a sample."""
        gates = FaceLearningGates()
        
        # Auth gate (already done in FaceConfirmationService)
        gates.auth_gate_passed = True
        
        # Detection gate (already done in FaceConfirmationService)
        gates.detection_gate_passed = True
        
        # Identity gate (already done in FaceConfirmationService)
        gates.identity_gate_passed = True
        
        # Quality gate
        try:
            profile_exists = self.repo.profile_exists(confirmed_student_id)
            min_quality = self.config.QUALITY_SCORE_MIN if profile_exists else self.config.QUALITY_SCORE_MIN_NEW
            
            if quality_score < min_quality:
                gates.quality_gate_passed = False
                gates.details["quality_gate"] = {
                    "passed": False,
                    "score": quality_score,
                    "min_required": min_quality,
                    "reason": "Quality score too low"
                }
            else:
                gates.quality_gate_passed = True
                gates.details["quality_gate"] = {"passed": True, "score": quality_score}
        
        except Exception as exc:
            logger.warning(f"Error checking quality gate: {exc}")
            gates.quality_gate_passed = False
            gates.details["quality_gate"] = {"error": str(exc)}
        
        # Liveness gate
        try:
            profile_exists = self.repo.profile_exists(confirmed_student_id)
            min_liveness = self.config.LIVENESS_SCORE_MIN if profile_exists else self.config.LIVENESS_SCORE_MIN_NEW
            
            if liveness_score < min_liveness:
                gates.liveness_gate_passed = False
                gates.details["liveness_gate"] = {
                    "passed": False,
                    "score": liveness_score,
                    "min_required": min_liveness,
                    "reason": "Liveness score too low"
                }
            else:
                gates.liveness_gate_passed = True
                gates.details["liveness_gate"] = {"passed": True, "score": liveness_score}
        
        except Exception as exc:
            logger.warning(f"Error checking liveness gate: {exc}")
            gates.liveness_gate_passed = False
            gates.details["liveness_gate"] = {"error": str(exc)}
        
        # Fused confidence gate
        if fused_confidence < self.config.FUSED_CONFIDENCE_MIN:
            gates.similarity_gate_passed = False
            gates.details["confidence_gate"] = {
                "passed": False,
                "confidence": fused_confidence,
                "min_required": self.config.FUSED_CONFIDENCE_MIN,
            }
        else:
            gates.similarity_gate_passed = True
            gates.details["confidence_gate"] = {"passed": True, "confidence": fused_confidence}
        
        # Similarity gate
        try:
            profile_exists = self.repo.profile_exists(confirmed_student_id)
            if profile_exists:
                profile = self.repo.get_profile(confirmed_student_id)
                adaptive_threshold = profile.get("adaptive_threshold", self.config.SIMILARITY_MIN)
                min_similarity = max(
                    self.config.SIMILARITY_MIN,
                    adaptive_threshold + self.config.SIMILARITY_MARGIN_FROM_THRESHOLD,
                )
                
                if similarity < min_similarity:
                    gates.similarity_gate_passed = False
                    gates.details["similarity_gate"] = {
                        "passed": False,
                        "similarity": similarity,
                        "min_required": min_similarity,
                        "threshold": adaptive_threshold,
                    }
                else:
                    gates.similarity_gate_passed = True
                    gates.details["similarity_gate"] = {"passed": True, "similarity": similarity}
            else:
                # New profile: pass similarity gate
                gates.similarity_gate_passed = True
                gates.details["similarity_gate"] = {"passed": True, "new_profile": True}
        
        except Exception as exc:
            logger.warning(f"Error checking similarity gate: {exc}")
            gates.similarity_gate_passed = False
            gates.details["similarity_gate"] = {"error": str(exc)}
        
        # Anti-drift gate
        try:
            if self.repo.profile_exists(confirmed_student_id):
                profile = self.repo.get_profile(confirmed_student_id)
                centroid = profile.get("centroid", [])
                rolling_mean = profile.get("rolling_similarity_mean", 0.0)
                rolling_std = profile.get("rolling_similarity_std", 0.0)
                
                # Check if sample is outlier
                if rolling_std > 0:
                    zscore = abs(similarity - rolling_mean) / rolling_std
                    if zscore > self.config.OUTLIER_THRESHOLD_STD:
                        gates.anti_drift_gate_passed = False
                        gates.details["anti_drift_gate"] = {
                            "passed": False,
                            "zscore": zscore,
                            "max_allowed": self.config.OUTLIER_THRESHOLD_STD,
                            "reason": "Outlier detected"
                        }
                    else:
                        gates.anti_drift_gate_passed = True
                        gates.details["anti_drift_gate"] = {"passed": True, "zscore": zscore}
                else:
                    gates.anti_drift_gate_passed = True
                    gates.details["anti_drift_gate"] = {"passed": True, "new_profile": True}
            else:
                # New profile: pass anti-drift gate
                gates.anti_drift_gate_passed = True
                gates.details["anti_drift_gate"] = {"passed": True, "new_profile": True}
        
        except Exception as exc:
            logger.warning(f"Error checking anti-drift gate: {exc}")
            gates.anti_drift_gate_passed = False
            gates.details["anti_drift_gate"] = {"error": str(exc)}
        
        return gates
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Profile Updates
    # ══════════════════════════════════════════════════════════════════════════════
    
    def _create_initial_profile(
        self,
        student_id: str,
        embedding: List[float],
    ) -> Dict[str, Any]:
        """Create initial profile from first embedding."""
        centroid = self._normalize_embedding(embedding)
        variance = 0.0
        adaptive_threshold = 0.70  # Initial conservative threshold
        
        return self.repo.create_or_update_profile(
            student_id=student_id,
            centroid=centroid,
            variance=variance,
            adaptive_threshold=adaptive_threshold,
            trusted_sample_count=1,
            sample_count=1,
        )
    
    def _update_profile_prototype(
        self,
        student_id: str,
        old_profile: Dict[str, Any],
        recent_samples: List[Dict[str, Any]],
    ) -> None:
        """Recompute centroid, variance, and threshold from recent samples."""
        try:
            # Cap samples
            samples_to_use = recent_samples[:self.config.MAX_TRUSTED_SAMPLES]
            
            if not samples_to_use:
                logger.warning(f"No samples to update profile for {student_id}")
                return
            
            # Extract embeddings and compute centroid
            embeddings = [np.array(s.get("embedding", [])) for s in samples_to_use]
            embeddings = [e for e in embeddings if len(e) > 0]
            
            if not embeddings:
                logger.warning(f"No valid embeddings for {student_id}")
                return
            
            # Compute new centroid
            centroid = np.mean(embeddings, axis=0)
            centroid = self._normalize_embedding(centroid.tolist())
            
            # Compute variance
            variance = float(np.mean([
                np.linalg.norm(e - np.array(centroid)) ** 2
                for e in embeddings
            ]))
            
            # Compute similarity statistics
            similarities = [
                self._cosine_similarity(centroid, e.tolist())
                for e in embeddings
            ]
            rolling_mean = float(np.mean(similarities)) if similarities else 0.0
            rolling_std = float(np.std(similarities)) if similarities else 0.0
            
            # Update adaptive threshold
            adaptive_threshold = self._compute_adaptive_threshold(
                rolling_mean,
                rolling_std,
            )
            
            # Update profile
            self.repo.create_or_update_profile(
                student_id=student_id,
                centroid=centroid,
                variance=variance,
                adaptive_threshold=adaptive_threshold,
                model_version="facenet_vggface2",
                trusted_sample_count=len(samples_to_use),
                sample_count=old_profile.get("sample_count", len(samples_to_use)),
            )
            
            logger.info(
                f"✓ Updated profile for {student_id}: "
                f"samples={len(samples_to_use)}, "
                f"var={variance:.4f}, "
                f"threshold={adaptive_threshold:.4f}"
            )
        
        except Exception as exc:
            logger.error(f"Error updating profile for {student_id}: {exc}", exc_info=True)
    
    # ══════════════════════════════════════════════════════════════════════════════
    # Utility Methods
    # ══════════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _normalize_embedding(embedding: List[float]) -> List[float]:
        """Normalize embedding to unit length."""
        arr = np.array(embedding)
        norm = np.linalg.norm(arr)
        if norm == 0:
            return embedding
        return (arr / norm).tolist()
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    
    @staticmethod
    def _compute_adaptive_threshold(mean: float, std: float) -> float:
        """Compute adaptive threshold from similarity statistics."""
        threshold = mean - 1.0 * std
        threshold = max(0.62, min(0.88, threshold))  # Clamp to safe range
        return float(threshold)
    
    @staticmethod
    def _generate_sample_id() -> str:
        """Generate unique sample ID."""
        import uuid
        return f"fps_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
