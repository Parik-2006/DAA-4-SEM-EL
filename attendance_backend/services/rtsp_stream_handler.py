"""
RTSP stream handler for real-time processing of camera feeds.

Supports multiple concurrent RTSP streams.
Integrates with the Super Attendance Pipeline (motion-gated YOLO + FaceNet).

Changes from original
---------------------
- ``_process_frame`` now delegates to ``OptimizedAttendancePipeline.process_frame``
  instead of being a no-op placeholder.
- Motion gate state is exposed in ``get_metrics`` so the admin dashboard can
  show per-stream AI skip rates.
- ``StreamManager`` exposes ``configure_motion_gate`` for runtime tuning.
- Student embeddings are loaded at stream start (``register_students``).
"""

import logging
import threading
import time
import cv2
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from queue import Queue, Empty

from services.optimized_attendance_pipeline import (
    OptimizedAttendancePipeline,
    PipelineFrameResult,
)
from utils.motion_detector import MotionConfig
from services.firebase_service import get_firebase_service

logger = logging.getLogger(__name__)


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

    Features
    --------
    - Motion-gated AI inference (60–80 % CPU reduction in static scenes)
    - SORT tracking for smooth identity labels across frames
    - Temporal verification before marking attendance
    - Thread-safe start / stop / pause / resume
    - Automatic reconnection on stream drop (``_reconnect`` strategy)
    - Per-stream runtime motion config updates
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
        """
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay

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

        logger.info("RTSPStreamHandler created: %s → %s", stream_id, rtsp_url)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Open the RTSP stream and start the processing thread.

        Returns
        -------
        bool
            True if the thread was launched successfully.
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
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name=f"stream-{self.stream_id}"
            )
            self._thread.start()

            self.metrics.status = "running"
            logger.info("✅ Stream started: %s", self.stream_id)
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
                            break          # give up after reconnect failure
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
        """
        Try to reopen the RTSP stream after a drop.

        Returns True if reconnection succeeded.
        """
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
            # Reset motion state so the re-opened scene is treated as fresh
            self.pipeline.motion_detector.reset()
            logger.info("✅ Reconnected: %s", self.stream_id)
            return True
        except Exception as exc:
            logger.error("Reconnect failed for %s: %s", self.stream_id, exc)
            self.metrics.status = "error"
            self.metrics.last_error = str(exc)
            self.metrics.errors += 1
            return False

    # ── Per-frame processing (motion-gated Super Pipeline) ────────────────────

    def _process_frame(self, frame) -> None:
        """
        Run one frame through the Super Pipeline.

        The pipeline internally:
        1. Checks motion detector (μs) — exits early if static
        2. Checks frame-skip counter   — exits early if not this frame
        3. Runs YOLO + FaceNet + FAISS + SORT + temporal verifier

        Side effects
        ------------
        - Updates ``self.metrics``
        - Fires ``self.on_detection`` and ``self.on_attendance`` callbacks
        - Persists new attendance records to Firebase via callback
        """
        result: PipelineFrameResult = self.pipeline.process_frame(
            frame, self._fps_samples
        )

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

        # ── Attendance callback: fire once per newly confirmed student ──────
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
        Load student face embeddings into the pipeline's FAISS index.

        Parameters
        ----------
        students_data:
            ``{student_id: [face_np_array, …]}``

        Returns
        -------
        bool
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
            Forwarded to ``MotionDetector.update_config``, e.g.
            ``diff_threshold=30``, ``cooldown_frames=12``.

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

        Includes motion gate efficiency stats from the pipeline so the
        admin dashboard can display per-stream AI skip rates.
        """
        uptime = (datetime.now() - self.metrics.start_time).total_seconds()
        pipeline_stats = self.pipeline.get_statistics()
        md_stats = self.pipeline.motion_detector.get_stats()

        return {
            "stream_id": self.stream_id,
            "status": self.metrics.status,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "uptime_seconds": int(uptime),
            # Frame counts
            "frames_read": self.metrics.frames_read,
            "frames_processed_by_ai": self.metrics.frames_processed,
            "frames_motion_gated": self.metrics.frames_motion_gated,
            "frames_frame_skipped": self.metrics.frames_frame_skipped,
            # Efficiency
            "ai_skip_rate_pct": round(md_stats["ml_skip_rate"] * 100, 1),
            "motion_gate_enabled": pipeline_stats["motion_gate_enabled"],
            # Quality
            "fps": round(self.metrics.current_fps, 2),
            "active_tracks": self.metrics.active_tracks,
            "total_detections": self.metrics.total_detections,
            "marked_students": pipeline_stats["marked_students"],
            # Errors
            "errors": self.metrics.errors,
            "last_error": self.metrics.last_error,
            "last_frame": (
                self.metrics.last_frame_time.isoformat()
                if self.metrics.last_frame_time
                else None
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
                    stream_id=stream_id, rtsp_url=rtsp_url, **kwargs
                )
                self.streams[stream_id] = handler
                logger.info("Stream registered: %s", stream_id)
                return handler

        except Exception as exc:
            logger.error("Failed to add stream %s: %s", stream_id, exc)
            return None

    def start_stream(self, stream_id: str) -> bool:
        """Start a registered stream."""
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
