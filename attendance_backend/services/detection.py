"""
Real-time Face Detection Pipeline using YOLOv8.

Captures video from webcam and performs face detection on each frame
using YOLOv8 model from Ultralytics.

Usage:
    detector = FaceDetectionPipeline()
    for frame, detections in detector.detect_faces():
        # Process detections: [(x1, y1, x2, y2, confidence), ...]
"""

import cv2
import numpy as np
from typing import List, Tuple, Generator, Optional
import logging
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("ultralytics not installed. Run: pip install ultralytics")


logger = logging.getLogger(__name__)


class FaceDetectionPipeline:
    """
    Real-time face detection pipeline using YOLOv8.
    
    Captures video from webcam, detects faces on each frame,
    and yields frames with detection results.
    
    Attributes:
        model_name: YOLOv8 model variant (nano, small, medium, large, xlarge)
        confidence_threshold: Minimum confidence for detections (0-1)
        device: Device to run inference on ('cpu' or 'cuda')
    """
    
    def __init__(
        self,
        model_name: str = "yolov8n",
        confidence_threshold: float = 0.5,
        device: str = "cpu"
    ):
        """
        Initialize face detection pipeline.
        
        Args:
            model_name: YOLOv8 model variant
            confidence_threshold: Minimum confidence threshold
            device: Device for inference ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model = None
        
        self._load_model()
    
    def _load_model(self) -> None:
        """
        Load YOLOv8 model.
        
        Downloads model from Ultralytics if not already cached.
        """
        try:
            logger.info(f"Loading YOLOv8 {self.model_name} model...")
            
            # Load model (auto-downloads if not cached)
            self.model = YOLO(f"{self.model_name}.pt")
            self.model.to(self.device)
            
            logger.info(f"✅ YOLOv8 model loaded successfully on device: {self.device}")
        
        except Exception as e:
            logger.error(f"❌ Failed to load YOLOv8 model: {e}")
            raise
    
    def detect_faces_in_frame(
        self,
        frame: np.ndarray
    ) -> List[Tuple[float, float, float, float, float]]:
        """
        Detect faces in a single frame.
        
        Args:
            frame: Input frame (BGR format from OpenCV)
        
        Returns:
            List of detections: [(x1, y1, x2, y2, confidence), ...]
            where coordinates are in pixel values
        """
        if frame is None or frame.size == 0:
            return []
        
        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            detections = []
            
            # Extract bounding boxes
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Get box coordinates and confidence
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    detections.append((
                        float(x1),
                        float(y1),
                        float(x2),
                        float(y2),
                        confidence
                    ))
            
            return detections
        
        except Exception as e:
            logger.error(f"Error during face detection: {e}")
            return []
    
    def detect_faces(
        self,
        webcam_index: int = 0,
        frame_skip: int = 1
    ) -> Generator[Tuple[np.ndarray, List[Tuple[float, float, float, float, float]]], None, None]:
        """
        Real-time face detection from webcam.
        
        Captures frames from webcam and yields (frame, detections) tuples.
        Press 'q' to stop.
        
        Args:
            webcam_index: Webcam device index (0 for default/built-in camera)
            frame_skip: Process every Nth frame (for performance)
        
        Yields:
            Tuple of (frame, detections) where detections are bounding boxes
        
        Raises:
            RuntimeError: If webcam cannot be opened
        """
        # Open webcam
        cap = cv2.VideoCapture(webcam_index)
        
        if not cap.isOpened():
            raise RuntimeError(f"❌ Cannot open webcam (index {webcam_index})")
        
        try:
            logger.info(f"✅ Webcam opened successfully (index {webcam_index})")
            
            # Get video properties
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Resolution: {frame_width}x{frame_height}, FPS: {fps:.1f}")
            
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning("Failed to read frame from webcam")
                    break
                
                frame_count += 1
                
                # Process every Nth frame
                if frame_count % frame_skip != 0:
                    yield frame, []
                    continue
                
                # Detect faces
                detections = self.detect_faces_in_frame(frame)
                
                yield frame, detections
        
        except KeyboardInterrupt:
            logger.info("Face detection stopped by user")
        
        except Exception as e:
            logger.error(f"Error in detection pipeline: {e}")
        
        finally:
            cap.release()
            logger.info("Webcam closed")
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Tuple[float, float, float, float, float]],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw bounding boxes on frame.
        
        Args:
            frame: Input frame
            detections: List of detections
            color: Box color (BGR)
            thickness: Box line thickness
        
        Returns:
            Frame with drawn detections
        """
        frame_copy = frame.copy()
        
        for x1, y1, x2, y2, conf in detections:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Draw rectangle
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, thickness)
            
            # Draw confidence score
            conf_text = f"Conf: {conf:.2f}"
            cv2.putText(
                frame_copy,
                conf_text,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )
        
        return frame_copy
    
    def extract_face_regions(
        self,
        frame: np.ndarray,
        detections: List[Tuple[float, float, float, float, float]],
        padding: int = 10
    ) -> List[np.ndarray]:
        """
        Extract face regions from frame based on detections.
        
        Args:
            frame: Input frame
            detections: List of detections
            padding: Padding around face region (pixels)
        
        Returns:
            List of cropped face images
        """
        faces = []
        h, w = frame.shape[:2]
        
        for x1, y1, x2, y2, _ in detections:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Add padding
            x1_padded = max(0, x1 - padding)
            y1_padded = max(0, y1 - padding)
            x2_padded = min(w, x2 + padding)
            y2_padded = min(h, y2 + padding)
            
            # Extract face region
            face = frame[y1_padded:y2_padded, x1_padded:x2_padded]
            
            if face.size > 0:
                faces.append(face)
        
        return faces


def demo_detection(webcam_index: int = 0, frame_skip: int = 2):
    """
    Demo script for real-time face detection.
    
    Shows live webcam with detected faces highlighted.
    Press 'q' to stop.
    
    Args:
        webcam_index: Webcam device index
        frame_skip: Process every Nth frame
    """
    logger.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize pipeline
    pipeline = FaceDetectionPipeline(
        model_name="yolov8n",  # nano for speed
        confidence_threshold=0.5,
        device="cpu"
    )
    
    # Process frames
    frame_count = 0
    detection_count = 0
    
    try:
        for frame, detections in pipeline.detect_faces(webcam_index, frame_skip):
            frame_count += 1
            detection_count += len(detections)
            
            # Draw detections
            frame_with_boxes = pipeline.draw_detections(frame, detections)
            
            # Add statistics
            stats_text = f"Frames: {frame_count} | Faces: {detection_count}"
            cv2.putText(
                frame_with_boxes,
                stats_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            # Display
            cv2.imshow("Face Detection - YOLOv8", frame_with_boxes)
            
            # Exit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cv2.destroyAllWindows()
        logger.info(f"Demo ended. Processed {frame_count} frames, detected {detection_count} faces")


if __name__ == "__main__":
    # Run demo
    demo_detection(webcam_index=0, frame_skip=2)
