"""
Face Detection Service for real-time face detection and processing.

Handles face detection from images and video frames using YOLOv8,
including preprocessing and bounding box filtering.
"""

from typing import List, Tuple, Optional
import logging

import cv2
import numpy as np

from models.model_manager import ModelManager
from utils.preprocessing import ImagePreprocessor
from utils.validators import Validators
from config.constants import FACE_MIN_PIXEL_SIZE


logger = logging.getLogger(__name__)


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
