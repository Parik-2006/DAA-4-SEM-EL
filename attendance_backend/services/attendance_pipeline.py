"""
Integrated Face Detection and Recognition Pipeline.

Combines YOLOv8 face detection with FaceNet embeddings for
real-time attendance system processing.

Usage:
    pipeline = AttendancePipeline()
    for frame_data in pipeline.process_frames(webcam_index=0):
        # frame_data contains detections, crops, and embeddings
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Generator
import logging
from dataclasses import dataclass
from datetime import datetime
import json

from .detection import FaceDetectionPipeline
from .recognition import FaceRecognitionPipeline, FaceDatabase


logger = logging.getLogger(__name__)


@dataclass
class DetectedFace:
    """Represents a detected face with all associated data."""
    
    face_id: int  # Unique ID for this detection
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float  # Detection confidence
    cropped_image: np.ndarray  # Cropped face region
    embedding: Optional[np.ndarray]  # 128-dim embedding
    timestamp: datetime  # When detected
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (for JSON serialization)."""
        return {
            'face_id': self.face_id,
            'bbox': self.bbox,
            'confidence': float(self.confidence),
            'embedding': self.embedding.tolist() if self.embedding is not None else None,
            'timestamp': self.timestamp.isoformat()
        }


class AttendancePipeline:
    """
    Integrated real-time attendance processing pipeline.
    
    Combines:
    1. YOLOv8 face detection
    2. Face cropping and preprocessing
    3. FaceNet embedding generation
    4. Face database matching
    
    Attributes:
        detector: FaceDetectionPipeline instance
        recognizer: FaceRecognitionPipeline instance
        database: Face database for matching
    """
    
    def __init__(
        self,
        detection_model: str = "yolov8n",
        detection_threshold: float = 0.5,
        recognition_threshold: float = 0.6,
        device: str = "cpu"
    ):
        """
        Initialize attendance pipeline.
        
        Args:
            detection_model: YOLOv8 model variant
            detection_threshold: Minimum confidence for detections
            recognition_threshold: Embedding similarity threshold
            device: Device for inference ('cpu' or 'cuda')
        """
        self.detection_threshold = detection_threshold
        self.recognition_threshold = recognition_threshold
        self.device = device
        
        logger.info("Initializing Attendance Pipeline...")
        
        # Initialize detector
        self.detector = FaceDetectionPipeline(
            model_name=detection_model,
            confidence_threshold=detection_threshold,
            device=device
        )
        
        # Initialize recognizer
        self.recognizer = FaceRecognitionPipeline(
            model_name="vggface2",
            device=device,
            pretrained=True
        )
        
        # Initialize database
        self.database = FaceDatabase()
        
        self.face_counter = 0
        
        logger.info("✅ Attendance Pipeline initialized successfully")
    
    def register_student(
        self,
        student_id: str,
        name: str,
        faces: List[np.ndarray]
    ) -> Dict:
        """
        Register a student with facial embeddings.
        
        Args:
            student_id: Unique student identifier
            name: Student name
            faces: List of face images for enrollment
        
        Returns:
            Registration result dictionary
        """
        try:
            logger.info(f"Registering student: {student_id} ({name})")
            
            # Generate embeddings for all provided faces
            embeddings = self.recognizer.generate_embeddings(faces)
            
            # Filter valid embeddings
            valid_embeddings = [e for e in embeddings if e is not None]
            
            if not valid_embeddings:
                logger.error(f"❌ No valid embeddings generated for {student_id}")
                return {
                    'success': False,
                    'message': 'No valid face embeddings',
                    'student_id': student_id
                }
            
            # Average embeddings for more robust matching
            avg_embedding = np.mean(valid_embeddings, axis=0)
            avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
            
            # Store in database
            self.database.add_face(
                student_id,
                avg_embedding,
                {
                    'name': name,
                    'student_id': student_id,
                    'registered_at': datetime.now().isoformat(),
                    'num_samples': len(valid_embeddings)
                }
            )
            
            logger.info(
                f"✅ Student registered: {student_id}\n"
                f"   Name: {name}\n"
                f"   Samples: {len(valid_embeddings)}/{len(faces)}"
            )
            
            return {
                'success': True,
                'message': f'Registered {len(valid_embeddings)} samples',
                'student_id': student_id,
                'samples': len(valid_embeddings)
            }
        
        except Exception as e:
            logger.error(f"Registration error for {student_id}: {e}")
            return {
                'success': False,
                'message': str(e),
                'student_id': student_id
            }
    
    def process_frame(
        self,
        frame: np.ndarray,
        perform_recognition: bool = True
    ) -> Dict:
        """
        Process a single frame: detect faces, extract, and recognize.
        
        Args:
            frame: Input frame (BGR from OpenCV)
            perform_recognition: Whether to generate embeddings
        
        Returns:
            Dictionary with detection and recognition results
        """
        try:
            # Detect faces
            detections = self.detector.detect_faces_in_frame(frame)
            
            if not detections:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'frame_shape': frame.shape,
                    'detections_count': 0,
                    'faces': []
                }
            
            # Extract faces and generate embeddings
            faces = self.detector.extract_face_regions(frame, detections)
            
            # Generate embeddings if requested
            embeddings = []
            if perform_recognition and faces:
                embeddings = self.recognizer.generate_embeddings(faces)
            else:
                embeddings = [None] * len(faces)
            
            # Create detected face objects
            detected_faces = []
            
            for (x1, y1, x2, y2, conf), face, embedding in zip(
                detections, faces, embeddings
            ):
                self.face_counter += 1
                
                detected_face = DetectedFace(
                    face_id=self.face_counter,
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    cropped_image=face,
                    embedding=embedding,
                    timestamp=datetime.now()
                )
                
                detected_faces.append(detected_face)
            
            return {
                'timestamp': datetime.now().isoformat(),
                'frame_shape': frame.shape,
                'detections_count': len(detected_faces),
                'faces': detected_faces
            }
        
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'faces': []
            }
    
    def mark_attendance(
        self,
        embedding: np.ndarray,
        course_id: str,
        student_data_callback=None
    ) -> Optional[Dict]:
        """
        Mark attendance for a detected face.
        
        Args:
            embedding: Face embedding (128-dim)
            course_id: Course identifier
            student_data_callback: Callback to store attendance data
        
        Returns:
            Matched student info or None
        """
        try:
            # Find similar faces in database
            matches = self.database.find_similar_faces(
                embedding,
                threshold=self.recognition_threshold,
                top_k=1
            )
            
            if matches:
                student_id, distance, metadata = matches[0]
                
                result = {
                    'matched': True,
                    'student_id': student_id,
                    'name': metadata.get('name', 'Unknown'),
                    'distance': float(distance),
                    'course_id': course_id,
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.info(
                    f"✅ Attendance marked: {student_id} "
                    f"({metadata.get('name')}, distance={distance:.4f})"
                )
                
                # Store attendance if callback provided
                if student_data_callback:
                    student_data_callback(result)
                
                return result
            else:
                logger.warning("No matching student found in database")
                return {
                    'matched': False,
                    'course_id': course_id,
                    'timestamp': datetime.now().isoformat(),
                    'message': 'No matching face in database'
                }
        
        except Exception as e:
            logger.error(f"Error marking attendance: {e}")
            return None
    
    def process_frames(
        self,
        webcam_index: int = 0,
        frame_skip: int = 1,
        perform_recognition: bool = True
    ) -> Generator[Dict, None, None]:
        """
        Process frames from webcam in real-time.
        
        Args:
            webcam_index: Webcam device index
            frame_skip: Process every Nth frame
            perform_recognition: Generate embeddings
        
        Yields:
            Frame processing results
        """
        try:
            for frame, _ in self.detector.detect_faces(webcam_index, frame_skip):
                result = self.process_frame(frame, perform_recognition)
                yield {
                    'frame': frame,
                    **result
                }
        
        except Exception as e:
            logger.error(f"Error in frame processing loop: {e}")
            raise
    
    def draw_results(
        self,
        frame: np.ndarray,
        detected_faces: List[DetectedFace]
    ) -> np.ndarray:
        """
        Draw detection and recognition results on frame.
        
        Args:
            frame: Input frame
            detected_faces: List of detected faces
        
        Returns:
            Frame with visualizations
        """
        frame_copy = frame.copy()
        h, w = frame.shape[:2]
        
        for face in detected_faces:
            x1, y1, x2, y2 = face.bbox
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Draw bounding box
            color = (0, 255, 0)  # Green for detected faces
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)
            
            # Draw face ID
            cv2.putText(
                frame_copy,
                f"ID: {face.face_id}",
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )
            
            # Draw confidence
            conf_text = f"Conf: {face.confidence:.2f}"
            cv2.putText(
                frame_copy,
                conf_text,
                (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1
            )
        
        # Draw statistics
        stats_text = f"Detected: {len(detected_faces)}"
        cv2.putText(
            frame_copy,
            stats_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        return frame_copy


def demo_attendance_pipeline():
    """
    Demo script for the full attendance pipeline.
    
    Shows real-time detection and recognition.
    Press 'q' to stop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize pipeline
    pipeline = AttendancePipeline(
        detection_model="yolov8n",
        detection_threshold=0.5,
        device="cpu"
    )
    
    # Demo: Register a sample student (with dummy face)
    logger.info("\n📝 Demo: Registering sample student...")
    # (Skipped for now since we don't have real face images in demo)
    
    logger.info("\n🎥 Starting real-time processing...")
    logger.info("Press 'q' to stop\n")
    
    try:
        for frame_data in pipeline.process_frames(
            webcam_index=0,
            frame_skip=2,
            perform_recognition=True
        ):
            frame = frame_data['frame']
            detected_faces = frame_data.get('faces', [])
            
            # Draw results
            frame_with_results = pipeline.draw_results(frame, detected_faces)
            
            # Add detection count
            cv2.putText(
                frame_with_results,
                f"Detections: {len(detected_faces)}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            # Display
            cv2.imshow("Attendance Pipeline", frame_with_results)
            
            # Exit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cv2.destroyAllWindows()
        logger.info("\n✅ Demo completed")


if __name__ == "__main__":
    demo_attendance_pipeline()
