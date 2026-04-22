"""
Application-wide constants for the Smart Attendance System.

This module centralizes all configuration values including:
- ML model parameters
- Detection thresholds
- API and DB constants
- CORS and environment configs
"""

import os as _os
import re as _re
from enum import Enum
from typing import Final

# ───────────────────────────────────────────────────────────────
# 🧠 SYSTEM INFO
# ───────────────────────────────────────────────────────────────
SYSTEM_NAME: Final[str] = "Smart Attendance System"
SYSTEM_VERSION: Final[str] = "1.0.0"
ORGANIZATION_NAME: Final[str] = "Educational Institution"

# ───────────────────────────────────────────────────────────────
# 🤖 MODEL CONFIGURATION
# ───────────────────────────────────────────────────────────────
MODEL_INPUT_SIZE: Final[int] = 640
FACE_EMBEDDING_DIM: Final[int] = 128
FACE_RECOGNITION_MODEL: Final[str] = "FaceNet"

YOLOV8_VARIANTS = {
    "nano": "yolov8n-face.pt",
    "small": "yolov8s-face.pt",
    "medium": "yolov8m-face.pt",
    "large": "yolov8l-face.pt",
    "xlarge": "yolov8x-face.pt",
}

# ───────────────────────────────────────────────────────────────
# 🎯 DETECTION & RECOGNITION
# ───────────────────────────────────────────────────────────────
FACE_DETECTION_CONFIDENCE_MIN: Final[float] = 0.5
FACE_RECOGNITION_CONFIDENCE_MIN: Final[float] = 0.6
FACE_MIN_PIXEL_SIZE: Final[int] = 30

# Similarity thresholds
FACE_SIMILARITY_THRESHOLD: Final[float] = 0.6
FACE_EMBEDDING_DISTANCE_THRESHOLD: Final[float] = 0.6

# ───────────────────────────────────────────────────────────────
# 🎥 TRACKING
# ───────────────────────────────────────────────────────────────
TRACK_MAX_AGE: Final[int] = 30
TRACK_BUFFER_SIZE: Final[int] = 30
TRACKER_CONFIDENCE_MIN: Final[float] = 0.5

# Prevent duplicate attendance (in seconds)
DUPLICATE_DETECTION_COOLDOWN: Final[int] = 300  # 5 minutes

# ───────────────────────────────────────────────────────────────
# 📅 ATTENDANCE STATUS
# ───────────────────────────────────────────────────────────────
class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    PENDING = "pending"

# ───────────────────────────────────────────────────────────────
# 🌐 HTTP STATUS
# ───────────────────────────────────────────────────────────────
class HTTPStatus(int, Enum):
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503

# ───────────────────────────────────────────────────────────────
# ⚠️ ERROR & SUCCESS MESSAGES
# ───────────────────────────────────────────────────────────────
ERROR_MESSAGES = {
    "INVALID_IMAGE": "Invalid image format or corrupted image data",
    "NO_FACE_DETECTED": "No face detected in the provided image",
    "MULTIPLE_FACES": "Multiple faces detected; expected single face",
    "LOW_CONFIDENCE": "Face recognition confidence too low",
    "STUDENT_NOT_FOUND": "Student not found",
    "DATABASE_ERROR": "Database operation failed",
    "MODEL_LOAD_ERROR": "Failed to load model",
    "UNAUTHORIZED": "Invalid or expired token",
    "SERVER_ERROR": "Internal server error",
}

SUCCESS_MESSAGES = {
    "ATTENDANCE_MARKED": "Attendance marked successfully",
    "FACE_RECOGNIZED": "Face recognized successfully",
    "STUDENT_REGISTERED": "Student registered successfully",
}

# ───────────────────────────────────────────────────────────────
# 🗄️ DATABASE CONFIG
# ───────────────────────────────────────────────────────────────
FIREBASE_COLLECTIONS = {
    "students": "students",
    "attendance": "attendance",
    "courses": "courses",
    "face_embeddings": "face_embeddings",
}

DB_FIELD_STUDENT_ID = "student_id"
DB_FIELD_NAME = "name"
DB_FIELD_EMAIL = "email"
DB_FIELD_FACE_EMBEDDING = "face_embedding"
DB_FIELD_TIMESTAMP = "timestamp"
DB_FIELD_CONFIDENCE = "confidence_score"

ATTENDANCE_RETENTION_DAYS: Final[int] = 365

# ───────────────────────────────────────────────────────────────
# 🔗 API CONFIG
# ───────────────────────────────────────────────────────────────
API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

RESPONSE_SUCCESS = "success"
RESPONSE_DATA = "data"
RESPONSE_MESSAGE = "message"
RESPONSE_ERROR = "error"

# ───────────────────────────────────────────────────────────────
# ⚡ CACHE CONFIG
# ───────────────────────────────────────────────────────────────
CACHE_TTL_EMBEDDINGS: Final[int] = 3600
CACHE_TTL_STUDENTS: Final[int] = 1800
CACHE_TTL_ATTENDANCE: Final[int] = 300

# ───────────────────────────────────────────────────────────────
# 📂 FILE PATHS
# ───────────────────────────────────────────────────────────────
WEIGHTS_DIR: Final[str] = "weights"
LOGS_DIR: Final[str] = "logs"
TEMP_DIR: Final[str] = "/tmp/attendance_system"

# ───────────────────────────────────────────────────────────────
# ⚙️ PERFORMANCE
# ───────────────────────────────────────────────────────────────
MAX_BATCH_SIZE: Final[int] = 32
MAX_WORKERS: Final[int] = 4
REQUEST_TIMEOUT: Final[int] = 30

# ───────────────────────────────────────────────────────────────
# 📝 LOGGING
# ───────────────────────────────────────────────────────────────
LOG_FORMAT: Final[str] = "[%(asctime)s] [%(levelname)s] %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# ───────────────────────────────────────────────────────────────
# 🌍 CORS CONFIG (IMPROVED ✅)
# ───────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

# Dynamic localhost support (Claude improvement 🔥)
if _os.getenv("CORS_ALLOW_ALL_LOCALHOST", "false").lower() == "true":
    CORS_ALLOWED_ORIGINS_PATTERN = _re.compile(r"^https?://localhost(:\d+)?$")
else:
    CORS_ALLOWED_ORIGINS_PATTERN = None

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
CORS_ALLOWED_HEADERS = ["Content-Type", "Authorization", "X-Requested-With"]
CORS_ALLOW_CREDENTIALS: Final[bool] = True

# ───────────────────────────────────────────────────────────────
# 🚀 FEATURE FLAGS
# ───────────────────────────────────────────────────────────────
ENABLE_FAISS_INDEXING: Final[bool] = True
ENABLE_FACE_TRACKING: Final[bool] = True
ENABLE_EMBEDDING_CACHE: Final[bool] = True
ENABLE_DUPLICATE_DETECTION: Final[bool] = True

# ───────────────────────────────────────────────────────────────
# 📄 PAGINATION
# ───────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100

# ───────────────────────────────────────────────────────────────
# 📅 DATE & TIME
# ───────────────────────────────────────────────────────────────
DATE_FORMAT: Final[str] = "%Y-%m-%d"
TIME_FORMAT: Final[str] = "%H:%M:%S"
DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
TIMEZONE: Final[str] = "UTC"

# ───────────────────────────────────────────────────────────────
# 🔁 RETRY CONFIG
# ───────────────────────────────────────────────────────────────
MAX_DATABASE_RETRIES: Final[int] = 3
DATABASE_RETRY_DELAY: Final[float] = 1.0