"""
Services package for the attendance system.

Provides business logic services for face detection, recognition,
tracking, and attendance marking.

Core Pipelines:
- detection.py: YOLOv8-based face detection from webcam
- recognition.py: FaceNet embedding generation (128-dim)
- attendance_pipeline.py: Integrated real-time attendance processing

Legacy Services (High-level abstractions):
- face_detection_service.py
- face_recognition_service.py
- tracking_service.py
- attendance_service.py
"""

# Legacy service imports
from services.face_detection_service import FaceDetectionService
from services.face_recognition_service import FaceRecognitionService
from services.tracking_service import TrackingService
from services.attendance_service import AttendanceLockService as AttendanceService

# New core pipeline imports
try:
    from services.detection import (
        FaceDetectionPipeline,
        demo_detection
    )
except ImportError:
    FaceDetectionPipeline = None
    demo_detection = None

try:
    from services.recognition import (
        FaceRecognitionPipeline,
        FaceDatabase,
        demo_recognition
    )
except ImportError:
    FaceRecognitionPipeline = None
    FaceDatabase = None
    demo_recognition = None

try:
    from services.attendance_pipeline import (
        AttendancePipeline,
        DetectedFace,
        demo_attendance_pipeline
    )
except ImportError:
    AttendancePipeline = None
    DetectedFace = None
    demo_attendance_pipeline = None

__all__ = [
    # Legacy services
    "FaceDetectionService",
    "FaceRecognitionService",
    "TrackingService",
    "AttendanceService",
    
    # New core pipelines
    "FaceDetectionPipeline",
    "FaceRecognitionPipeline",
    "FaceDatabase",
    "AttendancePipeline",
    "DetectedFace",
    
    # Demo functions
    "demo_detection",
    "demo_recognition",
    "demo_attendance_pipeline",
]
