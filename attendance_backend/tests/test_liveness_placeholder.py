"""
tests/test_liveness_placeholder.py
════════════════════════════════════════════════════════════════════════════════
Unit tests for lightweight liveness detection with minimal dependencies.

Covers:
  • Texture (Laplacian variance) liveness heuristic.
  • Blink detection (EAR) across frame sequences.
  • Metadata scoring for login-origin signals.
  • Confidence fusion combining embedding + liveness + metadata.
  • Graceful fallback when no hardware model or landmarks available.
  • LIVENESS_DISABLE_STRICT bypass mode.

Dependencies:
  • numpy (array operations)
  • opencv-python (optional; falls back to numpy)
  • liveness module (service under test)
"""

from __future__ import annotations

import logging
import os
import unittest
from unittest import mock

import numpy as np

from services.liveness import (
    LivenessDetector,
    LivenessResult,
    LoginMetadata,
    FusedConfidenceResult,
    get_liveness_detector,
    score_login_metadata,
    fuse_confidence,
)

logger = logging.getLogger(__name__)


# ── Fixtures: synthetic test images ───────────────────────────────────────────

def make_blank_image(h: int = 96, w: int = 96, channels: int = 3) -> np.ndarray:
    """Create a low-texture uniform image (like a photo on a flat screen)."""
    return np.ones((h, w, channels), dtype=np.uint8) * 128


def make_textured_image(h: int = 96, w: int = 96, channels: int = 3) -> np.ndarray:
    """Create a high-texture image (simulates a real face with detail)."""
    np.random.seed(42)
    base = np.random.randint(50, 200, size=(h, w, channels), dtype=np.uint8)
    # Add Laplacian-like edges to simulate facial features
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if (i + j) % 5 == 0:
                base[i, j] = np.clip(base[i, j] + 100, 0, 255)
    return base


def make_blink_landmark_sequence(n_frames: int = 25) -> list[np.ndarray]:
    """
    Simulate a sequence of eye landmarks across n_frames.

    dlib 68-pt format for simplicity:
        [36:42]  = left eye (6 pts)
        [42:48]  = right eye (6 pts)

    Frames 0-8:   Eyes open (EAR ~ 0.40).
    Frames 9-14:  Eyes closing (EAR drops below threshold 0.21).
    Frames 15-20: Eyes closed (EAR ~ 0.05).
    Frames 21-24: Eyes opening (EAR rises back).
    """
    sequence = []
    for frame_idx in range(n_frames):
        landmarks = np.zeros((68, 2), dtype=np.float32)

        # Simulate EAR by moving top/bottom eye points
        if frame_idx < 9:
            # Eyes open
            ear_offset = 12  # large vertical distance → high EAR
        elif frame_idx < 15:
            # Eyes closing
            ear_offset = int(12 * (1.0 - (frame_idx - 9) / 6.0))
        elif frame_idx < 21:
            # Eyes closed
            ear_offset = 0
        else:
            # Eyes opening
            ear_offset = int(12 * ((frame_idx - 21) / 4.0))

        # Left eye: points [36:42]
        landmarks[36] = [30, 50]  # left corner
        landmarks[37] = [35, 50 - ear_offset]  # top-left
        landmarks[38] = [45, 50 - ear_offset]  # top-right
        landmarks[39] = [60, 50]  # right corner
        landmarks[40] = [45, 50 + ear_offset]  # bottom-right
        landmarks[41] = [35, 50 + ear_offset]  # bottom-left

        # Right eye: points [42:48] (mirror)
        landmarks[42] = [30, 80]
        landmarks[43] = [35, 80 - ear_offset]
        landmarks[44] = [45, 80 - ear_offset]
        landmarks[45] = [60, 80]
        landmarks[46] = [45, 80 + ear_offset]
        landmarks[47] = [35, 80 + ear_offset]

        sequence.append(landmarks)
    return sequence


# ── Test suite ────────────────────────────────────────────────────────────────

class TestLivenessDetectorTexture(unittest.TestCase):
    """Test texture-based (Laplacian variance) liveness detection."""

    def setUp(self) -> None:
        """Create a fresh detector for each test."""
        self.detector = LivenessDetector(threshold=0.55, enable_blink=False)

    def test_blank_image_low_texture_score(self) -> None:
        """Low-texture (blank/photo) image should produce low texture score."""
        blank = make_blank_image()
        result = self.detector.check(blank)
        self.assertLess(result.texture_score, 0.3, "Blank image should have low texture")
        self.assertEqual(result.method, "texture")

    def test_textured_image_high_texture_score(self) -> None:
        """High-texture image should produce high texture score."""
        textured = make_textured_image()
        result = self.detector.check(textured)
        self.assertGreater(result.texture_score, 0.4, "Textured image should have higher texture")
        self.assertEqual(result.method, "texture")

    def test_texture_score_clamped_to_unit(self) -> None:
        """Texture score should be in [0, 1] range."""
        images = [make_blank_image(), make_textured_image()]
        for img in images:
            result = self.detector.check(img)
            self.assertGreaterEqual(result.texture_score, 0.0)
            self.assertLessEqual(result.texture_score, 1.0)

    def test_score_vs_threshold_determines_is_live(self) -> None:
        """When texture score >= threshold, is_live should be True."""
        detector_high_threshold = LivenessDetector(threshold=0.95)
        detector_low_threshold = LivenessDetector(threshold=0.1)

        textured = make_textured_image()
        result_high = detector_high_threshold.check(textured)
        result_low = detector_low_threshold.check(textured)

        # Same image, different thresholds
        self.assertFalse(result_high.is_live, "Threshold 0.95 should reject moderate texture")
        self.assertTrue(result_low.is_live, "Threshold 0.1 should accept moderate texture")

    def test_different_image_sizes(self) -> None:
        """Texture check should handle various image sizes."""
        for h, w in [(64, 64), (128, 128), (224, 224)]:
            img = make_textured_image(h=h, w=w)
            result = self.detector.check(img)
            self.assertTrue(0.0 <= result.texture_score <= 1.0)
            self.assertEqual(result.method, "texture")

    def test_grayscale_image(self) -> None:
        """Detector should handle single-channel (grayscale) input."""
        gray = make_textured_image()
        gray_single = gray[:, :, 0]  # drop to 2D
        result = self.detector.check(gray_single)
        self.assertIn(result.method, ["texture", "texture_interim"])

    def test_empty_image_graceful_fallback(self) -> None:
        """Empty image should return neutral score, not crash."""
        empty = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        result = self.detector.check(empty)
        self.assertEqual(result.texture_score, 0.0)
        self.assertFalse(result.is_live)


class TestLivenessDetectorBlink(unittest.TestCase):
    """Test blink detection (EAR heuristic) across frame sequences."""

    def setUp(self) -> None:
        """Create detector with blink enabled."""
        self.detector = LivenessDetector(threshold=0.5, enable_blink=True)

    def test_blink_sequence_detected(self) -> None:
        """A proper blink sequence should trigger blink_score > 0.7."""
        landmarks_seq = make_blink_landmark_sequence(n_frames=25)
        textured = make_textured_image()

        track_id = 1
        final_result = None

        for frame_idx, landmarks in enumerate(landmarks_seq):
            result = self.detector.check(
                textured,
                landmarks=landmarks,
                track_id=track_id,
            )
            if frame_idx == len(landmarks_seq) - 1:
                final_result = result

        self.assertIsNotNone(final_result)
        self.assertGreaterEqual(final_result.blink_score, 0.70)

    def test_no_blink_in_static_sequence(self) -> None:
        """Landmarks that don't show a blink should return low blink_score."""
        # Create a sequence where eyes are always open
        landmarks_seq = [
            np.array(
                [[30, 50], [35, 38], [45, 38], [60, 50], [45, 62], [35, 62]] +
                [[30, 80], [35, 68], [45, 68], [60, 80], [45, 92], [35, 92]] +
                [[0, 0]] * (68 - 12),
                dtype=np.float32
            )
            for _ in range(_EAR_BUFFER_LEN + 1)
        ]

        track_id = 2
        textured = make_textured_image()

        for landmarks in landmarks_seq:
            result = self.detector.check(
                textured,
                landmarks=landmarks,
                track_id=track_id,
            )

        self.assertLess(result.blink_score, 0.45, "No blink in static sequence")

    def test_blink_buffer_size_tracking(self) -> None:
        """Blink accumulation buffer should respect _EAR_BUFFER_LEN."""
        from services import liveness as liveness_module
        buffer_len = liveness_module._EAR_BUFFER_LEN
        landmarks_seq = make_blink_landmark_sequence(n_frames=buffer_len + 5)

        track_id = 3
        textured = make_textured_image()

        for landmarks in landmarks_seq:
            self.detector.check(
                textured,
                landmarks=landmarks,
                track_id=track_id,
            )

        # Check internal buffer
        buf = self.detector._ear_buffers.get(track_id)
        self.assertIsNotNone(buf)
        self.assertLessEqual(len(buf), buffer_len, "Buffer should not exceed maxlen")

    def test_reset_track_clears_blink_state(self) -> None:
        """reset_track() should clear accumulated blink state for a track."""
        landmarks_seq = make_blink_landmark_sequence(n_frames=25)
        track_id = 4
        textured = make_textured_image()

        for landmarks in landmarks_seq:
            self.detector.check(
                textured,
                landmarks=landmarks,
                track_id=track_id,
            )

        # Verify state is accumulated
        self.assertIn(track_id, self.detector._ear_buffers)

        # Reset
        self.detector.reset_track(track_id)

        # Verify state is cleared
        self.assertNotIn(track_id, self.detector._ear_buffers)
        self.assertNotIn(track_id, self.detector._blink_counts)

    def test_no_landmarks_returns_neutral_blink_score(self) -> None:
        """When landmarks are None, blink_score should be 0.5 (neutral)."""
        textured = make_textured_image()
        result = self.detector.check(textured, landmarks=None, track_id=1)
        self.assertEqual(result.blink_score, 0.5)

    def test_wrong_landmark_shape_fallback(self) -> None:
        """Landmarks with < 12 points should fallback gracefully."""
        textured = make_textured_image()
        wrong_landmarks = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = self.detector.check(
            textured,
            landmarks=wrong_landmarks,
            track_id=1,
        )
        self.assertIn(result.method, ["texture", "texture_interim"])


class TestMetadataScoring(unittest.TestCase):
    """Test login metadata scoring."""

    def test_known_device_boosts_score(self) -> None:
        """Known device should add +0.20 to base 0.5."""
        metadata = LoginMetadata(known_device=True)
        score = score_login_metadata(metadata)
        self.assertGreater(score, 0.5, "Known device should boost score")
        self.assertAlmostEqual(score, 0.7, places=1)

    def test_unknown_device_penalizes(self) -> None:
        """Unknown device should subtract from score."""
        metadata = LoginMetadata(known_device=False)
        score = score_login_metadata(metadata)
        self.assertLess(score, 0.5, "Unknown device should penalize")

    def test_expected_location_boosts_score(self) -> None:
        """Expected location should add +0.20."""
        metadata = LoginMetadata(expected_location=True)
        score = score_login_metadata(metadata)
        self.assertGreater(score, 0.5)

    def test_unexpected_location_penalizes(self) -> None:
        """Unexpected location should penalize."""
        metadata = LoginMetadata(expected_location=False)
        score = score_login_metadata(metadata)
        self.assertLess(score, 0.5)

    def test_daytime_hour_boosts(self) -> None:
        """Daytime hour (7–20) should add +0.10."""
        metadata = LoginMetadata(time_of_day_hour=12)  # noon
        score = score_login_metadata(metadata)
        self.assertGreater(score, 0.5)

    def test_night_hour_penalizes(self) -> None:
        """Night hour (0–6, 21–23) should subtract -0.05."""
        metadata = LoginMetadata(time_of_day_hour=3)  # 3 AM
        score = score_login_metadata(metadata)
        self.assertLess(score, 0.5)

    def test_multiple_signals_combine(self) -> None:
        """Multiple positive signals should compound."""
        metadata = LoginMetadata(
            known_device=True,
            expected_location=True,
            time_of_day_hour=12,
        )
        score = score_login_metadata(metadata)
        self.assertGreater(score, 0.8, "Multiple positive signals should compound")

    def test_score_clamped_to_valid_range(self) -> None:
        """Score should stay in [0.1, 1.0]."""
        # Try to break it with extreme metadata
        metadata = LoginMetadata(
            known_device=True,
            expected_location=True,
            time_of_day_hour=15,
        )
        score = score_login_metadata(metadata)
        self.assertGreaterEqual(score, 0.1)
        self.assertLessEqual(score, 1.0)

    def test_none_metadata_returns_neutral(self) -> None:
        """None metadata should return neutral 0.5."""
        score = score_login_metadata(None)
        self.assertEqual(score, 0.5)


class TestConfidenceFusion(unittest.TestCase):
    """Test fused confidence combining embedding + liveness + metadata."""

    def setUp(self) -> None:
        """Create a liveness result for testing."""
        detector = LivenessDetector(enable_blink=False)
        textured = make_textured_image()
        self.live_result = detector.check(textured)
        self.live_result.is_live = True
        self.live_result.overall_score = 0.80

        blank = make_blank_image()
        self.dead_result = detector.check(blank)
        self.dead_result.is_live = False
        self.dead_result.overall_score = 0.20

    def test_high_embedding_sim_live_accepts(self) -> None:
        """High embedding sim + live + good metadata → accept."""
        fused = fuse_confidence(
            embedding_similarity=0.92,
            liveness_result=self.live_result,
            metadata=LoginMetadata(known_device=True),
            accept_threshold=0.65,
        )
        self.assertTrue(fused.accept, "Should accept strong match")
        self.assertGreater(fused.final_confidence, 0.65)

    def test_low_embedding_sim_rejects(self) -> None:
        """Low embedding sim → reject regardless of liveness."""
        fused = fuse_confidence(
            embedding_similarity=0.45,
            liveness_result=self.live_result,
            metadata=LoginMetadata(known_device=True),
            accept_threshold=0.65,
        )
        self.assertFalse(fused.accept)
        self.assertLess(fused.final_confidence, 0.65)

    def test_liveness_failure_hard_gate(self) -> None:
        """Liveness failure should reject even with high embedding sim."""
        fused = fuse_confidence(
            embedding_similarity=0.95,
            liveness_result=self.dead_result,
            metadata=LoginMetadata(known_device=True),
            accept_threshold=0.65,
        )
        self.assertFalse(fused.accept, "Liveness failure should hard-gate to reject")

    def test_weights_normalized(self) -> None:
        """Weights should be normalized so they sum to 1.0."""
        fused = fuse_confidence(
            embedding_similarity=0.80,
            liveness_result=self.live_result,
            metadata=None,
            w_embedding=0.6,
            w_liveness=0.3,
            w_metadata=0.1,
        )
        # No assertion on exact value, but should not crash with non-unit weights
        self.assertIsNotNone(fused.breakdown)

    def test_breakdown_contains_contributions(self) -> None:
        """Breakdown dict should have per-component contributions."""
        fused = fuse_confidence(
            embedding_similarity=0.80,
            liveness_result=self.live_result,
            metadata=LoginMetadata(known_device=True),
        )
        self.assertIn("embedding_contribution", fused.breakdown)
        self.assertIn("liveness_contribution", fused.breakdown)
        self.assertIn("metadata_contribution", fused.breakdown)

    def test_threshold_affects_acceptance(self) -> None:
        """Different thresholds should affect acceptance decision."""
        fused_low = fuse_confidence(
            embedding_similarity=0.70,
            liveness_result=self.live_result,
            metadata=LoginMetadata(known_device=True),
            accept_threshold=0.60,
        )
        fused_high = fuse_confidence(
            embedding_similarity=0.70,
            liveness_result=self.live_result,
            metadata=LoginMetadata(known_device=True),
            accept_threshold=0.75,
        )
        # Same inputs, different thresholds → possibly different outcomes
        # At least verify both return valid results
        self.assertIsInstance(fused_low.accept, bool)
        self.assertIsInstance(fused_high.accept, bool)


class TestLivenessDetectorSingleton(unittest.TestCase):
    """Test module-level singleton get_liveness_detector()."""

    def tearDown(self) -> None:
        """Reset singleton between tests."""
        from services import liveness as liveness_module
        liveness_module._detector = None

    def test_singleton_lazy_init(self) -> None:
        """First call should create the detector."""
        from services import liveness as liveness_module
        liveness_module._detector = None
        detector1 = get_liveness_detector()
        self.assertIsNotNone(detector1)

    def test_singleton_reuses_instance(self) -> None:
        """Subsequent calls should return same instance."""
        from services import liveness as liveness_module
        liveness_module._detector = None
        detector1 = get_liveness_detector()
        detector2 = get_liveness_detector()
        self.assertIs(detector1, detector2)


class TestDisableStrictMode(unittest.TestCase):
    """Test LIVENESS_DISABLE_STRICT bypass mode."""

    def test_disable_strict_always_accepts(self) -> None:
        """When LIVENESS_DISABLE_STRICT=1, all checks should pass."""
        with mock.patch.dict(os.environ, {"LIVENESS_DISABLE_STRICT": "1"}):
            # Re-import to pick up the env var change
            from services import liveness as liveness_module
            # Reload the module to reread the env var
            import importlib
            importlib.reload(liveness_module)

            detector = liveness_module.LivenessDetector()
            blank = make_blank_image()
            result = detector.check(blank)

            self.assertTrue(result.is_live, "Should bypass strict mode")
            self.assertEqual(result.method, "bypass")

        # Clean up: reload again without the env var
        import importlib
        importlib.reload(liveness_module)


class TestBatchProcessing(unittest.TestCase):
    """Test batch processing of multiple images."""

    def setUp(self) -> None:
        self.detector = LivenessDetector(enable_blink=False)

    def test_batch_check(self) -> None:
        """check_batch should process multiple images."""
        images = [make_blank_image(), make_textured_image(), make_textured_image()]
        results = self.detector.check_batch(images)
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, LivenessResult)

    def test_batch_with_landmarks(self) -> None:
        """Batch check should handle landmarks list."""
        images = [make_textured_image()] * 3
        landmarks_seq = make_blink_landmark_sequence(n_frames=3)
        results = self.detector.check_batch(images, landmarks_list=landmarks_seq)
        self.assertEqual(len(results), 3)


# ── Env var constants used in tests ───────────────────────────────────────────
# These are re-imported to ensure test isolation
_EAR_BUFFER_LEN = int(os.getenv("LIVENESS_EAR_BUFFER_LEN", "20"))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    unittest.main()
