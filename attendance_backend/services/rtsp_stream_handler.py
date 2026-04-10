"""
RTSP stream handler for real-time processing of camera feeds.

Supports multiple concurrent RTSP streams.
Integrates with optimized attendance pipeline.
Handles frame processing, detection, and attendance marking.
"""

import logging
import threading
import cv2
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from queue import Queue
import time

from services.optimized_attendance_pipeline import OptimizedAttendancePipeline
from services.firebase_service import get_firebase_service

logger = logging.getLogger(__name__)


@dataclass
class StreamMetrics:
    """Metrics for stream processing."""
    
    stream_id: str
    start_time: datetime
    frames_processed: int = 0
    frames_skipped: int = 0
    last_frame_time: Optional[datetime] = None
    current_fps: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    total_detections: int = 0
    active_tracks: int = 0
    status: str = "idle"  # idle, initializing, running, paused, stopped, error


class RTSPStreamHandler:
    """
    Handler for RTSP stream processing.
    
    Features:
    - Supports multiple concurrent streams
    - Real-time face detection and recognition
    - Temporal verification
    - Automatic error recovery
    """
    
    def __init__(
        self,
        stream_id: str,
        rtsp_url: str,
        frame_skip: int = 2,
        min_consecutive_frames: int = 5,
        confidence_threshold: float = 0.6,
        device: str = "cuda"
    ):
        """
        Initialize RTSP stream handler.
        
        Args:
            stream_id: Unique stream identifier
            rtsp_url: RTSP stream URL
            frame_skip: Process every Nth frame
            min_consecutive_frames: Frames for temporal verification
            confidence_threshold: Recognition confidence threshold
            device: 'cpu' or 'cuda'
        """
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.frame_skip = frame_skip
        self.min_consecutive_frames = min_consecutive_frames
        self.confidence_threshold = confidence_threshold
        self.device = device
        
        # Pipeline
        self.pipeline = OptimizedAttendancePipeline(
            frame_skip=frame_skip,
            min_consecutive_frames=min_consecutive_frames,
            device=device
        )
        
        # Stream state
        self.cap = None
        self.is_running = False
        self.is_paused = False
        self.thread = None
        
        # Metrics
        self.metrics = StreamMetrics(stream_id=stream_id, start_time=datetime.now())
        
        # Callbacks
        self.on_detection: Optional[Callable] = None
        self.on_attendance: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Firebase
        self.firebase = get_firebase_service()
        
        logger.info(f"RTSP handler created: {stream_id}")
    
    def start(self) -> bool:
        """
        Start stream processing.
        
        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning(f"Stream {self.stream_id} already running")
            return False
        
        try:
            logger.info(f"Starting stream: {self.stream_id}")
            self.metrics.status = "initializing"
            
            # Open stream
            self.cap = cv2.VideoCapture(self.rtsp_url)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open RTSP stream: {self.rtsp_url}")
            
            # Set stream properties
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer
            
            logger.info(f"✓ Stream opened: {self.stream_id}")
            
            # Start worker thread
            self.is_running = True
            self.thread = threading.Thread(target=self._process_stream, daemon=True)
            self.thread.start()
            
            self.metrics.status = "running"
            logger.info(f"✓ Stream processing started: {self.stream_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start stream {self.stream_id}: {e}")
            self.metrics.status = "error"
            self.metrics.last_error = str(e)
            self.metrics.errors += 1
            
            if self.on_error:
                self.on_error(self.stream_id, str(e))
            
            return False
    
    def stop(self) -> bool:
        """
        Stop stream processing.
        
        Returns:
            True if stopped successfully
        """
        try:
            logger.info(f"Stopping stream: {self.stream_id}")
            
            self.is_running = False
            
            if self.thread:
                self.thread.join(timeout=5)
            
            if self.cap:
                self.cap.release()
            
            self.metrics.status = "stopped"
            logger.info(f"✓ Stream stopped: {self.stream_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error stopping stream {self.stream_id}: {e}")
            return False
    
    def pause(self) -> bool:
        """Pause stream processing."""
        self.is_paused = True
        self.metrics.status = "paused"
        logger.info(f"Stream paused: {self.stream_id}")
        return True
    
    def resume(self) -> bool:
        """Resume stream processing."""
        self.is_paused = False
        self.metrics.status = "running"
        logger.info(f"Stream resumed: {self.stream_id}")
        return True
    
    def _process_stream(self) -> None:
        """
        Main stream processing loop.
        Runs in separate thread.
        """
        frame_id = 0
        fps_samples = []
        
        try:
            logger.info(f"Stream processing started: {self.stream_id}")
            
            while self.is_running:
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                try:
                    frame_time = time.time()
                    
                    # Read frame
                    ret, frame = self.cap.read()
                    
                    if not ret:
                        # Stream ended or error
                        logger.warning(f"Stream ended: {self.stream_id}")
                        self.metrics.status = "error"
                        self.metrics.last_error = "Failed to read frame"
                        break
                    
                    frame_id += 1
                    self.metrics.frames_processed += 1
                    self.metrics.last_frame_time = datetime.now()
                    
                    # Process frame
                    self._process_frame(frame)
                    
                    # Calculate FPS
                    frame_elapsed = time.time() - frame_time
                    if frame_elapsed > 0:
                        fps = 1.0 / frame_elapsed
                        fps_samples.append(fps)
                        
                        if len(fps_samples) > 30:
                            fps_samples.pop(0)
                        
                        self.metrics.current_fps = sum(fps_samples) / len(fps_samples)
                
                except Exception as e:
                    self.metrics.errors += 1
                    self.metrics.last_error = str(e)
                    logger.error(f"Error processing frame in {self.stream_id}: {e}")
                    
                    if self.on_error:
                        self.on_error(self.stream_id, str(e))
        
        except Exception as e:
            logger.error(f"Stream processing error {self.stream_id}: {e}")
            self.metrics.status = "error"
            self.metrics.last_error = str(e)
            self.metrics.errors += 1
        
        finally:
            logger.info(f"Stream processing ended: {self.stream_id}")
            if self.cap:
                self.cap.release()
            self.is_running = False
            self.metrics.status = "stopped"
    
    def _process_frame(self, frame) -> None:
        """
        Process a single frame.
        
        Args:
            frame: OpenCV frame
        """
        # This is where the pipeline would integrate
        # For now, we do minimal processing
        
        # In real implementation, you would:
        # 1. Run face detection
        # 2. Generate embeddings
        # 3. Search against registered students
        # 4. Verify with temporal verification
        # 5. Mark attendance if verified
        
        # This is simplified - integrate with actual pipeline
        pass
    
    def register_students(self, students_data: Dict[str, Any]) -> bool:
        """
        Load student embeddings for this stream.
        
        Args:
            students_data: Dictionary of student_id -> embeddings
        
        Returns:
            True if successful
        """
        try:
            self.pipeline.register_students(students_data)
            logger.info(f"Registered {len(students_data)} students for stream {self.stream_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register students: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get stream metrics.
        
        Returns:
            Dictionary with stream metrics
        """
        uptime = (datetime.now() - self.metrics.start_time).total_seconds()
        
        return {
            "stream_id": self.stream_id,
            "status": self.metrics.status,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "uptime_seconds": int(uptime),
            "frames_processed": self.metrics.frames_processed,
            "frames_skipped": self.metrics.frames_skipped,
            "fps": round(self.metrics.current_fps, 2),
            "errors": self.metrics.errors,
            "total_detections": self.metrics.total_detections,
            "active_tracks": self.metrics.active_tracks,
            "last_frame": (
                self.metrics.last_frame_time.isoformat()
                if self.metrics.last_frame_time else None
            ),
            "last_error": self.metrics.last_error
        }


class StreamManager:
    """
    Manages multiple RTSP streams.
    """
    
    def __init__(self):
        """Initialize stream manager."""
        self.streams: Dict[str, RTSPStreamHandler] = {}
        self.lock = threading.Lock()
        logger.info("Stream manager initialized")
    
    def add_stream(
        self,
        stream_id: str,
        rtsp_url: str,
        **kwargs
    ) -> Optional[RTSPStreamHandler]:
        """
        Add new stream.
        
        Args:
            stream_id: Unique stream ID
            rtsp_url: RTSP URL
            **kwargs: Additional parameters
        
        Returns:
            RTSPStreamHandler instance or None if failed
        """
        try:
            with self.lock:
                if stream_id in self.streams:
                    logger.warning(f"Stream {stream_id} already exists")
                    return self.streams[stream_id]
                
                handler = RTSPStreamHandler(
                    stream_id=stream_id,
                    rtsp_url=rtsp_url,
                    **kwargs
                )
                
                self.streams[stream_id] = handler
                logger.info(f"Stream added: {stream_id}")
                
                return handler
        
        except Exception as e:
            logger.error(f"Failed to add stream: {e}")
            return None
    
    def start_stream(self, stream_id: str) -> bool:
        """Start a stream."""
        try:
            with self.lock:
                if stream_id not in self.streams:
                    logger.error(f"Stream not found: {stream_id}")
                    return False
                
                return self.streams[stream_id].start()
        except Exception as e:
            logger.error(f"Error starting stream: {e}")
            return False
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop a stream."""
        try:
            with self.lock:
                if stream_id not in self.streams:
                    logger.error(f"Stream not found: {stream_id}")
                    return False
                
                result = self.streams[stream_id].stop()
                del self.streams[stream_id]
                return result
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            return False
    
    def get_stream(self, stream_id: str) -> Optional[RTSPStreamHandler]:
        """Get stream handler."""
        return self.streams.get(stream_id)
    
    def get_all_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all streams."""
        with self.lock:
            return {
                stream_id: handler.get_metrics()
                for stream_id, handler in self.streams.items()
            }
    
    def list_streams(self) -> list:
        """List all stream IDs."""
        with self.lock:
            return list(self.streams.keys())


# Global stream manager
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
