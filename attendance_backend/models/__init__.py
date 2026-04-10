"""
Models package for the attendance system.

Provides ML model loading and inference capabilities for face detection
and recognition.
"""

from models.yolov8_detector import YOLOv8Detector
from models.facenet_extractor import FaceNetExtractor
from models.model_manager import ModelManager

__all__ = [
    "YOLOv8Detector",
    "FaceNetExtractor",
    "ModelManager",
]
