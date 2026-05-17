"""
Optimized Attendance Pipeline with Tracking, Temporal Verification,
Motion Detection Gatekeeper, Liveness Checks, and SELF_VERIFY Quick-Accept.

Integrates:
- Motion Detection Gatekeeper    — frame differencing, O(W×H) μs cost
- SORT tracking                  — O(1) identity maintenance
- Frame-skipping                 — configurable 2–3 frame intervals
- Efficient embedding search     — O(log n) via FAISS
- FrameAggregator                — multi-frame embedding averaging + decisions
- FusedConfidenceScorer          — risk-weighted acceptance gate
- Temporal verification          — fallback consecutive-frame counter
- Liveness detection             — per-crop texture/blink/depth checks;
                                   acts as both a hard gate and a score input
- SELF_VERIFY quick-accept       — single-frame bypass of aggregator when
                                   adaptive threshold + liveness pass

Performance optimizations:
- Motion gating:  skips YOLO + FaceNet entirely on static frames
  → typical classroom: 60–80 % of frames are static between arrivals
- Frame skipping:  8–12 FPS → 15–20 FPS with skip=2
- O(log n) FAISS search replaces O(n×m) brute-force scan
- Quick-accept:  SELF_VERIFY marking in 1 frame instead of 5+

Pipeline decision tree (per frame)
-----------------------------------
Frame arrives
  └─ Motion detector (μs)
       ├─ No motion  →  return cached result, skip AI entirely
       └─ Motion detected
            └─ Frame-skip check
                 ├─ Skip this frame  →  return cached result
                 └─ Process frame
                      ├─ YOLOv8 face detection
                      ├─ FaceNet embedding extraction
                      ├─ Liveness check per crop
                      │    ├─ Fail  →  drop face (not forwarded to tracker)
                      │    └─ Pass  →  build liveness_by_emb_id + live_det_emb_lr
                      ├─ SORT tracker update (liveness-gated input only)
                      ├─ Lost-track cleanup  →  aggregator.force_decision()
                      └─ Per-track decision
                           ├─ SELF_VERIFY scope + quick_accept_self_verify enabled
                           │    └─ ScopedEmbeddingSearch.search()
                           │         ├─ quick_accept=True  →  force_mark immediately ⚡
                           │         └─ quick_accept=False →  fall through to aggregator
                           └─ Aggregator path (all other tracks)
                                ├─ aggregator.add_frame()
                                ├─ fused_scorer.compute_risk_score() [if session_meta]
                                ├─ fused_scorer.score()
                                └─ mark attendance if accepted
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Generator
import logging
from datetime import datetime
from dataclasses import dataclass, field

from .detection import FaceDetectionPipeline
from .recognition import FaceRecognitionPipeline
from .sorting_tracker import FaceTracker, TemporalVerification, TrackedFace
from .frame_aggregator import FrameAggregator, AggregationVerdict
from .fused_confidence import FusedConfidenceScorer
from utils.efficient_embedding_search import OptimizedEmbeddingSearch
from utils.motion_detector import MotionDetector, MotionConfig, MotionResult

# ── Liveness ────────────────────────────────────────────────────────────────────
# Primary: new LivenessDetector (instantiated per-pipeline, stateless per-crop).
# Fallback: get_liveness_detector() from the existing module (stateful, per-track).
# Both are imported; get_liveness_detector is still called in on_track_lost for
# reset_track() to clean up per-track state in the legacy detector.
try:
    from .liveness import (
        LivenessDetector,
        LivenessResult,
        LoginMetadata,
        fuse_confidence,
        get_liveness_detector,
    )
    _LIVENESS_AVAILABLE = True
except ImportError:
    try:
        # Older module shape — only the factory function exists
        from .liveness import get_liveness_detector
        LivenessDetector = None   # type: ignore[assignment,misc]
        LivenessResult = None     # type: ignore[assignment,misc]
        LoginMetadata = None      # type: ignore[assignment,misc]
        fuse_confidence = None    # type: ignore[assignment,misc]
        _LIVENESS_AVAILABLE = False
    except ImportError:
        get_liveness_detector = None  # type: ignore[assignment]
        LivenessDetector = None       # type: ignore[assignment,misc]
        LivenessResult = None         # type: ignore[assignment,misc]
        LoginMetadata = None          # type: ignore[assignment,misc]
        fuse_confidence = None        # type: ignore[assignment,misc]
        _LIVENESS_AVAILABLE = False

# ── Quick-accept config ─────────────────────────────────────────────────────────
try:
    from attendance_backend.services.scoped_embedding_search import (
        QUICK_ACCEPT_SELF_VERIFY as _QA_DEFAULT,
    )
except ImportError:
    import os
    _QA_DEFAULT: bool = os.environ.get("QUICK_ACCEPT_SELF_VERIFY", "true").lower() == "true"

# ── Scope types ─────────────────────────────────────────────────────────────────
try:
    from attendance_backend.models.identity_context import IdentityScopeType
    _SCOPE_AVAILABLE = True
except ImportError:
    _SCOPE_AVAILABLE = False
    IdentityScopeType = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class OptimizedDetectedFace:
    """Enhanced detected face with tracking, liveness, and quick-accept info."""
    face_id: int
    track_id: int
    bbox: Tuple[float, float, float, float]
    confidence: float
    embedding: Optional[np.ndarray]
    student_id: Optional[str]
    match_similarity: Optional[float]
    timestamp: datetime
    liveness_score: float = 0.5   # per-face liveness score in [0, 1]
    quick_accepted: bool = False  # True when SELF_VERIFY fast path was used


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
        Students confirmed this frame (by aggregator, temporal verifier,
        or quick-accept).
    fps:
        Rolling-average frames-per-second of the AI sub-pipeline.
    motion_result:
        Raw output from the motion detector for this frame.
    ai_triggered:
        True if YOLO + FaceNet actually ran; False if gated out by motion
        detector or frame-skip logic.
    quick_accepted_students:
        Student IDs accepted via the SELF_VERIFY fast path this frame.
        Always a subset of ``marked_students``.
    """
    frame: np.ndarray
    frame_id: int
    detections: List[OptimizedDetectedFace]
    tracked_faces: List[TrackedFace]
    marked_students: dict
    fps: float
    motion_result: MotionResult
    ai_triggered: bool
    quick_accepted_students: frozenset = field(default_factory=frozenset)


# ── Pipeline ───────────────────────────────────────────────────────────────────

class OptimizedAttendancePipeline:
    """
    Production-grade attendance pipeline.

    Decision layers (outermost → innermost)
    ----------------------------------------
    1. Motion gate       — O(W×H) frame diff; skips AI entirely on static scenes.
    2. Frame skip        — processes every Nth motion-triggered frame.
    3. Liveness gate     — Laplacian-texture (+ blink/depth stubs); drops spoofed
                           crops before they reach the tracker.
    4. SORT tracker      — maintains identities across frames.
    5. Quick-accept      — for SELF_VERIFY sessions: single-frame accept when
                           ScopedEmbeddingSearch returns quick_accept=True.
    6. Aggregator path   — FrameAggregator averages embeddings across frames;
                           FusedConfidenceScorer applies risk weighting.
    7. Temporal verifier — fallback consecutive-frame gate (standard sessions).

    Parameters
    ----------
    detection_model:
        YOLOv8 model variant ('yolov8n', 'yolov8s', …).
    detection_threshold:
        YOLO confidence threshold (0–1).
    recognition_threshold:
        Cosine distance threshold for FaceNet match (0–1).
    device:
        'cpu' or 'cuda'.
    frame_skip:
        Process every Nth frame from the motion-triggered frames (1–5).
    min_consecutive_frames:
        Temporal verifier requirement before marking attendance.
    motion_config:
        Fine-grained motion detector settings.  Pass ``None`` for defaults.
    enable_motion_gate:
        Set False to disable motion gating entirely.
    enable_liveness:
        Set False to disable liveness checks.  When False all faces are
        treated as live, preserving original behaviour.
    quick_accept_self_verify:
        Instance-level override for ``QUICK_ACCEPT_SELF_VERIFY``.
        ``None`` reads the module-level / env-var value.
    session_scope:
        Optional ``ScopeTarget`` for the current session.  When
        ``scope_type == SELF_VERIFY`` the quick-accept path is active.
        Can also be set later via ``set_session_scope()``.
    """

    def __init__(
        self,
        detection_model: str = "yolov8n",
        detection_threshold: float = 0.5,
        recognition_threshold: float = 0.6,
        device: str = "cpu",
        frame_skip: int = 2,
        min_consecutive_frames: int = 5,
        motion_config: Optional[MotionConfig] = None,
        enable_motion_gate: bool = True,
        enable_liveness: bool = True,
        quick_accept_self_verify: Optional[bool] = None,
        session_scope=None,  # Optional[ScopeTarget]
    ):
        self.detection_threshold = detection_threshold
        self.recognition_threshold = recognition_threshold
        self.device = device
        self.frame_skip = max(1, min(5, frame_skip))
        self.min_consecutive_frames = min_consecutive_frames
        self.enable_motion_gate = enable_motion_gate
        self.enable_liveness = enable_liveness
        self.quick_accept_self_verify: bool = (
            _QA_DEFAULT if quick_accept_self_verify is None
            else quick_accept_self_verify
        )
        self.session_scope = session_scope

        logger.info("🚀 Initializing Super Attendance Pipeline…")
        logger.info("   Motion gate       : %s", "ON" if enable_motion_gate else "OFF")
        logger.info("   Frame skip        : %d", self.frame_skip)
        logger.info("   Min frames        : %d", self.min_consecutive_frames)
        logger.info("   Liveness checks   : %s", "ON" if self.enable_liveness else "OFF")
        logger.info("   Quick-accept SELF : %s", "ON" if self.quick_accept_self_verify else "OFF")

        # ── Motion detector ─────────────────────────────────────────────────
        self.motion_detector = MotionDetector(config=motion_config or MotionConfig())

        # ── ML models ────────────────────────────────────────────────────────
        self.detector = FaceDetectionPipeline(
            model_name=detection_model,
            confidence_threshold=detection_threshold,
            device=device,
        )
        self.recognizer = FaceRecognitionPipeline(device=device, pretrained=True)

        # ── Liveness ─────────────────────────────────────────────────────────
        # self.liveness_detector  — new LivenessDetector (stateless per-crop).
        #   Provides both the hard gate (live_mask) and the per-crop score that
        #   feeds the aggregator.  Takes priority when available.
        # self._legacy_liveness   — get_liveness_detector() result.
        #   Used in on_track_lost for reset_track() (stateful per-track cleanup)
        #   and as a score-only fallback when LivenessDetector is not present.
        if enable_liveness and _LIVENESS_AVAILABLE and LivenessDetector is not None:
            self.liveness_detector = LivenessDetector(
                texture_threshold=80.0,
                enable_blink=True,
                enable_depth=False,
            )
        else:
            self.liveness_detector = None

        self._legacy_liveness = (
            get_liveness_detector() if get_liveness_detector is not None else None
        )

        # ── Multi-frame decision helpers ─────────────────────────────────────
        self.aggregator = FrameAggregator()
        self.fused_scorer = FusedConfidenceScorer()

        # ── Tracking ──────────────────────────────────────────────────────────
        self.tracker = FaceTracker(max_age=30, min_hits=2)
        self.tracker.set_frame_skip(frame_skip)
        self.temporal_verifier = TemporalVerification(
            min_consecutive=min_consecutive_frames
        )

        # ── FAISS search ──────────────────────────────────────────────────────
        self.embedding_search = OptimizedEmbeddingSearch(use_faiss=True)

        # ── Counters ──────────────────────────────────────────────────────────
        self.face_counter = 0
        self.frame_counter = 0
        self.processed_frames = 0
        self.skipped_frames = 0
        self.motion_gated_frames = 0
        self.ai_triggered_frames = 0
        self.liveness_rejected_faces = 0
        self.quick_accepted_total = 0

        # Track IDs seen in the previous processed frame (for lost-track detection)
        self._previous_track_ids: set = set()

        # Cache last result for motion-gated / skipped frames
        self._last_result: Optional[PipelineFrameResult] = None

        logger.info(
            "✅ Super Pipeline ready "
            "(motion-gated YOLO + liveness + FAISS + SORT + aggregator + quick-accept)"
        )

    # ── Public API ──────────────────────────────────────────────────────────────

    def set_frame_skip(self, skip: int) -> None:
        """Adjust frame-skip at runtime."""
        self.frame_skip = max(1, min(5, skip))
        self.tracker.set_frame_skip(skip)
        logger.info("Frame skip updated to %d", skip)

    def set_motion_gate(self, enabled: bool) -> None:
        """Enable or disable the motion gatekeeper at runtime."""
        self.enable_motion_gate = enabled
        logger.info("Motion gate %s", "ENABLED" if enabled else "DISABLED")

    def set_quick_accept(self, enabled: bool) -> None:
        """Toggle the SELF_VERIFY quick-accept path at runtime."""
        self.quick_accept_self_verify = enabled
        logger.info("Quick-accept SELF_VERIFY %s", "ENABLED" if enabled else "DISABLED")

    def set_session_scope(self, scope) -> None:
        """
        Set or update the session scope at runtime.

        When ``scope.scope_type == IdentityScopeType.SELF_VERIFY`` the
        quick-accept path becomes active (subject to
        ``quick_accept_self_verify``).
        """
        self.session_scope = scope
        scope_label = getattr(scope, "scope_type", "unknown") if scope else "None"
        logger.info("Session scope updated to: %s", scope_label)

    def update_motion_config(self, **kwargs) -> None:
        """
        Hot-update motion detector settings without restarting the pipeline.

        Example
        -------
        >>> pipeline.update_motion_config(diff_threshold=30, cooldown_frames=12)
        """
        self.motion_detector.update_config(**kwargs)

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _recognize_embedding_match(
        self,
        embedding: np.ndarray,
    ) -> Optional[Tuple[str, float]]:
        """Return the top FAISS match as ``(student_id, similarity)`` or None."""
        matches = self.embedding_search.search(
            embedding,
            top_k=1,
            threshold=self.recognition_threshold,
        )
        if not matches:
            return None
        match = matches[0]
        student_id = getattr(match, "student_id", None)
        similarity = getattr(match, "similarity", None)
        if not student_id or similarity is None:
            return None
        return student_id, float(similarity)

    def _is_self_verify_scope(self) -> bool:
        """Return True when the active session is a SELF_VERIFY scope."""
        if not _SCOPE_AVAILABLE or self.session_scope is None:
            return False
        scope_type = getattr(self.session_scope, "scope_type", None)
        if IdentityScopeType is None:
            return False
        return scope_type == IdentityScopeType.SELF_VERIFY

    def _liveness_score_for_track(
        self,
        track_embedding: np.ndarray,
        live_det_emb_lr: list,
    ) -> Tuple[float, Optional[object]]:
        """
        Find the liveness result whose detection embedding best aligns with
        ``track_embedding`` and return ``(score, LivenessResult | None)``.

        Alignment is measured by cosine similarity between the SORT-tracked
        embedding and each detection embedding that passed the liveness gate.
        Falls back to ``(0.5, None)`` when ``live_det_emb_lr`` is empty.
        """
        best_score = 0.5
        best_lr = None
        best_sim = -1.0
        for _x1, _y1, _x2, _y2, _conf, det_emb, lr in live_det_emb_lr:
            try:
                norm_t = np.linalg.norm(track_embedding)
                norm_d = np.linalg.norm(det_emb)
                s = float(
                    np.dot(track_embedding, det_emb) / (norm_t * norm_d + 1e-10)
                )
            except Exception:
                s = 0.0
            if s > best_sim:
                best_sim = s
                best_lr = lr
                best_score = (
                    float(lr.overall_score) if lr is not None
                    else 0.5
                )
        return best_score, best_lr

    # ── Track-lost handler ──────────────────────────────────────────────────────

    def on_track_lost(
        self,
        track_id: int,
        *,
        session_meta: Optional[Dict] = None,
    ) -> Optional[Tuple[str, float]]:
        """
        Force a final attendance decision for a lost track and clean up its
        state in the aggregator and liveness detector.

        Called automatically by ``process_frame`` when a SORT track
        disappears.  Can also be called manually when the session ends to
        flush any tracks still held by the aggregator.

        Returns
        -------
        ``(student_id, confidence)`` if the forced decision accepted the track,
        ``None`` otherwise.
        """
        result: AggregationVerdict = self.aggregator.force_decision(
            track_id,
            averaged_recognizer=self._recognize_embedding_match,
        )

        if result.accepted and result.student_id:
            logger.info(
                "Track %d lost — forced accept: %s (conf=%.3f)",
                track_id,
                result.student_id,
                result.confidence,
            )
            self.temporal_verifier.marked_students.add(result.student_id)

        self.aggregator.drop_track(track_id)

        # Clean up per-track state in the legacy liveness detector (if present)
        if self._legacy_liveness is not None:
            self._legacy_liveness.reset_track(track_id)

        if result.accepted and result.student_id:
            return result.student_id, result.confidence
        return None

    # ── Student registration ────────────────────────────────────────────────────

    def register_students(
        self,
        students: Dict[str, List[np.ndarray]],
    ) -> Dict:
        """
        Register students with face embeddings.

        Parameters
        ----------
        students:
            ``{student_id: [face_image1, face_image2, …]}``
            Each face image is a BGR or RGB numpy array.

        Returns
        -------
        dict
            ``{"success": bool, "count": int}``
        """
        logger.info("📝 Registering %d students…", len(students))

        student_ids, all_embeddings, metadata = [], [], {}

        for student_id, faces in students.items():
            if not faces:
                continue

            embeddings = self.recognizer.generate_embeddings(faces)
            valid = [e for e in embeddings if e is not None]
            if not valid:
                logger.warning("No valid embeddings for %s", student_id)
                continue

            avg = np.mean(valid, axis=0)
            avg = avg / (np.linalg.norm(avg) + 1e-8)

            student_ids.append(student_id)
            all_embeddings.append(avg)
            metadata[student_id] = {
                "name": student_id,
                "registered_at": datetime.now().isoformat(),
                "samples": len(valid),
            }

        if student_ids:
            self.embedding_search.add_students(
                student_ids, np.array(all_embeddings), metadata
            )
            logger.info("✅ Registered %d students in FAISS index", len(student_ids))
            return {"success": True, "count": len(student_ids)}

        return {"success": False, "count": 0}

    # ── Core processing ────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame: np.ndarray,
        fps_samples: Optional[List[float]] = None,
        session_meta: Optional[Dict] = None,
        login_metadata=None,  # Optional[LoginMetadata] — for quick-accept path
    ) -> PipelineFrameResult:
        """
        Process a single BGR frame through the full Super Pipeline.

        Parameters
        ----------
        frame:
            BGR image from the camera (any resolution).
        fps_samples:
            Optional rolling list; this method appends the per-frame AI time
            so callers can compute a running FPS average.
        session_meta:
            Optional risk context for ``FusedConfidenceScorer``.
            Recognised keys: ``device_known``, ``ip_anomaly``,
            ``time_anomaly``, ``attempt_pressure``.
        login_metadata:
            Optional ``LoginMetadata`` forwarded to ``ScopedEmbeddingSearch``
            when evaluating the SELF_VERIFY quick-accept path.

        Returns
        -------
        PipelineFrameResult
        """
        import time

        self.frame_counter += 1

        # ── GATE 1: Motion detection ────────────────────────────────────────
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
                )
            logger.debug("Motion gate: first frame, running AI despite static scene")

        # ── GATE 2: Frame-skip ──────────────────────────────────────────────
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
                )

        # ── AI pipeline ─────────────────────────────────────────────────────
        self.processed_frames += 1
        self.ai_triggered_frames += 1
        frame_start = time.time()

        # Step A: YOLOv8 detection
        detections = self.detector.detect_faces_in_frame(frame)

        # Step B: FaceNet embeddings
        faces = self.detector.extract_face_regions(frame, detections)
        embeddings = self.recognizer.generate_embeddings(faces) if faces else []

        # Step C: Liveness check per face crop
        # ──────────────────────────────────────
        # One check per crop; result feeds three downstream consumers:
        #
        #   live_mask          — True/False gate; only live faces enter tracker.
        #   liveness_by_emb_id — float score keyed by id(emb); consumed by the
        #                        aggregator path (matches existing behaviour).
        #   live_det_emb_lr    — [(bbox, emb, LivenessResult)] for quick-accept
        #                        liveness lookup and ScopedEmbeddingSearch.
        #
        # When liveness is disabled: all faces are marked live, score = 0.5.
        liveness_by_emb_id: Dict[int, float] = {}
        live_det_emb_lr: List = []   # (x1,y1,x2,y2,conf, emb, lr)
        live_mask: List[bool] = []

        for (x1, y1, x2, y2, conf), face, emb in zip(detections, faces, embeddings):
            if emb is None:
                live_mask.append(False)
                continue

            if self.enable_liveness and self.liveness_detector is not None:
                # Primary: new LivenessDetector — provides hard gate + score
                lr = self.liveness_detector.check(face)
                score = float(lr.overall_score)
                is_live = lr.is_live
            elif self.enable_liveness and self._legacy_liveness is not None:
                # Fallback: legacy detector — score only, no hard gate
                lr = self._legacy_liveness.check(face)
                score = float(getattr(lr, "score", 0.5))
                is_live = True
            else:
                lr = None
                score = 0.5
                is_live = True

            liveness_by_emb_id[id(emb)] = score

            if not is_live:
                self.liveness_rejected_faces += 1
                logger.debug(
                    "Face rejected by liveness (score=%.3f): %s",
                    score,
                    getattr(lr, "reason", ""),
                )
                live_mask.append(False)
            else:
                live_mask.append(True)
                live_det_emb_lr.append((x1, y1, x2, y2, conf, emb, lr))

        # Step D: Tracker input — liveness-approved faces only
        tracking_input = [
            (x1, y1, x2, y2, conf, emb)
            for (x1, y1, x2, y2, conf), emb, is_live
            in zip(detections, embeddings, live_mask)
            if emb is not None and is_live
        ]

        # Step E: SORT tracker update + lost-track detection
        tracked_faces = self.tracker.update(tracking_input, self.processed_frames)
        current_track_ids = {t.track_id for t in tracked_faces}
        lost_track_ids = self._previous_track_ids - current_track_ids

        # Step F: Per-track attendance decisions
        results: List[OptimizedDetectedFace] = []
        quick_accepted_this_frame: set = set()
        is_self_verify = self._is_self_verify_scope()

        for track in tracked_faces:
            if track.embedding is None:
                continue

            liveness_score, best_lr = self._liveness_score_for_track(
                track.embedding, live_det_emb_lr
            )

            # ── F1. SELF_VERIFY quick-accept path ─────────────────────────
            if (
                is_self_verify
                and self.quick_accept_self_verify
                and self.session_scope is not None
                and hasattr(self.session_scope, "student_ids")
            ):
                try:
                    from attendance_backend.services.scoped_embedding_search import (
                        ScopedEmbeddingSearch,
                    )
                except ImportError:
                    from services.scoped_embedding_search import ScopedEmbeddingSearch

                # TODO: inject a shared ScopedEmbeddingSearch instance via DI
                # so the per-user adaptive threshold history persists across frames.
                scoped_searcher = ScopedEmbeddingSearch(
                    firebase_service=None,
                    quick_accept_enabled=self.quick_accept_self_verify,
                )
                scoped_result = scoped_searcher.search(
                    query_embedding=track.embedding,
                    scope=self.session_scope,
                    liveness_result=best_lr,
                    login_metadata=login_metadata,
                )

                if scoped_result.matched and scoped_result.quick_accept:
                    student_id = scoped_result.student_id
                    track.student_id = student_id

                    # Mark immediately — bypass aggregator and temporal verifier
                    self.temporal_verifier.force_mark(student_id)
                    quick_accepted_this_frame.add(student_id)
                    self.quick_accepted_total += 1

                    logger.info(
                        "⚡ QUICK-ACCEPT SELF_VERIFY: %s (fused_conf=%.4f)",
                        student_id,
                        scoped_result.confidence,
                    )

                    self.face_counter += 1
                    results.append(OptimizedDetectedFace(
                        face_id=self.face_counter,
                        track_id=track.track_id,
                        bbox=track.bbox,
                        confidence=track.confidence,
                        embedding=track.embedding,
                        student_id=student_id,
                        match_similarity=scoped_result.confidence,
                        timestamp=datetime.now(),
                        liveness_score=liveness_score,
                        quick_accepted=True,
                    ))
                    continue  # Skip aggregator path for this track

                # quick_accept=False → fall through to aggregator below

            # ── F2. Aggregator path (all non-quick-accepted tracks) ───────
            raw_match = self._recognize_embedding_match(track.embedding)

            agg_result: AggregationVerdict = self.aggregator.add_frame(
                track_id=track.track_id,
                embedding=track.embedding,
                single_frame_match=raw_match,
                liveness_score=liveness_score,
                averaged_recognizer=self._recognize_embedding_match,
            )

            if not agg_result.accepted or not agg_result.student_id:
                continue

            # Risk scoring from session_meta
            risk_score = 0.0
            if session_meta:
                risk_score = self.fused_scorer.compute_risk_score(
                    device_known=bool(session_meta.get("device_known", True)),
                    ip_anomaly=float(session_meta.get("ip_anomaly", 0.0) or 0.0),
                    time_anomaly=float(session_meta.get("time_anomaly", 0.0) or 0.0),
                    attempt_pressure=float(
                        session_meta.get("attempt_pressure", 0.0) or 0.0
                    ),
                )

            fused = self.fused_scorer.score(
                similarity=agg_result.confidence,
                liveness=liveness_score,
                risk_score=risk_score,
            )

            if not fused.accepted:
                logger.info(
                    "Aggregator accepted but fused rejected: "
                    "track=%d student=%s reason=%s",
                    track.track_id,
                    agg_result.student_id,
                    fused.reject_reason,
                )
                continue

            track.student_id = agg_result.student_id
            self.temporal_verifier.marked_students.add(agg_result.student_id)
            self.temporal_verifier.add_detection(
                agg_result.student_id, self.processed_frames
            )

            self.face_counter += 1
            results.append(OptimizedDetectedFace(
                face_id=self.face_counter,
                track_id=track.track_id,
                bbox=track.bbox,
                confidence=track.confidence,
                embedding=track.embedding,
                student_id=agg_result.student_id,
                match_similarity=agg_result.confidence,
                timestamp=datetime.now(),
                liveness_score=liveness_score,
                quick_accepted=False,
            ))
            logger.info(
                "✅ ATTENDANCE MARKED: %s (agg=%.4f fused=%.4f live=%.4f)",
                agg_result.student_id,
                agg_result.confidence,
                fused.fused,
                liveness_score,
            )

        # Step G: Handle lost tracks
        for lost_id in lost_track_ids:
            self.on_track_lost(lost_id, session_meta=session_meta)

        # Periodic aggregator stale-track eviction (every 30 total frames)
        if self.frame_counter % 30 == 0:
            self.aggregator.evict_stale_tracks(max_age_frames=60)

        self._previous_track_ids = current_track_ids

        # Step H: FPS accounting
        elapsed = time.time() - frame_start
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
            quick_accepted_students=frozenset(quick_accepted_this_frame),
        )
        self._last_result = result
        return result

    # ── Webcam generator ────────────────────────────────────────────────────────

    def process_frames(
        self,
        webcam_index: int = 0,
        show_stats: bool = True,
    ) -> Generator[PipelineFrameResult, None, None]:
        """
        Yield processed frames from a webcam (blocking generator).

        Each yielded ``PipelineFrameResult`` carries whether AI actually ran
        (``ai_triggered``) and which students were quick-accepted this frame
        (``quick_accepted_students``).
        """
        cap = cv2.VideoCapture(webcam_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {webcam_index}")

        fps_samples: List[float] = []
        report_every = 30

        try:
            logger.info("🎥 Webcam %d opened", webcam_index)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                result = self.process_frame(frame, fps_samples)

                if show_stats and self.frame_counter % report_every == 0:
                    md_stats = self.motion_detector.get_stats()
                    logger.info(
                        "📊 Frame %d | AI FPS=%.1f | motion-gated=%.1f%% | "
                        "tracks=%d | marked=%d | quick-accepted=%d",
                        self.frame_counter,
                        result.fps,
                        md_stats["ml_skip_rate"] * 100,
                        len(self.tracker.tracks),
                        len(self.temporal_verifier.marked_students),
                        self.quick_accepted_total,
                    )

                yield result

        except KeyboardInterrupt:
            logger.info("Processing stopped by user")
        finally:
            cap.release()
            self._log_final_stats()

    # ── Drawing helper ───────────────────────────────────────────────────────────

    def draw_results(
        self,
        result: PipelineFrameResult,
        show_motion_overlay: bool = True,
    ) -> np.ndarray:
        """
        Render tracking boxes, identities, liveness score, quick-accept
        indicator, and motion HUD on the frame.

        Parameters
        ----------
        result:
            Output from ``process_frame``.
        show_motion_overlay:
            If True, draw motion regions and the MOTION / STATIC / COOLDOWN
            status bar.

        Returns
        -------
        np.ndarray
            Annotated BGR copy of the frame.
        """
        vis = result.frame.copy()

        if show_motion_overlay:
            vis = self.motion_detector.draw_motion_overlay(vis, result.motion_result)

        # AI-triggered indicator
        ai_color = (0, 255, 128) if result.ai_triggered else (100, 100, 100)
        cv2.putText(
            vis,
            "AI: ON" if result.ai_triggered else "AI: GATED",
            (10, 48),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, ai_color, 2,
        )

        # Tracked face boxes
        for track in result.tracked_faces:
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            color = (0, 255, 0) if track.student_id else (0, 165, 255)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                vis, f"ID:{track.track_id}",
                (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
            )

        # Matched student labels — include liveness score and quick-accept tag
        for det in result.detections:
            x1, y1, x2, y2 = (int(v) for v in det.bbox)
            qa_tag = " ⚡QA" if det.quick_accepted else ""
            label = (
                f"{det.student_id} ({det.match_similarity:.2f}) "
                f"L:{det.liveness_score:.2f}{qa_tag}"
            )
            label_color = (0, 215, 255) if det.quick_accepted else (0, 255, 0)
            cv2.putText(
                vis, label,
                (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, label_color, 1,
            )

        # FPS counter
        cv2.putText(
            vis, f"FPS: {result.fps:.1f}",
            (vis.shape[1] - 120, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2,
        )

        return vis

    # ── Statistics ───────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict:
        """Return pipeline efficiency and attendance statistics."""
        total = max(self.frame_counter, 1)
        md_stats = self.motion_detector.get_stats()
        return {
            "total_frames": self.frame_counter,
            "motion_gated_frames": self.motion_gated_frames,
            "frame_skipped_frames": self.skipped_frames,
            "ai_triggered_frames": self.ai_triggered_frames,
            "ai_skip_rate": round(1 - self.ai_triggered_frames / total, 4),
            "motion_ml_skip_rate": md_stats["ml_skip_rate"],
            "active_tracks": len(self.tracker.tracks),
            "confirmed_tracks": len(self.tracker.get_active_tracks()),
            "marked_students": len(self.temporal_verifier.marked_students),
            "liveness_rejected_faces": self.liveness_rejected_faces,
            "quick_accepted_total": self.quick_accepted_total,
            "frame_skip": self.frame_skip,
            "motion_gate_enabled": self.enable_motion_gate,
            "liveness_enabled": self.enable_liveness,
            "quick_accept_self_verify": self.quick_accept_self_verify,
        }

    def _log_final_stats(self) -> None:
        stats = self.get_statistics()
        logger.info(
            "✅ Pipeline stopped\n"
            "   Total frames          : %d\n"
            "   Motion-gated          : %d (%.1f%%)\n"
            "   Frame-skipped         : %d\n"
            "   AI triggered          : %d\n"
            "   AI skip rate          : %.1f%%\n"
            "   Liveness rejected     : %d\n"
            "   Quick-accepted        : %d\n"
            "   Students marked       : %d",
            stats["total_frames"],
            stats["motion_gated_frames"],
            stats["motion_ml_skip_rate"] * 100,
            stats["frame_skipped_frames"],
            stats["ai_triggered_frames"],
            stats["ai_skip_rate"] * 100,
            stats["liveness_rejected_faces"],
            stats["quick_accepted_total"],
            stats["marked_students"],
        )