"""
frame_aggregator.py — Multi-frame embedding aggregation with adaptive policy
═════════════════════════════════════════════════════════════════════════════
Aggregates embeddings over 2–5 frames per tracked face before committing to
an identity decision.  Designed to plug into the motion-gated pipeline
(optimized_attendance_pipeline.py) after SORT tracking assigns stable IDs.

Decision policy (configurable, tuned for ≤2 recognition attempts)
─────────────────────────────────────────────────────────────────
1. Accumulate frames until MIN_FRAMES_FOR_DECISION is reached.
2. Try VOTING: if ≥ VOTE_QUORUM fraction of individual matches agree on the
   same student_id AND their average similarity ≥ SIMILARITY_THRESHOLD → accept.
3. If voting fails (disagreement / low similarity), try AVERAGING: compute the
   centroid embedding, run a single FAISS search, accept if similarity clears
   AVERAGED_SIMILARITY_THRESHOLD (slightly more lenient because averaging
   suppresses noise).
4. If neither passes AND we have reached MAX_FRAMES, emit a REJECTED verdict
   to avoid holding a track open indefinitely.
5. Single-frame fast-path: if a single frame already clears
   FAST_ACCEPT_SIMILARITY (very high confidence), skip accumulation and
   accept immediately.  This satisfies the "quick confirmation" requirement.

All thresholds are env-configurable; see constants below.
"""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Env-driven constants ──────────────────────────────────────────────────────
def _ef(key: str, default: float) -> float:
    try:
        return float(os.environ[key])
    except (KeyError, ValueError):
        return default


def _ei(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


# Frame counts
MIN_FRAMES = _ei("AGG_MIN_FRAMES", 2)          # wait for at least this many frames
MAX_FRAMES = _ei("AGG_MAX_FRAMES", 5)           # give up after this many frames

# Fast single-frame accept (no aggregation needed)
FAST_ACCEPT_SIM = _ef("AGG_FAST_ACCEPT_SIM", 0.92)

# Voting policy
VOTE_QUORUM = _ef("AGG_VOTE_QUORUM", 0.60)             # fraction of frames that must agree
VOTE_SIM_THRESHOLD = _ef("AGG_VOTE_SIM_THRESHOLD", 0.72)

# Averaging policy (centroid embedding)
AVG_SIM_THRESHOLD = _ef("AGG_AVG_SIM_THRESHOLD", 0.68)

# Minimum liveness score required *per frame* to be included in aggregation
MIN_FRAME_LIVENESS = _ef("AGG_MIN_FRAME_LIVENESS", 0.40)


# ── Types ─────────────────────────────────────────────────────────────────────
class AggregationVerdict(Enum):
    FAST_ACCEPT   = auto()   # single frame, very high similarity
    VOTE_ACCEPT   = auto()   # voting quorum reached
    AVERAGE_ACCEPT = auto()  # centroid embedding cleared threshold
    PENDING       = auto()   # still accumulating frames
    REJECTED      = auto()   # max frames reached, no consensus


@dataclass
class FrameSample:
    """One frame's contribution to an aggregation window."""
    embedding: np.ndarray      # L2-normalised, shape (D,)
    student_id: Optional[str]  # best-match from per-frame FAISS search
    similarity: float          # similarity from per-frame search (0–1)
    liveness: float            # LivenessResult.score (0–1)
    frame_idx: int             # monotonically increasing frame counter


@dataclass
class AggregationResult:
    """Returned by FrameAggregator.add_frame / .force_decision."""
    verdict: AggregationVerdict
    student_id: Optional[str] = None
    confidence: float = 0.0           # fused / similarity that triggered accept
    frames_used: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.verdict in (
            AggregationVerdict.FAST_ACCEPT,
            AggregationVerdict.VOTE_ACCEPT,
            AggregationVerdict.AVERAGE_ACCEPT,
        )


# ── Per-track accumulator ─────────────────────────────────────────────────────
class TrackAccumulator:
    """Holds frame samples for one SORT track."""

    def __init__(self, track_id: int) -> None:
        self.track_id = track_id
        self.samples: List[FrameSample] = []
        self.frame_counter: int = 0
        self.decided: bool = False

    def add(self, sample: FrameSample) -> None:
        self.samples.append(sample)

    @property
    def count(self) -> int:
        return len(self.samples)

    def valid_samples(self) -> List[FrameSample]:
        """Samples that cleared the per-frame liveness floor."""
        return [s for s in self.samples if s.liveness >= MIN_FRAME_LIVENESS]

    def centroid_embedding(self, valid_only: bool = True) -> Optional[np.ndarray]:
        pool = self.valid_samples() if valid_only else self.samples
        if not pool:
            return None
        stack = np.stack([s.embedding for s in pool], axis=0)
        mean = stack.mean(axis=0)
        norm = np.linalg.norm(mean)
        return mean / (norm + 1e-8)

    def vote_result(self) -> Tuple[Optional[str], float, int]:
        """
        Returns (student_id, avg_similarity, vote_count) for the plurality candidate.
        vote_count is the number of samples that voted for the top candidate.
        """
        valid = self.valid_samples()
        if not valid:
            return None, 0.0, 0

        # Group by student_id
        sim_by_student: Dict[str, List[float]] = defaultdict(list)
        for s in valid:
            if s.student_id:
                sim_by_student[s.student_id].append(s.similarity)

        if not sim_by_student:
            return None, 0.0, 0

        # Pick the candidate with the most votes; break ties by avg similarity
        def _rank(item: Tuple[str, List[float]]) -> Tuple[int, float]:
            sid, sims = item
            return len(sims), float(np.mean(sims))

        top_id, top_sims = max(sim_by_student.items(), key=_rank)
        return top_id, float(np.mean(top_sims)), len(top_sims)


# ── FrameAggregator ───────────────────────────────────────────────────────────
class FrameAggregator:
    """
    Aggregates per-frame recognition results for all active SORT tracks.

    Wiring into optimized_attendance_pipeline.py
    ─────────────────────────────────────────────
    Replace the per-frame `recognize_face` → mark-attendance call with:

        result = self.aggregator.add_frame(
            track_id=sort_track_id,
            embedding=face_embedding,      # from FaceRecognitionService
            single_frame_match=(sid, sim), # from FaceRecognitionService.recognize_face
            liveness_score=liveness_score, # from LivenessDetector.check().score
            averaged_recognizer=self.face_recognition_svc.recognize_face,
        )
        if result.accepted:
            mark_attendance(result.student_id, confidence=result.confidence)
            self.aggregator.drop_track(track_id)

    A motion-gated frame-skip loop should call `add_frame` only on frames
    where motion was detected (existing MotionDetector gate is fine as-is).
    Call `evict_stale_tracks(max_age_frames)` periodically to free memory.
    """

    def __init__(self) -> None:
        self._tracks: Dict[int, TrackAccumulator] = {}

    # ── Public API ────────────────────────────────────────────────────────────
    def add_frame(
        self,
        *,
        track_id: int,
        embedding: np.ndarray,
        single_frame_match: Optional[Tuple[str, float]],
        liveness_score: float,
        averaged_recognizer: Optional[Callable[[np.ndarray], Optional[Tuple[str, float]]]] = None,
    ) -> AggregationResult:
        """
        Submit one frame's data for a tracked face.

        Args:
            track_id:             SORT stable track ID.
            embedding:            Normalised face embedding (D,).
            single_frame_match:   (student_id, similarity) from per-frame FAISS
                                  search, or None if no match found.
            liveness_score:       LivenessDetector score for this frame [0, 1].
            averaged_recognizer:  Callable that runs a FAISS search on a
                                  provided embedding and returns
                                  (student_id, similarity) or None.
                                  Required for the AVERAGING fallback.

        Returns:
            AggregationResult — check `.accepted` and `.verdict`.
        """
        accum = self._tracks.setdefault(track_id, TrackAccumulator(track_id))

        if accum.decided:
            # Track already has a verdict; caller should have called drop_track.
            logger.debug(f"Track {track_id}: already decided, ignoring frame.")
            return AggregationResult(
                verdict=AggregationVerdict.REJECTED,
                details={"reason": "already_decided"},
            )

        student_id = single_frame_match[0] if single_frame_match else None
        similarity = single_frame_match[1] if single_frame_match else 0.0

        sample = FrameSample(
            embedding=embedding,
            student_id=student_id,
            similarity=similarity,
            liveness=liveness_score,
            frame_idx=accum.frame_counter,
        )
        accum.frame_counter += 1
        accum.add(sample)

        # ── Fast accept (single high-confidence frame) ────────────────────────
        if (
            student_id is not None
            and similarity >= FAST_ACCEPT_SIM
            and liveness_score >= MIN_FRAME_LIVENESS
        ):
            accum.decided = True
            logger.info(
                f"Track {track_id}: fast-accept {student_id} "
                f"(sim={similarity:.3f}, live={liveness_score:.3f})"
            )
            return AggregationResult(
                verdict=AggregationVerdict.FAST_ACCEPT,
                student_id=student_id,
                confidence=similarity,
                frames_used=1,
                details={"similarity": similarity, "liveness": liveness_score},
            )

        # Still accumulating
        if accum.count < MIN_FRAMES:
            return AggregationResult(
                verdict=AggregationVerdict.PENDING,
                frames_used=accum.count,
                details={"need": MIN_FRAMES - accum.count},
            )

        # ── Voting policy ─────────────────────────────────────────────────────
        top_id, avg_sim, vote_count = accum.vote_result()
        total_valid = len(accum.valid_samples())

        if (
            top_id is not None
            and total_valid > 0
            and (vote_count / total_valid) >= VOTE_QUORUM
            and avg_sim >= VOTE_SIM_THRESHOLD
        ):
            accum.decided = True
            logger.info(
                f"Track {track_id}: vote-accept {top_id} "
                f"({vote_count}/{total_valid} votes, avg_sim={avg_sim:.3f})"
            )
            return AggregationResult(
                verdict=AggregationVerdict.VOTE_ACCEPT,
                student_id=top_id,
                confidence=avg_sim,
                frames_used=accum.count,
                details={
                    "vote_count": vote_count,
                    "total_valid": total_valid,
                    "avg_similarity": avg_sim,
                },
            )

        # ── Averaging policy ──────────────────────────────────────────────────
        if averaged_recognizer is not None:
            centroid = accum.centroid_embedding()
            if centroid is not None:
                avg_match = averaged_recognizer(centroid)
                if avg_match is not None:
                    avg_id, avg_centroid_sim = avg_match
                    if avg_centroid_sim >= AVG_SIM_THRESHOLD:
                        accum.decided = True
                        logger.info(
                            f"Track {track_id}: average-accept {avg_id} "
                            f"(centroid_sim={avg_centroid_sim:.3f})"
                        )
                        return AggregationResult(
                            verdict=AggregationVerdict.AVERAGE_ACCEPT,
                            student_id=avg_id,
                            confidence=avg_centroid_sim,
                            frames_used=accum.count,
                            details={"centroid_similarity": avg_centroid_sim},
                        )

        # ── Max frames reached → reject ───────────────────────────────────────
        if accum.count >= MAX_FRAMES:
            accum.decided = True
            logger.warning(
                f"Track {track_id}: rejected after {accum.count} frames "
                f"(top_id={top_id}, avg_sim={avg_sim:.3f})"
            )
            return AggregationResult(
                verdict=AggregationVerdict.REJECTED,
                frames_used=accum.count,
                details={
                    "best_candidate": top_id,
                    "best_avg_sim": avg_sim,
                    "reason": "no_consensus_after_max_frames",
                },
            )

        # Still within window, continue accumulating
        return AggregationResult(
            verdict=AggregationVerdict.PENDING,
            frames_used=accum.count,
            details={
                "best_candidate": top_id,
                "best_avg_sim": avg_sim,
                "need_frames": max(0, MIN_FRAMES - accum.count),
            },
        )

    def force_decision(
        self,
        track_id: int,
        averaged_recognizer: Optional[Callable[[np.ndarray], Optional[Tuple[str, float]]]] = None,
    ) -> AggregationResult:
        """
        Force an immediate decision for a track (e.g. when SORT loses the
        track and we must decide before eviction).

        Falls back through voting → averaging → reject with whatever frames
        we have, even if below MIN_FRAMES.
        """
        accum = self._tracks.get(track_id)
        if accum is None or accum.count == 0:
            return AggregationResult(
                verdict=AggregationVerdict.REJECTED,
                details={"reason": "no_frames"},
            )

        top_id, avg_sim, vote_count = accum.vote_result()
        total_valid = len(accum.valid_samples())

        if (
            top_id is not None
            and total_valid > 0
            and (vote_count / total_valid) >= VOTE_QUORUM
            and avg_sim >= VOTE_SIM_THRESHOLD
        ):
            accum.decided = True
            return AggregationResult(
                verdict=AggregationVerdict.VOTE_ACCEPT,
                student_id=top_id,
                confidence=avg_sim,
                frames_used=accum.count,
                details={"forced": True},
            )

        if averaged_recognizer is not None:
            centroid = accum.centroid_embedding(valid_only=len(accum.valid_samples()) > 0)
            if centroid is not None:
                avg_match = averaged_recognizer(centroid)
                if avg_match and avg_match[1] >= AVG_SIM_THRESHOLD:
                    accum.decided = True
                    return AggregationResult(
                        verdict=AggregationVerdict.AVERAGE_ACCEPT,
                        student_id=avg_match[0],
                        confidence=avg_match[1],
                        frames_used=accum.count,
                        details={"forced": True},
                    )

        accum.decided = True
        return AggregationResult(
            verdict=AggregationVerdict.REJECTED,
            frames_used=accum.count,
            details={"reason": "forced_no_consensus"},
        )

    def drop_track(self, track_id: int) -> None:
        """Remove a track from memory (call after accepting or final rejection)."""
        self._tracks.pop(track_id, None)

    def evict_stale_tracks(self, max_age_frames: int = 60) -> List[int]:
        """
        Evict tracks that have not received a new frame in `max_age_frames`
        frames.  Returns list of evicted track IDs.

        Call this once per pipeline tick with the pipeline's global frame counter.
        Uses frame_counter as a proxy for age — call only if you increment
        track.frame_counter on each new frame (add_frame does this).
        """
        # We use total sample count as a proxy for "last seen"
        # In a real integration use a timestamp or pipeline frame counter.
        evicted: List[int] = []
        active_max = max(
            (a.frame_counter for a in self._tracks.values()), default=0
        )
        cutoff = active_max - max_age_frames

        for tid, accum in list(self._tracks.items()):
            if accum.decided or accum.frame_counter < cutoff:
                evicted.append(tid)
                del self._tracks[tid]

        if evicted:
            logger.debug(f"Evicted stale tracks: {evicted}")
        return evicted

    def active_track_count(self) -> int:
        return len(self._tracks)

    def get_track_summary(self, track_id: int) -> Optional[Dict[str, Any]]:
        accum = self._tracks.get(track_id)
        if accum is None:
            return None
        top_id, avg_sim, votes = accum.vote_result()
        return {
            "track_id": track_id,
            "frames": accum.count,
            "valid_frames": len(accum.valid_samples()),
            "decided": accum.decided,
            "top_candidate": top_id,
            "top_avg_sim": avg_sim,
            "top_votes": votes,
        }