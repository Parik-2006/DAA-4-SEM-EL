"""
Face Detection Service for real-time face detection and processing.

Handles face detection from images and video frames using YOLOv8,
including preprocessing and bounding box filtering.

Changes
-------
• Added ``CaptureQuality`` dataclass — carries frontality/sharpness/motion
  scores and a tier label for each detected face.
• Added ``FaceDetectionService.score_capture_quality()`` — assigns a
  ``CaptureQuality`` to a single (face_image, motion_magnitude) pair.
• Added ``FaceDetectionService.get_quality_scored_faces()`` — full pipeline
  helper: detect → crop → score → sort by quality.  Used by the enrollment
  endpoint and the attendance pipeline's QUICK_ACCEPT path.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

import cv2
import numpy as np

from models.model_manager import ModelManager
from utils.preprocessing import FaceQualityAnalyzer, ImagePreprocessor
from utils.validators import Validators
from config.constants import FACE_MIN_PIXEL_SIZE


logger = logging.getLogger(__name__)


# ── CaptureQuality ────────────────────────────────────────────────────────────

@dataclass
class CaptureQuality:
    """
    Per-face capture quality assessment.

    Attributes
    ----------
    score : float
        Composite quality score in [0.0, 1.0].
    tier : str
        One of ``"HIGH"`` / ``"ACCEPTABLE"`` / ``"LOW"``.
    frontality : float
        Frontality component in [0.0, 1.0].
        Based on bbox aspect-ratio + horizontal-symmetry heuristic.
        No ML model required; O(pixels) cost.
    sharpness : float
        Sharpness component in [0.0, 1.0].
        Laplacian-variance normalised by face area.
    stillness : float
        Stillness component in [0.0, 1.0]; inverse of ``motion_magnitude``.
    motion_magnitude : float
        Raw normalised motion level passed in by the caller (0 = still).
    is_high_quality : bool
        Shortcut: ``tier == "HIGH"``.
    """
    score:            float
    tier:             str
    frontality:       float
    sharpness:        float
    stillness:        float
    motion_magnitude: float

    @property
    def is_high_quality(self) -> bool:
        return self.tier == "HIGH"

    @property
    def is_usable(self) -> bool:
        """True for HIGH or ACCEPTABLE — suitable for enrollment."""
        return self.tier in ("HIGH", "ACCEPTABLE")


# ── Service ───────────────────────────────────────────────────────────────────

class FaceDetectionService:
    """
    Face Detection Service using YOLOv8.
    
    Provides methods for detecting faces in images and applying
    confidence filtering and size validation.
    """
    
    def __init__(self):
        """Initialize face detection service."""
        self.detector = None
        self.preprocessor = ImagePreprocessor()
    
    def ensure_detector_loaded(self) -> None:
        """Ensure detector model is loaded."""
        if self.detector is None:
            try:
                self.detector = ModelManager.get_yolov8_detector()
            except RuntimeError:
                logger.error("Failed to load detector model")
                raise
    
    def detect_faces(
        self,
        image: np.ndarray,
        min_confidence: Optional[float] = None,
        min_size: Optional[int] = None
    ) -> List[Tuple[float, float, float, float, float]]:
        """
        Detect faces in image.
        
        Args:
            image: Input image (BGR format)
            min_confidence: Minimum confidence threshold (0-1)
            min_size: Minimum face size in pixels
        
        Returns:
            List of detections: [(x1, y1, x2, y2, confidence), ...]
        
        Raises:
            ValueError: If image is invalid
        """
        try:
            self.ensure_detector_loaded()
            
            if not Validators.validate_image_size(image.shape[1], image.shape[0]):
                raise ValueError("Image size out of valid range")
            
            # Run detection
            detections = self.detector.detect(image, min_confidence)
            
            # Filter by size
            min_size = min_size or FACE_MIN_PIXEL_SIZE
            filtered_detections = self._filter_by_size(detections, min_size)
            
            logger.debug(f"Detected {len(filtered_detections)} faces after filtering")
            return filtered_detections
        
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            raise
    
    def detect_batch_faces(
        self,
        images: List[np.ndarray],
        min_confidence: Optional[float] = None
    ) -> List[List[Tuple[float, float, float, float, float]]]:
        """
        Detect faces in multiple images.
        
        Args:
            images: List of images
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of detection lists
        """
        batch_detections = []
        
        for image in images:
            try:
                detections = self.detect_faces(image, min_confidence)
                batch_detections.append(detections)
            except Exception as e:
                logger.warning(f"Skipped detection for one image: {e}")
                batch_detections.append([])
        
        return batch_detections
    
    def extract_face_regions(
        self,
        image: np.ndarray,
        detections: List[Tuple[float, float, float, float, float]],
        padding_percent: float = 0.1
    ) -> List[np.ndarray]:
        """
        Extract face regions from image using detections.
        
        Args:
            image: Input image
            detections: List of bounding boxes
            padding_percent: Padding around faces
        
        Returns:
            List of extracted face images
        """
        face_regions = []
        
        for x1, y1, x2, y2, conf in detections:
            try:
                face = self.preprocessor.extract_face_region(
                    image,
                    (x1, y1, x2, y2),
                    padding_percent
                )
                face_regions.append(face)
            except Exception as e:
                logger.warning(f"Failed to extract face region: {e}")
        
        return face_regions
    
    def get_detection_stats(self) -> dict:
        """
        Get detection model statistics.
        
        Returns:
            Dictionary with model info
        """
        try:
            self.ensure_detector_loaded()
            return self.detector.get_model_info()
        except Exception as e:
            logger.error(f"Error getting detection stats: {e}")
            return {}
    
    @staticmethod
    def _filter_by_size(
        detections: List[Tuple[float, float, float, float, float]],
        min_size: int
    ) -> List[Tuple[float, float, float, float, float]]:
        """Filter detections by minimum size."""
        filtered = []
        
        for x1, y1, x2, y2, conf in detections:
            width = x2 - x1
            height = y2 - y1
            
            if width >= min_size and height >= min_size:
                filtered.append((x1, y1, x2, y2, conf))
        
        return filtered

    # ── Quality scoring ───────────────────────────────────────────────────────

    @staticmethod
    def score_capture_quality(
        face_image:       np.ndarray,
        motion_magnitude: float = 0.0,
    ) -> CaptureQuality:
        """
        Score the capture quality of a single cropped face image.

        Delegates all signal extraction to ``FaceQualityAnalyzer``, which
        applies only cheap O(pixels) operations (one grayscale conversion,
        one Laplacian pass, two array-mean calls).  No ML model is involved.

        Args:
            face_image:
                Cropped face region (BGR or grayscale, any size).
            motion_magnitude:
                Normalised motion level in [0.0, 1.0] from the frame's
                ``MotionResult``.  Use 0.0 when motion info is unavailable.

        Returns:
            A ``CaptureQuality`` instance with individual component scores,
            a composite score, and a tier label.
        """
        frontality = FaceQualityAnalyzer.frontality_score(face_image)
        sharpness  = FaceQualityAnalyzer.sharpness_score(face_image)
        stillness  = float(max(0.0, 1.0 - min(motion_magnitude, 1.0)))
        score      = FaceQualityAnalyzer.composite_score(face_image, motion_magnitude)
        tier       = FaceQualityAnalyzer.tier(score)

        return CaptureQuality(
            score=round(score, 4),
            tier=tier,
            frontality=round(frontality, 4),
            sharpness=round(sharpness, 4),
            stillness=round(stillness, 4),
            motion_magnitude=round(motion_magnitude, 4),
        )

    def get_quality_scored_faces(
        self,
        image:            np.ndarray,
        motion_magnitude: float = 0.0,
        min_confidence:   Optional[float] = None,
        min_size:         Optional[int]   = None,
        padding_percent:  float = 0.1,
    ) -> List[Tuple[Tuple[float, float, float, float, float], np.ndarray, CaptureQuality]]:
        """
        Detect faces, crop them, score quality, and return sorted results.

        This is the primary helper used by:
        - The enrollment endpoint (needs best N frontal frames).
        - The attendance pipeline's QUICK_ACCEPT path (needs to know if the
          current face is high quality before bypassing temporal verification).

        Pipeline (all operations are cheap; no second ML call):
        1. YOLO detection (already loaded).
        2. Crop each face region with padding.
        3. Score each crop with ``score_capture_quality()``.
        4. Return sorted by descending composite score.

        Args:
            image:
                Full BGR frame.
            motion_magnitude:
                Normalised motion level from ``MotionDetector`` for this frame.
            min_confidence:
                YOLO detection threshold (default: model default).
            min_size:
                Minimum face dimension in pixels (default: FACE_MIN_PIXEL_SIZE).
            padding_percent:
                Padding fraction applied when cropping face regions.

        Returns:
            List of ``(detection, face_crop, quality)`` triples, sorted by
            ``quality.score`` descending (best first).  Empty list if no
            faces are detected.
        """
        detections = self.detect_faces(image, min_confidence, min_size)
        if not detections:
            return []

        face_crops = self.extract_face_regions(image, detections, padding_percent)

        scored: List[Tuple[
            Tuple[float, float, float, float, float],
            np.ndarray,
            CaptureQuality,
        ]] = []

        for det, crop in zip(detections, face_crops):
            if crop is None or crop.size == 0:
                continue
            quality = self.score_capture_quality(crop, motion_magnitude)
            scored.append((det, crop, quality))

        # Best face first — enrollment and QUICK_ACCEPT both want this order
        scored.sort(key=lambda t: t[2].score, reverse=True)

        logger.debug(
            "Quality-scored %d faces; top score=%.3f tier=%s",
            len(scored),
            scored[0][2].score if scored else 0.0,
            scored[0][2].tier  if scored else "N/A",
        )
        return scored