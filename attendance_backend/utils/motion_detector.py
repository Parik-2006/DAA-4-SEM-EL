"""
Motion Detection Gatekeeper — OpenCV Frame Differencing.

Acts as a cheap pre-filter before expensive ML inference.
Only when motion is detected does the pipeline trigger YOLO + FaceNet.

Algorithm
---------
1. Convert frame to grayscale and apply Gaussian blur (reduces noise).
2. Compute absolute pixel-wise difference from the previous frame
   (frame differencing) – O(W×H), costs microseconds on CPU.
3. Threshold the diff image → binary mask of "changed" pixels.
4. Morphologically dilate the mask to fill gaps (MORPH_DILATE).
5. Count white pixels; if the ratio > ``motion_ratio_threshold`` declare motion.

Tuning guide
------------
``min_area_ratio``      – fraction of frame that must change (default 0.002 = 0.2 %).
                          Raise this if subtle background movement (fans, curtains)
                          triggers false positives.
``diff_threshold``      – per-pixel brightness change counted as "changed" (0–255).
                          Lower = more sensitive, higher = less sensitive.
``blur_ksize``          – Gaussian kernel size (must be odd). Larger = more noise immunity.
``cooldown_frames``     – after motion stops, keep pipeline active for N more frames
                          so the tracker can cleanly close tracks.
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class MotionConfig:
    """
    Tunable parameters for the motion detector.

    Attributes
    ----------
    diff_threshold:
        Per-pixel absolute brightness change (0-255) that counts as motion.
        Default 25 works well for indoor classroom cameras.
    min_area_ratio:
        Minimum fraction of frame pixels that must be "changed" to declare
        motion.  0.002 = 0.2 % of a 1280×720 frame ≈ 1 843 px.
    blur_ksize:
        Gaussian blur kernel size (odd integer). Removes camera sensor noise
        before differencing.  5 is a good starting point.
    dilate_iterations:
        Morphological dilation passes after thresholding.  Fills small gaps
        so a walking person registers as one connected region, not fragments.
    cooldown_frames:
        After motion drops below threshold, keep returning ``motion=True``
        for this many additional frames.  Prevents flickering during slow
        movement and gives the tracker time to confirm identity.
    history_len:
        Rolling window of per-frame motion scores used for smoothing.
    """
    diff_threshold: int = 25
    min_area_ratio: float = 0.002
    blur_ksize: int = 5
    dilate_iterations: int = 2
    cooldown_frames: int = 8
    history_len: int = 5


@dataclass
class MotionResult:
    """
    Result from a single frame analysis.

    Attributes
    ----------
    motion_detected:
        True if the frame should be passed to the AI pipeline.
    motion_score:
        Fraction of pixels that changed (0.0–1.0).  Useful for debugging
        and adaptive threshold tuning.
    contours:
        Bounding contours of moving regions (for optional visualisation).
    diff_frame:
        Thresholded binary difference image (H×W uint8).  None if the
        detector has not yet seen two frames.
    in_cooldown:
        True if motion_detected is True *only* because of the cooldown
        extension (real motion has already stopped).
    """
    motion_detected: bool
    motion_score: float
    contours: list = field(default_factory=list)
    diff_frame: Optional[np.ndarray] = None
    in_cooldown: bool = False


# ── Main class ─────────────────────────────────────────────────────────────────

class MotionDetector:
    """
    Lightweight frame-differencing motion detector.

    Designed to gate expensive ML inference: call ``detect(frame)`` before
    running YOLO/FaceNet.  If it returns ``motion_detected=False`` skip
    inference entirely.

    Thread safety
    -------------
    Each ``RTSPStreamHandler`` owns its own ``MotionDetector`` instance, so
    no locking is required.

    Example
    -------
    >>> detector = MotionDetector()
    >>> result = detector.detect(frame)
    >>> if result.motion_detected:
    ...     run_yolo_and_facenet(frame)
    """

    def __init__(self, config: Optional[MotionConfig] = None):
        self.config = config or MotionConfig()
        self._prev_gray: Optional[np.ndarray] = None
        self._cooldown_remaining: int = 0
        self._history: deque = deque(maxlen=self.config.history_len)

        # Pre-build the dilation kernel once
        self._kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (5, 5)
        )

        # Stats
        self.frames_checked: int = 0
        self.frames_with_motion: int = 0
        self.frames_skipped_ml: int = 0   # frames where AI was gated off

        logger.info(
            "MotionDetector ready | threshold=%d  min_area=%.3f%%  cooldown=%d frames",
            self.config.diff_threshold,
            self.config.min_area_ratio * 100,
            self.config.cooldown_frames,
        )

    # ── Public API ──────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> MotionResult:
        """
        Analyse one frame for motion.

        Parameters
        ----------
        frame:
            BGR image (OpenCV format, any resolution).

        Returns
        -------
        MotionResult
            Always returns a result; the very first call returns
            ``motion_detected=True`` (no previous frame to compare) so the
            pipeline captures the initial scene.
        """
        self.frames_checked += 1

        # ── 1. Convert & blur ───────────────────────────────────────────────
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(
            gray,
            (self.config.blur_ksize, self.config.blur_ksize),
            0,
        )

        # ── 2. Bootstrap: no previous frame yet ────────────────────────────
        if self._prev_gray is None:
            self._prev_gray = gray
            # Treat first frame as motion so the pipeline initialises
            return MotionResult(motion_detected=True, motion_score=1.0)

        # ── 3. Frame differencing ───────────────────────────────────────────
        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray                 # slide the window

        # ── 4. Threshold → binary mask ─────────────────────────────────────
        _, thresh = cv2.threshold(
            diff,
            self.config.diff_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        # ── 5. Morphological dilation (fill gaps) ──────────────────────────
        dilated = cv2.dilate(
            thresh,
            self._kernel,
            iterations=self.config.dilate_iterations,
        )

        # ── 6. Compute motion score ─────────────────────────────────────────
        total_pixels = gray.shape[0] * gray.shape[1]
        changed_pixels = int(np.count_nonzero(dilated))
        score = changed_pixels / total_pixels

        self._history.append(score)
        smoothed_score = float(np.mean(self._history))

        # ── 7. Find contours (optional, used for visualisation) ─────────────
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # ── 8. Decision ─────────────────────────────────────────────────────
        real_motion = smoothed_score >= self.config.min_area_ratio
        in_cooldown = False

        if real_motion:
            self._cooldown_remaining = self.config.cooldown_frames
            self.frames_with_motion += 1
        elif self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            in_cooldown = True                 # extend due to cooldown
        else:
            self.frames_skipped_ml += 1

        motion_detected = real_motion or in_cooldown

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Motion: score=%.4f  smoothed=%.4f  detected=%s  cooldown=%d",
                score, smoothed_score, motion_detected, self._cooldown_remaining,
            )

        return MotionResult(
            motion_detected=motion_detected,
            motion_score=smoothed_score,
            contours=list(contours),
            diff_frame=dilated,
            in_cooldown=in_cooldown,
        )

    def reset(self) -> None:
        """
        Clear internal state (call when stream restarts or camera changes).
        The next call to ``detect`` will treat the frame as the first frame.
        """
        self._prev_gray = None
        self._cooldown_remaining = 0
        self._history.clear()
        logger.info("MotionDetector state reset")

    def update_config(self, **kwargs) -> None:
        """
        Hot-update config parameters at runtime without restarting the stream.

        Example
        -------
        >>> detector.update_config(diff_threshold=30, cooldown_frames=12)
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info("MotionDetector config updated: %s = %s", key, value)
            else:
                logger.warning("Unknown config key: %s", key)

    # ── Visualisation helper ───────────────────────────────────────────────────

    def draw_motion_overlay(
        self,
        frame: np.ndarray,
        result: MotionResult,
        draw_contours: bool = True,
    ) -> np.ndarray:
        """
        Draw motion regions and score on a copy of ``frame``.

        Parameters
        ----------
        frame:
            Original BGR frame.
        result:
            ``MotionResult`` from the most recent ``detect()`` call.
        draw_contours:
            If True, draw bounding boxes around moving regions.

        Returns
        -------
        np.ndarray
            Annotated BGR frame copy.
        """
        vis = frame.copy()

        if draw_contours and result.motion_detected:
            for cnt in result.contours:
                if cv2.contourArea(cnt) < 200:   # skip tiny noise contours
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 200, 255), 1)

        # HUD bar
        color = (0, 200, 0) if result.motion_detected else (80, 80, 80)
        status = "MOTION" if result.motion_detected else "STATIC"
        if result.in_cooldown:
            status = "COOLDOWN"
            color = (0, 165, 255)

        cv2.putText(
            vis,
            f"{status}  score={result.motion_score:.4f}",
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )
        return vis

    # ── Statistics ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """
        Return efficiency statistics since instantiation.

        Returns
        -------
        dict
            ``frames_checked``, ``frames_with_motion``, ``frames_skipped_ml``,
            ``ml_skip_rate`` (fraction of frames where AI was bypassed).
        """
        skipped = self.frames_skipped_ml
        checked = max(self.frames_checked, 1)
        return {
            "frames_checked": self.frames_checked,
            "frames_with_motion": self.frames_with_motion,
            "frames_skipped_ml": skipped,
            "ml_skip_rate": round(skipped / checked, 4),
        }
