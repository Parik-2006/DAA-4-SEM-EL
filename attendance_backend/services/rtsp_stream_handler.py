"""
RTSP stream handler for real-time processing of camera feeds.

Supports multiple concurrent RTSP streams.
Integrates with the Super Attendance Pipeline (motion-gated YOLO + FaceNet).

Changes (2026-04)
-----------------
- ``start()`` now spawns a background thread that auto-loads registered
  students for the configured classroom directly from Firebase into the
  pipeline's FAISS index — bypassing generate_embeddings() because Firebase
  already stores precomputed float32 vectors.
- ``_process_frame`` tracks ``_is_ai_active`` with a 3-second cooldown so the
  teacher dashboard doesn't flicker on a per-frame basis.
- ``get_metrics`` exposes ``is_ai_active`` and ``students_loaded`` so the
  frontend can show "Live Monitoring" vs "System Idle" and know whether the
  student index is ready.
- ``StreamManager`` forwards ``classroom_id`` to the handler.
"""

import logging
import threading
import time
import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from queue import Queue, Empty

from services.optimized_attendance_pipeline import (
    OptimizedAttendancePipeline,
    PipelineFrameResult,
)
from utils.motion_detector import MotionConfig
from services.firebase_service import get_firebase_service, FirebaseService

logger = logging.getLogger(__name__)

# How long (seconds) is_ai_active stays True after the last AI trigger.
# Prevents the teacher dashboard from flickering between frames.
_AI_ACTIVE_COOLDOWN_SECONDS = 3.0


# ── Stream Metrics ─────────────────────────────────────────────────────────────

@dataclass
class StreamMetrics:
    """Live metrics for one RTSP stream."""
    stream_id: str
    start_time: datetime
    frames_read: int = 0
    frames_processed: int = 0          # AI actually ran
    frames_motion_gated: int = 0       # skipped by motion detector
    frames_frame_skipped: int = 0      # skipped by frame-skip logic
    last_frame_time: Optional[datetime] = None
    current_fps: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    total_detections: int = 0
    active_tracks: int = 0
    status: str = "idle"               # idle | initializing | running | paused | stopped | error


# ── RTSPStreamHandler ──────────────────────────────────────────────────────────

class RTSPStreamHandler:
    """
    Handler for a single RTSP stream.

    Runs in its own daemon thread.  The Super Pipeline is used to process
    each frame; the motion gatekeeper ensures YOLO + FaceNet are only called
    when movement is detected, slashing CPU usage between arrivals.

    Student auto-loading
    --------------------
    When ``start()`` is called, a separate daemon thread immediately fetches
    all students for ``classroom_id`` from Firebase and injects their stored
    embeddings straight into the pipeline's FAISS index.  This means:

    * The API returns instantly — ``start()`` never blocks on Firebase.
    * The stream begins processing frames right away.
    * The FAISS index becomes ready within ~1–2 s for typical class sizes.
    * ``get_metrics()["students_loaded"]`` flips to True once indexing is done.

    AI-active tracking
    ------------------
    ``is_ai_active`` is True when the AI models ran within the last
    ``_AI_ACTIVE_COOLDOWN_SECONDS`` seconds.  The cooldown prevents the
    teacher dashboard from flickering: once motion stops, the indicator
    stays green for 3 s before switching to "System Idle".
    """

    def __init__(
        self,
        stream_id: str,
        rtsp_url: str,
        frame_skip: int = 2,
        min_consecutive_frames: int = 5,
        confidence_threshold: float = 0.6,
        device: str = "cpu",
        motion_config: Optional[MotionConfig] = None,
        enable_motion_gate: bool = True,
        reconnect_delay: float = 5.0,
        classroom_id: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        stream_id:
            Unique identifier (shown in logs and metrics).
        rtsp_url:
            Full RTSP URL, e.g. ``rtsp://192.168.1.10:554/live``.
        frame_skip:
            After motion gating, still skip every Nth frame to reduce load.
        min_consecutive_frames:
            Temporal verifier threshold before marking attendance.
        confidence_threshold:
            FaceNet match threshold.
        device:
            ``'cpu'`` or ``'cuda'``.
        motion_config:
            Fine-grained motion detector settings (``None`` → defaults).
        enable_motion_gate:
            Set ``False`` to disable gating (useful for testing).
        reconnect_delay:
            Seconds to wait before reconnecting after a stream drop.
        classroom_id:
            Optional classroom identifier.  When set, only students whose
            ``metadata.classroom_id`` matches are loaded into the FAISS index.
            Pass ``None`` to load *all* registered students.
        """
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay
        self.classroom_id = classroom_id

        # ── Super Pipeline ──────────────────────────────────────────────────
        self.pipeline = OptimizedAttendancePipeline(
            detection_threshold=confidence_threshold,
            recognition_threshold=confidence_threshold,
            device=device,
            frame_skip=frame_skip,
            min_consecutive_frames=min_consecutive_frames,
            motion_config=motion_config,
            enable_motion_gate=enable_motion_gate,
        )

        # ── Stream state ────────────────────────────────────────────────────
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.is_paused: bool = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # ── Student loading state ───────────────────────────────────────────
        self._students_loaded: bool = False
        self._students_loaded_count: int = 0
        self._student_load_error: Optional[str] = None

        # ── AI-active tracking (with cooldown) ──────────────────────────────
        # Timestamp of the last frame where result.ai_triggered was True.
        # is_ai_active = (now - _last_ai_trigger_time) < _AI_ACTIVE_COOLDOWN_SECONDS
        self._last_ai_trigger_time: Optional[datetime] = None
        self._is_ai_active: bool = False

        # ── FPS rolling window ──────────────────────────────────────────────
        self._fps_samples: List[float] = []

        # ── Metrics ─────────────────────────────────────────────────────────
        self.metrics = StreamMetrics(
            stream_id=stream_id, start_time=datetime.now()
        )

        # ── Callbacks (optional) ────────────────────────────────────────────
        self.on_detection: Optional[Callable[[str, PipelineFrameResult], None]] = None
        self.on_attendance: Optional[Callable[[str, str], None]] = None
        self.on_error: Optional[Callable[[str, str], None]] = None

        # ── Firebase ────────────────────────────────────────────────────────
        self.firebase = get_firebase_service()

        logger.info(
            "RTSPStreamHandler created: %s → %s (classroom=%s)",
            stream_id, rtsp_url, classroom_id or "ALL",
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Open the RTSP stream and start the processing thread.

        Also immediately launches a *separate* background thread to fetch
        student embeddings from Firebase.  The main processing thread is
        not blocked — frames are processed even while the FAISS index is
        being populated.

        Returns
        -------
        bool
            True if the processing thread was launched successfully.
        """
        if self.is_running:
            logger.warning("Stream %s already running", self.stream_id)
            return False

        try:
            logger.info("Starting stream: %s", self.stream_id)
            self.metrics.status = "initializing"

            self.cap = cv2.VideoCapture(self.rtsp_url)
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open: {self.rtsp_url}")

            # Reduce internal OpenCV buffer so we always get the latest frame
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self._stop_event.clear()
            self.is_running = True

            # ── Background thread: load students into FAISS (non-blocking) ──
            loader = threading.Thread(
                target=self._load_students_from_firebase_bg,
                daemon=True,
                name=f"student-loader-{self.stream_id}",
            )
            loader.start()

            # ── Main processing thread ──────────────────────────────────────
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name=f"stream-{self.stream_id}",
            )
            self._thread.start()

            self.metrics.status = "running"
            logger.info("✅ Stream started: %s (student index loading in background)", self.stream_id)
            return True

        except Exception as exc:
            logger.error("Failed to start stream %s: %s", self.stream_id, exc)
            self.metrics.status = "error"
            self.metrics.last_error = str(exc)
            self.metrics.errors += 1
            if self.on_error:
                self.on_error(self.stream_id, str(exc))
            return False

    def stop(self) -> bool:
        """Stop the stream and release resources."""
        try:
            logger.info("Stopping stream: %s", self.stream_id)
            self._stop_event.set()
            self.is_running = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=8)

            if self.cap:
                self.cap.release()
                self.cap = None

            self.metrics.status = "stopped"
            logger.info("✅ Stream stopped: %s", self.stream_id)
            return True

        except Exception as exc:
            logger.error("Error stopping stream %s: %s", self.stream_id, exc)
            return False

    def pause(self) -> bool:
        """Pause frame processing (stream stays connected)."""
        self.is_paused = True
        self.metrics.status = "paused"
        logger.info("Stream paused: %s", self.stream_id)
        return True

    def resume(self) -> bool:
        """Resume frame processing."""
        self.is_paused = False
        self.metrics.status = "running"
        # Reset motion detector so cooldown doesn't trigger false positives
        self.pipeline.motion_detector.reset()
        logger.info("Stream resumed: %s", self.stream_id)
        return True

    # ── Student auto-loading (background thread) ───────────────────────────────

    def _load_students_from_firebase_bg(self) -> None:
        """
        Fetch students from Firebase and inject their stored embeddings
        directly into the pipeline's FAISS index.

        Why direct injection instead of pipeline.register_students()
        ------------------------------------------------------------
        ``OptimizedAttendancePipeline.register_students()`` expects raw face
        *images* (BGR numpy arrays) and calls ``generate_embeddings()`` on
        them — a full FaceNet forward pass per image.  Firebase already stores
        precomputed float32 vectors produced by FaceNet at registration time.
        Re-running FaceNet on stored vectors is meaningless; instead we
        average the stored vectors per student and add them to FAISS directly
        via ``embedding_search.add_students()``.

        Classroom filtering
        -------------------
        If ``self.classroom_id`` is set, only students whose
        ``metadata.classroom_id`` matches are loaded.  This keeps each stream's
        FAISS index small — O(class_size) rather than O(whole_school).
        """
        logger.info(
            "🔄 Loading student embeddings for stream %s (classroom=%s)…",
            self.stream_id, self.classroom_id or "ALL",
        )

        try:
            if not self.firebase:
                raise RuntimeError("Firebase service not available")

            all_students = self.firebase.get_all_students()

            # ── Filter by classroom ─────────────────────────────────────────
            if self.classroom_id:
                students = [
                    s for s in all_students
                    if s.get("metadata", {}).get("classroom_id") == self.classroom_id
                ]
                logger.info(
                    "Classroom filter '%s': %d/%d students match",
                    self.classroom_id, len(students), len(all_students),
                )
            else:
                students = all_students

            if not students:
                logger.warning(
                    "No students found for stream %s (classroom=%s). "
                    "Attendance recognition will be unavailable until students are registered.",
                    self.stream_id, self.classroom_id or "ALL",
                )
                self._students_loaded = True   # mark done — nothing to load
                return

            # ── Build averaged embedding per student ────────────────────────
            student_ids: List[str] = []
            embeddings_list: List[np.ndarray] = []
            metadata: Dict[str, Any] = {}
            skipped = 0

            for student in students:
                sid = student.get("student_id")
                if not sid:
                    skipped += 1
                    continue

                stored_embs = FirebaseService.get_all_embeddings(student)
                if not stored_embs:
                    logger.debug("No embeddings for student %s — skipping", sid)
                    skipped += 1
                    continue

                # Average all face shots and L2-normalise (matches FaceNet convention)
                avg = np.mean(stored_embs, axis=0).astype(np.float32)
                norm = np.linalg.norm(avg)
                if norm > 0:
                    avg = avg / norm

                student_ids.append(sid)
                embeddings_list.append(avg)
                metadata[sid] = {
                    "name": student.get("name", sid),
                    "registered_at": student.get("registered_at", ""),
                    "samples": len(stored_embs),
                }

            if not student_ids:
                logger.warning(
                    "All %d student records lacked valid embeddings for stream %s.",
                    len(students), self.stream_id,
                )
                self._student_load_error = "No valid embeddings found"
                self._students_loaded = True
                return

            # ── Inject into FAISS — bypasses generate_embeddings() ──────────
            embeddings_array = np.array(embeddings_list, dtype=np.float32)
            self.pipeline.embedding_search.add_students(
                student_ids, embeddings_array, metadata
            )

            self._students_loaded_count = len(student_ids)
            self._students_loaded = True

            logger.info(
                "✅ FAISS index ready for stream %s: %d students loaded "
                "(%d skipped, classroom=%s)",
                self.stream_id, len(student_ids), skipped,
                self.classroom_id or "ALL",
            )

        except Exception as exc:
            self._student_load_error = str(exc)
            self._students_loaded = True   # mark done so metrics are honest
            logger.error(
                "Failed to load students for stream %s: %s",
                self.stream_id, exc,
            )

    # ── Main processing loop ───────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """
        Main thread loop.

        Reads frames from the RTSP source and calls ``_process_frame``.
        Handles stream drops by attempting reconnection.
        """
        logger.info("Processing thread started: %s", self.stream_id)
        consecutive_read_failures = 0

        try:
            while not self._stop_event.is_set():
                if self.is_paused:
                    time.sleep(0.05)
                    continue

                ret, frame = self.cap.read()

                if not ret:
                    consecutive_read_failures += 1
                    logger.warning(
                        "Frame read failed (%s) – attempt %d",
                        self.stream_id, consecutive_read_failures,
                    )
                    if consecutive_read_failures >= 5:
                        if not self._reconnect():
                            break
                    else:
                        time.sleep(0.2)
                    continue

                consecutive_read_failures = 0
                self.metrics.frames_read += 1
                self.metrics.last_frame_time = datetime.now()

                try:
                    self._process_frame(frame)
                except Exception as exc:
                    self.metrics.errors += 1
                    self.metrics.last_error = str(exc)
                    logger.error(
                        "Frame processing error in %s: %s", self.stream_id, exc
                    )
                    if self.on_error:
                        self.on_error(self.stream_id, str(exc))

        except Exception as exc:
            logger.error("Stream loop crashed %s: %s", self.stream_id, exc)
            self.metrics.status = "error"
            self.metrics.last_error = str(exc)
        finally:
            if self.cap:
                self.cap.release()
            self.is_running = False
            self.metrics.status = "stopped"
            logger.info("Processing thread ended: %s", self.stream_id)

    def _reconnect(self) -> bool:
        """Try to reopen the RTSP stream after a drop."""
        logger.info(
            "Reconnecting stream %s in %.1f s…", self.stream_id, self.reconnect_delay
        )
        if self.cap:
            self.cap.release()
        time.sleep(self.reconnect_delay)

        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if not self.cap.isOpened():
                raise RuntimeError("Failed to reopen stream")
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.pipeline.motion_detector.reset()
            logger.info("✅ Reconnected: %s", self.stream_id)
            return True
        except Exception as exc:
            logger.error("Reconnect failed for %s: %s", self.stream_id, exc)
            self.metrics.status = "error"
            self.metrics.last_error = str(exc)
            self.metrics.errors += 1
            return False

    # ── Per-frame processing ───────────────────────────────────────────────────

    def _process_frame(self, frame) -> None:
        """
        Run one frame through the Super Pipeline and update AI-active state.

        AI-active cooldown
        ------------------
        When ``result.ai_triggered`` is True, ``_last_ai_trigger_time`` is
        stamped to now.  ``_is_ai_active`` is then True as long as the elapsed
        time since that stamp is within ``_AI_ACTIVE_COOLDOWN_SECONDS``.
        This means the teacher's "Live Monitoring" indicator stays green for
        3 s after motion stops — preventing distracting rapid toggling.
        """
        result: PipelineFrameResult = self.pipeline.process_frame(
            frame, self._fps_samples
        )

        # ── Update AI-active state ──────────────────────────────────────────
        now = datetime.now()
        if result.ai_triggered:
            self._last_ai_trigger_time = now

        if self._last_ai_trigger_time is not None:
            elapsed = (now - self._last_ai_trigger_time).total_seconds()
            self._is_ai_active = elapsed < _AI_ACTIVE_COOLDOWN_SECONDS
        else:
            self._is_ai_active = False

        # ── Update metrics ──────────────────────────────────────────────────
        self.metrics.current_fps = result.fps
        if result.ai_triggered:
            self.metrics.frames_processed += 1
            self.metrics.active_tracks = len(result.tracked_faces)
            self.metrics.total_detections += len(result.detections)
        else:
            if result.motion_result.motion_detected:
                self.metrics.frames_frame_skipped += 1
            else:
                self.metrics.frames_motion_gated += 1

        # ── Detection callback ──────────────────────────────────────────────
        if result.detections and self.on_detection:
            self.on_detection(self.stream_id, result)

        # ── Attendance callback ─────────────────────────────────────────────
        if self.on_attendance and self.firebase:
            for student_id, info in result.marked_students.items():
                if info.get("just_confirmed"):
                    try:
                        self.firebase.mark_attendance(
                            student_id=student_id,
                            timestamp=datetime.now(),
                            confidence=info.get("confidence", 0.0),
                            track_id=info.get("track_id"),
                            camera_id=self.stream_id,
                            metadata={
                                "method": "rtsp_super_pipeline",
                                "motion_score": result.motion_result.motion_score,
                                "ai_triggered": result.ai_triggered,
                                "classroom_id": self.classroom_id,
                            },
                        )
                        self.on_attendance(self.stream_id, student_id)
                        logger.info(
                            "📋 Attendance persisted: %s via stream %s",
                            student_id, self.stream_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "Firebase write failed for %s: %s", student_id, exc
                        )

    # ── Student registration ───────────────────────────────────────────────────

    def register_students(self, students_data: Dict[str, Any]) -> bool:
        """
        Manually load student face embeddings into the pipeline's FAISS index.

        This is the *manual* path — auto-loading happens automatically in
        ``start()`` via ``_load_students_from_firebase_bg()``.  Use this
        method to push updates (new registrations) at runtime without
        restarting the stream.

        Parameters
        ----------
        students_data:
            ``{student_id: [face_np_array, …]}``
        """
        try:
            result = self.pipeline.register_students(students_data)
            logger.info(
                "Registered %d students for stream %s",
                result.get("count", 0), self.stream_id,
            )
            return result.get("success", False)
        except Exception as exc:
            logger.error("Failed to register students for %s: %s", self.stream_id, exc)
            return False

    def reload_students(self) -> None:
        """
        Trigger a fresh student reload from Firebase in the background.

        Useful after new students are registered mid-session without restarting
        the stream.  The existing FAISS index continues to serve recognition
        requests until the reload completes.
        """
        loader = threading.Thread(
            target=self._load_students_from_firebase_bg,
            daemon=True,
            name=f"student-reload-{self.stream_id}",
        )
        loader.start()
        logger.info("Student reload triggered for stream %s", self.stream_id)

    # ── Runtime configuration ──────────────────────────────────────────────────

    def configure_motion_gate(
        self,
        enabled: Optional[bool] = None,
        **motion_kwargs,
    ) -> None:
        """
        Adjust motion gate at runtime without stopping the stream.

        Parameters
        ----------
        enabled:
            If not None, enable or disable the gate entirely.
        **motion_kwargs:
            Forwarded to ``MotionDetector.update_config``.

        Example
        -------
        >>> handler.configure_motion_gate(enabled=True, diff_threshold=20)
        """
        if enabled is not None:
            self.pipeline.set_motion_gate(enabled)
        if motion_kwargs:
            self.pipeline.update_motion_config(**motion_kwargs)

    # ── Metrics ────────────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return a JSON-serialisable metrics snapshot.

        Key fields for the teacher dashboard
        -------------------------------------
        ``is_ai_active``
            True when the AI models (YOLO + FaceNet) ran within the last
            ``_AI_ACTIVE_COOLDOWN_SECONDS`` seconds.  Drives the
            "Live Monitoring" / "System Idle" indicator.
        ``students_loaded``
            True once the background student loader has finished (success or
            failure).  While False, the FAISS index may be empty.
        ``students_loaded_count``
            Number of students successfully indexed.
        ``student_load_error``
            Non-null if the background loader encountered an error.
        """
        uptime = (datetime.now() - self.metrics.start_time).total_seconds()
        pipeline_stats = self.pipeline.get_statistics()
        md_stats = self.pipeline.motion_detector.get_stats()

        return {
            # ── Identity ──────────────────────────────────────────────────
            "stream_id": self.stream_id,
            "classroom_id": self.classroom_id,
            "status": self.metrics.status,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "uptime_seconds": int(uptime),

            # ── AI status (teacher dashboard) ─────────────────────────────
            #
            # is_ai_active: True  → motion was detected recently; YOLO +
            #                        FaceNet are running → "Live Monitoring"
            # is_ai_active: False → no motion for >3 s; models idle       →
            #                        "System Idle"
            "is_ai_active": self._is_ai_active,
            "last_ai_trigger": (
                self._last_ai_trigger_time.isoformat()
                if self._last_ai_trigger_time else None
            ),

            # ── Student index ─────────────────────────────────────────────
            "students_loaded": self._students_loaded,
            "students_loaded_count": self._students_loaded_count,
            "student_load_error": self._student_load_error,

            # ── Frame counts ──────────────────────────────────────────────
            "frames_read": self.metrics.frames_read,
            "frames_processed_by_ai": self.metrics.frames_processed,
            "frames_motion_gated": self.metrics.frames_motion_gated,
            "frames_frame_skipped": self.metrics.frames_frame_skipped,

            # ── Efficiency ────────────────────────────────────────────────
            "ai_skip_rate_pct": round(md_stats["ml_skip_rate"] * 100, 1),
            "motion_gate_enabled": pipeline_stats["motion_gate_enabled"],

            # ── Quality ───────────────────────────────────────────────────
            "fps": round(self.metrics.current_fps, 2),
            "active_tracks": self.metrics.active_tracks,
            "total_detections": self.metrics.total_detections,
            "marked_students": pipeline_stats["marked_students"],

            # ── Errors ────────────────────────────────────────────────────
            "errors": self.metrics.errors,
            "last_error": self.metrics.last_error,
            "last_frame": (
                self.metrics.last_frame_time.isoformat()
                if self.metrics.last_frame_time else None
            ),
        }


# ── StreamManager ──────────────────────────────────────────────────────────────

class StreamManager:
    """
    Manages multiple concurrent RTSP streams.

    All streams share a single Firebase connection but each has its own
    ``OptimizedAttendancePipeline`` (and therefore its own motion detector,
    FAISS index, and SORT tracker).
    """

    def __init__(self):
        self.streams: Dict[str, RTSPStreamHandler] = {}
        self._lock = threading.Lock()
        logger.info("StreamManager initialised")

    def add_stream(
        self,
        stream_id: str,
        rtsp_url: str,
        classroom_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[RTSPStreamHandler]:
        """
        Register a new RTSP stream (does not start it).

        Parameters
        ----------
        stream_id:
            Unique key, e.g. ``"cam_entrance"``.
        rtsp_url:
            Full RTSP URL.
        classroom_id:
            Classroom identifier for student filtering.  ``None`` loads all
            students.
        **kwargs:
            Forwarded to ``RTSPStreamHandler.__init__``.
            Useful keys: ``frame_skip``, ``confidence_threshold``,
            ``enable_motion_gate``, ``motion_config``, ``device``.

        Returns
        -------
        RTSPStreamHandler or None on failure.
        """
        try:
            with self._lock:
                if stream_id in self.streams:
                    logger.warning("Stream %s already registered", stream_id)
                    return self.streams[stream_id]

                handler = RTSPStreamHandler(
                    stream_id=stream_id,
                    rtsp_url=rtsp_url,
                    classroom_id=classroom_id,
                    **kwargs,
                )
                self.streams[stream_id] = handler
                logger.info("Stream registered: %s (classroom=%s)", stream_id, classroom_id or "ALL")
                return handler

        except Exception as exc:
            logger.error("Failed to add stream %s: %s", stream_id, exc)
            return None

    def start_stream(self, stream_id: str) -> bool:
        """Start a registered stream (also triggers student auto-loading)."""
        with self._lock:
            handler = self.streams.get(stream_id)
        if handler is None:
            logger.error("Stream not found: %s", stream_id)
            return False
        return handler.start()

    def stop_stream(self, stream_id: str) -> bool:
        """Stop and remove a stream."""
        with self._lock:
            handler = self.streams.pop(stream_id, None)
        if handler is None:
            logger.error("Stream not found: %s", stream_id)
            return False
        return handler.stop()

    def pause_stream(self, stream_id: str) -> bool:
        """Pause a running stream."""
        handler = self._get(stream_id)
        return handler.pause() if handler else False

    def resume_stream(self, stream_id: str) -> bool:
        """Resume a paused stream."""
        handler = self._get(stream_id)
        return handler.resume() if handler else False

    def reload_students(self, stream_id: str) -> bool:
        """Trigger a background student reload for a specific stream."""
        handler = self._get(stream_id)
        if handler is None:
            return False
        handler.reload_students()
        return True

    def get_stream(self, stream_id: str) -> Optional[RTSPStreamHandler]:
        return self._get(stream_id)

    def get_all_streams(self) -> Dict[str, Dict[str, Any]]:
        """Return metrics for every registered stream."""
        with self._lock:
            return {sid: h.get_metrics() for sid, h in self.streams.items()}

    def list_streams(self) -> list:
        with self._lock:
            return list(self.streams.keys())

    def configure_motion_gate(
        self,
        stream_id: str,
        enabled: Optional[bool] = None,
        **motion_kwargs,
    ) -> bool:
        """
        Adjust motion gate settings for a specific stream at runtime.

        Example
        -------
        >>> manager.configure_motion_gate("cam_entrance", diff_threshold=20)
        >>> manager.configure_motion_gate("cam_hallway", enabled=False)
        """
        handler = self._get(stream_id)
        if handler is None:
            return False
        handler.configure_motion_gate(enabled=enabled, **motion_kwargs)
        return True

    def _get(self, stream_id: str) -> Optional[RTSPStreamHandler]:
        with self._lock:
            return self.streams.get(stream_id)


# ── Singleton ──────────────────────────────────────────────────────────────────

_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create the global StreamManager singleton."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
