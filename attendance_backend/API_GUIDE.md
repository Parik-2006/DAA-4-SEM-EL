# 🚀 REST API Guide - Attendance System

**Status**: ✅ Complete with Firebase Integration and RTSP Stream Support

## Table of Contents

1. [Quick Start](#quick-start)
2. [Setup & Installation](#setup--installation)
3. [Firebase Configuration](#firebase-configuration)
4. [API Endpoints](#api-endpoints)
5. [Running Locally](#running-locally)
6. [Testing with Postman](#testing-with-postman)
7. [RTSP Stream Integration](#rtsp-stream-integration)
8. [Error Handling](#error-handling)
9. [Advanced Features](#advanced-features)

---

## Quick Start

```bash
# 1. Setup Python environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure Firebase
cp .env.example .env
# Edit .env and add your Firebase credentials

# 4. Run server
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. Access API
# - Open http://localhost:8000/docs (Swagger UI)
# - Open http://localhost:8000/redoc (ReDoc)
```

---

## Setup & Installation

### Prerequisites

```
Python 3.8+
pip (Python package manager)
Firebase project with admin credentials
OpenCV compatible system (Linux/Windows/Mac)
NVIDIA GPU (recommended for real-time performance)
```

### Step 1: Clone and Setup

```bash
cd attendance_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Key settings to configure:
# - FIREBASE_CREDENTIALS_PATH
# - FASTAPI_ENV (development/production)
# - PROCESSING_DEVICE (cuda/cpu)
```

### Step 3: Verify Installation

```bash
# Test imports
python -c "import fastapi, firebase_admin, cv2, torch; print('✓ All imports successful')"

# Check FastAPI version
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
```

---

## Firebase Configuration

### Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Set up Firestore or Realtime Database

### Step 2: Get Admin Credentials

1. In Firebase Console, go to **Project Settings** → **Service Accounts**
2. Click **Generate New Private Key**
3. Save as `config/firebase-credentials.json`

### Step 3: Configure in .env

```env
# .env configuration
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
USE_FIRESTORE=True  # or False for Realtime DB
```

### Step 4: Verify Firebase Connection

```bash
# Create test script
cat > test_firebase.py << 'EOF'
from services.firebase_service import initialize_firebase
import os

firebase = initialize_firebase(
    credentials_path=os.getenv("FIREBASE_CREDENTIALS_PATH")
)
print("✓ Firebase connected successfully")
EOF

python test_firebase.py
```

---

## API Endpoints

### Base URL
```
http://localhost:8000/api/v1
```

### 1. Student Registration

#### POST `/attendance/register-student`

Register a new student with face embeddings.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/attendance/register-student" \
  -H "Content-Type: application/json" \
  -d {
    "student_id": "STU001",
    "name": "John Doe",
    "email": "john@college.edu",
    "phone": "+1234567890",
    "embeddings": [[0.1, 0.2, ...]]  # 128-dim arrays
  }
```

**Response (201 Created):**
```json
{
  "success": true,
  "student_id": "STU001",
  "message": "Student registered successfully",
  "timestamp": "2024-04-10T10:30:00"
}
```

**Error (400 Bad Request):**
```json
{
  "success": false,
  "error": "Validation error",
  "error_code": "VALIDATION_ERROR"
}
```

### 2. Get All Students

#### GET `/attendance/students`

Retrieve list of all registered students.

**Request:**
```bash
curl "http://localhost:8000/api/v1/attendance/students?limit=100&offset=0"
```

**Response:**
```json
{
  "success": true,
  "count": 100,
  "students": [
    {
      "student_id": "STU001",
      "name": "John Doe",
      "email": "john@college.edu",
      "phone": "+1234567890",
      "registered_at": "2024-04-10T09:00:00",
      "last_seen": "2024-04-10T10:30:00",
      "attendance_count": 45,
      "status": "active"
    }
  ],
  "timestamp": "2024-04-10T10:35:00"
}
```

### 3. Get Specific Student

#### GET `/attendance/students/{student_id}`

Get details for a specific student.

**Request:**
```bash
curl "http://localhost:8000/api/v1/attendance/students/STU001"
```

**Response:**
```json
{
  "student_id": "STU001",
  "name": "John Doe",
  "email": "john@college.edu",
  "phone": "+1234567890",
  "registered_at": "2024-04-10T09:00:00",
  "last_seen": "2024-04-10T10:30:00",
  "attendance_count": 45,
  "status": "active"
}
```

### 4. Mark Attendance

#### POST `/attendance/mark-attendance`

Mark attendance for a recognized student.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/attendance/mark-attendance" \
  -H "Content-Type: application/json" \
  -d {
    "student_id": "STU001",
    "timestamp": "2024-04-10T10:30:00",
    "confidence": 0.95,
    "track_id": 1,
    "camera_id": "CAM_MAIN",
    "metadata": {
      "detection_method": "optimized_pipeline"
    }
  }
```

**Response (201 Created):**
```json
{
  "success": true,
  "record_id": "REC123456789",
  "student_id": "STU001",
  "timestamp": "2024-04-10T10:30:00",
  "message": "Attendance marked successfully"
}
```

### 5. Get Attendance Records

#### GET `/attendance/attendance`

Retrieve attendance records with filtering.

**Request:**
```bash
# Get all records
curl "http://localhost:8000/api/v1/attendance/attendance?limit=100"

# Filter by student
curl "http://localhost:8000/api/v1/attendance/attendance?student_id=STU001&limit=50"

# Filter by date range
curl "http://localhost:8000/api/v1/attendance/attendance\
?date_from=2024-04-10T00:00:00\
&date_to=2024-04-10T23:59:59"
```

**Response:**
```json
{
  "success": true,
  "count": 10,
  "records": [
    {
      "record_id": "REC123456789",
      "student_id": "STU001",
      "timestamp": "2024-04-10T10:30:00",
      "date": "2024-04-10",
      "time": "10:30:00",
      "confidence": 0.95,
      "track_id": 1,
      "camera_id": "CAM_MAIN",
      "status": "present"
    }
  ],
  "timestamp": "2024-04-10T10:35:00"
}
```

### 6. Daily Report

#### GET `/attendance/attendance/daily-report`

Get attendance report for a specific date.

**Request:**
```bash
# Today's report
curl "http://localhost:8000/api/v1/attendance/attendance/daily-report"

# Specific date
curl "http://localhost:8000/api/v1/attendance/attendance/daily-report?date=2024-04-10"
```

**Response:**
```json
{
  "date": "2024-04-10",
  "total_records": 150,
  "unique_students": 45,
  "records": []
}
```

### 7. Stream Management

#### POST `/attendance/streams`

Add new RTSP stream.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/attendance/streams" \
  -H "Content-Type: application/json" \
  -d {
    "stream_id": "stream_main",
    "rtsp_url": "rtsp://192.168.1.100:554/stream1",
    "camera_name": "Main Entrance",
    "location": "Building A",
    "enabled": true,
    "frame_skip": 2,
    "min_consecutive_frames": 5,
    "confidence_threshold": 0.6
  }
```

#### GET `/attendance/streams`

List all RTSP streams.

```bash
curl "http://localhost:8000/api/v1/attendance/streams"
```

#### POST `/attendance/streams/{stream_id}/start`

Start a stream.

```bash
curl -X POST "http://localhost:8000/api/v1/attendance/streams/stream_main/start"
```

#### POST `/attendance/streams/{stream_id}/stop`

Stop a stream.

```bash
curl -X POST "http://localhost:8000/api/v1/attendance/streams/stream_main/stop"
```

### 8. Health Check

#### GET `/attendance/health`

System health status.

```bash
curl "http://localhost:8000/api/v1/attendance/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-04-10T10:30:00",
  "services": {
    "firebase": "healthy",
    "streams": "healthy"
  },
  "uptime_seconds": 3600
}
```

### 9. System Statistics

#### GET `/attendance/stats`

Get system-wide statistics.

```bash
curl "http://localhost:8000/api/v1/attendance/stats"
```

**Response:**
```json
{
  "total_students": 1000,
  "total_attendance_records": 50000,
  "active_streams": 3,
  "total_detections_today": 500,
  "average_confidence": 0.92,
  "timestamp": "2024-04-10T10:30:00"
}
```

---

## Running Locally

### Method 1: Direct Python

```bash
python main.py
```

This will start the server on `http://localhost:8000`

### Method 2: Uvicorn (Recommended)

```bash
# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Method 3: Docker

```bash
# Build image
docker build -t attendance-api .

# Run container
docker run -p 8000:8000 -e FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json attendance-api
```

### Accessing API Documentation

Once server is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Testing with Postman

### Import Collection

1. Download Postman from https://www.postman.com/
2. Create new collection: "Attendance System API"
3. Add requests as documented below

### Create Environment

1. In Postman, click "Environments" → "Create New"
2. Name it "Attendance Dev"
3. Add variables:

```
{
  "base_url": "http://localhost:8000/api/v1",
  "student_id": "STU001",
  "camera_id": "CAM_MAIN"
}
```

### Test Sequence

#### 1. Health Check

```
Method: GET
URL: {{base_url}}/attendance/health

Expected: 200 OK
```

#### 2. Register Student

```
Method: POST
URL: {{base_url}}/attendance/register-student
Header: Content-Type: application/json

Body (raw JSON):
{
  "student_id": "{{student_id}}",
  "name": "Test Student",
  "email": "test@example.com",
  "phone": "+1234567890",
  "embeddings": [
    [0.1, 0.2, 0.3, ...] // 128 values
  ]
}

Expected: 201 Created
```

#### 3. Get Students

```
Method: GET
URL: {{base_url}}/attendance/students?limit=10

Expected: 200 OK with student list
```

#### 4. Mark Attendance

```
Method: POST
URL: {{base_url}}/attendance/mark-attendance
Header: Content-Type: application/json

Body (raw JSON):
{
  "student_id": "{{student_id}}",
  "confidence": 0.95,
  "camera_id": "{{camera_id}}"
}

Expected: 201 Created
```

#### 5. Get Attendance

```
Method: GET
URL: {{base_url}}/attendance/attendance?student_id={{student_id}}

Expected: 200 OK with attendance records
```

### Postman Collection JSON

Save as `Attendance_API.postman_collection.json`:

```json
{
  "info": {
    "name": "Attendance System API",
    "version": "1.0.0"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/attendance/health"
      }
    },
    {
      "name": "Register Student",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/attendance/register-student",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"student_id\": \"STU001\", \"name\": \"Test\", \"email\": \"test@example.com\", \"embeddings\": [[0.1, ...]]}"
        }
      }
    }
  ]
}
```

---

## RTSP Stream Integration

### Configure Stream Without Code Changes

All configuration via API:

```bash
# 1. Add stream
curl -X POST "http://localhost:8000/api/v1/attendance/streams" \
  -H "Content-Type: application/json" \
  -d '{
    "stream_id": "entrance_cam",
    "rtsp_url": "rtsp://camera_ip:554/stream1",
    "camera_name": "Entrance",
    "frame_skip": 2,
    "min_consecutive_frames": 5
  }'

# 2. Check stream status
curl "http://localhost:8000/api/v1/attendance/streams"

# 3. Start stream
curl -X POST "http://localhost:8000/api/v1/attendance/streams/entrance_cam/start"

# 4. Stop stream
curl -X POST "http://localhost:8000/api/v1/attendance/streams/entrance_cam/stop"
```

### Core Logic Remains Unchanged

The optimized pipeline automatically:
- Processes RTSP frames
- Applies frame-skipping
- Detects faces with YOLOv8
- Generates embeddings
- Tracks with SORT
- Searches with FAISS
- Verifies with temporal filtering
- Marks attendance to Firebase

**No core logic changes needed** - just different input source (RTSP vs Webcam)

---

## Error Handling

### Standard Error Response

All errors follow this format:

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {}
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `STUDENT_NOT_FOUND` | 404 | Student ID not found |
| `STUDENT_EXISTS` | 409 | Student already registered |
| `FIREBASE_ERROR` | 503 | Firebase service unavailable |
| `STREAM_ERROR` | 400 | RTSP stream error |
| `INTERNAL_ERROR` | 500 | Server error |

### Example Error Handling in Client

```python
import requests

try:
    response = requests.get("http://localhost:8000/api/v1/attendance/students/STU999")
    
    if response.status_code == 404:
        print("Student not found")
    elif response.status_code == 200:
        student = response.json()
        print(f"Found: {student['name']}")

except requests.exceptions.ConnectionError:
    print("Cannot connect to API server")
```

---

## Advanced Features

### Batch Operations

```bash
# Register multiple students
curl -X POST "http://localhost:8000/api/v1/attendance/batch-register" \
  -H "Content-Type: application/json" \
  -d '{
    "students": [
      {"student_id": "STU001", "name": "John", "email": "john@example.com", "embeddings": []},
      {"student_id": "STU002", "name": "Jane", "email": "jane@example.com", "embeddings": []}
    ]
  }'

# Mark multiple attendance records
curl -X POST "http://localhost:8000/api/v1/attendance/batch-mark-attendance" \
  -H "Content-Type: application/json" \
  -d '{
    "records": [
      {"student_id": "STU001", "confidence": 0.95},
      {"student_id": "STU002", "confidence": 0.92}
    ]
  }'
```

### Pagination

```bash
# Get students with pagination
curl "http://localhost:8000/api/v1/attendance/students?limit=50&offset=0"
curl "http://localhost:8000/api/v1/attendance/students?limit=50&offset=50"
```

### Date Filtering

```bash
# Get attendance for date range
curl "http://localhost:8000/api/v1/attendance/attendance\
?date_from=2024-04-10T00:00:00\
&date_to=2024-04-10T23:59:59"
```

---

## Troubleshooting

### Server Won't Start

```bash
# Check if port 8000 is in use
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Use different port
uvicorn main:app --port 8001
```

### Firebase Connection Error

```bash
# Verify credentials file
ls -la config/firebase-credentials.json

# Test Firebase connection
python -c "from services.firebase_service import initialize_firebase; initialize_firebase('config/firebase-credentials.json')"
```

### Slow Response Times

```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"

# Use CPU if GPU not available
# Edit .env: PROCESSING_DEVICE=cpu
```

### RTSP Stream Issues

```bash
# Test RTSP connection
ffprobe rtsp://camera_ip:554/stream1

# Check network connectivity
ping camera_ip
```

---

## Performance Monitoring

### API Response Times

Monitor via Swagger UI logs or implement custom middleware:

```python
from fastapi.middleware.timing import TimingMiddleware

# Add to main.py
app.add_middleware(TimingMiddleware)
```

### Stream Metrics

```bash
curl "http://localhost:8000/api/v1/attendance/streams" | jq '.streams[] | {stream_id, fps, status}'
```

### System Statistics

```bash
curl "http://localhost:8000/api/v1/attendance/stats" | jq '.'
```

---

## Summary

✅ **Complete REST API** with:
- Student registration & management
- Attendance marking & retrieval
- RTSP stream support
- Firebase integration (Firestore or RTDB)
- Comprehensive error handling
- Production-ready deployment

**Start:** `python main.py`  
**Docs:** http://localhost:8000/docs  
**Test:** Use Postman collection above

---

**Version**: 1.0  
**Status**: Production Ready ✅  
**Last Updated**: 2024
