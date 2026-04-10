"""
Application-wide constants.

This module defines all constants used throughout the attendance system,
including model parameters, status codes, error messages, and feature flags.
"""

from enum import Enum
from typing import Final

# ============ Model Configuration Constants ============

MODEL_INPUT_SIZE: Final[int] = 640  # YOLOv8 input size
FACE_EMBEDDING_DIM: Final[int] = 128  # FaceNet embedding dimension (D-dimensional space)
FACE_RECOGNITION_MODEL: Final[str] = "FaceNet"  # Primary face recognition model

# YOLOv8 Model Variants (smaller = faster, larger = more accurate)
YOLOV8_VARIANTS = {
    "nano": "yolov8n-face.pt",      # Fastest, lightweight
    "small": "yolov8s-face.pt",     # Light
    "medium": "yolov8m-face.pt",    # Medium
    "large": "yolov8l-face.pt",     # Large
    "xlarge": "yolov8x-face.pt",    # Largest, most accurate
}

# ============ Detection Thresholds ============

FACE_DETECTION_CONFIDENCE_MIN: Final[float] = 0.5   # Minimum confidence for face detection
FACE_RECOGNITION_CONFIDENCE_MIN: Final[float] = 0.6  # Minimum confidence for face recognition
FACE_MIN_PIXEL_SIZE: Final[int] = 20  # Minimum face size in pixels

# FAISS distance metric thresholds
FACE_SIMILARITY_THRESHOLD: Final[float] = 0.6  # Cosine similarity threshold (higher = more strict)
FACE_EMBEDDING_DISTANCE_THRESHOLD: Final[float] = 0.6  # Euclidean distance threshold

# ============ Tracking Constants ============

TRACK_MAX_AGE: Final[int] = 30  # Maximum frames to retain a track without updates
TRACK_BUFFER_SIZE: Final[int] = 30  # Number of frames to buffer for tracking
TRACKER_CONFIDENCE_MIN: Final[float] = 0.5  # Minimum confidence for tracker
DUPLICATE_DETECTION_COOLDOWN: Final[int] = 120  # Seconds to prevent duplicate attendance marks

# ============ Image Processing Constants ============

IMAGE_FORMAT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff")
SUPPORTED_IMAGE_FORMATS = {"jpeg", "jpg", "png", "bmp", "tiff"}

# Color conversion constants
BGR_TO_RGB_CONVERSION: Final[str] = "bgr2rgb"
RGB_NORMALIZATION_FACTOR: Final[float] = 1.0 / 255.0

# Face alignment constants
FACE_ALIGNMENT_PADDING: Final[int] = 0  # Padding around detected face

# ============ HTTP Status Codes ============

class HTTPStatus(int, Enum):
    """HTTP status code enumerations."""
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


# ============ Attendance Status ============

class AttendanceStatus(str, Enum):
    """Attendance status enumerations."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    PENDING = "pending"


# ============ Error Messages ============

ERROR_MESSAGES = {
    "INVALID_IMAGE": "Invalid image format or corrupted image data",
    "NO_FACE_DETECTED": "No face detected in the provided image",
    "MULTIPLE_FACES": "Multiple faces detected; expected single face",
    "LOW_CONFIDENCE": "Face recognition confidence below minimum threshold",
    "STUDENT_NOT_FOUND": "Student with provided ID not found in database",
    "FACE_EMBEDDING_NOT_FOUND": "No face embedding found for student",
    "DATABASE_ERROR": "Database operation failed",
    "MODEL_LOAD_ERROR": "Failed to load ML model",
    "FAISS_INDEX_ERROR": "Failed to access FAISS index",
    "UNAUTHORIZED": "Authentication token is invalid or expired",
    "PERMISSION_DENIED": "User does not have permission to perform this action",
    "RATE_LIMIT_EXCEEDED": "Request rate limit exceeded",
    "SERVER_ERROR": "Internal server error occurred",
}

# ============ Success Messages ============

SUCCESS_MESSAGES = {
    "ATTENDANCE_MARKED": "Attendance marked successfully",
    "FACE_EMBEDDING_STORED": "Face embedding stored successfully",
    "STUDENT_REGISTERED": "Student registered successfully",
    "FACE_RECOGNIZED": "Face recognized successfully",
    "HEALTH_CHECK_PASS": "All systems operational",
}

# ============ Database Constants ============

# Firebase collection names
FIREBASE_COLLECTIONS = {
    "students": "students",
    "attendance": "attendance",
    "courses": "courses",
    "face_embeddings": "face_embeddings",
    "sessions": "sessions",
}

# Database field names
DB_FIELD_STUDENT_ID = "student_id"
DB_FIELD_STUDENT_NAME = "name"
DB_FIELD_STUDENT_EMAIL = "email"
DB_FIELD_FACE_EMBEDDING = "face_embedding"
DB_FIELD_EMBEDDING_VERSION = "embedding_version"  # Track embedding model version
DB_FIELD_TIMESTAMP = "timestamp"
DB_FIELD_COURSE_ID = "course_id"
DB_FIELD_ATTENDANCE_DATE = "date"
DB_FIELD_ATTENDANCE_TIME = "time"
DB_FIELD_CONFIDENCE_SCORE = "confidence_score"
DB_FIELD_MODEL_VERSION = "model_version"  # Track which detection model was used

# Deletion retention policy (days)
ATTENDANCE_RETENTION_DAYS: Final[int] = 365  # Keep attendance records for 1 year
FACE_EMBEDDING_BACKUP_INTERVAL: Final[int] = 7  # Backup embeddings weekly

# ============ API Response Constants ============

API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

# Response wrapper fields
RESPONSE_SUCCESS = "success"
RESPONSE_DATA = "data"
RESPONSE_MESSAGE = "message"
RESPONSE_ERROR = "error"
RESPONSE_TIMESTAMP = "timestamp"
RESPONSE_REQUEST_ID = "request_id"

# ============ Cache Constants ============

CACHE_TTL_EMBEDDINGS: Final[int] = 3600  # 1 hour
CACHE_TTL_STUDENTS: Final[int] = 1800  # 30 minutes
CACHE_TTL_ATTENDANCE: Final[int] = 300  # 5 minutes
CACHE_TTL_MODELS: Final[int] = 86400  # 24 hours (models rarely change)

# ============ File Paths & Directories ============

WEIGHTS_DIR: Final[str] = "weights"
INDEXES_DIR: Final[str] = "indexes"
LOGS_DIR: Final[str] = "logs"
TEMP_DIR: Final[str] = "/tmp/attendance_system"

# ============ Performance Constants ============

MAX_BATCH_SIZE: Final[int] = 32  # Maximum batch size for inference
MAX_WORKERS: Final[int] = 4  # Maximum worker threads
REQUEST_TIMEOUT: Final[int] = 30  # Seconds
INFERENCE_TIMEOUT: Final[int] = 10  # Seconds for model inference

# ============ Logging Constants ============

LOG_FORMAT: Final[str] = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Log levels
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# ============ CORS Configuration ============

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",      # React development
    "http://localhost:5173",      # Vite development
    "http://localhost:8080",      # Flutter web development
]

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Content-Type", "Authorization"]
CORS_ALLOW_CREDENTIALS: Final[bool] = True

# ============ Feature Flags ============

ENABLE_FAISS_INDEXING: Final[bool] = True  # Use FAISS for fast similarity search
ENABLE_FACE_TRACKING: Final[bool] = True  # Enable temporal face tracking
ENABLE_EMBEDDING_CACHE: Final[bool] = True  # Cache face embeddings
ENABLE_DUPLICATE_DETECTION: Final[bool] = True  # Prevent duplicate attendance marks
ENABLE_DETAILED_LOGGING: Final[bool] = True  # Verbose logging for debugging

# ============ Pagination Constants ============

DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 1

# ============ Date/Time Constants ============

DATE_FORMAT: Final[str] = "%Y-%m-%d"
TIME_FORMAT: Final[str] = "%H:%M:%S"
DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
TIMEZONE: Final[str] = "UTC"

# ============ System Constants ============

SYSTEM_NAME: Final[str] = "Smart Attendance System"
SYSTEM_VERSION: Final[str] = "1.0.0"
ORGANIZATION_NAME: Final[str] = "Educational Institution"

# Max retries for database operations
MAX_DATABASE_RETRIES: Final[int] = 3
DATABASE_RETRY_DELAY: Final[float] = 1.0  # Seconds with exponential backoff
