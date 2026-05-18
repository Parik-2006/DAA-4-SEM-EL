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
- ★ Per-track embedding rolling buffer (N=3) for multi-frame aggregation
    TrackedFace.get_aggregated_embedding() returns a mean-normalised vector
    built from the last N embeddings in the track, falling back to the most
    recent single-frame embedding when the buffer is too small.

References:
- SORT: Simple Online and Realtime Tracking (Bewley et al.)
- Hungarian Algorithm: O(n³) optimal assignment
"""

import numpy as np
from typing import Deque, Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available for Hungarian algorithm")


# ── Aggregation constants ──────────────────────────────────────────────────────
# Keep N small (3) so the buffer fills quickly and adds ≤2 frames of latency.
# Increasing beyond 5 gives diminishing returns and raises first-detection delay.
AGGREGATION_BUFFER_SIZE = 3    # rolling window: up to 3 embeddings per track
AGGREGATION_MIN_FRAMES  = 2    # minimum frames before aggregation is used


@dataclass
class TrackedFace:
    """
    Represents a tracked face across frames.

    Embedding buffer
    ----------------
    Each call to ``update()`` appends the new embedding to a fixed-size deque
    (maxlen = ``AGGREGATION_BUFFER_SIZE``).  The oldest entry is automatically
    evicted when the buffer is full, so it always reflects the *most recent N
    frames* for this track.

    ``get_aggregated_embedding(min_frames)`` returns:
    • mean-normalised aggregate when len(buffer) ≥ min_frames  →  richer signal
    • the single most-recent embedding when buffer is too small →  zero latency
    • None when no embedding has ever been seen for this track
    """
    track_id:          int
    student_id:        Optional[str]                 = None
    bbox:              Tuple[float, float, float, float] = (0, 0, 0, 0)
    centroid:          Tuple[float, float]           = (0, 0)
    embedding:         Optional[np.ndarray]          = None
    confidence:        float                         = 0.0
    frame_count:       int                           = 0
    last_seen_frame:   int                           = 0
    detection_history: List[Tuple[int, str]]         = field(default_factory=list)

    # ★ Rolling embedding buffer — populated by update(), read by get_aggregated_embedding()
    embedding_buffer:  Deque[np.ndarray] = field(
        default_factory=lambda: deque(maxlen=AGGREGATION_BUFFER_SIZE)
    )

    def update(
        self,
        bbox:       Tuple[float, float, float, float],
        embedding:  Optional[np.ndarray],
        confidence: float,
        frame_id:   int,
    ) -> None:
        """
        Update tracking state for a new frame.

        In addition to overwriting ``self.embedding`` (preserves legacy
        single-frame access), the new embedding is appended to the rolling
        ``embedding_buffer`` so that ``get_aggregated_embedding()`` can
        blend across recent frames.
        """
        self.bbox       = bbox
        self.embedding  = embedding
        self.confidence = confidence
        self.frame_count += 1
        self.last_seen_frame = frame_id

        x1, y1, x2, y2 = bbox
        self.centroid = ((x1 + x2) / 2, (y1 + y2) / 2)

        # ★ Accumulate embedding in the rolling buffer
        if embedding is not None:
            self.embedding_buffer.append(embedding)

    # ── ★ Multi-frame aggregation ──────────────────────────────────────────────

    def get_aggregated_embedding(
        self,
        min_frames: int = AGGREGATION_MIN_FRAMES,
    ) -> Optional[np.ndarray]:
        """
        Return a mean-normalised embedding built from the rolling buffer.

        Decision logic
        --------------
        ┌─────────────────────────────────────────────────────────────────┐
        │ buffer empty           →  return None                           │
        │ len(buffer) < min_frames → return most-recent embedding (raw)  │
        │ len(buffer) ≥ min_frames → return normalised mean of all       │
        └─────────────────────────────────────────────────────────────────┘

        Why mean-then-normalise instead of normalise-then-mean
        -------------------------------------------------------
        Normalising each vector first and then averaging is equivalent to
        spherical linear interpolation on the unit hypersphere — geometrically
        correct but more expensive.  For face embeddings the two approaches
        produce nearly identical results; mean-then-normalise is faster and
        simpler for N ≤ 3.

        Parameters
        ----------
        min_frames:
            Minimum number of buffered embeddings required to use aggregation.
            When the buffer has fewer entries the single-frame embedding is
            returned as-is, incurring zero extra latency.

        Returns
        -------
        np.ndarray or None
        """
        buf = list(self.embedding_buffer)

        if not buf:
            return None                            # no embeddings seen yet

        if len(buf) < min_frames:
            return self.embedding                  # fallback: single-frame

        # ── Aggregate ─────────────────────────────────────────────────────
        try:
            stacked  = np.stack(buf, axis=0).astype(np.float32)
            mean_emb = np.mean(stacked, axis=0)
            norm     = np.linalg.norm(mean_emb)
            if norm > 1e-8:
                mean_emb = mean_emb / norm
            return mean_emb
        except Exception as exc:
            # Shape mismatch (e.g. model hot-swap mid-session) — fall back safely
            logger.debug(
                "Embedding aggregation failed for track %d (%s); "
                "falling back to single-frame embedding.",
                self.track_id, exc,
            )
            return self.embedding

    def buffer_size(self) -> int:
        """Number of embeddings currently in the rolling buffer."""
        return len(self.embedding_buffer)

    def clear_buffer(self) -> None:
        """Flush the embedding buffer (e.g. after a confirmed attendance mark)."""
        self.embedding_buffer.clear()


class KalmanFilter:
    """Simple Kalman filter for tracking estimation."""

    def __init__(self, process_var: float = 1e-4, measurement_var: float = 1e-1):
        self.process_var    = process_var
        self.measurement_var = measurement_var
        self.value = None
        self.error = 1.0

    def predict(self) -> float:
        if self.value is None:
            return 0
        return self.value

    def update(self, measurement: float) -> float:
        if self.value is None:
            self.value = measurement
            self.error = self.measurement_var
        else:
            k = self.error / (self.error + self.measurement_var)
            self.value = self.value + k * (measurement - self.value)
            self.error = (1 - k) * (self.error + self.process_var)
        return self.value


class FaceTracker:
    """
    SORT-based face tracking system.

    Tracks faces across frames and maintains identity through
    temporal sequences.

    Multi-frame aggregation is opt-in at the pipeline level; the tracker
    itself only populates ``TrackedFace.embedding_buffer`` automatically
    — the caller decides whether to call ``get_aggregated_embedding()``
    or read ``track.embedding`` directly.
    """

    def __init__(
        self,
        max_age:       int   = 30,
        min_hits:      int   = 3,
        iou_threshold: float = 0.3,
    ):
        self.max_age       = max_age
        self.min_hits      = min_hits
        self.iou_threshold = iou_threshold

        self.tracks:     Dict[int, TrackedFace] = {}
        self.next_id     = 1
        self.frame_count = 0
        self.frame_skip  = 1

    def set_frame_skip(self, skip: int) -> None:
        self.frame_skip = max(1, skip)

    def update(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]],
        frame_id:   int,
    ) -> List[TrackedFace]:
        """
        Update tracks with new detections.

        Args:
            detections: List of (x1, y1, x2, y2, confidence, embedding)
            frame_id:   Current frame ID

        Returns:
            List of active TrackedFace objects (each with a populated
            embedding_buffer ready for aggregation).
        """
        self.frame_count += 1

        if self.frame_count % self.frame_skip != 0:
            return list(self.tracks.values())

        matched, unmatched_dets, unmatched_tracks = self._match_detections(detections)

        for track_id, det_idx in matched:
            x1, y1, x2, y2, conf, emb = detections[det_idx]
            self.tracks[track_id].update((x1, y1, x2, y2), emb, conf, self.frame_count)

        for det_idx in unmatched_dets:
            x1, y1, x2, y2, conf, emb = detections[det_idx]
            self._create_track(x1, y1, x2, y2, conf, emb, self.frame_count)

        self._cleanup_tracks()

        return list(self.tracks.values())

    def _match_detections(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not self.tracks or not detections:
            return [], list(range(len(detections))), list(self.tracks.keys())

        cost_matrix = self._compute_cost_matrix(detections)

        if not SCIPY_AVAILABLE:
            return self._greedy_match(cost_matrix, len(detections))

        track_ids = list(self.tracks.keys())

        if cost_matrix.size == 0:
            return [], list(range(len(detections))), track_ids

        try:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            matched, matched_dets, matched_tracks = [], set(), set()
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < 1e6:
                    matched.append((track_ids[r], c))
                    matched_dets.add(c)
                    matched_tracks.add(track_ids[r])

            unmatched_dets   = [i for i in range(len(detections)) if i not in matched_dets]
            unmatched_tracks = [tid for tid in track_ids if tid not in matched_tracks]

            return matched, unmatched_dets, unmatched_tracks

        except Exception as exc:
            logger.error("Matching error: %s", exc)
            return [], list(range(len(detections))), list(self.tracks.keys())

    def _compute_cost_matrix(
        self,
        detections: List[Tuple[float, float, float, float, float, np.ndarray]],
    ) -> np.ndarray:
        track_ids    = list(self.tracks.keys())
        n_tracks     = len(track_ids)
        n_dets       = len(detections)
        cost_matrix  = np.ones((n_tracks, n_dets)) * 1e6

        for i, track_id in enumerate(track_ids):
            track = self.tracks[track_id]
            for j, detection in enumerate(detections):
                x1, y1, x2, y2, conf, emb = detection
                iou      = self._compute_iou(track.bbox, (x1, y1, x2, y2))
                emb_cost = 0.0
                if track.embedding is not None and emb is not None:
                    emb_cost = self._cosine_distance(track.embedding, emb)
                cost_matrix[i, j] = 0.7 * (1 - iou) + 0.3 * emb_cost

        return cost_matrix

    @staticmethod
    def _compute_iou(bbox1: Tuple, bbox2: Tuple) -> float:
        x1a, y1a, x2a, y2a = bbox1
        x1b, y1b, x2b, y2b = bbox2
        xi1 = max(x1a, x1b); yi1 = max(y1a, y1b)
        xi2 = min(x2a, x2b); yi2 = min(y2a, y2b)
        if xi2 < xi1 or yi2 < yi1:
            return 0.0
        intersection = (xi2 - xi1) * (yi2 - yi1)
        area_a = (x2a - x1a) * (y2a - y1a)
        area_b = (x2b - x1b) * (y2b - y1b)
        return intersection / max(area_a + area_b - intersection, 1e-8)

    @staticmethod
    def _cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-8)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-8)
        return float(max(0.0, min(1.0, 1 - np.dot(emb1, emb2))))

    @staticmethod
    def _greedy_match(
        cost_matrix: np.ndarray,
        n_dets:      int,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        matched, matched_dets, matched_tracks = [], set(), set()

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
            cost_matrix[row, :] = 1e6
            cost_matrix[:, col] = 1e6

        unmatched_dets   = [i for i in range(n_dets) if i not in matched_dets]
        unmatched_tracks = [-1]
        return matched, unmatched_dets, unmatched_tracks

    def _create_track(
        self,
        x1: float, y1: float, x2: float, y2: float,
        confidence: float,
        embedding:  np.ndarray,
        frame_id:   int,
    ) -> None:
        track = TrackedFace(
            track_id=self.next_id,
            bbox=(x1, y1, x2, y2),
            embedding=embedding,
            confidence=confidence,
            frame_count=1,
            last_seen_frame=frame_id,
            centroid=((x1 + x2) / 2, (y1 + y2) / 2),
        )
        # Seed the buffer with the first embedding immediately
        if embedding is not None:
            track.embedding_buffer.append(embedding)

        self.tracks[self.next_id] = track
        self.next_id += 1

    def _cleanup_tracks(self) -> None:
        to_remove = [
            tid for tid, track in self.tracks.items()
            if self.frame_count - track.last_seen_frame > self.max_age
        ]
        for tid in to_remove:
            del self.tracks[tid]

    def get_active_tracks(self, min_hits: int = None) -> List[TrackedFace]:
        min_hits = min_hits or self.min_hits
        return [t for t in self.tracks.values() if t.frame_count >= min_hits]

    def reset(self) -> None:
        self.tracks.clear()
        self.frame_count = 0
        self.next_id     = 1


class TemporalVerification:
    """
    Temporal verification for attendance marking.

    Requires a student to be detected in at least ``min_consecutive`` frames
    before marking attendance.  This class tracks *frame IDs only* and is
    intentionally decoupled from the embedding aggregation path.
    """

    def __init__(self, min_consecutive: int = 5):
        self.min_consecutive = min_consecutive
        self.student_history: Dict[str, List[int]] = defaultdict(list)
        self.marked_students: set = set()

    def add_detection(self, student_id: str, frame_id: int) -> bool:
        history = self.student_history[student_id]
        history.append(frame_id)
        history[:] = [f for f in history if frame_id - f < 10]

        if len(history) >= self.min_consecutive:
            diffs = [history[i + 1] - history[i] for i in range(len(history) - 1)]
            if all(d <= 2 for d in diffs):
                if student_id not in self.marked_students:
                    self.marked_students.add(student_id)
                    logger.info(
                        "✅ Temporal verification passed: %s (%d consecutive frames)",
                        student_id, len(history),
                    )
                    return True

        return False

    def clear(self) -> None:
        self.student_history.clear()
        self.marked_students.clear()

    def get_marked_students(self) -> set:
        return self.marked_students.copy()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    tracker = FaceTracker()

    detections = [
        (10, 10, 60, 60, 0.95, np.random.randn(128)),
        (100, 100, 150, 150, 0.90, np.random.randn(128)),
    ]

    for frame_id in range(10):
        shifted = [
            (d[0] + frame_id, d[1] + frame_id, d[2] + frame_id, d[3] + frame_id, d[4], d[5])
            for d in detections
        ]
        tracks = tracker.update(shifted, frame_id)
        for t in tracks:
            agg = t.get_aggregated_embedding()
            logger.info(
                "Frame %d  track=%d  buf=%d  agg_shape=%s",
                frame_id, t.track_id, t.buffer_size(),
                agg.shape if agg is not None else "None",
            )

    logger.info("✅ Aggregation demo complete")