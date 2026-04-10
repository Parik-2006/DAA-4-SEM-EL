# AI Pipeline Quick Reference Guide

## Quick Start (3 minutes)

### 1. Installation
```bash
pip install ultralytics>=8.0.0
pip install facenet-pytorch>=2.5.0
pip install torch>=2.0.0
pip install opencv-python>=4.8.0
```

### 2. Real-time Face Detection
```python
from services.detection import FaceDetectionPipeline

detector = FaceDetectionPipeline(model_name="yolov8n", device="cpu")

for frame, detections in detector.detect_faces(webcam_index=0):
    # detections: [(x1, y1, x2, y2, confidence), ...]
    frame = detector.draw_detections(frame, detections)
    cv2.imshow("Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
```

### 3. Generate Face Embeddings
```python
from services.recognition import FaceRecognitionPipeline
import cv2

recognizer = FaceRecognitionPipeline(device="cpu")

face = cv2.imread("face.jpg")
embedding = recognizer.generate_embedding(face)
# embedding: (128,) numpy array (L2 normalized)
```

### 4. Integrated Pipeline
```python
from services.attendance_pipeline import AttendancePipeline

pipeline = AttendancePipeline(device="cpu")

# Register student
faces = [face1, face2, face3]
pipeline.register_student("STU001", "John Doe", faces)

# Mark attendance
for frame_data in pipeline.process_frames():
    for face in frame_data['faces']:
        if face.embedding is not None:
            attendance = pipeline.mark_attendance(
                face.embedding, 
                course_id="CS101"
            )
```

---

## Core Classes & Methods

### FaceDetectionPipeline

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `detect_faces_in_frame(frame)` | np.ndarray (BGR) | list of tuples | Single frame detection |
| `extract_face_regions(frame, detections, padding)` | frame + detections | list of arrays | Crop faces from frame |
| `draw_detections(frame, detections)` | frame + detections | np.ndarray | Visualize with boxes |
| `detect_faces(webcam_index, frame_skip)` | int, int | Generator | Real-time webcam stream |

**Output Format**:
```python
# detect_faces_in_frame returns:
[(x1, y1, x2, y2, confidence), ...]  # Pixel coordinates, 0-1 confidence
```

### FaceRecognitionPipeline

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `generate_embedding(face, target_size)` | np.ndarray | np.ndarray (128,) | Single embedding |
| `generate_embeddings(faces, target_size, batch_size)` | list | list of arrays | Batch processing |
| `compare_faces(emb1, emb2, threshold)` | two arrays | (bool, float) | Face comparison |
| `compute_similarity(emb1, emb2)` | two arrays | float | Distance metric |

**Embedding Properties**:
- **Shape**: (128,)
- **Type**: np.float32
- **Normalization**: L2 normalized
- **Range**: [-1, 1] (after normalization)
- **Metric**: Euclidean distance (lower = more similar)

### FaceDatabase

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `add_face(face_id, embedding, metadata)` | str, array, dict | None | Register face |
| `find_similar_faces(embedding, threshold, top_k)` | array, float, int | list | Search database |
| `clear()` | None | None | Clear all data |

**Output Format**:
```python
# find_similar_faces returns:
[(face_id, distance, metadata), ...]  # Sorted by distance (ascending)
```

### AttendancePipeline

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `register_student(student_id, name, faces)` | str, str, list | dict | Enroll student |
| `process_frame(frame, perform_recognition)` | ndarray, bool | dict | Single frame |
| `process_frames(webcam_index, frame_skip, perform_recognition)` | int, int, bool | Generator | Stream processing |
| `mark_attendance(embedding, course_id, callback)` | array, str, callable | dict | Mark attendance |
| `draw_results(frame, detected_faces)` | ndarray, list | ndarray | Visualize |

**DetectedFace Dataclass**:
```python
@dataclass
class DetectedFace:
    face_id: int                    # Unique ID
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float               # 0-1 confidence
    cropped_image: np.ndarray       # Cropped face
    embedding: Optional[np.ndarray] # 128-dim embedding
    timestamp: datetime             # Detection time
```

---

## Common Code Patterns

### Pattern 1: Real-time Detection
```python
detector = FaceDetectionPipeline(model_name="yolov8n", device="cpu")

for frame, detections in detector.detect_faces(webcam_index=0, frame_skip=2):
    for x1, y1, x2, y2, conf in detections:
        print(f"Face detected with confidence {conf:.2f}")
```

### Pattern 2: Batch Embedding Generation
```python
recognizer = FaceRecognitionPipeline(device="cpu")

# Efficient batch processing
embeddings = recognizer.generate_embeddings(
    faces=detected_faces,
    batch_size=32  # Process 32 faces at a time
)

# Filter valid embeddings
valid = [e for e in embeddings if e is not None]
```

### Pattern 3: Face Matching with Threshold
```python
recognizer = FaceRecognitionPipeline(device="cpu")

emb1 = recognizer.generate_embedding(face1)
emb2 = recognizer.generate_embedding(face2)

# Compare with threshold
is_same_person, distance = recognizer.compare_faces(
    emb1, 
    emb2, 
    threshold=0.6  # Typical threshold
)

if is_same_person:
    print(f"✅ Same person (distance: {distance:.4f})")
else:
    print(f"❌ Different people (distance: {distance:.4f})")
```

### Pattern 4: Database Search
```python
database = FaceDatabase()

# Add students
for student_id, name, embedding in students:
    database.add_face(student_id, embedding, {'name': name})

# Find matching student
matches = database.find_similar_faces(
    query_embedding,
    threshold=0.6,  # Maximum distance
    top_k=1         # Top 1 match
)

if matches:
    student_id, distance, metadata = matches[0]
    print(f"Matched: {metadata['name']} (distance: {distance:.4f})")
```

### Pattern 5: Student Registration & Attendance
```python
pipeline = AttendancePipeline(device="cpu")

# 1. Register
pipeline.register_student(
    student_id="STU001",
    name="John Doe",
    faces=[face1, face2, face3]  # Multiple samples for robust matching
)

# 2. Mark attendance
def save_attendance(record):
    print(f"Marked: {record['student_id']}")
    # Store in database, etc.

for frame_data in pipeline.process_frames(frame_skip=2):
    for face in frame_data['faces']:
        if face.embedding is not None:
            pipeline.mark_attendance(
                face.embedding,
                course_id="CS101",
                student_data_callback=save_attendance
            )
```

---

## Configuration Guide

### Detection Tuning

```python
# Speed vs Accuracy tradeoff
# Faster (lower accuracy):
detector = FaceDetectionPipeline(model_name="yolov8n")

# Slower (higher accuracy):
detector = FaceDetectionPipeline(model_name="yolov8l")

# Confidence filtering
detector = FaceDetectionPipeline(confidence_threshold=0.7)  # Stricter
detector = FaceDetectionPipeline(confidence_threshold=0.3)  # Lenient

# Performance tuning
for frame, detections in detector.detect_faces(frame_skip=3):  # Process every 3rd frame
    pass  # Get 30 FPS with frame_skip=3 if base FPS is ~90
```

### Recognition Tuning

```python
# Matching sensitivity
recognizer = FaceRecognitionPipeline(device="cpu")

# Stricter (fewer false positives):
is_match, dist = recognizer.compare_faces(emb1, emb2, threshold=0.4)

# Lenient (more matches):
is_match, dist = recognizer.compare_faces(emb1, emb2, threshold=0.8)

# Typical thresholds:
# 0.4: Very strict (high false negatives)
# 0.6: Recommended (balanced)
# 0.8: Lenient (high false positives)
```

### Pipeline Configuration

```python
pipeline = AttendancePipeline(
    detection_model="yolov8n",      # Detection model size
    detection_threshold=0.5,         # Detection confidence
    recognition_threshold=0.6,       # Face matching threshold
    device="cpu"                     # "cpu" or "cuda"
)
```

---

## Performance Tips

### 1. Speed Optimization
```python
# Use nano model + frame skipping
detector = FaceDetectionPipeline(model_name="yolov8n")
for frame, dets in detector.detect_faces(frame_skip=3):
    pass  # ~10-15 FPS on CPU
```

### 2. Batch Processing
```python
# Generate embeddings in batches
embeddings = recognizer.generate_embeddings(
    faces,
    batch_size=64  # Larger batch = faster, more memory
)
```

### 3. GPU Acceleration
```python
# Use CUDA if available
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"

pipeline = AttendancePipeline(device=device)
```

### 4. Frame Resolution
```python
# Lower resolution = faster processing
# Resize before detection if needed
resized = cv2.resize(frame, (640, 480))  # Instead of (1920, 1080)
```

---

## Error Handling

### Webcam Issues
```python
try:
    for frame, dets in detector.detect_faces(webcam_index=0):
        pass
except RuntimeError as e:
    if "Cannot open webcam" in str(e):
        print("Try webcam_index=1 or check permissions")
```

### CUDA Out of Memory
```python
# Fall back to CPU
try:
    pipeline = AttendancePipeline(device="cuda")
except Exception:
    pipeline = AttendancePipeline(device="cpu")
```

### Poor Recognition Results
```python
# Register more samples
faces = [face1, face2, face3, face4, face5]  # 5 samples
pipeline.register_student("STU001", "John", faces)

# Lower matching threshold
matches = database.find_similar_faces(emb, threshold=0.8)
```

---

## Integration Examples

### With FastAPI
```python
from fastapi import FastAPI
from services.attendance_pipeline import AttendancePipeline

app = FastAPI()
pipeline = AttendancePipeline(device="cpu")

@app.post("/api/v1/attendance/detect")
async def detect(frame_base64: str):
    frame = base64_to_cv2(frame_base64)
    result = pipeline.process_frame(frame)
    return result

@app.post("/api/v1/attendance/mark")
async def mark(embedding: List[float], course_id: str):
    result = pipeline.mark_attendance(np.array(embedding), course_id)
    return result
```

### With Async Processing
```python
import asyncio

async def process_attendance():
    pipeline = AttendancePipeline(device="cpu")
    
    for frame_data in pipeline.process_frames():
        for face in frame_data['faces']:
            # Process asynchronously
            await asyncio.to_thread(
                pipeline.mark_attendance,
                face.embedding,
                "CS101"
            )
```

---

## Debugging Tips

### Enable Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now you'll see detailed logs from the pipeline
pipeline = AttendancePipeline(device="cpu")
```

### Visualize Detections
```python
# Draw all detections to verify
frame_annotated = detector.draw_detections(frame, detections)
cv2.imshow("Debug", frame_annotated)

# Save to file
cv2.imwrite("debug.jpg", frame_annotated)
```

### Verify Embeddings
```python
# Check embedding properties
print(f"Shape: {embedding.shape}")        # Should be (128,)
print(f"Dtype: {embedding.dtype}")        # Should be float32
print(f"Norm: {np.linalg.norm(embedding)}")  # Should be ~1.0 (L2 normalized)
```

### Comparison Debugging
```python
emb1 = recognizer.generate_embedding(face1)
emb2 = recognizer.generate_embedding(face2)

dist = recognizer.compute_similarity(emb1, emb2)
print(f"Distance: {dist:.4f}")

# If distance > threshold, faces don't match
# If distance < threshold, faces match
```

---

## Thresholds & Constants

### Recommended Thresholds

| Setting | Value | Range | Notes |
|---------|-------|-------|-------|
| Detection Confidence | 0.5 | 0.1-0.9 | Lower = more detections |
| Face Matching | 0.6 | 0.3-0.8 | Lower = stricter |
| Min Face Size | 20px | 10-50px | Skip tiny faces |
| Frame Skip | 2-3 | 1-5 | Trade FPS vs accuracy |

### Model Comparison

| Model | Speed | Accuracy | Memory | Best For |
|-------|-------|----------|--------|----------|
| YOLOv8n | Fast | 88% | Low | Real-time mobile |
| YOLOv8s | Medium | 90% | Medium | Balanced |
| YOLOv8l | Slow | 92% | High | Accuracy critical |
| FaceNet | Fast | 99%+ | Low | Embedding generation |

---

## Running Examples

```bash
# From attendance_backend directory

# Run interactive examples
python examples.py

# Run individual demos
python -m services.detection      # Detection demo
python -m services.recognition    # Recognition demo
python -m services.attendance_pipeline  # Pipeline demo
```

---

## Files Organization

```
attendance_backend/
├── services/
│   ├── detection.py              # YOLOv8 face detection pipeline
│   ├── recognition.py            # FaceNet embeddings + database
│   ├── attendance_pipeline.py     # Integrated real-time processing
│   └── __init__.py               # Package exports
├── AI_PIPELINE_GUIDE.md          # Detailed architecture & usage
├── PIPELINE_QUICK_REFERENCE.md   # This file
└── examples.py                   # 5 comprehensive examples
```

---

## FAQ

**Q: How many face samples needed for registration?**
A: Minimum 3, recommended 5+ for robust matching

**Q: What's the max database size?**
A: In-memory: ~10,000 students per GB of RAM

**Q: Can I run on mobile?**
A: Yes, use yolov8n and quantization

**Q: How accurate is face matching?**
A: 99%+ accuracy on controlled conditions

**Q: What if multiple faces in frame?**
A: All detected faces processed independently

**Q: Can I use different face recognition models?**
A: Yes, swap FaceNet with DeepFace, ArcFace, etc.

**Q: How to improve accuracy?**
A: Register more samples, use better lighting, optimize thresholds

**Q: Is GPU required?**
A: No, CPU works fine. GPU provides 5-10x speedup

**Q: How to deploy for production?**
A: Use FastAPI endpoints + persistent database + containerization
