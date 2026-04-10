"""
Services package for the attendance system.

Provides business logic services for face detection, recognition,
tracking, and attendance marking.
"""

from services.face_detection_service import FaceDetectionService
from services.face_recognition_service import FaceRecognitionService
from services.tracking_service import TrackingService
from services.attendance_service import AttendanceService

__all__ = [
    "FaceDetectionService",
    "FaceRecognitionService",
    "TrackingService",
    "AttendanceService",
]
