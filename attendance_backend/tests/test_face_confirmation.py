"""
Face Confirmation Learning Tests.

Integration and unit tests for face confirmation learning feature.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

from database.face_profile_repository import FaceProfileRepository
from services.face_confirmation_service import FaceConfirmationService
from services.face_profile_learning_service import (
    FaceProfileLearningService,
    LearningGateConfig,
)
from utils.face_exceptions import (
    FaceConfirmationError,
    FaceAuthorizationError,
    FaceDetectionNotFoundError,
    FaceProfileNotFoundError,
)


# ════════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_embedding() -> List[float]:
    """Generate a random normalized embedding."""
    embedding = np.random.randn(128).astype(float)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()


@pytest.fixture
def sample_quality_metrics() -> Dict[str, Any]:
    """Sample quality metrics."""
    return {
        "tier": "HIGH",
        "score": 0.86,
        "frontality": 0.91,
        "sharpness": 0.82,
    }


@pytest.fixture
def sample_liveness_metrics() -> Dict[str, Any]:
    """Sample liveness metrics."""
    return {
        "is_live": True,
        "score": 0.74,
        "method": "blink_texture",
    }


@pytest.fixture
def sample_candidate_scores() -> List[Dict[str, Any]]:
    """Sample candidate scores."""
    return [
        {"student_id": "STUD_001", "similarity": 0.83},
        {"student_id": "STUD_002", "similarity": 0.61},
    ]


# ════════════════════════════════════════════════════════════════════════════════
# FaceProfileRepository Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFaceProfileRepository:
    """Test FaceProfileRepository CRUD operations."""
    
    def test_profile_lifecycle(self, sample_embedding):
        """Test create, read, and update profile."""
        repo = FaceProfileRepository()
        student_id = "TEST_STUD_001"
        
        # Create profile
        profile = repo.create_or_update_profile(
            student_id=student_id,
            centroid=sample_embedding,
            variance=0.018,
            adaptive_threshold=0.70,
            trusted_sample_count=1,
            sample_count=1,
        )
        
        assert profile["student_id"] == student_id
        assert profile["adaptive_threshold"] == 0.70
        assert profile["status"] == "active"
        
        # Retrieve profile
        retrieved = repo.get_profile(student_id)
        assert retrieved["student_id"] == student_id
        
        # Check existence
        assert repo.profile_exists(student_id) is True
    
    def test_profile_not_found(self):
        """Test error when profile doesn't exist."""
        repo = FaceProfileRepository()
        
        with pytest.raises(FaceProfileNotFoundError):
            repo.get_profile("NONEXISTENT_STUDENT")
    
    def test_add_and_retrieve_samples(self, sample_embedding):
        """Test adding and retrieving profile samples."""
        repo = FaceProfileRepository()
        student_id = "TEST_STUD_002"
        
        # Create profile first
        repo.create_or_update_profile(
            student_id=student_id,
            centroid=sample_embedding,
            variance=0.018,
            adaptive_threshold=0.70,
        )
        
        # Add samples
        sample_id_1 = "fps_001"
        sample_id_2 = "fps_002"
        
        repo.add_profile_sample(
            student_id=student_id,
            sample_id=sample_id_1,
            embedding=sample_embedding,
            quality_score=0.85,
            quality_tier="HIGH",
            liveness_score=0.75,
        )
        
        repo.add_profile_sample(
            student_id=student_id,
            sample_id=sample_id_2,
            embedding=sample_embedding,
            quality_score=0.80,
            quality_tier="ACCEPTABLE",
            liveness_score=0.70,
        )
        
        # Retrieve samples
        samples = repo.get_profile_samples(student_id, limit=10)
        assert len(samples) >= 2
    
    def test_pending_detection_lifecycle(
        self,
        sample_embedding,
        sample_quality_metrics,
        sample_liveness_metrics,
        sample_candidate_scores,
    ):
        """Test storing and retrieving pending detections."""
        repo = FaceProfileRepository()
        detection_id = "det_test_001"
        
        detection_data = {
            "detection_id": detection_id,
            "session_id": "session_abc123",
            "predicted_student_id": "STUD_001",
            "candidate_scores": sample_candidate_scores,
            "embedding": sample_embedding,
            "embedding_model": "facenet_vggface2",
            "bbox": [120, 80, 310, 300],
            "quality": sample_quality_metrics,
            "liveness": sample_liveness_metrics,
            "confidence": 0.83,
            "fused_confidence": 0.79,
            "period_id": "period_001",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z",
            "used_for_learning": False,
        }
        
        # Store detection
        repo.store_pending_detection(detection_id, detection_data)
        
        # Retrieve detection
        retrieved = repo.get_pending_detection(detection_id)
        assert retrieved["detection_id"] == detection_id
        assert retrieved["predicted_student_id"] == "STUD_001"
        
        # Mark as used
        repo.mark_detection_used(detection_id)
        used_detection = repo.get_pending_detection(detection_id)
        assert used_detection["used_for_learning"] is True
    
    def test_detection_expiry(self, sample_embedding, sample_quality_metrics):
        """Test that expired detections are rejected."""
        repo = FaceProfileRepository()
        detection_id = "det_expired_001"
        
        expired_data = {
            "detection_id": detection_id,
            "session_id": "session_xyz",
            "predicted_student_id": "STUD_999",
            "embedding": sample_embedding,
            "quality": sample_quality_metrics,
            "liveness": {"is_live": True, "score": 0.75, "method": "test"},
            "created_at": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
            "used_for_learning": False,
        }
        
        repo.store_pending_detection(detection_id, expired_data)
        
        with pytest.raises(FaceDetectionExpiredError):
            repo.get_pending_detection(detection_id)
    
    def test_confirmation_event_storage(self):
        """Test storing confirmation events."""
        repo = FaceProfileRepository()
        event_id = "fce_test_001"
        
        event_data = {
            "event_id": event_id,
            "detection_id": "det_001",
            "session_id": "session_abc",
            "confirmed_student_id": "STUD_001",
            "predicted_student_id": "STUD_001",
            "confirmed_by": "STUD_001",
            "confirmed_by_role": "student",
            "decision": "positive",
            "quality_tier": "HIGH",
            "similarity": 0.83,
            "fused_confidence": 0.79,
            "liveness_score": 0.74,
            "learning_action": "queued",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        
        repo.store_confirmation_event(event_id, event_data)
        
        events = repo.get_confirmation_events("STUD_001", limit=10)
        assert len(events) >= 1


# ════════════════════════════════════════════════════════════════════════════════
# FaceProfileLearningService Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFaceProfileLearningService:
    """Test FaceProfileLearningService learning gates and profile updates."""
    
    def test_learning_gates_high_quality(self, sample_embedding):
        """Test that high-quality samples pass all gates."""
        svc = FaceProfileLearningService()
        
        gates = svc._run_learning_gates(
            confirmed_student_id="STUD_001",
            quality_tier="HIGH",
            quality_score=0.85,
            liveness_score=0.75,
            fused_confidence=0.78,
            similarity=0.80,
            embedding=sample_embedding,
        )
        
        assert gates.quality_gate_passed is True
        assert gates.liveness_gate_passed is True
        assert gates.similarity_gate_passed is True
        assert gates.anti_drift_gate_passed is True
    
    def test_learning_gates_low_quality(self, sample_embedding):
        """Test that low-quality samples fail gates."""
        svc = FaceProfileLearningService()
        
        gates = svc._run_learning_gates(
            confirmed_student_id="STUD_001",
            quality_tier="LOW",
            quality_score=0.50,
            liveness_score=0.40,
            fused_confidence=0.55,
            similarity=0.70,
            embedding=sample_embedding,
        )
        
        assert gates.quality_gate_passed is False
        assert gates.liveness_gate_passed is False
    
    def test_embedding_normalization(self):
        """Test embedding normalization."""
        svc = FaceProfileLearningService()
        
        embedding = [1.0, 2.0, 3.0, 4.0]
        normalized = svc._normalize_embedding(embedding)
        
        # Check that it's unit length
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-6
    
    def test_cosine_similarity(self):
        """Test cosine similarity computation."""
        svc = FaceProfileLearningService()
        
        a = [1.0, 0.0]
        b = [1.0, 0.0]
        c = [0.0, 1.0]
        
        # Same vectors
        sim_aa = svc._cosine_similarity(a, a)
        assert abs(sim_aa - 1.0) < 1e-6
        
        # Orthogonal vectors
        sim_ac = svc._cosine_similarity(a, c)
        assert abs(sim_ac) < 1e-6
    
    def test_adaptive_threshold_computation(self):
        """Test adaptive threshold calculation."""
        svc = FaceProfileLearningService()
        
        # High-variance profile should lower threshold
        threshold = svc._compute_adaptive_threshold(
            mean=0.80,
            std=0.05,
        )
        assert 0.62 <= threshold <= 0.88
        
        # Low-variance profile should raise threshold
        threshold_stable = svc._compute_adaptive_threshold(
            mean=0.85,
            std=0.01,
        )
        assert threshold_stable > threshold


# ════════════════════════════════════════════════════════════════════════════════
# FaceConfirmationService Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFaceConfirmationService:
    """Test FaceConfirmationService validation and authorization."""
    
    def test_student_cannot_confirm_other_student(self):
        """Test that students cannot confirm another student's identity."""
        svc = FaceConfirmationService()
        
        with pytest.raises(FaceAuthorizationError):
            svc._validate_authorization(
                confirmed_student_id="STUD_002",
                authenticated_user_id="STUD_001",
                authenticated_user_role="student",
            )
    
    def test_student_can_confirm_self(self):
        """Test that students can confirm their own identity."""
        svc = FaceConfirmationService()
        
        # Should not raise
        svc._validate_authorization(
            confirmed_student_id="STUD_001",
            authenticated_user_id="STUD_001",
            authenticated_user_role="student",
        )
    
    def test_teacher_can_confirm_students(self):
        """Test that teachers can confirm any student."""
        svc = FaceConfirmationService()
        
        # Should not raise
        svc._validate_authorization(
            confirmed_student_id="STUD_001",
            authenticated_user_id="TEACH_001",
            authenticated_user_role="teacher",
        )


# ════════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFaceConfirmationIntegration:
    """Integration tests for the full face confirmation learning pipeline."""
    
    def test_full_confirmation_workflow(self, sample_embedding):
        """Test complete confirmation and learning workflow."""
        # This is a placeholder for an integration test
        # that would need a test database
        pytest.skip("Integration test requires test database")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
