"""
Model Manager with Singleton Pattern.

This module manages the lifecycle of ML models, ensuring they are loaded once
and reused across the application to minimize memory and startup overhead.
"""

from typing import Optional
import logging
import threading

from models.yolov8_detector import YOLOv8Detector
from models.facenet_extractor import FaceNetExtractor
from config.settings import get_settings


logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton model manager for loading and managing ML models.
    
    Ensures models are loaded only once and provides thread-safe access
    to detector and embedding extractor instances.
    """
    
    _instance: Optional['ModelManager'] = None
    _lock = threading.Lock()
    
    _yolov8_detector: Optional[YOLOv8Detector] = None
    _facenet_extractor: Optional[FaceNetExtractor] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ModelManager':
        """
        Create singleton instance.
        
        Returns:
            ModelManager: Singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize model manager (called once per instance)."""
        pass
    
    @classmethod
    def initialize(cls, device: str = "cpu") -> 'ModelManager':
        """
        Initialize models (call at application startup).
        
        Args:
            device: Device to load models on ('cuda' or 'cpu')
        
        Returns:
            ModelManager: Initialized singleton instance
        
        Raises:
            RuntimeError: If model initialization fails
        """
        with cls._lock:
            if cls._initialized:
                logger.info("Models already initialized")
                return cls._instance
            
            try:
                logger.info("Initializing ML models...")
                settings = get_settings()
                
                # Load YOLOv8 detector
                logger.info("Loading YOLOv8 face detector...")
                cls._yolov8_detector = YOLOv8Detector(
                    model_path=settings.yolov8_model_path,
                    confidence_threshold=settings.yolov8_confidence_threshold,
                    device=device
                )
                
                # Load FaceNet extractor
                logger.info("Loading FaceNet embedding extractor...")
                cls._facenet_extractor = FaceNetExtractor(
                    pretrained=True,
                    device=device
                )
                
                cls._initialized = True
                logger.info("All models initialized successfully")
                
            except Exception as e:
                logger.error(f"Model initialization failed: {e}")
                raise RuntimeError(f"Failed to initialize models: {e}")
        
        return cls._instance
    
    @classmethod
    def get_yolov8_detector(cls) -> YOLOv8Detector:
        """
        Get YOLOv8 detector instance.
        
        Returns:
            YOLOv8Detector: Face detector
        
        Raises:
            RuntimeError: If models not initialized
        """
        if not cls._initialized or cls._yolov8_detector is None:
            raise RuntimeError(
                "Models not initialized. Call ModelManager.initialize() first."
            )
        return cls._yolov8_detector
    
    @classmethod
    def get_facenet_extractor(cls) -> FaceNetExtractor:
        """
        Get FaceNet extractor instance.
        
        Returns:
            FaceNetExtractor: Embedding extractor
        
        Raises:
            RuntimeError: If models not initialized
        """
        if not cls._initialized or cls._facenet_extractor is None:
            raise RuntimeError(
                "Models not initialized. Call ModelManager.initialize() first."
            )
        return cls._facenet_extractor
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if models are initialized.
        
        Returns:
            bool: True if models are loaded
        """
        return cls._initialized
    
    @classmethod
    def get_status(cls) -> dict:
        """
        Get model manager status.
        
        Returns:
            Dictionary with initialization status and model info
        """
        status = {
            "initialized": cls._initialized,
            "yolov8_loaded": cls._yolov8_detector is not None,
            "facenet_loaded": cls._facenet_extractor is not None,
        }
        
        if cls._yolov8_detector:
            status["yolov8_info"] = cls._yolov8_detector.get_model_info()
        
        if cls._facenet_extractor:
            status["facenet_info"] = cls._facenet_extractor.get_model_info()
        
        return status
    
    @classmethod
    def cleanup(cls) -> None:
        """
        Cleanup and release model resources.
        
        Call at application shutdown.
        """
        with cls._lock:
            if cls._yolov8_detector:
                del cls._yolov8_detector
                cls._yolov8_detector = None
            
            if cls._facenet_extractor:
                del cls._facenet_extractor
                cls._facenet_extractor = None
            
            cls._initialized = False
            logger.info("Model resources cleaned up")
