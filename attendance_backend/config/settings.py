"""
Configuration management using Pydantic Settings.

This module provides environment-based configuration for the entire application
using Pydantic's BaseSettings, ensuring type safety and validation.
"""

from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    Settings are validated automatically by Pydantic, ensuring type safety
    and providing clear error messages for invalid configurations.
    """
    
    # ============ FastAPI Configuration ============
    fastapi_env: str = Field(default="development", alias="FASTAPI_ENV")
    fastapi_debug: bool = Field(default=True, alias="FASTAPI_DEBUG")
    fastapi_reload: bool = Field(default=True, alias="FASTAPI_RELOAD")
    
    # ============ Server Configuration ============
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # ============ Logging Configuration ============
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/attendance_system.log", alias="LOG_FILE")
    
    # ============ YOLOv8 Model Configuration ============
    yolov8_model_path: str = Field(default="weights/yolov8n-face.pt", alias="YOLOV8_MODEL_PATH")
    yolov8_confidence_threshold: float = Field(default=0.5, alias="YOLOV8_CONFIDENCE_THRESHOLD")
    
    # ============ FaceNet Configuration ============
    facenet_model_path: str = Field(default="weights/facenet_model.pt", alias="FACENET_MODEL_PATH")
    face_embedding_dim: int = Field(default=128, alias="FACE_EMBEDDING_DIM")
    face_recognition_threshold: float = Field(default=0.6, alias="FACE_RECOGNITION_THRESHOLD")
    
    # ============ Detection Configuration ============
    detection_img_size: int = Field(default=640, alias="DETECTION_IMG_SIZE")
    detection_stride: int = Field(default=32, alias="DETECTION_STRIDE")
    detection_max_det: int = Field(default=300, alias="DETECTION_MAX_DET")
    
    # ============ Face Recognition Configuration ============
    face_min_confidence: float = Field(default=0.6, alias="FACE_MIN_CONFIDENCE")
    face_min_size: int = Field(default=20, alias="FACE_MIN_SIZE")
    
    # ============ Database Configuration ============
    firebase_credentials_path: str = Field(
        default="config/firebase-credentials.json",
        alias="FIREBASE_CREDENTIALS_PATH"
    )
    firebase_database_url: str = Field(
        default="https://your-project.firebaseio.com",
        alias="FIREBASE_DATABASE_URL"
    )
    firebase_collection_students: str = Field(
        default="students",
        alias="FIREBASE_COLLECTION_STUDENTS"
    )
    firebase_collection_attendance: str = Field(
        default="attendance",
        alias="FIREBASE_COLLECTION_ATTENDANCE"
    )
    firebase_collection_faces: str = Field(
        default="face_embeddings",
        alias="FIREBASE_COLLECTION_FACES"
    )
    
    # ============ Vector Search (FAISS) Configuration ============
    use_faiss: bool = Field(default=True, alias="USE_FAISS")
    faiss_index_path: str = Field(default="indexes/face_embeddings.index", alias="FAISS_INDEX_PATH")
    faiss_metadata_path: str = Field(default="indexes/face_metadata.pkl", alias="FAISS_METADATA_PATH")
    
    # ============ Tracking Configuration ============
    track_buffer_size: int = Field(default=30, alias="TRACK_BUFFER_SIZE")
    tracker_confidence_threshold: float = Field(default=0.5, alias="TRACKER_CONFIDENCE_THRESHOLD")
    
    # ============ API Configuration ============
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
        alias="CORS_ORIGINS"
    )
    
    # ============ Performance Configuration ============
    max_workers: int = Field(default=4, alias="MAX_WORKERS")
    batch_size: int = Field(default=8, alias="BATCH_SIZE")
    
    # ============ Cache Configuration ============
    cache_embeddings: bool = Field(default=True, alias="CACHE_EMBEDDINGS")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")
    
    class Config:
        """Pydantic configuration for Settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow both alias and field name
        populate_by_name = True
    
    # ============ Validators ============
    
    @validator('fastapi_env')
    def validate_env(cls, v):
        """Validate FastAPI environment."""
        if v not in ["development", "staging", "production"]:
            raise ValueError(f"FASTAPI_ENV must be one of: development, staging, production. Got: {v}")
        return v
    
    @validator('port')
    def validate_port(cls, v):
        """Validate port number."""
        if not 1 <= v <= 65535:
            raise ValueError(f"PORT must be between 1 and 65535. Got: {v}")
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}. Got: {v}")
        return v
    
    @validator('yolov8_confidence_threshold', 'face_recognition_threshold',
               'face_min_confidence', 'tracker_confidence_threshold')
    def validate_confidence(cls, v):
        """Validate confidence threshold values."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence threshold must be between 0.0 and 1.0. Got: {v}")
        return v
    
    @validator('detection_img_size')
    def validate_img_size(cls, v):
        """Validate image size (must be multiple of stride)."""
        if v % 32 != 0:
            raise ValueError(f"detection_img_size must be multiple of 32. Got: {v}")
        return v
    
    # ============ Helper Methods ============
    
    def get_database_url(self) -> str:
        """Get Firebase database URL."""
        return self.firebase_database_url
    
    def get_credentials_path(self) -> Path:
        """Get absolute path to Firebase credentials."""
        return Path(self.firebase_credentials_path).resolve()
    
    def get_model_path(self, model_name: str) -> Path:
        """
        Get absolute path to a model file.
        
        Args:
            model_name: Name of the model ('yolov8' or 'facenet')
        
        Returns:
            Absolute path to the model file
        """
        if model_name == "yolov8":
            return Path(self.yolov8_model_path).resolve()
        elif model_name == "facenet":
            return Path(self.facenet_model_path).resolve()
        else:
            raise ValueError(f"Unknown model name: {model_name}")
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.fastapi_env == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.fastapi_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get settings singleton instance.
    
    Uses LRU cache to ensure only one Settings instance is created
    and reused throughout the application lifetime.
    
    Returns:
        Settings: The singleton Settings instance
    """
    return Settings()
