"""
Comprehensive examples and testing script for the AI pipeline.

Demonstrates:
1. Face detection pipeline
2. Face recognition and embeddings
3. Face database operations
4. Integrated attendance pipeline
5. Real-time webcam processing
6. Student enrollment workflow
"""

import cv2
import numpy as np
import logging
from datetime import datetime
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Example 1: Face Detection Only
def example_1_face_detection():
    """
    Example 1: Real-time face detection with YOLOv8
    
    Features:
    - Captures frames from webcam
    - Detects faces in each frame
    - Draws bounding boxes with confidence scores
    - Shows detection statistics
    
    Controls:
    - Press 'q' to quit
    - Press 's' to save detected faces
    """
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE 1: Face Detection Pipeline")
    logger.info("="*70)
    
    try:
        from services.detection import FaceDetectionPipeline
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return
    
    try:
        # Initialize detector
        detector = FaceDetectionPipeline(
            model_name="yolov8n",
            confidence_threshold=0.5,
            device="cpu"
        )
        
        logger.info("🎥 Starting webcam...")
        logger.info("Press 'q' to quit, 's' to save detection snapshot\n")
        
        frame_count = 0
        detection_count = 0
        
        for frame, detections in detector.detect_faces(webcam_index=0, frame_skip=1):
            frame_count += 1
            detection_count += len(detections)
            
            # Draw detections
            frame_annotated = detector.draw_detections(frame, detections)
            
            # Add stats
            stats = f"Frames: {frame_count} | Detections: {len(detections)} | Total: {detection_count}"
            cv2.putText(
                frame_annotated, stats, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            
            cv2.imshow("Example 1: Face Detection", frame_annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(filename, frame_annotated)
                logger.info(f"✅ Saved: {filename}")
        
        logger.info(f"\n✅ Example 1 Complete")
        logger.info(f"   Total frames: {frame_count}")
        logger.info(f"   Total detections: {detection_count}")
        logger.info(f"   Avg faces/frame: {detection_count/max(frame_count, 1):.2f}")
    
    except Exception as e:
        logger.error(f"Error in Example 1: {e}")
    
    finally:
        cv2.destroyAllWindows()


# Example 2: Face Recognition & Embeddings
def example_2_face_recognition():
    """
    Example 2: Generate face embeddings
    
    Demonstrates:
    - Single face embedding generation
    - Batch embedding processing
    - Embedding similarity computation
    - Face matching with thresholds
    """
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE 2: Face Recognition & Embeddings")
    logger.info("="*70)
    
    try:
        from services.recognition import FaceRecognitionPipeline
        from services.detection import FaceDetectionPipeline
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return
    
    try:
        # Initialize components
        detector = FaceDetectionPipeline(device="cpu")
        recognizer = FaceRecognitionPipeline(device="cpu")
        
        logger.info("🎥 Capturing face samples...")
        logger.info("Press SPACE to capture, 'Enter' when done, 'q' to quit\n")
        
        cap = cv2.VideoCapture(0)
        captured_faces = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect faces
            detections = detector.detect_faces_in_frame(frame)
            frame_annotated = detector.draw_detections(frame, detections)
            
            # Add instruction
            instruction = f"Faces in frame: {len(detections)} | Captured: {len(captured_faces)}"
            cv2.putText(
                frame_annotated, instruction, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            
            cv2.imshow("Example 2: Face Recognition", frame_annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):  # SPACE to capture
                if detections:
                    faces = detector.extract_face_regions(frame, detections)
                    captured_faces.extend(faces)
                    logger.info(f"✅ Captured {len(faces)} face(s). Total: {len(captured_faces)}")
            elif key == ord('\r') or key == 13:  # Enter to finish
                if captured_faces:
                    break
        
        cap.release()
        
        if captured_faces:
            logger.info(f"\n📊 Generating embeddings for {len(captured_faces)} faces...")
            
            # Generate embeddings
            embeddings = recognizer.generate_embeddings(captured_faces)
            valid_embeddings = [e for e in embeddings if e is not None]
            
            logger.info(f"✅ Generated {len(valid_embeddings)} valid embeddings")
            
            if len(valid_embeddings) >= 2:
                # Compare first two embeddings
                emb1, emb2 = valid_embeddings[0], valid_embeddings[1]
                distance = recognizer.compute_similarity(emb1, emb2)
                is_match, dist = recognizer.compare_faces(emb1, emb2, threshold=0.6)
                
                logger.info(f"\n📏 Face Comparison:")
                logger.info(f"   Distance: {distance:.4f}")
                logger.info(f"   Threshold: 0.6")
                logger.info(f"   Match: {'✅ YES' if is_match else '❌ NO'}")
            
            logger.info(f"\n✅ Example 2 Complete")
        else:
            logger.warning("No faces captured")
    
    except Exception as e:
        logger.error(f"Error in Example 2: {e}")
    
    finally:
        cv2.destroyAllWindows()


# Example 3: Face Database
def example_3_face_database():
    """
    Example 3: Face database operations
    
    Demonstrates:
    - Adding faces to database
    - Querying similar faces
    - Matching with distance thresholds
    """
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE 3: Face Database Operations")
    logger.info("="*70)
    
    try:
        from services.recognition import FaceDatabase
        import numpy as np
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return
    
    try:
        # Create database
        database = FaceDatabase()
        
        logger.info("📚 Initializing face database...")
        
        # Add sample students
        students = [
            ("STU001", "John Doe"),
            ("STU002", "Jane Smith"),
            ("STU003", "Bob Wilson"),
            ("STU004", "Alice Brown"),
        ]
        
        for student_id, name in students:
            # Generate random embeddings (in real scenario, from FaceNet)
            embedding = np.random.randn(128)
            embedding = embedding / np.linalg.norm(embedding)
            
            database.add_face(
                student_id,
                embedding,
                {
                    'name': name,
                    'student_id': student_id,
                    'registered_at': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Added: {student_id} - {name}")
        
        # Query similar faces
        logger.info(f"\n🔍 Searching for similar faces...")
        query_embedding = np.random.randn(128)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        matches = database.find_similar_faces(
            query_embedding,
            threshold=1.5,  # Generous threshold for random embeddings
            top_k=2
        )
        
        if matches:
            logger.info(f"Found {len(matches)} matches:")
            for student_id, distance, metadata in matches:
                logger.info(
                    f"  - {student_id}: {metadata['name']} (distance={distance:.4f})"
                )
        else:
            logger.info("No matches found")
        
        logger.info(f"\n✅ Example 3 Complete")
        logger.info(f"   Database size: {len(database.embeddings)} students")
    
    except Exception as e:
        logger.error(f"Error in Example 3: {e}")


# Example 4: Integrated Attendance Pipeline
def example_4_integrated_pipeline():
    """
    Example 4: Full integrated attendance pipeline
    
    Demonstrates:
    - Pipeline initialization
    - Student registration
    - Real-time face processing
    - Attendance marking
    - Results visualization
    """
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE 4: Integrated Attendance Pipeline")
    logger.info("="*70)
    
    try:
        from services.attendance_pipeline import AttendancePipeline
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return
    
    try:
        # Initialize pipeline
        logger.info("🚀 Initializing attendance pipeline...")
        pipeline = AttendancePipeline(
            detection_model="yolov8n",
            detection_threshold=0.5,
            recognition_threshold=0.6,
            device="cpu"
        )
        
        # Note: In real scenario, collect student faces for registration
        logger.info(
            "\n📝 Note: Student registration requires actual face images.\n"
            "   Skipping registration phase for this demo.\n"
            "   See example_5_student_workflow() for complete registration process."
        )
        
        # Process frames
        logger.info("\n🎥 Starting real-time face detection...")
        logger.info("Press 'q' to quit\n")
        
        frame_count = 0
        detection_count = 0
        
        for frame_data in pipeline.process_frames(
            webcam_index=0,
            frame_skip=2,
            perform_recognition=True
        ):
            frame = frame_data['frame']
            detected_faces = frame_data.get('faces', [])
            frame_count += 1
            detection_count += len(detected_faces)
            
            # Draw results
            frame_annotated = pipeline.draw_results(frame, detected_faces)
            
            # Add statistics
            stats = f"Frames: {frame_count} | Detected: {len(detected_faces)}"
            cv2.putText(
                frame_annotated, stats, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            
            cv2.imshow("Example 4: Attendance Pipeline", frame_annotated)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        logger.info(f"\n✅ Example 4 Complete")
        logger.info(f"   Total frames: {frame_count}")
        logger.info(f"   Total detections: {detection_count}")
    
    except Exception as e:
        logger.error(f"Error in Example 4: {e}")
    
    finally:
        cv2.destroyAllWindows()


# Example 5: Complete Student Workflow
def example_5_student_workflow():
    """
    Example 5: Complete student registration and attendance workflow
    
    Workflow:
    1. Capture enrollment faces (3-5 samples)
    2. Register student with generated embeddings
    3. Mark attendance in real-time
    4. Query and verify attendance records
    """
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE 5: Complete Student Workflow")
    logger.info("="*70)
    
    try:
        from services.attendance_pipeline import AttendancePipeline
        from services.detection import FaceDetectionPipeline
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return
    
    try:
        # Initialize components
        pipeline = AttendancePipeline(device="cpu")
        detector = FaceDetectionPipeline(device="cpu")
        
        # Step 1: Enrollment
        logger.info("\n📝 STEP 1: Student Enrollment")
        logger.info("-" * 50)
        
        logger.info("Capturing enrollment faces for new student...")
        logger.info("Press SPACE to capture, 'Enter' when done, 'q' to quit\n")
        
        cap = cv2.VideoCapture(0)
        enrollment_faces = []
        
        while len(enrollment_faces) < 3:  # Require 3 samples minimum
            ret, frame = cap.read()
            if not ret:
                break
            
            detections = detector.detect_faces_in_frame(frame)
            frame_annotated = detector.draw_detections(frame, detections)
            
            instruction = (
                f"Captured: {len(enrollment_faces)}/3 | "
                f"Faces in frame: {len(detections)}"
            )
            cv2.putText(
                frame_annotated, instruction, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )
            
            cv2.imshow("Student Enrollment", frame_annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' ') and detections:
                faces = detector.extract_face_regions(frame, detections)
                enrollment_faces.extend(faces[:1])  # Take first face
                logger.info(f"✅ Captured face {len(enrollment_faces)}/3")
            elif (key == ord('\r') or key == 13) and len(enrollment_faces) >= 3:
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if len(enrollment_faces) >= 3:
            # Step 2: Register student
            logger.info(f"\n✅ Captured {len(enrollment_faces)} enrollment faces")
            
            logger.info("\n📋 STEP 2: Register Student")
            logger.info("-" * 50)
            
            student_id = "STU_DEMO_001"
            student_name = "Demo Student"
            
            result = pipeline.register_student(
                student_id=student_id,
                name=student_name,
                faces=enrollment_faces
            )
            
            logger.info(f"Registration Result: {result}")
            
            if result['success']:
                # Step 3: Real-time attendance marking
                logger.info("\n✅ Student registered successfully!")
                
                logger.info("\n📊 STEP 3: Mark Attendance")
                logger.info("-" * 50)
                logger.info("Detecting and marking attendance...")
                logger.info("Press 'q' to quit\n")
                
                attendance_records = []
                frame_count = 0
                
                cap = cv2.VideoCapture(0)
                
                while frame_count < 100:  # Process 100 frames
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Process frame
                    frame_data = pipeline.process_frame(frame, perform_recognition=True)
                    detected_faces = frame_data.get('faces', [])
                    frame_count += 1
                    
                    # Try to mark attendance
                    for face in detected_faces:
                        if face.embedding is not None:
                            attendance = pipeline.mark_attendance(
                                face.embedding,
                                course_id="CS101"
                            )
                            if attendance and attendance.get('matched'):
                                attendance_records.append(attendance)
                                logger.info(
                                    f"✅ Attendance marked: "
                                    f"{attendance.get('name')} "
                                    f"(distance={attendance.get('distance'):.4f})"
                                )
                    
                    # Visualize
                    frame_annotated = pipeline.draw_results(frame, detected_faces)
                    cv2.putText(
                        frame_annotated,
                        f"Attendance records: {len(attendance_records)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )
                    
                    cv2.imshow("Attendance Marking", frame_annotated)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                cap.release()
                cv2.destroyAllWindows()
                
                # Step 4: Summary
                logger.info(f"\n✅ Attendance Summary")
                logger.info("-" * 50)
                logger.info(f"Frames processed: {frame_count}")
                logger.info(f"Attendance records: {len(attendance_records)}")
                
                if attendance_records:
                    logger.info(f"Student marked attendance {len(attendance_records)} times")
                    # Show latest record
                    latest = attendance_records[-1]
                    logger.info(f"Latest: {latest['timestamp']}")
            else:
                logger.error("❌ Student registration failed")
        else:
            logger.warning("⚠️  Not enough faces captured for enrollment")
    
    except Exception as e:
        logger.error(f"Error in Example 5: {e}")
    
    finally:
        cv2.destroyAllWindows()


def main():
    """Main menu for running examples"""
    
    examples = {
        '1': ('Face Detection Only', example_1_face_detection),
        '2': ('Face Recognition & Embeddings', example_2_face_recognition),
        '3': ('Face Database Operations', example_3_face_database),
        '4': ('Integrated Pipeline', example_4_integrated_pipeline),
        '5': ('Complete Student Workflow', example_5_student_workflow),
    }
    
    logger.info("\n" + "="*70)
    logger.info("AI PIPELINE EXAMPLES & TESTING")
    logger.info("="*70)
    logger.info("\nAvailable Examples:\n")
    
    for key, (name, _) in examples.items():
        logger.info(f"  {key}. {name}")
    
    logger.info(f"  0. Exit")
    
    while True:
        choice = input("\nSelect example (0-5): ").strip()
        
        if choice == '0':
            logger.info("Exiting...")
            break
        elif choice in examples:
            _, func = examples[choice]
            try:
                func()
            except KeyboardInterrupt:
                logger.info("\n⚠️  Interrupted by user")
            except Exception as e:
                logger.error(f"Error: {e}")
        else:
            logger.warning("Invalid choice")


if __name__ == "__main__":
    main()
