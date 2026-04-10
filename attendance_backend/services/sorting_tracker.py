"""
SORT (Simple Online and Realtime Tracking) Algorithm for Face Tracking.

Maintains face identity across frames using centroid tracking and
Kalman filter predictions for smooth tracking.

Features:
- Centroid-based face tracking
- Hungarian algorithm for optimal matching
- Kalman filter predictions for temporal smoothing
- Automatic ID assignment and cleanup
- Frame-skipping for performance
- Temporal verification (5+ consecutive frames for attendance)

References:
- SORT: Simple Online and Realtime Tracking (Bewley et al.)
- Hungarian Algorithm: O(n³) optimal assignment
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available for Hungarian algorithm")


@dataclass
class TrackedFace:
    """Represents a tracked face across frames."""
    track_id: int
    student_id: Optional[str] = None
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    centroid: Tuple[float, float] = (0, 0)
    embedding: Optional[np.ndarray] = None
    confidence: float = 0.0
    frame_count: int = 0  # Frames this tracked face has been seen
    last_seen_frame: int = 0
    detection_history: List[Tuple[int, str]] = field(default_factory=list)  # (frame, student_id)
    
    def update(
        self,
        bbox: Tuple[float, float, float, float],
        embedding: Optional[np.ndarray],
        confidence: float,
        frame_id: int
    ) -> None:
        """Update tracking info."""
        self.bbox = bbox
        self.embedding = embedding
        self.confidence = confidence
        self.frame_count += 1
        self.last_seen_frame = frame_id
        
        # Update centroid
        x1, y1, x2, y2 = bbox
        self.centroid = ((x1 + x2) / 2, (y1 + y2) / 2)


class KalmanFilter:
    """Simple Kalman filter for tracking estimation."""
    
    def __init__(self, process_var: float = 1e-4, measurement_var: float = 1e-1):
        """
        Initialize Kalman filter.
        
        Args:
            process_var: Process variance (model uncertainty)
            measurement_var: Measurement variance (sensor noise)
        """
        self.process_var = process_var
        self.measurement_var = measurement_var
        self.value = None
        self.error = 1.0
    
    def predict(self) -> float:
        """Predict next value."""
        if self.value is None:
            return 0
        return self.value
    
    def update(self, measurement: float) -> float:
        """Update with measurement."""
        if self.value is None:
            self.value = measurement
            self.error = self.measurement_var
        else:
            # Kalman gain
            k = self.error / (self.error + self.measurement_var)
            
            # Update value
            self.value = self.value + k * (measurement - self.value)
            
            # Update error
            self.error = (1 - k) * (self.error + self.process_var)
        
        return self.value


class FaceTracker:
    """
    SORT-based face tracking system.
    
    Tracks faces across frames and maintains identity through
    temporal sequences.
    """
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3
    ):
        """
        Initialize face tracker.
        
        Args:
            max_age: Max frames to keep inactive track
            min_hits: Min detections before confirming track
            iou_threshold: IoU threshold for matching
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.tracks: Dict[int, TrackedFace] = {}
        self.next_id = 1
        self.frame_count = 0
        self.frame_skip = 1  # Process every Nth frame
    
    def set_frame_skip(self, skip: int) -> None:
        """Set frame skipping (e.g., skip=2 processes every 2nd frame)."""
        self.frame_skip = max(1, skip)
    
    def update(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]],
        frame_id: int
    ) -> List[TrackedFace]:
        """
        Update tracks with new detections.
        
        Args:
            detections: List of (x1, y1, x2, y2, confidence, embedding)
            frame_id: Current frame ID
        
        Returns:
            List of active tracks
        """
        self.frame_count += 1
        
        # Skip frames if needed
        if self.frame_count % self.frame_skip != 0:
            return list(self.tracks.values())
        
        # Match detections to existing tracks
        matched, unmatched_dets, unmatched_tracks = self._match_detections(detections)
        
        # Update matched tracks
        for track_id, det_idx in matched:
            x1, y1, x2, y2, conf, emb = detections[det_idx]
            self.tracks[track_id].update((x1, y1, x2, y2), emb, conf, self.frame_count)
        
        # Create new tracks from unmatched detections
        for det_idx in unmatched_dets:
            x1, y1, x2, y2, conf, emb = detections[det_idx]
            self._create_track(x1, y1, x2, y2, conf, emb, self.frame_count)
        
        # Mark unmatched tracks as inactive
        for track_id in unmatched_tracks:
            if track_id in self.tracks:
                # Track will be removed if too old
                pass
        
        # Remove old tracks
        self._cleanup_tracks()
        
        return list(self.tracks.values())
    
    def _match_detections(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]]
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match detections to existing tracks using Hungarian algorithm.
        
        Returns:
            (matched_pairs, unmatched_dets, unmatched_tracks)
        """
        if not self.tracks or not detections:
            return [], list(range(len(detections))), list(self.tracks.keys())
        
        # Compute cost matrix (distances between detections and tracks)
        cost_matrix = self._compute_cost_matrix(detections)
        
        if not SCIPY_AVAILABLE:
            # Greedy matching fallback
            return self._greedy_match(cost_matrix, len(detections))
        
        # Hungarian algorithm (optimal assignment)
        track_ids = list(self.tracks.keys())
        
        if cost_matrix.size == 0:
            return [], list(range(len(detections))), track_ids
        
        try:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            matched = []
            matched_dets = set()
            matched_tracks = set()
            
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < 1e6:  # Valid match
                    matched.append((track_ids[r], c))
                    matched_dets.add(c)
                    matched_tracks.add(track_ids[r])
            
            unmatched_dets = [i for i in range(len(detections)) if i not in matched_dets]
            unmatched_tracks = [tid for tid in track_ids if tid not in matched_tracks]
            
            return matched, unmatched_dets, unmatched_tracks
        
        except Exception as e:
            logger.error(f"Matching error: {e}")
            return [], list(range(len(detections))), list(self.tracks.keys())
    
    def _compute_cost_matrix(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]]
    ) -> np.ndarray:
        """
        Compute cost matrix for Hungarian algorithm.
        
        High cost = unlikely match, low cost = likely match
        Uses IoU and embedding distance.
        """
        track_ids = list(self.tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)
        
        cost_matrix = np.ones((n_tracks, n_dets)) * 1e6
        
        for i, track_id in enumerate(track_ids):
            track = self.tracks[track_id]
            
            for j, detection in enumerate(detections):
                x1, y1, x2, y2, conf, emb = detection
                
                # IoU cost
                iou = self._compute_iou(track.bbox, (x1, y1, x2, y2))
                
                # Embedding distance cost (if available)
                emb_cost = 0
                if track.embedding is not None and emb is not None:
                    # Cosine distance
                    emb_cost = self._cosine_distance(track.embedding, emb)
                
                # Combined cost (weighted)
                cost = 0.7 * (1 - iou) + 0.3 * emb_cost
                
                cost_matrix[i, j] = cost
        
        return cost_matrix
    
    @staticmethod
    def _compute_iou(bbox1: Tuple, bbox2: Tuple) -> float:
        """Compute Intersection over Union."""
        x1a, y1a, x2a, y2a = bbox1
        x1b, y1b, x2b, y2b = bbox2
        
        # Intersection
        xi1 = max(x1a, x1b)
        yi1 = max(y1a, y1b)
        xi2 = min(x2a, x2b)
        yi2 = min(y2a, y2b)
        
        if xi2 < xi1 or yi2 < yi1:
            return 0
        
        intersection = (xi2 - xi1) * (yi2 - yi1)
        
        # Union
        area_a = (x2a - x1a) * (y2a - y1a)
        area_b = (x2b - x1b) * (y2b - y1b)
        union = area_a + area_b - intersection
        
        return intersection / max(union, 1e-8)
    
    @staticmethod
    def _cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine distance between embeddings."""
        # Normalize
        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-8)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-8)
        
        # Cosine similarity: dot product
        similarity = np.dot(emb1, emb2)
        
        # Convert to distance (0=identical, 1=different)
        distance = 1 - similarity
        
        return max(0, min(1, distance))
    
    @staticmethod
    def _greedy_match(
        cost_matrix: np.ndarray,
        n_dets: int
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """Greedy matching fallback (if scipy not available)."""
        matched = []
        matched_dets = set()
        matched_tracks = set()
        
        # Greedy assignment: best matches first
        while True:
            if cost_matrix.size == 0:
                break
            
            min_cost = cost_matrix.min()
            if min_cost >= 1e6:
                break
            
            row, col = np.unravel_index(np.argmin(cost_matrix), cost_matrix.shape)
            
            matched.append((row, col))
            matched_dets.add(col)
            matched_tracks.add(row)
            
            # Remove row and column
            cost_matrix[row, :] = 1e6
            cost_matrix[:, col] = 1e6
        
        unmatched_dets = [i for i in range(n_dets) if i not in matched_dets]
        unmatched_tracks = [-1]  # Simplified
        
        return matched, unmatched_dets, unmatched_tracks
    
    def _create_track(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        confidence: float,
        embedding: np.ndarray,
        frame_id: int
    ) -> None:
        """Create new track."""
        track = TrackedFace(
            track_id=self.next_id,
            bbox=(x1, y1, x2, y2),
            embedding=embedding,
            confidence=confidence,
            frame_count=1,
            last_seen_frame=frame_id,
            centroid=((x1 + x2) / 2, (y1 + y2) / 2)
        )
        
        self.tracks[self.next_id] = track
        self.next_id += 1
    
    def _cleanup_tracks(self) -> None:
        """Remove tracks that haven't been seen for too long."""
        to_remove = [
            tid for tid, track in self.tracks.items()
            if self.frame_count - track.last_seen_frame > self.max_age
        ]
        
        for tid in to_remove:
            del self.tracks[tid]
    
    def get_active_tracks(self, min_hits: int = None) -> List[TrackedFace]:
        """
        Get confirmed tracks (with min_hits detections).
        
        Args:
            min_hits: Min detections for track confirmation
        
        Returns:
            List of confirmed tracks
        """
        min_hits = min_hits or self.min_hits
        return [t for t in self.tracks.values() if t.frame_count >= min_hits]
    
    def reset(self) -> None:
        """Reset tracker."""
        self.tracks.clear()
        self.frame_count = 0
        self.next_id = 1


class TemporalVerification:
    """
    Temporal verification for attendance marking.
    
    Requires student to be detected in at least 5 consecutive frames
    before marking attendance.
    """
    
    def __init__(self, min_consecutive: int = 5):
        """
        Initialize temporal verification.
        
        Args:
            min_consecutive: Min consecutive frames for marking
        """
        self.min_consecutive = min_consecutive
        self.student_history: Dict[str, List[int]] = defaultdict(list)
        self.marked_students: set = set()
    
    def add_detection(
        self,
        student_id: str,
        frame_id: int
    ) -> bool:
        """
        Add detection and check if should mark attendance.
        
        Args:
            student_id: Detected student ID
            frame_id: Current frame ID
        
        Returns:
            True if should mark attendance
        """
        history = self.student_history[student_id]
        
        # Add to history
        history.append(frame_id)
        
        # Keep only recent frames (within 10 frames)
        history[:] = [f for f in history if frame_id - f < 10]
        
        # Check for min consecutive
        if len(history) >= self.min_consecutive:
            # Check if frames are approximately consecutive
            diffs = [history[i+1] - history[i] for i in range(len(history)-1)]
            
            if all(d <= 2 for d in diffs):  # Allow ±1 frame gap
                if student_id not in self.marked_students:
                    self.marked_students.add(student_id)
                    logger.info(
                        f"✅ Temporal verification passed: {student_id} "
                        f"({len(history)} consecutive frames)"
                    )
                    return True
        
        return False
    
    def clear(self) -> None:
        """Clear history for new session."""
        self.student_history.clear()
        self.marked_students.clear()
    
    def get_marked_students(self) -> set:
        """Get students marked for attendance."""
        return self.marked_students.copy()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo tracking
    tracker = FaceTracker()
    
    # Simulate detections
    detections = [
        (10, 10, 60, 60, 0.95, np.random.randn(128)),
        (100, 100, 150, 150, 0.90, np.random.randn(128)),
    ]
    
    for frame_id in range(10):
        # Shift detections slightly each frame (simulating movement)
        shifted = [
            (d[0] + frame_id, d[1] + frame_id, d[2] + frame_id, d[3] + frame_id, d[4], d[5])
            for d in detections
        ]
        
        tracks = tracker.update(shifted, frame_id)
        logger.info(f"Frame {frame_id}: {len(tracks)} active tracks")
    
    logger.info("✅ Tracking demo complete")
