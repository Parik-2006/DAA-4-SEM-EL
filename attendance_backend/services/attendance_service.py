"""
Attendance Service for marking and managing attendance.

Coordinates face detection, recognition, and tracking to mark attendance.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

import numpy as np

from services.face_detection_service import FaceDetectionService
from services.face_recognition_service import FaceRecognitionService
from services.tracking_service import TrackingService
from database.attendance_repository import AttendanceRepository
from config.constants import AttendanceStatus


logger = logging.getLogger(__name__)


class AttendanceService:
    """
    Attendance Service.
    
    Orchestrates the entire attendance marking pipeline:
    1. Detect faces in image
    2. Extract embeddings
    3. Match against enrolled students
    4. Track faces to prevent duplicates
    5. Record attendance in database
    """
    
    def __init__(self):
        """Initialize attendance service."""
        self.detection_service = FaceDetectionService()
        self.recognition_service = FaceRecognitionService()
        self.tracking_service = TrackingService()
        self.attendance_repo = AttendanceRepository()
    
    def process_frame(
        self,
        image: np.ndarray,
        course_id: str,
        auto_mark: bool = True
    ) -> Dict[str, Any]:
        """
        Process single frame for attendance.
        
        Args:
            image: Input image
            course_id: Course identifier
            auto_mark: Automatically mark attendance if recognized
        
        Returns:
            Dictionary with processing results
        """
        results = {
            "success": False,
            "faces_detected": 0,
            "faces_recognized": 0,
            "attendance_marked": [],
            "errors": [],
        }
        
        try:
            # Detect faces
            detections = self.detection_service.detect_faces(image)
            results["faces_detected"] = len(detections)
            
            if not detections:
                return results
            
            # Extract face regions and embeddings
            face_regions = self.detection_service.extract_face_regions(
                image,
                detections
            )
            
            embeddings = self.recognition_service.extract_batch_embeddings(
                face_regions
            )
            
            # Match and track faces
            for i, embedding in enumerate(embeddings):
                if embedding is not None and len(embedding) > 0:
                    # Recognize face
                    match = self.recognition_service.recognize_face(embedding)
                    
                    if match:
                        student_id, confidence = match
                        results["faces_recognized"] += 1
                        
                        # Track and mark attendance
                        if auto_mark:
                            marked = self._mark_attendance(
                                student_id,
                                course_id,
                                confidence
                            )
                            
                            if marked:
                                results["attendance_marked"].append({
                                    "student_id": student_id,
                                    "confidence": round(confidence, 3),
                                    "timestamp": datetime.utcnow().isoformat(),
                                })
            
            results["success"] = True
        
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            results["errors"].append(str(e))
        
        return results
    
    def _mark_attendance(
        self,
        student_id: str,
        course_id: str,
        confidence: float
    ) -> bool:
        """
        Mark attendance for recognized student.
        
        Args:
            student_id: Student identifier
            course_id: Course identifier
            confidence: Recognition confidence score
        
        Returns:
            True if attendance marked, False if blocked (duplicate)
        """
        try:
            # Check tracking service for duplicates
            if not self.tracking_service.mark_attendance_for_student(student_id):
                logger.debug(f"Attendance marking blocked for {student_id}")
                return False
            
            # Record attendance
            success = self.attendance_repo.mark_attendance(
                student_id,
                course_id,
                confidence,
                status=AttendanceStatus.PRESENT,
                metadata={
                    "marked_by": "face_recognition",
                    "system_version": "1.0.0",
                }
            )
            
            if success:
                logger.info(f"Attendance marked for {student_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error marking attendance: {e}")
            return False
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get current session statistics.
        
        Returns:
            Dictionary with session stats
        """
        return {
            "tracking": self.tracking_service.get_track_statistics(),
            "detection_model": self.detection_service.get_detection_stats(),
            "recognition_model": self.recognition_service.get_recognition_stats(),
            "index_stats": self.recognition_service.get_index_stats(),
        }
    
    def reset_session(self) -> None:
        """
        Reset attendance session.
        
        Call at end of class session to clear tracking data.
        """
        self.tracking_service.reset_session()
        logger.info("Attendance session reset")
