"""
attendance_backend/services/liveness.py
════════════════════════════════════════════════════════════════════════════════
Liveness detection and metadata-weighted confidence fusion.

Detection strategy (in priority order)
───────────────────────────────────────
1. Hardware / deep-learning model  — loaded from LIVENESS_MODEL_PATH (ONNX).
2. Blink detection (EAR across a short ring buffer) — requires facial landmarks.
3. Texture analysis (Laplacian variance) — always available, cheapest fallback.

When no hardware model is present and no landmark stream is available, the
texture heuristic is used.  It is deliberately conservative (biased toward
accepting real faces) — a production deployment MUST supply a proper model.

LivenessResult
──────────────
Carries both the cascade-winner fields (score, method, is_live) **and** the
per-sub-score breakdown (texture_score, blink_score, depth_score, overall_score)
so downstream callers (fuse_confidence, diagnostic API) can inspect each signal.

Metadata fusion
───────────────
``fuse_confidence()`` combines:
  - embedding cosine similarity  (primary signal)
  - liveness overall_score       (anti-spoofing gate)
  - login-origin metadata        (device continuity, IP/geo, time-of-day)

The fused score is consumed by ``ScopedEmbeddingSearch`` and the quick-accept
path in ``OptimizedAttendancePipeline``.

Env flags
─────────
  LIVENESS_MODEL_PATH        — path to ONNX liveness model; omit → heuristics
  LIVENESS_LAP_VAR_CAP       — Laplacian-variance normalisation cap (default 300)
  LIVENESS_EAR_BLINK_THRESH  — EAR blink threshold (default 0.21)
  LIVENESS_EAR_CONSEC_FRAMES — frames EAR must stay low to register blink (default 2)
  LIVENESS_EAR_BUFFER_LEN    — rolling EAR window length in frames (default 20)
  LIVENESS_DISABLE_STRICT    — set "1" to skip liveness gate (constrained devices)

Usage examples
──────────────
# Stateless single-frame texture:
    detector = get_liveness_detector()
    result = detector.check(face_crop_bgr)

# Stateful blink-aware (feed frames in temporal order):
    for frame, landmarks in video_stream:
        result = detector.check(frame, landmarks=landmarks, track_id=track_id)

# Fused confidence:
    meta = LoginMetadata(device_id="dev-abc", known_device=True)
    fused = fuse_confidence(
        embedding_similarity=0.82,
        liveness_result=result,
        metadata=meta,
    )
    if fused.accept:
        mark_attendance()
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ── Env-tunable constants ─────────────────────────────────────────────────────

# Texture: Laplacian-variance normalisation cap.
# Frames above this are treated as full-score (enough texture detail).
_LAP_VAR_CAP: float = float(os.getenv("LIVENESS_LAP_VAR_CAP", "300.0"))

# Blink EAR thresholds (Soukupová & Čech, 2016).
_EAR_BLINK_THRESH: float = float(os.getenv("LIVENESS_EAR_BLINK_THRESH", "0.21"))
_EAR_CONSEC_FRAMES: int = int(os.getenv("LIVENESS_EAR_CONSEC_FRAMES", "2"))
_EAR_BUFFER_LEN: int = int(os.getenv("LIVENESS_EAR_BUFFER_LEN", "20"))

# Score returned when a confirmed blink is detected.
_BLINK_DETECTED_SCORE: float = 0.85

# Texture score that is good enough to skip the blink requirement.
_TEXTURE_PASS_THRESHOLD: float = 0.70

# Path to an optional ONNX deep-learning liveness model.
_MODEL_PATH: Optional[str] = os.getenv("LIVENESS_MODEL_PATH")

# Set LIVENESS_DISABLE_STRICT=1 to skip liveness gate on constrained devices.
_DISABLE_STRICT: bool = os.getenv("LIVENESS_DISABLE_STRICT", "0") == "1"

# Weights for the per-sub-score overall_score rollup inside LivenessResult.
_W_TEXTURE: float = 0.50
_W_BLINK: float = 0.30
_W_DEPTH: float = 0.20

# Weights used by fuse_confidence().
_W_EMBEDDING: float = 0.60
_W_LIVENESS: float = 0.25
_W_METADATA: float = 0.15

# Default accept threshold for fuse_confidence().
_DEFAULT_ACCEPT_THRESHOLD: float = 0.65

# Laplacian variance below this (on a 0–1 scale) → likely a flat photo/screen.
_TEXTURE_LIVENESS_THRESHOLD: float = float(
    os.getenv("LIVENESS_TEXTURE_THRESHOLD", "80.0")
)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class LivenessResult:
    """
    Result of a liveness check on a single face crop.

    Cascade fields (always populated)
    ───────────────────────────────────
    score:   Winner score from the cascade in [0, 1]  (1.0 = certainly live).
    method:  Which strategy produced the score:
             "model" | "blink" | "texture" | "texture_interim" | "bypass"
    is_live: score >= detector.threshold  (or True when strict mode disabled).

    Sub-score breakdown (for diagnostics and fuse_confidence)
    ──────────────────────────────────────────────────────────
    texture_score:  Normalised Laplacian-variance score in [0, 1].
    blink_score:    EAR-based blink score in [0, 1]; 0.5 when no landmarks.
    depth_score:    IR/depth-based score in [0, 1]; 0.5 when no depth map.
    overall_score:  Weighted average of the three sub-scores, used by
                    fuse_confidence() as the liveness signal.
    check_ms:       Wall-clock time for the full check (milliseconds).
    details:        Method-specific diagnostic dict.
    reason:         Human-readable rejection reason when is_live is False.
    """

    # Cascade winner
    score: float
    method: str
    is_live: bool

    # Sub-score breakdown
    texture_score: float = 0.5
    blink_score: float = 0.5
    depth_score: float = 0.5
    overall_score: float = 0.0
    check_ms: float = 0.0
    details: dict = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        # Compute overall_score from sub-scores when not explicitly set.
        if self.overall_score == 0.0:
            self.overall_score = (
                _W_TEXTURE * self.texture_score
                + _W_BLINK * self.blink_score
                + _W_DEPTH * self.depth_score
            )


@dataclass
class LoginMetadata:
    """
    Contextual metadata captured at the moment of a recognition attempt.

    All fields are optional; missing values contribute a neutral 0.5 weight
    to the metadata score rather than penalising the attempt.

    Attributes
    ──────────
    device_id:          Persistent device identifier (Android ID, iOS IFV).
    ip_address:         Originating IP address.
    geolocation:        {"lat": float, "lon": float} or None.
    time_of_day_hour:   UTC hour (0–23) at submission time.
    known_device:       True if device_id seen in last 30 days for this user.
    expected_location:  True if geolocation is within the classroom boundary.
    """

    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    geolocation: Optional[Dict[str, float]] = None
    time_of_day_hour: Optional[int] = None
    known_device: Optional[bool] = None
    expected_location: Optional[bool] = None


@dataclass
class FusedConfidenceResult:
    """
    Output of ``fuse_confidence()``.

    Attributes
    ──────────
    final_confidence:    Weighted combination of embedding + liveness + metadata
                         scores in [0, 1].
    accept:              True when final_confidence ≥ accept_threshold AND
                         liveness passes (or strict mode is disabled).
    embedding_similarity: Raw cosine similarity passed in.
    liveness_result:     The LivenessResult used during fusion.
    metadata_score:      [0, 1] score derived from LoginMetadata.
    accept_threshold:    Threshold that was applied.
    breakdown:           Per-component weighted contributions for debugging.
    """

    final_confidence: float
    accept: bool
    embedding_similarity: float
    liveness_result: LivenessResult
    metadata_score: float
    accept_threshold: float
    breakdown: Dict[str, float] = field(default_factory=dict)


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _eye_aspect_ratio(eye_landmarks: np.ndarray) -> float:
    """
    Compute EAR for one eye.

    eye_landmarks: (6, 2) array — the 6 eye keypoints in dlib 68-point order:
        [0] left-corner, [1] top-left, [2] top-right,
        [3] right-corner, [4] bot-right, [5] bot-left
    """
    v1 = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
    v2 = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
    h = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
    return (v1 + v2) / (2.0 * h + 1e-6)


def _laplacian_variance(gray: np.ndarray) -> float:
    """
    Measure image sharpness via the variance of the Laplacian.

    Accepts a single-channel uint8 image.  Falls back to a pure-numpy
    implementation when OpenCV is unavailable.
    """
    try:
        import cv2  # type: ignore
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except ImportError:
        kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
        from numpy.lib.stride_tricks import sliding_window_view  # numpy ≥ 1.20
        windows = sliding_window_view(gray.astype(np.float64), (3, 3))
        return float((windows * kernel).sum(axis=(-2, -1)).var())


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Convert BGR / RGB / RGBA / grayscale image to single-channel uint8."""
    if image.ndim == 2:
        return image.astype(np.uint8)
    c = image.shape[2]
    if c == 1:
        return image[:, :, 0].astype(np.uint8)
    if c == 4:
        image = image[:, :, :3]
    try:
        import cv2  # type: ignore
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except ImportError:
        return (
            0.2126 * image[:, :, 0]
            + 0.7152 * image[:, :, 1]
            + 0.0722 * image[:, :, 2]
        ).astype(np.uint8)


def _resize(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resize image using cv2 when available, else nearest-neighbour via numpy."""
    try:
        import cv2  # type: ignore
        return cv2.resize(image, size)
    except ImportError:
        # Very basic numpy resize (good enough for scoring purposes)
        h, w = size[1], size[0]
        return image[
            np.linspace(0, image.shape[0] - 1, h, dtype=int), :
        ][:, np.linspace(0, image.shape[1] - 1, w, dtype=int)]


# ── Core detector ─────────────────────────────────────────────────────────────

class LivenessDetector:
    """
    Multi-strategy liveness detector.

    Cascade order:  hardware model  →  blink (EAR)  →  texture (Laplacian).

    The detector is stateful only for blink accumulation (per track_id ring
    buffers).  All other operations are stateless and thread-safe per instance.

    Parameters
    ──────────
    threshold:           Score at or above which is_live is True (default 0.55).
    texture_threshold:   Laplacian-variance cutoff used for the legacy
                         is_live decision in _texture_check (default 80.0).
                         Lower for low-resolution cameras, higher in bright
                         studio environments.
    enable_blink:        If False, blink strategy is skipped entirely.
    enable_depth:        If True, _depth_check stub is called (requires depth map).
    """

    def __init__(
        self,
        threshold: float = 0.55,
        texture_threshold: float = _TEXTURE_LIVENESS_THRESHOLD,
        enable_blink: bool = True,
        enable_depth: bool = False,
    ) -> None:
        self.threshold = threshold
        self.texture_threshold = texture_threshold
        self.enable_blink = enable_blink
        self.enable_depth = enable_depth

        # ONNX model state
        self._model: Optional[Any] = None
        self._model_loaded: bool = False

        # Per-track blink state  {track_id → deque[ear]}
        self._ear_buffers: dict[int, Deque[float]] = {}
        self._blink_counts: dict[int, int] = {}
        self._consec_below: dict[int, int] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        face_image: np.ndarray,
        *,
        landmarks: Optional[np.ndarray] = None,
        track_id: Optional[int] = None,
        depth_map: Optional[np.ndarray] = None,
    ) -> LivenessResult:
        """
        Score liveness for a single face crop.

        Always populates the full sub-score breakdown so callers and the
        diagnostic endpoint can inspect each signal independently.

        Args:
            face_image:  Cropped face image (H×W×C BGR, or H×W grayscale).
            landmarks:   Optional (N, 2) facial keypoints for blink detection.
                         If N ≥ 12, blink strategy is attempted.
            track_id:    Stable ID for the tracked face; required for blink
                         accumulation across frames.  Each call is independent
                         when None.
            depth_map:   Optional depth / IR image aligned to face_image (stub).

        Returns:
            LivenessResult with cascade winner fields + full sub-score breakdown.
        """
        t0 = time.perf_counter()

        if _DISABLE_STRICT:
            return self._bypass_result(face_image, t0)

        # Always compute all sub-scores for the breakdown.
        texture_score = self._texture_check(face_image)
        blink_score = (
            self._blink_score_only(face_image, landmarks, track_id)
            if self.enable_blink
            else 0.5
        )
        depth_score = (
            self._depth_check_score(face_image, depth_map)
            if self.enable_depth
            else 0.5
        )

        # ── Cascade: pick winner score + method ───────────────────────────────
        winner_score: float
        winner_method: str
        winner_details: dict

        if self._try_load_model():
            # Strategy 1: hardware model
            model_result = self._run_model(face_image)
            winner_score = model_result["score"]
            winner_method = "model"
            winner_details = model_result

        elif landmarks is not None and track_id is not None and self.enable_blink:
            # Strategy 2: blink (full stateful result)
            blink_res = self._check_blink_full(face_image, landmarks, track_id, texture_score)
            if blink_res is not None:
                winner_score = blink_res["score"]
                winner_method = blink_res["method"]
                winner_details = blink_res["details"]
            else:
                # landmarks wrong shape → fall through
                winner_score = texture_score
                winner_method = "texture"
                winner_details = {"laplacian_variance": _laplacian_variance(_to_gray(face_image))}

        else:
            # Strategy 3: texture
            winner_score = texture_score
            winner_method = "texture"
            winner_details = {"laplacian_variance": _laplacian_variance(_to_gray(face_image))}

        is_live = winner_score >= self.threshold
        reason = "" if is_live else (
            f"{winner_method} score {winner_score:.3f} below threshold {self.threshold:.3f}"
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = LivenessResult(
            score=winner_score,
            method=winner_method,
            is_live=is_live,
            texture_score=texture_score,
            blink_score=blink_score,
            depth_score=depth_score,
            check_ms=elapsed_ms,
            details=winner_details,
            reason=reason,
        )

        logger.debug(
            "Liveness: live=%s method=%s score=%.3f "
            "(tex=%.3f blink=%.3f depth=%.3f overall=%.3f) %.1f ms",
            result.is_live, result.method, result.score,
            result.texture_score, result.blink_score,
            result.depth_score, result.overall_score, result.check_ms,
        )
        return result

    def check_batch(
        self,
        face_images: List[np.ndarray],
        landmarks_list: Optional[List[Optional[np.ndarray]]] = None,
        track_ids: Optional[List[Optional[int]]] = None,
        depth_maps: Optional[List[Optional[np.ndarray]]] = None,
    ) -> List[LivenessResult]:
        """Score liveness for a batch of face crops."""
        n = len(face_images)
        lms = landmarks_list or [None] * n
        tids = track_ids or [None] * n
        dms = depth_maps or [None] * n
        return [
            self.check(img, landmarks=lm, track_id=tid, depth_map=dm)
            for img, lm, tid, dm in zip(face_images, lms, tids, dms)
        ]

    def reset_track(self, track_id: int) -> None:
        """Discard accumulated blink state for a track after identity is confirmed."""
        self._ear_buffers.pop(track_id, None)
        self._blink_counts.pop(track_id, None)
        self._consec_below.pop(track_id, None)

    # ── Strategy 1: hardware ONNX model ──────────────────────────────────────

    def _try_load_model(self) -> bool:
        """Attempt lazy load of ONNX model. Returns True if loaded successfully."""
        if self._model_loaded:
            return self._model is not None
        self._model_loaded = True
        if not _MODEL_PATH or not os.path.isfile(_MODEL_PATH):
            logger.debug("No liveness model at LIVENESS_MODEL_PATH — using heuristics.")
            return False
        try:
            import onnxruntime as ort  # type: ignore
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            self._model = ort.InferenceSession(_MODEL_PATH, opts)
            logger.info("Loaded liveness model from %s", _MODEL_PATH)
            return True
        except Exception as exc:
            logger.warning("Could not load liveness model: %s", exc)
            return False

    def _run_model(self, face_image: np.ndarray) -> dict:
        """Run ONNX inference; return {'score': float, ...}. Falls back to texture on error."""
        try:
            resized = _resize(face_image, (224, 224))
            blob = resized.astype(np.float32) / 255.0
            if blob.ndim == 2:
                blob = np.stack([blob] * 3, axis=0)
            else:
                blob = blob.transpose(2, 0, 1)
            blob = blob[np.newaxis]
            input_name = self._model.get_inputs()[0].name
            outputs = self._model.run(None, {input_name: blob})
            score = float(np.clip(np.squeeze(outputs[0]), 0.0, 1.0))
            return {"score": score, "raw_output": score}
        except Exception as exc:
            logger.error("Liveness model inference failed: %s; falling back to texture.", exc)
            tex = self._texture_check(face_image)
            return {"score": tex, "fallback": "texture"}

    # ── Strategy 2: blink detection (EAR) ────────────────────────────────────

    def _blink_score_only(
        self,
        face_image: np.ndarray,
        landmarks: Optional[np.ndarray],
        track_id: Optional[int],
    ) -> float:
        """
        Return a blink sub-score in [0, 1] without the full cascade side-effects.
        Used to populate blink_score in the breakdown regardless of which
        cascade strategy wins.
        """
        if landmarks is None or track_id is None or landmarks.shape[0] < 12:
            return 0.5
        blinks = self._blink_counts.get(track_id, 0)
        if blinks >= 1:
            return _BLINK_DETECTED_SCORE
        buf = self._ear_buffers.get(track_id)
        if buf and len(buf) >= _EAR_BUFFER_LEN:
            return 0.35  # buffer full, no blink → suspicious
        return 0.5       # still accumulating

    def _check_blink_full(
        self,
        face_image: np.ndarray,
        landmarks: np.ndarray,
        track_id: int,
        texture_score: float,
    ) -> Optional[dict]:
        """
        Full stateful blink check.  Returns a dict with score/method/details,
        or None if landmarks are in an unsupported shape.
        """
        if landmarks.shape[0] < 12:
            return None
        try:
            # Support both dlib 68-pt and a compact 12-pt eye-only array.
            if landmarks.shape[0] >= 48:
                left_eye = landmarks[36:42]
                right_eye = landmarks[42:48]
            else:
                left_eye = landmarks[:6]
                right_eye = landmarks[6:12]

            ear = (_eye_aspect_ratio(left_eye) + _eye_aspect_ratio(right_eye)) / 2.0

            buf = self._ear_buffers.setdefault(
                track_id, deque(maxlen=_EAR_BUFFER_LEN)
            )
            buf.append(ear)

            below = self._consec_below.get(track_id, 0)
            if ear < _EAR_BLINK_THRESH:
                below += 1
            else:
                if below >= _EAR_CONSEC_FRAMES:
                    self._blink_counts[track_id] = (
                        self._blink_counts.get(track_id, 0) + 1
                    )
                below = 0
            self._consec_below[track_id] = below
            blinks = self._blink_counts.get(track_id, 0)

            if blinks >= 1:
                return {
                    "score": _BLINK_DETECTED_SCORE,
                    "method": "blink",
                    "details": {"ear": ear, "blinks": blinks},
                }
            if len(buf) < _EAR_BUFFER_LEN:
                # Buffer still filling — use texture as interim score.
                return {
                    "score": texture_score,
                    "method": "texture_interim",
                    "details": {
                        "ear": ear, "blinks": blinks,
                        "buffer_fill": len(buf),
                    },
                }
            # Buffer full, no blink — suspicious (photo / video replay).
            return {
                "score": 0.35,
                "method": "blink",
                "details": {"ear": ear, "blinks": blinks, "note": "no_blink_detected"},
            }
        except Exception as exc:
            logger.warning("Blink detection failed for track %s: %s", track_id, exc)
            return None

    # ── Strategy 3: texture (Laplacian variance) ──────────────────────────────

    def _texture_check(self, face_image: np.ndarray) -> float:
        """
        Passive texture liveness via Laplacian variance.

        Steps:
          1. Resize to 96×96 (removes resolution dependency).
          2. Convert to greyscale.
          3. Compute Laplacian variance.
          4. Normalise to [0, 1] against _LAP_VAR_CAP.

        Returns:
            Score in [0, 1]; higher → more textured → more likely live.
        """
        if face_image is None or face_image.size == 0:
            return 0.0
        try:
            resized = _resize(face_image, (96, 96))
            gray = _to_gray(resized)
            lap_var = _laplacian_variance(gray)
            return float(np.clip(lap_var / _LAP_VAR_CAP, 0.0, 1.0))
        except Exception as exc:
            logger.warning("Texture check failed: %s", exc)
            return 0.5  # neutral on error

    # ── Strategy 4: depth / IR (stub) ────────────────────────────────────────

    def _depth_check_score(
        self,
        face_image: np.ndarray,
        depth_map: Optional[np.ndarray],
    ) -> float:
        """
        Depth/IR liveness stub for RealSense / TrueDepth cameras.

        Full implementation:
            1. Align depth_map to the face bounding box.
            2. Compute depth variance across the face region.
            3. A flat surface (photo/screen) has very low depth variance;
               a real face has ~15–40 mm variance.

        Returns:
            0.5 (neutral) until a real depth map is supplied.

        TODO: implement RealSense / ARKit depth variance check:
            aligned = align_depth_to_face(depth_map, face_image)
            variance = float(np.var(aligned))
            return min(variance / 400.0, 1.0)
        """
        if depth_map is None:
            return 0.5
        return 0.5

    # ── Bypass (LIVENESS_DISABLE_STRICT=1) ───────────────────────────────────

    def _bypass_result(self, face_image: np.ndarray, t0: float) -> LivenessResult:
        """Return a permissive pass-through result when strict liveness is disabled."""
        tex = self._texture_check(face_image)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.debug("Liveness bypassed (LIVENESS_DISABLE_STRICT=1)")
        result = LivenessResult(
            score=1.0,
            method="bypass",
            is_live=True,
            texture_score=tex,
            blink_score=0.5,
            depth_score=0.5,
            check_ms=elapsed_ms,
            details={"bypass": True},
            reason="",
        )
        return result


# ── Module-level singleton ────────────────────────────────────────────────────

_detector: Optional[LivenessDetector] = None


def get_liveness_detector(
    threshold: float = 0.55,
    texture_threshold: float = _TEXTURE_LIVENESS_THRESHOLD,
    enable_blink: bool = True,
    enable_depth: bool = False,
) -> LivenessDetector:
    """Return a shared ``LivenessDetector`` instance (lazy init, singleton)."""
    global _detector
    if _detector is None:
        _detector = LivenessDetector(
            threshold=threshold,
            texture_threshold=texture_threshold,
            enable_blink=enable_blink,
            enable_depth=enable_depth,
        )
    return _detector


# ── Metadata scoring ──────────────────────────────────────────────────────────

def score_login_metadata(metadata: Optional[LoginMetadata]) -> float:
    """
    Convert ``LoginMetadata`` into a single score in [0, 1].

    Scoring rules (baseline 0.5; each signal shifts ±Δ):

    | Signal            | Condition       | Δ score |
    |-------------------|-----------------|---------|
    | known_device      | True            | +0.20   |
    | known_device      | False           | -0.10   |
    | expected_location | True            | +0.20   |
    | expected_location | False           | -0.15   |
    | time_of_day_hour  | 07–20 (daytime) | +0.10   |
    | time_of_day_hour  | outside range   | -0.05   |

    Missing signals are neutral (no contribution).

    Returns:
        Score clamped to [0.10, 1.0].
    """
    if metadata is None:
        return 0.5

    score = 0.5

    if metadata.known_device is True:
        score += 0.20
    elif metadata.known_device is False:
        score -= 0.10

    if metadata.expected_location is True:
        score += 0.20
    elif metadata.expected_location is False:
        score -= 0.15

    if metadata.time_of_day_hour is not None:
        if 7 <= metadata.time_of_day_hour <= 20:
            score += 0.10
        else:
            score -= 0.05

    return float(max(0.10, min(1.0, score)))


# ── Confidence fusion ─────────────────────────────────────────────────────────

def fuse_confidence(
    embedding_similarity: float,
    liveness_result: LivenessResult,
    metadata: Optional[LoginMetadata] = None,
    accept_threshold: float = _DEFAULT_ACCEPT_THRESHOLD,
    w_embedding: float = _W_EMBEDDING,
    w_liveness: float = _W_LIVENESS,
    w_metadata: float = _W_METADATA,
) -> FusedConfidenceResult:
    """
    Combine embedding similarity, liveness, and login metadata into a single
    fused acceptance decision.

    The liveness check acts as a hard gate: if ``liveness_result.is_live`` is
    False (and LIVENESS_DISABLE_STRICT is not set), the result is always
    rejected regardless of similarity.

    Formula (after weight normalisation):
        fused = w_e · similarity + w_l · overall_score + w_m · metadata_score

    Args:
        embedding_similarity: Cosine similarity from FAISS [0, 1].
        liveness_result:      Output of ``LivenessDetector.check()``.
        metadata:             Optional login-origin metadata.
        accept_threshold:     Minimum fused score required to accept.
        w_embedding:          Weight for embedding similarity.
        w_liveness:           Weight for liveness overall_score.
        w_metadata:           Weight for metadata score.

    Returns:
        FusedConfidenceResult with .accept and full breakdown.
    """
    # Normalise weights so they always sum to 1.0.
    total_w = w_embedding + w_liveness + w_metadata
    if total_w <= 0:
        total_w = 1.0
    w_e = w_embedding / total_w
    w_l = w_liveness / total_w
    w_m = w_metadata / total_w

    metadata_score = score_login_metadata(metadata)

    contrib_embedding = w_e * float(embedding_similarity)
    contrib_liveness = w_l * float(liveness_result.overall_score)
    contrib_metadata = w_m * float(metadata_score)
    final_confidence = contrib_embedding + contrib_liveness + contrib_metadata

    # Hard gate: liveness failure always rejects (unless bypass mode active).
    if not liveness_result.is_live:
        accept = False
    else:
        accept = final_confidence >= accept_threshold

    breakdown = {
        "embedding_contribution": round(contrib_embedding, 4),
        "liveness_contribution": round(contrib_liveness, 4),
        "metadata_contribution": round(contrib_metadata, 4),
    }

    logger.debug(
        "Fused confidence: %.4f (accept=%s) | emb=%.3f liv_overall=%.3f meta=%.3f",
        final_confidence, accept,
        embedding_similarity, liveness_result.overall_score, metadata_score,
    )

    return FusedConfidenceResult(
        final_confidence=float(final_confidence),
        accept=accept,
        embedding_similarity=float(embedding_similarity),
        liveness_result=liveness_result,
        metadata_score=float(metadata_score),
        accept_threshold=float(accept_threshold),
        breakdown=breakdown,
    )