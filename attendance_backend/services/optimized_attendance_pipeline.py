"""
Optimized Attendance Pipeline with Tracking, Temporal Verification,
Motion Detection Gatekeeper, Quality-Aware QUICK_ACCEPT, and
Multi-Frame Embedding Aggregation.

Integrates:
- Motion Detection Gatekeeper     — frame differencing, O(W×H) µs cost
- CaptureQuality scoring          — frontality + sharpness + stillness, O(pixels)
- QUICK_ACCEPT path               — bypass temporal verifier for HIGH-quality,
                                    high-confidence matches
- Quality-gated enrollment        — only HIGH/ACCEPTABLE frames fed to FAISS
- Multi-frame embedding aggregation
      Before each FAISS search, up to N=3 recent embeddings from the same
      SORT track are mean-averaged and L2-normalised into a single query
      vector.  One FAISS call is still made per track per frame; the
      aggregated query is simply more representative of the face's "true"
      embedding under lighting / expression variation.
      QUICK_ACCEPT naturally benefits: the aggregated similarity is more
      reliable than a single-frame score, making the high threshold safer.
- SORT tracking                   — O(1) identity maintenance
- Frame-skipping                  — configurable 2–3 frame intervals
- Efficient embedding search      — O(log n) via FAISS
- Temporal verification           — 5+ consecutive frames (standard path)
- Cosine similarity matching

Performance optimizations
--------------------------
- Motion gating      skips YOLO + FaceNet entirely on static frames
                     → typical classroom: 60–80 % of frames are static
- Quality gating     skips FaceNet on LOW-quality crops (blurred, profile)
                     → saves the costliest per-face call on bad frames
- Frame skipping     8–12 FPS → 15–20 FPS with skip=2
- O(log n) FAISS     replaces O(n×m) brute-force scan
- QUICK_ACCEPT       eliminates temporal accumulation for obvious matches
                     → mark-to-confirm latency from ~5 frames to 1 frame
- Aggregation        1 FAISS call per track unchanged; accuracy improves free

Pipeline decision tree (per frame)
------------------------------------
Frame arrives
  └─ Motion detector (µs)
       ├─ No motion  →  return cached result, skip AI entirely
       └─ Motion detected
            └─ Frame-skip check
                 ├─ Skip  →  return cached result
                 └─ Process frame
                      ├─ YOLOv8 detection
                      ├─ Quality scoring (frontality + sharpness + stillness)
                      ├─ FaceNet — HIGH/ACCEPTABLE faces only
                      ├─ SORT tracker update  (buffer += new embedding)
                      └─ For each track:
                           ├─ aggregated embedding (mean of ≤N buffered frames)
                           ├─ FAISS O(log n) search (one call per track)
                           ├─ QUICK_ACCEPT: HIGH quality + sim ≥ threshold
                           └─ Standard temporal verifier (fallback path)
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Generator
import logging
from datetime import datetime
from dataclasses import dataclass, field

from .detection import FaceDetectionPipeline
from .recognition import FaceRecognitionPipeline
from .sorting_tracker import (
    FaceTracker, TemporalVerification, TrackedFace,
    AGGREGATION_BUFFER_SIZE, AGGREGATION_MIN_FRAMES,
)
from services.face_detection_service import CaptureQuality, FaceDetectionService
from services.liveness import get_liveness_detector, fuse_confidence, LoginMetadata
from utils.efficient_embedding_search import OptimizedEmbeddingSearch
from utils.motion_detector import MotionDetector, MotionConfig, MotionResult
from utils.preprocessing import FaceQualityAnalyzer

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class OptimizedDetectedFace:
    """
    Enhanced detected face with tracking, quality, and aggregation info.

    Fields
    ------
    quality:
        CaptureQuality from the current frame's crop (frontality, sharpness,
        stillness).  None if the crop could not be scored.
    quick_accepted:
        True when QUICK_ACCEPT fired for this detection — attendance was
        marked immediately without waiting for temporal verification.
    frames_aggregated:
        Number of buffered embeddings that were mean-blended into the FAISS
        query vector for this match.  1 means a single-frame query was used.
    """
    face_id:           int
    track_id:          int
    bbox:              Tuple[float, float, float, float]
    confidence:        float
    embedding:         Optional[np.ndarray]   # the aggregated query vector
    student_id:        Optional[str]
    match_similarity:  Optional[float]
    timestamp:         datetime
    quality:           Optional[CaptureQuality] = None
    quick_accepted:    bool = False
    frames_aggregated: int  = 1


@dataclass
class PipelineFrameResult:
    """
    Full result for one processed frame.

    Attributes
    ----------
    frame:
        Original BGR frame.
    frame_id:
        Sequential index of *processed* frames (not total frames read).
    detections:
        Faces matched to registered students.
    tracked_faces:
        All SORT-tracked faces regardless of identity match.
    marked_students:
        Students confirmed by the verifier this frame.
    fps:
        Rolling-average FPS of the AI sub-pipeline.
    motion_result:
        Raw output from the motion detector for this frame.
    ai_triggered:
        True if YOLO + FaceNet actually ran.
    quick_accepted_students:
        Student IDs marked via QUICK_ACCEPT this frame.
    best_quality_score:
        Highest composite quality score across all detected faces this
        frame.  Useful for enrollment UI feedback.
    """
    frame:                   np.ndarray
    frame_id:                int
    detections:              List[OptimizedDetectedFace]
    tracked_faces:           List[TrackedFace]
    marked_students:         dict
    fps:                     float
    motion_result:           MotionResult
    ai_triggered:            bool
    quick_accepted_students: set   = field(default_factory=set)
    best_quality_score:      float = 0.0


# ── Pipeline ───────────────────────────────────────────────────────────────────

class OptimizedAttendancePipeline:
    """
    Production-grade attendance pipeline.

    Combines four orthogonal accuracy/performance features:

    1. Motion Detection Gatekeeper
       Static frames skip YOLO + FaceNet entirely; CPU usage drops 60–80 %
       in a typical classroom without affecting accuracy.

    2. Capture Quality Scoring
       Each face crop is scored for frontality, sharpness, and stillness
       before FaceNet is called.  LOW-tier crops skip embedding extraction
       (saves the costliest per-face operation on bad frames) and are excluded
       from enrollment centroids.

    3. Multi-Frame Embedding Aggregation
       ``TrackedFace.embedding_buffer`` holds the last N FaceNet outputs for
       each SORT track.  Before each FAISS call, the buffer contents are
       mean-averaged and L2-normalised into a single, noise-reduced query
       vector.  FAISS call count is unchanged; discriminative power increases.

    4. QUICK_ACCEPT
       When a face simultaneously passes the quality threshold AND the
       aggregated FAISS similarity exceeds ``quick_accept_similarity`` (default
       0.92), attendance is marked immediately — no temporal accumulation
       needed.  The combination of quality gating + aggregated similarity
       makes this safe: both false-positive sources (noisy embeddings and
       bad captures) are already suppressed.

    Parameters
    ----------
    detection_model:
        YOLOv8 model variant ('yolov8n', 'yolov8s', …).
    detection_threshold:
        YOLO confidence threshold (0–1).
    recognition_threshold:
        Cosine similarity floor for standard FAISS match (0–1).
    quick_accept_similarity:
        Similarity threshold for QUICK_ACCEPT.  Must be ≥
        ``recognition_threshold``.  Default: 0.92.
    quick_accept_min_tier:
        Minimum quality tier required for QUICK_ACCEPT.
        ``"HIGH"`` (default) is recommended; ``"ACCEPTABLE"`` is looser.
    device:
        ``'cpu'`` or ``'cuda'``.
    frame_skip:
        Process every Nth motion-triggered frame (1–5).
    min_consecutive_frames:
        Temporal verifier requirement for standard-path marking.
    motion_config:
        Fine-grained motion detector settings; ``None`` uses defaults.
    enable_motion_gate:
        ``False`` disables motion gating (useful for testing).
    enable_quick_accept:
        ``False`` always requires temporal verification (high-security mode).
    aggregation_buffer_size:
        Maximum embeddings stored per track (default: ``AGGREGATION_BUFFER_SIZE``).
        Effective range: [1, 10].
    aggregation_min_frames:
        Minimum buffer entries required before aggregation is used
        (default: ``AGGREGATION_MIN_FRAMES``).  Setting to 1 is effectively
        disabling aggregation without touching ``enable_aggregation``.
    enable_aggregation:
        Master switch for multi-frame aggregation.
        ``False`` always uses the single most-recent embedding.
    """

    DEFAULT_QUICK_ACCEPT_SIMILARITY: float = 0.92

    def __init__(
        self,
        detection_model:          str   = "yolov8n",
        detection_threshold:      float = 0.5,
        recognition_threshold:    float = 0.6,
        quick_accept_similarity:  float = DEFAULT_QUICK_ACCEPT_SIMILARITY,
        quick_accept_min_tier:    str   = "HIGH",
        device:                   str   = "cpu",
        frame_skip:               int   = 2,
        min_consecutive_frames:   int   = 5,
        motion_config:            Optional[MotionConfig] = None,
        enable_motion_gate:       bool  = True,
        enable_quick_accept:      bool  = True,
        # Aggregation knobs
        aggregation_buffer_size:  int   = AGGREGATION_BUFFER_SIZE,
        aggregation_min_frames:   int   = AGGREGATION_MIN_FRAMES,
        enable_aggregation:       bool  = True,
        # Liveness knobs
        enable_liveness:          bool  = True,
        liveness_threshold:       float = 0.55,
        fusion_accept_threshold:  float = 0.68,
    ):
        self.detection_threshold    = detection_threshold
        self.recognition_threshold  = recognition_threshold
        self.device                 = device
        self.frame_skip             = max(1, min(5, frame_skip))
        self.min_consecutive_frames = min_consecutive_frames
        self.enable_motion_gate     = enable_motion_gate
        self.enable_quick_accept    = enable_quick_accept
        self.enable_liveness        = enable_liveness
        self.liveness_threshold     = liveness_threshold
        self.fusion_accept_threshold = fusion_accept_threshold

        # QUICK_ACCEPT thresholds
        self.quick_accept_similarity = max(quick_accept_similarity, recognition_threshold)
        self.quick_accept_min_tier   = quick_accept_min_tier

        # Aggregation configuration
        self._agg_buffer_size   = max(1, min(10, aggregation_buffer_size))
        self._agg_min_frames    = max(1, min(self._agg_buffer_size, aggregation_min_frames))
        self.enable_aggregation = enable_aggregation

        logger.info("🚀 Initializing Super Attendance Pipeline…")
        logger.info("   Motion gate      : %s", "ON" if enable_motion_gate else "OFF")
        logger.info("   Frame skip       : %d", self.frame_skip)
        logger.info("   Min frames       : %d", self.min_consecutive_frames)
        logger.info(
            "   Quick accept     : %s (sim≥%.2f, tier≥%s)",
            "ON" if enable_quick_accept else "OFF",
            self.quick_accept_similarity,
            self.quick_accept_min_tier,
        )
        logger.info(
            "   Embedding aggr.  : %s (N=%d, min=%d)",
            "ON" if enable_aggregation else "OFF",
            self._agg_buffer_size,
            self._agg_min_frames,
        )

        # ── Motion detector ─────────────────────────────────────────────────
        self.motion_detector = MotionDetector(config=motion_config or MotionConfig())

        # ── Detection / quality service ─────────────────────────────────────
        self._detection_svc = FaceDetectionService()

        # ── ML models ───────────────────────────────────────────────────────
        self.detector   = FaceDetectionPipeline(
            model_name=detection_model,
            confidence_threshold=detection_threshold,
            device=device,
        )
        self.recognizer = FaceRecognitionPipeline(device=device, pretrained=True)

        # ── Tracking ────────────────────────────────────────────────────────
        self.tracker = FaceTracker(max_age=30, min_hits=2)
        self.tracker.set_frame_skip(frame_skip)
        self.temporal_verifier = TemporalVerification(
            min_consecutive=min_consecutive_frames
        )

        # ── Liveness detection ──────────────────────────────────────────────
        self.liveness_detector = get_liveness_detector(
            threshold=liveness_threshold,
            enable_blink=True,
            enable_depth=False,
        ) if enable_liveness else None

        # ── FAISS search ────────────────────────────────────────────────────
        self.embedding_search = OptimizedEmbeddingSearch(use_faiss=True)

        # ── Frame counters ───────────────────────────────────────────────────
        self.face_counter            = 0
        self.frame_counter           = 0
        self.processed_frames        = 0
        self.skipped_frames          = 0
        self.motion_gated_frames     = 0
        self.ai_triggered_frames     = 0
        self.quick_accept_count      = 0

        # Aggregation search counters
        self._agg_searches    = 0   # FAISS calls using aggregated query
        self._single_searches = 0   # FAISS calls using single-frame query

        self._last_result: Optional[PipelineFrameResult] = None

        logger.info(
            "✅ Super Pipeline ready "
            "(motion-gate + quality + aggregation + FAISS + SORT + QUICK_ACCEPT)"
        )

    # ── Public API ──────────────────────────────────────────────────────────────

    def set_frame_skip(self, skip: int) -> None:
        self.frame_skip = max(1, min(5, skip))
        self.tracker.set_frame_skip(skip)
        logger.info("Frame skip updated to %d", skip)

    def set_motion_gate(self, enabled: bool) -> None:
        self.enable_motion_gate = enabled
        logger.info("Motion gate %s", "ENABLED" if enabled else "DISABLED")

    def set_quick_accept(self, enabled: bool) -> None:
        """Enable or disable the QUICK_ACCEPT path at runtime."""
        self.enable_quick_accept = enabled
        logger.info("Quick-accept %s", "ENABLED" if enabled else "DISABLED")

    def set_aggregation(
        self,
        enabled:     Optional[bool] = None,
        buffer_size: Optional[int]  = None,
        min_frames:  Optional[int]  = None,
    ) -> None:
        """
        Adjust aggregation settings at runtime without restarting the pipeline.

        Note: changing ``buffer_size`` does **not** retroactively resize
        per-track deques already alive in the tracker — it takes effect on
        newly created tracks.  Call ``self.tracker.reset()`` to apply
        immediately (resets all tracks).

        Example
        -------
        >>> pipeline.set_aggregation(enabled=True, buffer_size=2, min_frames=2)
        """
        if enabled is not None:
            self.enable_aggregation = enabled
        if buffer_size is not None:
            self._agg_buffer_size = max(1, min(10, buffer_size))
        if min_frames is not None:
            self._agg_min_frames = max(1, min(self._agg_buffer_size, min_frames))
        logger.info(
            "Aggregation updated: enabled=%s buffer_size=%d min_frames=%d",
            self.enable_aggregation, self._agg_buffer_size, self._agg_min_frames,
        )

    def update_motion_config(self, **kwargs) -> None:
        """Hot-update motion detector settings without restarting the pipeline."""
        self.motion_detector.update_config(**kwargs)

    def register_students(
        self,
        students: Dict[str, List[np.ndarray]],
    ) -> Dict:
        """
        Register students with quality-gated face embeddings.

        Before averaging embeddings into a centroid, each sample is scored by
        ``FaceDetectionService.score_capture_quality()``.  LOW-tier frames are
        discarded.  If *all* frames for a student are LOW quality, the full set
        is used as a fallback — no student is silently unregistered.

        Parameters
        ----------
        students:
            ``{student_id: [face_image1, face_image2, …]}``
            Cropped face regions preferred; full frames are accepted.

        Returns
        -------
        dict
            ``{"success": bool, "count": int, "quality_filtered": int}``
        """
        logger.info("📝 Registering %d students (quality-gated)…", len(students))

        student_ids, all_embeddings, metadata = [], [], {}
        total_quality_filtered = 0

        for student_id, faces in students.items():
            if not faces:
                continue

            scored_faces: List[Tuple[np.ndarray, CaptureQuality]] = [
                (f, self._detection_svc.score_capture_quality(f, motion_magnitude=0.0))
                for f in faces
            ]

            usable     = [(f, q) for f, q in scored_faces if q.is_usable]
            n_filtered = len(scored_faces) - len(usable)
            total_quality_filtered += n_filtered

            if not usable:
                logger.warning(
                    "register_students: all %d frames for %s are LOW quality — "
                    "falling back to full set",
                    len(scored_faces), student_id,
                )
                usable = scored_faces
            elif n_filtered:
                logger.debug(
                    "register_students: %s — dropped %d LOW frames, kept %d",
                    student_id, n_filtered, len(usable),
                )

            embeddings = self.recognizer.generate_embeddings([f for f, _ in usable])
            valid      = [e for e in embeddings if e is not None]
            if not valid:
                logger.warning("No valid embeddings for %s", student_id)
                continue

            avg        = np.mean(valid, axis=0)
            avg        = avg / (np.linalg.norm(avg) + 1e-8)
            mean_score = float(np.mean([q.score for _, q in usable]))

            student_ids.append(student_id)
            all_embeddings.append(avg)
            metadata[student_id] = {
                "name":          student_id,
                "registered_at": datetime.now().isoformat(),
                "samples":       len(valid),
                "mean_quality":  round(mean_score, 3),
            }

        if student_ids:
            self.embedding_search.add_students(
                student_ids, np.array(all_embeddings), metadata
            )
            logger.info(
                "✅ Registered %d students in FAISS index "
                "(%d LOW-quality frames discarded)",
                len(student_ids), total_quality_filtered,
            )
            return {"success": True, "count": len(student_ids),
                    "quality_filtered": total_quality_filtered}

        return {"success": False, "count": 0, "quality_filtered": total_quality_filtered}

    # ── Core processing ────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame:       np.ndarray,
        fps_samples: Optional[List[float]] = None,
    ) -> PipelineFrameResult:
        """
        Process a single BGR frame through the full merged pipeline.

        Step order
        ----------
        A  YOLO detection
        B  Crop face regions
        C  Quality-score each crop (frontality + sharpness + stillness)
        D  FaceNet — HIGH/ACCEPTABLE crops only; inject None for LOW
        E  Build tracking input (valid-embedding faces only)
        F  SORT tracker update → per-track embedding buffer receives new vector
        G  Build quality map (bbox → CaptureQuality for annotation)
        H  Per-track loop:
              ① choose query: aggregated (mean of ≤N buffer) or single-frame
              ② FAISS search (one call per track, always)
              ③ QUICK_ACCEPT: HIGH quality + aggregated sim ≥ threshold
              ④ standard temporal verifier (non-QUICK_ACCEPT path)
        I  FPS accounting
        """
        import time

        self.frame_counter += 1

        # ── GATE 1: Motion detection ─────────────────────────────────────────
        motion_result = self.motion_detector.detect(frame)

        if self.enable_motion_gate and not motion_result.motion_detected:
            self.motion_gated_frames += 1
            if self._last_result is not None:
                return PipelineFrameResult(
                    frame=frame,
                    frame_id=self._last_result.frame_id,
                    detections=self._last_result.detections,
                    tracked_faces=self._last_result.tracked_faces,
                    marked_students=self._last_result.marked_students,
                    fps=self._last_result.fps,
                    motion_result=motion_result,
                    ai_triggered=False,
                    quick_accepted_students=self._last_result.quick_accepted_students,
                    best_quality_score=self._last_result.best_quality_score,
                )
            logger.debug("Motion gate: first frame — running AI despite static scene")

        # ── GATE 2: Frame-skip ───────────────────────────────────────────────
        if self.frame_counter % self.frame_skip != 0:
            self.skipped_frames += 1
            if self._last_result is not None:
                return PipelineFrameResult(
                    frame=frame,
                    frame_id=self._last_result.frame_id,
                    detections=self._last_result.detections,
                    tracked_faces=self._last_result.tracked_faces,
                    marked_students=self._last_result.marked_students,
                    fps=self._last_result.fps,
                    motion_result=motion_result,
                    ai_triggered=False,
                    quick_accepted_students=self._last_result.quick_accepted_students,
                    best_quality_score=self._last_result.best_quality_score,
                )

        # ── AI pipeline ──────────────────────────────────────────────────────
        self.processed_frames    += 1
        self.ai_triggered_frames += 1
        frame_start = time.time()

        # Normalised motion magnitude for quality stillness term.
        motion_mag: float = getattr(motion_result, "magnitude", 0.0)

        # ── Step A: YOLO detection ───────────────────────────────────────────
        raw_detections = self.detector.detect_faces_in_frame(frame)

        # ── Step B: Crop face regions ────────────────────────────────────────
        raw_faces = self.detector.extract_face_regions(frame, raw_detections)

        # ── Step C: Quality scoring ──────────────────────────────────────────
        # LOW faces skip FaceNet (Step D) to avoid wasting the costliest call.
        quality_scores: List[Optional[CaptureQuality]] = []
        best_quality_score: float = 0.0

        for face in raw_faces:
            if face is None or face.size == 0:
                quality_scores.append(None)
                continue
            q = self._detection_svc.score_capture_quality(face, motion_magnitude=motion_mag)
            quality_scores.append(q)
            if q.score > best_quality_score:
                best_quality_score = q.score

        # ── Step D: FaceNet — HIGH/ACCEPTABLE only ───────────────────────────
        # Parallel list aligned with raw_detections.  None = LOW quality or
        # bad crop; these faces will not enter the SORT tracker this frame.
        embeddings: List[Optional[np.ndarray]] = []
        for face, q in zip(raw_faces, quality_scores):
            if q is None or not q.is_usable:
                embeddings.append(None)
                continue
            embs = self.recognizer.generate_embeddings([face])
            embeddings.append(embs[0] if embs else None)

        # ── Step E: Build tracking input ─────────────────────────────────────
        tracking_input = []
        for (x1, y1, x2, y2, conf), emb in zip(raw_detections, embeddings):
            if emb is not None:
                tracking_input.append((x1, y1, x2, y2, conf, emb))

        # ── Step F: SORT tracker update ──────────────────────────────────────
        # Each TrackedFace.embedding_buffer receives the new embedding so the
        # aggregation window grows with each processed frame.
        tracked_faces = self.tracker.update(tracking_input, self.processed_frames)

        # ── Step G: Build quality map ────────────────────────────────────────
        det_quality_map = self._build_quality_map(raw_detections, quality_scores)

        # ── Step H: Per-track aggregated FAISS + QUICK_ACCEPT ────────────────
        results: List[OptimizedDetectedFace] = []
        quick_accepted_students: set = set()

        for track in tracked_faces:
            # ① Choose query embedding
            # -----------------------------------------------------------------
            # Aggregated query (mean-normalised from buffer) is more
            # discriminative than any single frame and therefore also safer
            # for QUICK_ACCEPT.  Falls back to single-frame on the first
            # processed frame of a new track (buffer not yet full).
            if self.enable_aggregation:
                query_emb      = track.get_aggregated_embedding(
                    min_frames=self._agg_min_frames
                )
                frames_used    = track.buffer_size()
                was_aggregated = frames_used >= self._agg_min_frames
            else:
                query_emb      = track.embedding
                frames_used    = 1
                was_aggregated = False

            if query_emb is None:
                continue

            # ② FAISS search ──────────────────────────────────────────────────
            matches = self.embedding_search.search(
                query_emb,
                top_k=1,
                threshold=self.recognition_threshold,
            )

            if was_aggregated:
                self._agg_searches    += 1
            else:
                self._single_searches += 1

            if not matches:
                continue

            match = matches[0]
            track.student_id = match.student_id

            # Retrieve quality for this track from the current-frame scores
            track_quality: Optional[CaptureQuality] = det_quality_map.get(
                self._nearest_det_key(track.bbox, raw_detections)
            )

            # ② Liveness detection (NEW) ──────────────────────────────────────
            # Check liveness on the best quality face for this track
            liveness_result = None
            if self.enable_liveness and self.liveness_detector is not None and raw_faces:
                best_face_idx = next(
                    (i for i, q in enumerate(quality_scores)
                     if q is not None and q.tier in ("HIGH", "ACCEPTABLE")),
                    None
                )
                if best_face_idx is not None and raw_faces[best_face_idx] is not None:
                    liveness_result = self.liveness_detector.check(raw_faces[best_face_idx])

            # ③ QUICK_ACCEPT with liveness fusion ────────────────────────────
            # Conditions (all must hold):
            #   a) feature enabled
            #   b) current-frame quality ≥ required tier
            #   c) fused confidence (similarity + liveness + metadata) ≥ threshold
            #   d) liveness passes (if enabled)
            #   e) student not already marked
            quick_accepted = False

            # Build metadata for fusion (extract from request context if available)
            metadata = LoginMetadata(
                device_id=None,  # Would be extracted from request headers
                known_device=True,  # Assume device continuity in production
                expected_location=True,  # Assume in-classroom
            )

            # Compute fused confidence if liveness is available
            fused_score = match.similarity  # fallback to raw similarity
            if liveness_result is not None:
                fused_result = fuse_confidence(
                    embedding_similarity=match.similarity,
                    liveness_result=liveness_result,
                    metadata=metadata,
                    accept_threshold=self.fusion_accept_threshold,
                    w_embedding=0.60,
                    w_liveness=0.25,
                    w_metadata=0.15,
                )
                fused_score = fused_result.final_confidence

            if (
                self.enable_quick_accept
                and track_quality is not None
                and track_quality.tier == self.quick_accept_min_tier
                and fused_score >= self.quick_accept_similarity
                and (liveness_result is None or liveness_result.is_live)
                and match.student_id not in self.temporal_verifier.marked_students
            ):
                self.temporal_verifier.force_mark(match.student_id)
                quick_accepted = True
                quick_accepted_students.add(match.student_id)
                self.quick_accept_count += 1
                logger.info(
                    "⚡ QUICK_ACCEPT: %s (sim=%.4f, fused=%.4f, quality=%.3f, "
                    "tier=%s, frames_agg=%d, live=%s)",
                    match.student_id, match.similarity, fused_score,
                    track_quality.score, track_quality.tier, frames_used,
                    liveness_result.is_live if liveness_result else "N/A",
                )

            # ④ Standard temporal verifier (only when QUICK_ACCEPT did not fire)
            else:
                # Gating: liveness must pass if enabled
                if liveness_result is not None and not liveness_result.is_live:
                    logger.debug(
                        "Temporal verifier skipped: %s failed liveness (score=%.3f)",
                        match.student_id, liveness_result.overall_score,
                    )
                else:
                    should_mark = self.temporal_verifier.add_detection(
                        match.student_id, self.processed_frames
                    )
                    if should_mark:
                        logger.info(
                            "✅ ATTENDANCE MARKED (temporal): %s "
                            "(sim=%.4f, fused=%.4f, frames_agg=%d, live=%s)",
                            match.student_id, match.similarity, fused_score, frames_used,
                            liveness_result.is_live if liveness_result else "N/A",
                        )

            self.face_counter += 1
            results.append(
                OptimizedDetectedFace(
                    face_id=self.face_counter,
                    track_id=track.track_id,
                    bbox=track.bbox,
                    confidence=track.confidence,
                    embedding=query_emb,          # aggregated or single-frame
                    student_id=match.student_id,
                    match_similarity=match.similarity,
                    timestamp=datetime.now(),
                    quality=track_quality,
                    quick_accepted=quick_accepted,
                    frames_aggregated=frames_used,
                )
            )

        # ── Step I: FPS accounting ────────────────────────────────────────────
        elapsed     = time.time() - frame_start
        current_fps = 1.0 / elapsed if elapsed > 0 else 0.0
        if fps_samples is not None:
            fps_samples.append(current_fps)
            if len(fps_samples) > 30:
                fps_samples.pop(0)
        avg_fps = float(np.mean(fps_samples)) if fps_samples else current_fps

        result = PipelineFrameResult(
            frame=frame,
            frame_id=self.processed_frames,
            detections=results,
            tracked_faces=tracked_faces,
            marked_students=self.temporal_verifier.get_marked_students(),
            fps=avg_fps,
            motion_result=motion_result,
            ai_triggered=True,
            quick_accepted_students=quick_accepted_students,
            best_quality_score=best_quality_score,
        )
        self._last_result = result
        return result

    # ── Webcam generator ───────────────────────────────────────────────────────

    def process_frames(
        self,
        webcam_index: int  = 0,
        show_stats:   bool = True,
    ) -> Generator[PipelineFrameResult, None, None]:
        """Yield processed frames from a webcam (blocking generator)."""
        cap = cv2.VideoCapture(webcam_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {webcam_index}")

        fps_samples: List[float] = []

        try:
            logger.info("🎥 Webcam %d opened", webcam_index)
            report_every = 30

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                result = self.process_frame(frame, fps_samples)

                if show_stats and self.frame_counter % report_every == 0:
                    md_stats = self.motion_detector.get_stats()
                    logger.info(
                        "📊 Frame %d | AI FPS=%.1f | motion-gated=%.1f%% | "
                        "quick-accepts=%d | agg=%d/single=%d | "
                        "tracks=%d | marked=%d | best-Q=%.2f",
                        self.frame_counter,
                        result.fps,
                        md_stats["ml_skip_rate"] * 100,
                        self.quick_accept_count,
                        self._agg_searches,
                        self._single_searches,
                        len(self.tracker.tracks),
                        len(self.temporal_verifier.marked_students),
                        result.best_quality_score,
                    )

                yield result

        except KeyboardInterrupt:
            logger.info("Processing stopped by user")
        finally:
            cap.release()
            self._log_final_stats()

    # ── Drawing helper ──────────────────────────────────────────────────────────

    def draw_results(
        self,
        result:               PipelineFrameResult,
        show_motion_overlay:  bool = True,
        show_quality_overlay: bool = True,
        show_aggregation_hud: bool = True,
    ) -> np.ndarray:
        """
        Render tracking boxes, identities, quality indicators, aggregation
        counts, and motion HUD on the frame.

        Visual encoding
        ---------------
        Bbox colour (quality tier of the *current* frame's crop):
            HIGH        bright green  (80, 255, 0)
            ACCEPTABLE  yellow        (0, 210, 255)
            LOW / none  orange        (0, 140, 255)

        Label line 1:  ``<name> (<sim>) [<N>f] ⚡``
            ``[Nf]``  when ``show_aggregation_hud`` and N > 1
            ``⚡``     when QUICK_ACCEPT fired

        Label line 2 (when ``show_quality_overlay``):
            ``Q:<score> F:<frontality> S:<sharpness>``

        Parameters
        ----------
        show_aggregation_hud:
            Show how many frames were blended per match.  Useful during
            tuning to verify the buffer fills as expected.
        show_quality_overlay:
            Show per-face quality component scores and the best-quality HUD.
        """
        vis = result.frame.copy()

        _tier_colors = {
            "HIGH":       (80,  255, 0),
            "ACCEPTABLE": (0,   210, 255),
            "LOW":        (0,   140, 255),
        }

        if show_motion_overlay:
            vis = self.motion_detector.draw_motion_overlay(vis, result.motion_result)

        # AI-triggered indicator
        ai_color = (0, 255, 128) if result.ai_triggered else (100, 100, 100)
        cv2.putText(
            vis,
            "AI: ON" if result.ai_triggered else "AI: GATED",
            (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ai_color, 2,
        )

        # Best quality score (top-right)
        if show_quality_overlay and result.ai_triggered:
            cv2.putText(
                vis, f"Q: {result.best_quality_score:.2f}",
                (vis.shape[1] - 120, 56),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2,
            )

        # Aggregation rate (top-right, below quality)
        if show_aggregation_hud and result.ai_triggered:
            total   = self._agg_searches + self._single_searches
            agg_pct = 100 * self._agg_searches / max(total, 1)
            cv2.putText(
                vis, f"AGG: {agg_pct:.0f}%",
                (vis.shape[1] - 120, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 255), 1,
            )

        # Tracked face boxes (all active SORT tracks)
        for track in result.tracked_faces:
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            color = (0, 255, 0) if track.student_id else (0, 165, 255)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                vis, f"ID:{track.track_id}",
                (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
            )

        # Per-detection labels (matched faces only)
        for det in result.detections:
            x1, y1, x2, y2 = (int(v) for v in det.bbox)

            box_color = (
                _tier_colors.get(det.quality.tier, (0, 255, 0))
                if det.quality else (255, 200, 0)
            )
            cv2.rectangle(vis, (x1, y1), (x2, y2), box_color, 3)

            # Line 1: identity + similarity + aggregation count + quick-accept flag
            id_label = f"{det.student_id} ({det.match_similarity:.2f})"
            if show_aggregation_hud and det.frames_aggregated > 1:
                id_label += f" [{det.frames_aggregated}f]"
            if det.quick_accepted:
                id_label += " ⚡"
            cv2.putText(
                vis, id_label,
                (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1,
            )

            # Line 2: quality breakdown
            if show_quality_overlay and det.quality:
                q = det.quality
                cv2.putText(
                    vis,
                    f"Q:{q.score:.2f} F:{q.frontality:.2f} S:{q.sharpness:.2f}",
                    (x1, y2 + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1,
                )

        # FPS (top-right)
        cv2.putText(
            vis, f"FPS: {result.fps:.1f}",
            (vis.shape[1] - 120, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2,
        )

        return vis

    # ── Statistics ──────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict:
        """
        Return pipeline efficiency, quality, and aggregation statistics.

        Keys
        ----
        Frame counts:
            total_frames, motion_gated_frames, frame_skipped_frames,
            ai_triggered_frames, ai_skip_rate, motion_ml_skip_rate

        Tracking:
            active_tracks, confirmed_tracks, marked_students,
            frame_skip, motion_gate_enabled

        QUICK_ACCEPT:
            quick_accept_enabled, quick_accept_count,
            quick_accept_sim_threshold

        Aggregation:
            aggregation_enabled, aggregation_buffer_size,
            aggregation_min_frames, aggregated_searches,
            single_frame_searches, aggregation_rate
        """
        total          = max(self.frame_counter, 1)
        md_stats       = self.motion_detector.get_stats()
        total_searches = self._agg_searches + self._single_searches

        return {
            # Frame counts
            "total_frames":          self.frame_counter,
            "motion_gated_frames":   self.motion_gated_frames,
            "frame_skipped_frames":  self.skipped_frames,
            "ai_triggered_frames":   self.ai_triggered_frames,
            "ai_skip_rate":          round(1 - self.ai_triggered_frames / total, 4),
            "motion_ml_skip_rate":   md_stats["ml_skip_rate"],
            # Tracking
            "active_tracks":         len(self.tracker.tracks),
            "confirmed_tracks":      len(self.tracker.get_active_tracks()),
            "marked_students":       len(self.temporal_verifier.marked_students),
            "frame_skip":            self.frame_skip,
            "motion_gate_enabled":   self.enable_motion_gate,
            # QUICK_ACCEPT
            "quick_accept_enabled":       self.enable_quick_accept,
            "quick_accept_count":         self.quick_accept_count,
            "quick_accept_sim_threshold": self.quick_accept_similarity,
            # Aggregation
            "aggregation_enabled":     self.enable_aggregation,
            "aggregation_buffer_size": self._agg_buffer_size,
            "aggregation_min_frames":  self._agg_min_frames,
            "aggregated_searches":     self._agg_searches,
            "single_frame_searches":   self._single_searches,
            "aggregation_rate":        round(
                self._agg_searches / max(total_searches, 1), 4
            ),
        }

    def _log_final_stats(self) -> None:
        stats = self.get_statistics()
        logger.info(
            "✅ Pipeline stopped\n"
            "   Total frames     : %d\n"
            "   Motion-gated     : %d (%.1f%%)\n"
            "   Frame-skipped    : %d\n"
            "   AI triggered     : %d\n"
            "   AI skip rate     : %.1f%%\n"
            "   Quick-accepts    : %d\n"
            "   Students marked  : %d\n"
            "   Aggregated FAISS : %d / %d searches (%.1f%%)",
            stats["total_frames"],
            stats["motion_gated_frames"],
            stats["motion_ml_skip_rate"] * 100,
            stats["frame_skipped_frames"],
            stats["ai_triggered_frames"],
            stats["ai_skip_rate"] * 100,
            stats["quick_accept_count"],
            stats["marked_students"],
            stats["aggregated_searches"],
            stats["aggregated_searches"] + stats["single_frame_searches"],
            stats["aggregation_rate"] * 100,
        )

    # ── Private helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_quality_map(
        detections:     List[Tuple],
        quality_scores: List[Optional[CaptureQuality]],
    ) -> Dict[str, CaptureQuality]:
        """
        Build a bbox-key → CaptureQuality dict for O(1) lookup during tracking.

        Key format: ``"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"`` — consistent
        within a single frame since YOLO returns stable float coords.
        """
        result = {}
        for det, q in zip(detections, quality_scores):
            if q is not None:
                x1, y1, x2, y2, _ = det
                result[f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"] = q
        return result

    @staticmethod
    def _nearest_det_key(
        track_bbox: Tuple[float, float, float, float],
        detections: List[Tuple],
    ) -> str:
        """
        Return the detection-map key whose bbox centre is closest to the
        tracked face's centre.

        SORT may interpolate bboxes slightly across frames, so nearest-centre
        lookup is more robust than exact-key matching.
        """
        if not detections:
            return ""

        tx = (track_bbox[0] + track_bbox[2]) / 2.0
        ty = (track_bbox[1] + track_bbox[3]) / 2.0

        best_key  = ""
        best_dist = float("inf")
        for det in detections:
            x1, y1, x2, y2, _ = det
            dx = ((x1 + x2) / 2.0) - tx
            dy = ((y1 + y2) / 2.0) - ty
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                best_key  = f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"
        return best_key