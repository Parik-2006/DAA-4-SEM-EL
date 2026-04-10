"""
Face Tracking Service for temporal face tracking across frames.

Prevents duplicate attendance marks by tracking faces across frames
and maintaining face identity consistency.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import defaultdict

from config.constants import (
    TRACK_MAX_AGE,
    TRACKER_CONFIDENCE_MIN,
    DUPLICATE_DETECTION_COOLDOWN,
)


logger = logging.getLogger(__name__)


class FaceTrack:
    """
    Represents a tracked face across multiple frames.
    
    Attributes:
        track_id: Unique track identifier
        student_id: Associated student ID (if recognized)
        confidence_scores: List of confidence scores from matches
        first_seen: Timestamp of first detection
        last_seen: Timestamp of last update
        age: Number of frames this track has existed
    """
    
    def __init__(self, track_id: int, student_id: str, confidence: float):
        """
        Initialize face track.
        
        Args:
            track_id: Unique track ID
            student_id: Student identifier
            confidence: Initial confidence score
        """
        self.track_id = track_id
        self.student_id = student_id
        self.confidence_scores = [confidence]
        self.first_seen = datetime.utcnow()
        self.last_seen = self.first_seen
        self.age = 1
        self.attendance_marked = False
    
    def update(self, confidence: float) -> None:
        """Update track with new detection."""
        self.confidence_scores.append(confidence)
        self.last_seen = datetime.utcnow()
        self.age += 1
    
    def get_avg_confidence(self) -> float:
        """Get average confidence across all detections."""
        return sum(self.confidence_scores) / len(self.confidence_scores) if self.confidence_scores else 0.0
    
    def is_expired(self, max_age: int = TRACK_MAX_AGE) -> bool:
        """Check if track has expired."""
        return self.age > max_age
    
    def can_mark_attendance(self, cooldown: int = DUPLICATE_DETECTION_COOLDOWN) -> bool:
        """Check if enough time has passed to mark attendance again."""
        if not self.attendance_marked:
            return True
        
        time_since_last = (datetime.utcnow() - self.last_seen).total_seconds()
        return time_since_last > cooldown


class TrackingService:
    """
    Face Tracking Service for temporal consistency.
    
    Maintains tracks of faces across frames to prevent duplicate
    attendance marks and ensure face identification consistency.
    """
    
    def __init__(self):
        """Initialize tracking service."""
        self.tracks: Dict[int, FaceTrack] = {}
        self.next_track_id = 0
        self.student_attendance_log: Dict[str, datetime] = {}
    
    def create_track(self, student_id: str, confidence: float) -> FaceTrack:
        """
        Create new face track.
        
        Args:
            student_id: Student identifier
            confidence: Detection confidence
        
        Returns:
            New FaceTrack object
        """
        track_id = self.next_track_id
        self.next_track_id += 1
        
        track = FaceTrack(track_id, student_id, confidence)
        self.tracks[track_id] = track
        
        logger.debug(f"Created track {track_id} for student {student_id}")
        return track
    
    def update_track(
        self,
        track_id: int,
        student_id: str,
        confidence: float
    ) -> Optional[FaceTrack]:
        """
        Update existing track.
        
        Args:
            track_id: Track identifier
            student_id: Student identifier
            confidence: Detection confidence
        
        Returns:
            Updated FaceTrack or None if track not found
        """
        if track_id not in self.tracks:
            return None
        
        track = self.tracks[track_id]
        track.update(confidence)
        
        # Update student ID if there's a change
        if student_id != track.student_id:
            logger.warning(
                f"Track {track_id} reassigned from {track.student_id} to {student_id}"
            )
            track.student_id = student_id
        
        return track
    
    def remove_expired_tracks(self) -> int:
        """
        Remove expired tracks.
        
        Returns:
            Number of removed tracks
        """
        expired_ids = [
            tid for tid, track in self.tracks.items()
            if track.is_expired()
        ]
        
        for tid in expired_ids:
            del self.tracks[tid]
        
        if expired_ids:
            logger.debug(f"Removed {len(expired_ids)} expired tracks")
        
        return len(expired_ids)
    
    def get_track(self, track_id: int) -> Optional[FaceTrack]:
        """Get track by ID."""
        return self.tracks.get(track_id)
    
    def get_student_track(self, student_id: str) -> Optional[FaceTrack]:
        """
        Get active track for student.
        
        Returns most recent active track for a student.
        """
        for track in sorted(
            self.tracks.values(),
            key=lambda t: t.last_seen,
            reverse=True
        ):
            if track.student_id == student_id and not track.is_expired():
                return track
        
        return None
    
    def mark_attendance_for_student(self, student_id: str) -> bool:
        """
        Mark attendance for student (check against duplicates).
        
        Args:
            student_id: Student identifier
        
        Returns:
            True if attendance can be marked
        """
        track = self.get_student_track(student_id)
        
        if track and not track.can_mark_attendance():
            logger.debug(f"Attendance mark blocked for {student_id} (duplicate check)")
            return False
        
        # Check if student marked recently (outside tracked frames)
        if student_id in self.student_attendance_log:
            last_marked = self.student_attendance_log[student_id]
            time_since = (datetime.utcnow() - last_marked).total_seconds()
            
            if time_since < DUPLICATE_DETECTION_COOLDOWN:
                logger.debug(f"Duplicate attendance blocked for {student_id}")
                return False
        
        # Mark attendance
        self.student_attendance_log[student_id] = datetime.utcnow()
        
        if track:
            track.attendance_marked = True
        
        return True
    
    def get_track_statistics(self) -> dict:
        """
        Get tracking statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            "total_tracks": len(self.tracks),
            "active_tracks": sum(
                1 for t in self.tracks.values()
                if not t.is_expired()
            ),
            "total_students_tracked": len(set(t.student_id for t in self.tracks.values())),
            "attendance_records": len(self.student_attendance_log),
        }
    
    def reset_session(self) -> None:
        """
        Reset tracking session (clear all tracks).
        
        Call at end of each class session.
        """
        self.tracks.clear()
        self.next_track_id = 0
        self.student_attendance_log.clear()
        logger.info("Tracking session reset")
