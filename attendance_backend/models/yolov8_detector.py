"""
YOLOv8 Face Detector Model.

This module provides a wrapper around the YOLOv8 face detection model,
handling model loading, inference, and bounding box post-processing.
"""

from pathlib import Path
from typing import List, Tuple, Optional
import logging

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from config.settings import get_settings
from config.constants import YOLOV8_VARIANTS


logger = logging.getLogger(__name__)


class YOLOv8Detector:
    """
    YOLOv8 Face Detection Model Wrapper.
    
    This class encapsulates the YOLOv8 model for efficient face detection.
    Handles model loading, inference, and post-processing of detections.
    
    Attributes:
        model: YOLO model instance
        model_path: Path to the model weights
        confidence_threshold: Minimum confidence for detections
        device: Device to run inference on (cuda or cpu)
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        device: str = "cpu"
    ):
        """
        Initialize YOLOv8 detector.
        
        Args:
            model_path: Path to model weights. If None, uses settings.
            confidence_threshold: Minimum confidence score. If None, uses settings.
            device: Device to run inference on ('cuda', 'cpu', or number)
        
        Raises:
            FileNotFoundError: If model file not found
            RuntimeError: If model loading fails
        """
        self.settings = get_settings()
        self.model_path = model_path or self.settings.yolov8_model_path
        self.confidence_threshold = confidence_threshold or self.settings.yolov8_confidence_threshold
        self.device = device
        
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """
        Load YOLOv8 model from disk.
        
        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If model loading fails
        """
        try:
            model_path = Path(self.model_path)
            
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
            
            logger.info(f"Loading YOLOv8 model from {self.model_path}")
            
            # Load model and move to device
            self.model = YOLO(str(model_path))
            self.model.to(self.device)
            
            logger.info(f"YOLOv8 model loaded successfully on device: {self.device}")
        
        except FileNotFoundError as e:
            logger.error(f"Model file not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    def detect(
        self,
        image: np.ndarray,
        confidence_threshold: Optional[float] = None
    ) -> List[Tuple[float, float, float, float, float]]:
        """
        Detect faces in image.
        
        Args:
            image: Input image (BGR format, numpy array)
            confidence_threshold: Override default confidence threshold
        
        Returns:
            List of detections: [(x1, y1, x2, y2, confidence), ...]
        
        Raises:
            ValueError: If image is invalid
            RuntimeError: If inference fails
        """
        if image is None or image.size == 0:
            raise ValueError("Invalid image provided")
        
        try:
            threshold = confidence_threshold or self.confidence_threshold
            
            # Run inference
            results = self.model(image, conf=threshold, device=self.device)
            
            detections = []
            
            # Process results
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Extract coordinates and confidence
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    conf = float(box.conf[0].cpu().numpy())
                    
                    detections.append((float(x1), float(y1), float(x2), float(y2), conf))
            
            logger.debug(f"Detected {len(detections)} faces in image")
            return detections
        
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            raise RuntimeError(f"Inference failed: {e}")
    
    def detect_batch(
        self,
        images: List[np.ndarray],
        confidence_threshold: Optional[float] = None
    ) -> List[List[Tuple[float, float, float, float, float]]]:
        """
        Detect faces in multiple images.
        
        Args:
            images: List of input images (BGR format)
            confidence_threshold: Override default confidence threshold
        
        Returns:
            List of detection lists for each image
        """
        batch_detections = []
        
        for image in images:
            try:
                detections = self.detect(image, confidence_threshold)
                batch_detections.append(detections)
            except Exception as e:
                logger.warning(f"Batch detection skipped for one image: {e}")
                batch_detections.append([])
        
        return batch_detections
    
    def get_model_info(self) -> dict:
        """
        Get model information.
        
        Returns:
            Dictionary with model metadata
        """
        return {
            "model_path": str(self.model_path),
            "confidence_threshold": self.confidence_threshold,
            "device": str(self.device),
            "model_type": "YOLOv8",
        }
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold for detections.
        
        Args:
            threshold: Confidence threshold (0.0 to 1.0)
        
        Raises:
            ValueError: If threshold not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")
        
        self.confidence_threshold = threshold
        logger.info(f"Confidence threshold updated to {threshold}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.model is not None:
            try:
                del self.model
                logger.debug("YOLOv8 model cleaned up")
            except Exception as e:
                logger.warning(f"Error during model cleanup: {e}")
