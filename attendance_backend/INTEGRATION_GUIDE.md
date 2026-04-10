# 🔗 Integration & Deployment Guide

Complete guide to integrating REST API with the optimized attendance pipeline and deploying to production.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Integration](#system-integration)
3. [Pipeline Integration](#pipeline-integration)
4. [Local Development](#local-development)
5. [Docker Deployment](#docker-deployment)
6. [Production Deployment](#production-deployment)
7. [Monitoring & Logging](#monitoring--logging)
8. [Scaling](#scaling)

---

## Architecture Overview

### End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ATTENDANCE SYSTEM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  RTSP STREAMS / WEBCAM                                               │
│         ↓                                                             │
│  ┌─────────────────────────────────────────────────────┐             │
│  │   OPTIMIZED ATTENDANCE PIPELINE (Real-time Processing)            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │           │
│  │  │ Face Detection│ → │   Embedding   │ → │ SORT Tracker  │         │
│  │  │  (YOLOv8)     │  │   Generation  │  │ (Multi-track) │         │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │           │
│  │         ↓              ↓                    ↓           │           │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │           │
│  │  │ FAISS Vector │  │ Temporal     │  │ Confidence  │ │           │
│  │  │ Search (O log n) │  │ Verification │  │ Scoring   │ │           │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │           │
│  └─────────────────────────────────────────────────────────┘           │
│         ↓ (Detection Events)                                          │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  FASTAPI REST ENDPOINTS (External API)              │             │
│  ├─────────────────────────────────────────────────────┤             │
│  │ • /attendance/register-student   (POST)              │             │
│  │ • /attendance/mark-attendance    (POST)              │             │
│  │ • /attendance/students           (GET)               │             │
│  │ • /attendance/attendance         (GET)               │             │
│  │ • /attendance/streams            (GET/POST)          │             │
│  │ • /attendance/health             (GET)               │             │
│  └─────────────────────────────────────────────────────┘             │
│         ↓                                                             │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  FIREBASE SERVICE LAYER                              │             │
│  ├────────────────────┬────────────────────────────────┤             │
│  │ FIRESTORE (Docs)   │ REALTIME DB (JSON)             │             │
│  ├────────────────────┼────────────────────────────────┤             │
│  │ • Students         │ • Real-time Metrics            │             │
│  │ • Attendance       │ • Stream Status                │             │
│  │ • Embeddings       │ • Session Data                │             │
│  │ • Sessions         │ • Analytics                    │             │
│  └────────────────────┴────────────────────────────────┘             │
│         ↓                                                             │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  FRONTEND / EXTERNAL APPS                            │             │
│  │  (Dashboard, Mobile, Third-party)                    │             │
│  └─────────────────────────────────────────────────────┘             │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Purpose | Tech Stack |
|-----------|---------|-----------|
| **RTSP Handler** | Manage video streams | OpenCV, threading |
| **Pipeline** | Real-time detection & tracking | YOLOv8, SORT, FAISS |
| **REST API** | External interface | FastAPI, Pydantic |
| **Firebase** | Data persistence | Firestore/RTDB |
| **Stream Manager** | Coordinate streams | Python threading |

---

## System Integration

### Complete Setup Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Firebase project created
- [ ] Service account credentials downloaded
- [ ] `.env` file configured with Firebase keys
- [ ] Database initialized (Firestore or RTDB)
- [ ] RTSP stream URLs available
- [ ] GPU drivers installed (optional but recommended)

### Installation Summary

```bash
# 1. Clone repository
cd attendance_backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup configuration
mkdir -p config
cp .env.example .env
# Edit .env with Firebase credentials

# 5. Test imports
python -c "import fastapi, firebase_admin, cv2, torch, faiss; print('✓ All imports successful')"

# 6. Verify Firebase connection
python -c "from services.firebase_service import initialize_firebase; initialize_firebase()"
```

---

## Pipeline Integration

### Current Architecture

The `RTSPStreamHandler` processes frames through the pipeline:

```python
# services/rtsp_stream_handler.py
class RTSPStreamHandler:
    def __init__(self, stream_id, rtsp_url, pipeline_config):
        self.pipeline = OptimizedAttendancePipeline(pipeline_config)
        self.stream_manager = StreamManager()
        
    def _process_frame(self, frame):
        """
        Core processing logic - integrates with optimized pipeline
        """
        # Current implementation (simplified):
        # 1. Detect faces (YOLOv8)
        # 2. Generate embeddings
        # 3. Track with SORT
        # 4. Search embeddings with FAISS
        # 5. Verify with temporal filtering
        # 6. Return detections
        
        detections = self.pipeline.process(frame)
        
        # For each detection, mark attendance
        for detection in detections:
            if detection.confidence > self.confidence_threshold:
                self.firebase_service.mark_attendance(
                    student_id=detection.student_id,
                    confidence=detection.confidence,
                    timestamp=datetime.now()
                )
        
        return detections
```

### Integration Workflow

```python
# From api/attendance.py

@router.post("/streams/{stream_id}/start")
async def start_stream(stream_id: str):
    """
    Start RTSP stream processing
    """
    stream_manager = get_stream_manager()
    handler = stream_manager.get_stream(stream_id)
    
    # Start asynchronous processing thread
    handler.start()
    
    # Pipeline automatically processes each frame:
    # Frame → Detection → Firebase → Response
    
    return {
        "success": True,
        "stream_id": stream_id,
        "status": "processing"
    }
```

### Frame Processing Flow

```
1. RTSP Stream (rtsp://camera_ip/stream)
   ↓
2. RTSP Handler (cv2.VideoCapture with buffer optimization)
   ↓
3. Frame Extraction (skip frames based on FRAME_SKIP)
   ↓
4. Face Detection (YOLOv8 model)
   ↓
5. Embedding Generation (Face embedding model)
   ↓
6. SORT Tracking (Historical association)
   ↓
7. FAISS Vector Search (Find matching students - O(log n))
   ↓
8. Temporal Verification (MIN_CONSECUTIVE_FRAMES)
   ↓
9. Confidence Scoring (threshold > 0.6)
   ↓
10. Mark Attendance (Firebase)
    ↓
11. Return Detection Result
```

### Key Integration Points

#### 1. Initialize Firebase on Startup

```python
# main.py
@app.lifespan("startup")
async def startup():
    try:
        initialize_firebase(
            credentials_path=settings.firebase_credentials_path,
            use_firestore=settings.use_firestore
        )
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
```

#### 2. Register Students with Embeddings

```python
# API endpoint that stores student embeddings
@router.post("/attendance/register-student")
async def register_student(request: StudentRegistrationRequest):
    """
    1. Validate embeddings (128 dimensions)
    2. Check for duplicates
    3. Store in Firebase with metadata
    """
    firebase_service = FirebaseService()
    
    # Store student with embeddings
    firebase_service.register_student(
        student_id=request.student_id,
        name=request.name,
        email=request.email,
        embeddings=request.embeddings  # Used by FAISS
    )
```

#### 3. Automatic Attendance Marking

```python
# From RTSP stream processing
def on_detection(self, detection):
    """
    Callback when face is detected and recognized
    """
    firebase_service.mark_attendance(
        student_id=detection.student_id,
        confidence=detection.confidence,
        track_id=detection.track_id,
        camera_id=self.stream_id,
        timestamp=datetime.now()
    )
```

#### 4. Stream Metrics Collection

```python
# Monitor stream health
stream_metrics = {
    "fps": handler.get_fps(),
    "frames_processed": handler.metrics.frames_processed,
    "detections_count": handler.metrics.detections_count,
    "last_error": handler.metrics.last_error
}

firebase_service.update_stream_metrics(stream_id, stream_metrics)
```

---

## Local Development

### Development Setup

```bash
# 1. Create .env.development
FASTAPI_ENV=development
DEBUG=True
LOG_LEVEL=DEBUG
PROCESSING_DEVICE=cuda
```

### Running All Services

```bash
# Terminal 1: Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Test API with Postman or curl
curl http://localhost:8000/docs

# Terminal 3: Monitor logs
tail -f logs/attendance.log

# Terminal 4: Start RTSP stream (if available)
# Configure via API: POST /attendance/streams
```

### Test Complete Workflow

```bash
# 1. Register a test student
curl -X POST http://localhost:8000/api/v1/attendance/register-student \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "TEST001",
    "name": "Test Student",
    "email": "test@example.com",
    "embeddings": [[0.1, 0.2, ...]]
  }'

# 2. Mark attendance manually
curl -X POST http://localhost:8000/api/v1/attendance/mark-attendance \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "TEST001",
    "confidence": 0.95
  }'

# 3. Verify records
curl http://localhost:8000/api/v1/attendance/students/TEST001

# 4. Check statistics
curl http://localhost:8000/api/v1/attendance/stats
```

---

## Docker Deployment

### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create config directory
RUN mkdir -p config

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/attendance/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Create docker-compose.yml

```yaml
version: '3.8'

services:
  attendance-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FASTAPI_ENV=production
      - FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json
      - PROCESSING_DEVICE=cuda
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/attendance/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  config:
  logs:
```

### Deploy with Docker

```bash
# Build image
docker build -t attendance-api:1.0 .

# Run container
docker run -p 8000:8000 \
  -v $(pwd)/config:/app/config:ro \
  -e FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json \
  attendance-api:1.0

# Or with docker-compose
docker-compose up -d

# View logs
docker logs -f attendance-api

# Stop
docker-compose down
```

---

## Production Deployment

### Pre-deployment Checklist

- [ ] All tests passing
- [ ] Code reviewed
- [ ] Environment variables configured
- [ ] Firebase credentials secured
- [ ] HTTPS enabled
- [ ] Rate limiting configured
- [ ] Logging setup
- [ ] Backups configured
- [ ] Monitoring alerts set

### Production Configuration

```env
# .env.production
FASTAPI_ENV=production
DEBUG=False
LOG_LEVEL=INFO

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=["api.attendance.com"]
CORS_ALLOWED_ORIGINS=["https://dashboard.attendance.com"]

# Firebase
FIREBASE_CREDENTIALS_PATH=/etc/attendance/firebase-credentials.json
USE_FIRESTORE=True

# Performance
PROCESSING_DEVICE=cuda
BATCH_SIZE=64
NUM_WORKERS=8
FRAME_SKIP=1  # Process every frame

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
LOG_FILE=/var/log/attendance/api.log
```

### Deploy to Cloud

#### AWS EC2

```bash
# 1. Create EC2 instance (Ubuntu 20.04+)
# 2. Install dependencies
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip

# 3. Clone repository
git clone https://github.com/your-repo/attendance_backend.git
cd attendance_backend

# 4. Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Configure environment
sudo mkdir -p /etc/attendance
sudo cp config/firebase-credentials.json /etc/attendance/
sudo chmod 600 /etc/attendance/firebase-credentials.json

# 7. Start with systemd
sudo cp systemd/attendance-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable attendance-api
sudo systemctl start attendance-api
```

#### Google Cloud Run

```bash
# 1. Deploy Docker image
gcloud run deploy attendance-api \
  --image gcr.io/your-project/attendance-api:1.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json

# 2. Configure domain
gcloud run services update-traffic attendance-api --to-revisions LATEST=100
```

### Load Balancing

```nginx
# nginx.conf
upstream attendance_api {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name api.attendance.com;

    location / {
        proxy_pass http://attendance_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
    }
}
```

### Multiple Worker Processes

```bash
# Run with Gunicorn and multiple workers
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/attendance/access.log \
  --error-logfile /var/log/attendance/error.log
```

---

## Monitoring & Logging

### Setup Logging

```python
# utils/logging_config.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger("attendance")
    
    # File handler
    file_handler = RotatingFileHandler(
        'logs/attendance.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### Monitor Metrics

```bash
# Check API response times
watch -n 1 "curl -w 'Response Time: %{time_total}s\n' http://localhost:8000/api/v1/attendance/health"

# Monitor system resources
watch -n 1 "nvidia-smi"  # GPU usage
watch -n 1 "top"  # CPU usage

# Check logs
tail -f logs/attendance.log

# Filter errors
grep ERROR logs/attendance.log
```

### Prometheus Metrics

Add to `main.py`:

```python
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
request_count = Counter(
    'attendance_requests_total',
    'Total requests',
    ['method', 'endpoint']
)

request_duration = Histogram(
    'attendance_request_duration_seconds',
    'Request duration'
)

# Start metrics server
start_http_server(8001)
```

---

## Scaling

### Horizontal Scaling

**Multiple API Instances:**

```bash
# Run multiple instances on different ports
uvicorn main:app --port 8000 &
uvicorn main:app --port 8001 &
uvicorn main:app --port 8002 &

# Use nginx for load balancing (see section above)
```

**Multiple Stream Handlers:**

```python
# services/stream_manager.py
class StreamManager:
    """
    Manages multiple RTSP streams concurrently
    - Each stream runs in separate thread
    - Scales to 10+ streams per machine
    - Add more workers for more streams
    """
    
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.streams = {}
```

### Database Scaling

**Firestore:**
- Automatic scaling
- Multi-region replication
- No manual configuration needed

**Realtime Database:**
- Auto-scaling with pricing
- Use indexes for performance
- Archive old data to Cloud Storage

### Caching

Add Redis caching:

```python
from redis import Redis
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend

# Setup
FastAPICache2.init(RedisBackend(redis=Redis(host="localhost")), prefix="attendance")

# Use in endpoints
from fastapi_cache2.decorator import cache

@router.get("/students")
@cache(expire=300)
async def get_students():
    # Cached for 5 minutes
    return firebase_service.get_all_students()
```

---

## Performance Tips

### Optimize Pipeline

```env
FRAME_SKIP=2        # Process every 2nd frame (~15 FPS instead of 30)
MIN_CONSECUTIVE_FRAMES=5  # Require 5 frames for confidence
BATCH_SIZE=32       # Process multiple students simultaneously
```

### Optimize Stream Handler

```python
# Reduce RTSP buffer size to minimize latency
cap = cv2.VideoCapture(rtsp_url)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Single frame buffer
```

### Database Query Optimization

```python
# Use indexes for frequent queries
# Firestore: Add composite indexes for date+student_id
# RTDB: Add .indexOn to security rules
```

### API Response Optimization

```python
# Pagination
limit: int = Query(50, le=1000)
offset: int = Query(0)

# Selective fields
fields: Optional[str] = Query(None)  # Only return specific fields
```

---

## Troubleshooting

### API Won't Start

```bash
# Check port availability
lsof -i :8000

# Check imports
python -c "import faiss, cv2, firebase_admin"

# Check Firebase connection
python -c "from services.firebase_service import initialize_firebase; initialize_firebase()"
```

### Slow Response Times

```bash
# Profile with cProfile
python -m cProfile -s cumtime main.py

# Check GPU utilization
nvidia-smi

# Check database queries
# Enable query logging in Firebase Console
```

### Stream Processing Fails

```bash
# Test RTSP URL
ffprobe rtsp://camera_ip:554/stream

# Check stream metrics
curl http://localhost:8000/api/v1/attendance/streams

# Get detailed error
curl http://localhost:8000/api/v1/attendance/streams/stream_id/details
```

---

## Success Criteria

✅ **System Ready When:**
- API responds in <100ms
- Firebase connects successfully
- RTSP streams process smoothly
- Daily attendance >95% reliable
- System uptime >99.5%

---

**Version**: 1.0  
**Last Updated**: 2024  
**Status**: ✅ Production Ready
