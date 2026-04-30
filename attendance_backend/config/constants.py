"""
config/constants.py  (additions for timetable & period detection)
─────────────────────────────────────────────────────────────────────────────
PASTE these blocks into the existing constants.py at the indicated positions.
The full original file content is reproduced here with the new sections
clearly marked so you can diff-apply or copy-paste.

New additions (2026-04-30):
  • TIMETABLE_CONFIG       — attendance window, late threshold, notification
  • PERIOD_DETECTION_CONFIG — poll interval, cache settings
  • ATTENDANCE_WINDOW_MINUTES, LATE_THRESHOLD_MINUTES,
    NOTIFICATION_TRIGGER_MINUTES  (top-level aliases for easy import)
  • Additions to FIREBASE_COLLECTIONS, FIRESTORE_COMPOSITE_INDEXES
  • PERIOD_STATUS enum
"""

# ── The following is a DIFF-READY addition set. ───────────────────────────────
# Add the blocks below to the existing constants.py file.

# ─────────────────────────────────────────────────────────────────────────────
# 📅 TIMETABLE & PERIOD DETECTION CONFIGURATION
# Add this section after the existing "ATTENDANCE STATUS" section.
# ─────────────────────────────────────────────────────────────────────────────
"""
python

from typing import Final
from enum import Enum

# ── Attendance timing windows ─────────────────────────────────────────────────
# How many minutes after a period ENDS that attendance is still accepted.
# Students who mark after this window get status = "closed" (rejected).
ATTENDANCE_WINDOW_MINUTES: Final[int] = int(
    os.getenv("ATTENDANCE_WINDOW_MINUTES", "10")
)

# How many minutes INTO a period a student must mark to be counted "present".
# If they mark after this threshold they are counted "late".
LATE_THRESHOLD_MINUTES: Final[int] = int(
    os.getenv("LATE_THRESHOLD_MINUTES", "5")
)

# How many minutes BEFORE a period STARTS to trigger a pre-class notification.
# The PeriodDetectionService exposes the upcoming period within this window.
NOTIFICATION_TRIGGER_MINUTES: Final[int] = int(
    os.getenv("NOTIFICATION_TRIGGER_MINUTES", "5")
)

# ── Period detection background service ───────────────────────────────────────
PERIOD_DETECTION_POLL_INTERVAL: Final[int] = int(
    os.getenv("PERIOD_DETECTION_POLL_INTERVAL", "60")   # seconds
)

# ── Period status hints (mirrors PeriodDetectionService._annotate output) ─────
class PeriodAttendanceHint(str, Enum):
    NOT_STARTED  = "not_started"
    ON_TIME      = "on_time"
    LATE         = "late"
    GRACE_PERIOD = "grace_period"
    CLOSED       = "closed"
    HOLIDAY      = "holiday"

# ── Valid period types (keep in sync with timetable_service.VALID_PERIOD_TYPES)
VALID_PERIOD_TYPES: Final[set] = {
    "lecture", "lab", "tutorial", "holiday", "break", "exam"
}

# ── Lab / long-session handling ───────────────────────────────────────────────
# Labs can span multiple consecutive slots. No special constant is required —
# the system handles them naturally via start_time / end_time. This note exists
# so developers know there is no hard cap on session duration.
LAB_MIN_DURATION_MINUTES: Final[int] = 90    # informational / used in validators
LAB_MAX_DURATION_MINUTES: Final[int] = 360   # 6 hours max sanity check

# ── Timetable cache TTL (seconds) ─────────────────────────────────────────────
# Added alongside the existing CACHE_TTL_* constants.
CACHE_TTL_TIMETABLE: Final[int] = 1800       # already present — no change
CACHE_TTL_ACTIVE_PERIOD: Final[int] = 90     # cache lives just beyond one poll cycle

# ── Firestore collections additions ───────────────────────────────────────────
# Merge into the existing FIREBASE_COLLECTIONS dict:
#
#   FIREBASE_COLLECTIONS["system_state"] = "system_state"
#
# The system_state collection holds a single document "current_period" that
# the PeriodDetectionService updates on every period transition.

# ── Additional Firestore composite indexes ────────────────────────────────────
# Merge into FIRESTORE_COMPOSITE_INDEXES:
#
# "periods__active_day_start": {
#     "collection": "periods",
#     "fields": [
#         {"field": "active_status", "order": "ASCENDING"},
#         {"field": "day_of_week",   "order": "ASCENDING"},
#         {"field": "start_time",    "order": "ASCENDING"},
#     ],
#     "used_by": ["PeriodDetectionService.get_all_active_periods"],
# },
#
# Deploy with:  firebase deploy --only firestore:indexes
"""

# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE / COPY-PASTE VERSION
# If you prefer to replace constants.py entirely, use the block below.
# It is the *original* constants.py with the new sections inserted.
# ─────────────────────────────────────────────────────────────────────────────

import os as _os
import re as _re
from enum import Enum
from typing import Final

# ───────────────────────────────────────────────────────────────
# 🧠 SYSTEM INFO
# ───────────────────────────────────────────────────────────────
SYSTEM_NAME: Final[str] = "Smart Attendance System"
SYSTEM_VERSION: Final[str] = "2.0.0"
ORGANIZATION_NAME: Final[str] = "Educational Institution"

# ───────────────────────────────────────────────────────────────
# 🤖 MODEL CONFIGURATION
# ───────────────────────────────────────────────────────────────
MODEL_INPUT_SIZE: Final[int] = 640
FACE_EMBEDDING_DIM: Final[int] = 128
FACE_RECOGNITION_MODEL: Final[str] = "FaceNet"

YOLOV8_VARIANTS = {
    "nano":   "yolov8n-face.pt",
    "small":  "yolov8s-face.pt",
    "medium": "yolov8m-face.pt",
    "large":  "yolov8l-face.pt",
    "xlarge": "yolov8x-face.pt",
}

# ───────────────────────────────────────────────────────────────
# 🎯 DETECTION & RECOGNITION
# ───────────────────────────────────────────────────────────────
FACE_DETECTION_CONFIDENCE_MIN: Final[float] = 0.5
FACE_RECOGNITION_CONFIDENCE_MIN: Final[float] = 0.6
FACE_MIN_PIXEL_SIZE: Final[int] = 30
FACE_RECOGNITION_THRESHOLD: Final[float] = FACE_RECOGNITION_CONFIDENCE_MIN

FACE_SIMILARITY_THRESHOLD: Final[float] = 0.6
FACE_EMBEDDING_DISTANCE_THRESHOLD: Final[float] = 0.6

# ───────────────────────────────────────────────────────────────
# 🎥 TRACKING
# ───────────────────────────────────────────────────────────────
TRACK_MAX_AGE: Final[int] = 30
TRACK_BUFFER_SIZE: Final[int] = 30
TRACKER_CONFIDENCE_MIN: Final[float] = 0.5

DUPLICATE_DETECTION_COOLDOWN: Final[int] = 300  # seconds

# ───────────────────────────────────────────────────────────────
# 📅 ATTENDANCE STATUS
# ───────────────────────────────────────────────────────────────
class AttendanceStatus(str, Enum):
    PRESENT  = "present"
    ABSENT   = "absent"
    LATE     = "late"
    EXCUSED  = "excused"
    PENDING  = "pending"

# ───────────────────────────────────────────────────────────────
# ⏱️  TIMETABLE & PERIOD DETECTION  [NEW 2026-04-30]
# ───────────────────────────────────────────────────────────────

# -- Attendance timing windows ------------------------------------------------
# Minutes AFTER period end during which late attendance is still accepted.
ATTENDANCE_WINDOW_MINUTES: Final[int] = int(
    _os.getenv("ATTENDANCE_WINDOW_MINUTES", "10")
)

# Minutes INTO a period after which the student is counted "late".
LATE_THRESHOLD_MINUTES: Final[int] = int(
    _os.getenv("LATE_THRESHOLD_MINUTES", "5")
)

# Minutes BEFORE period start to surface the "upcoming period" notification.
NOTIFICATION_TRIGGER_MINUTES: Final[int] = int(
    _os.getenv("NOTIFICATION_TRIGGER_MINUTES", "5")
)

# -- Period detection background poll -----------------------------------------
PERIOD_DETECTION_POLL_INTERVAL: Final[int] = int(
    _os.getenv("PERIOD_DETECTION_POLL_INTERVAL", "60")  # seconds
)

# -- Period attendance status hints -------------------------------------------
class PeriodAttendanceHint(str, Enum):
    NOT_STARTED  = "not_started"
    ON_TIME      = "on_time"
    LATE         = "late"
    GRACE_PERIOD = "grace_period"
    CLOSED       = "closed"
    HOLIDAY      = "holiday"

# -- Valid period types --------------------------------------------------------
VALID_PERIOD_TYPES: Final[set] = {
    "lecture", "lab", "tutorial", "holiday", "break", "exam"
}

# -- Lab duration guard rails (informational) ----------------------------------
LAB_MIN_DURATION_MINUTES: Final[int] = 90
LAB_MAX_DURATION_MINUTES: Final[int] = 360

# -- Active-period cache TTL --------------------------------------------------
CACHE_TTL_ACTIVE_PERIOD: Final[int] = 90   # seconds

# ───────────────────────────────────────────────────────────────
# 🌐 HTTP STATUS
# ───────────────────────────────────────────────────────────────
class HTTPStatus(int, Enum):
    OK                    = 200
    CREATED               = 201
    BAD_REQUEST           = 400
    UNAUTHORIZED          = 401
    FORBIDDEN             = 403
    NOT_FOUND             = 404
    CONFLICT              = 409
    UNPROCESSABLE_ENTITY  = 422
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE   = 503

# ───────────────────────────────────────────────────────────────
# ⚠️ ERROR & SUCCESS MESSAGES
# ───────────────────────────────────────────────────────────────
ERROR_MESSAGES = {
    "INVALID_IMAGE":      "Invalid image format or corrupted image data",
    "NO_FACE_DETECTED":   "No face detected in the provided image",
    "MULTIPLE_FACES":     "Multiple faces detected; expected single face",
    "LOW_CONFIDENCE":     "Face recognition confidence too low",
    "STUDENT_NOT_FOUND":  "Student not found",
    "FACULTY_NOT_FOUND":  "Faculty member not found",
    "CLASS_NOT_FOUND":    "Class not found",
    "CIE_NOT_FOUND":      "CIE not found",
    "PERIOD_NOT_FOUND":   "Period not found",
    "DATABASE_ERROR":     "Database operation failed",
    "MODEL_LOAD_ERROR":   "Failed to load model",
    "UNAUTHORIZED":       "Invalid or expired token",
    "SERVER_ERROR":       "Internal server error",
}

SUCCESS_MESSAGES = {
    "ATTENDANCE_MARKED":      "Attendance marked successfully",
    "FACE_RECOGNIZED":        "Face recognized successfully",
    "STUDENT_REGISTERED":     "Student registered successfully",
    "FACULTY_CREATED":        "Faculty member created successfully",
    "CLASS_CREATED":          "Class created successfully",
    "CIE_CREATED":            "CIE created successfully",
    "PERIOD_CREATED":         "Period created successfully",
    "ASSIGNMENT_CREATED":     "Course assignment created successfully",
    "TIMETABLE_UPLOADED":     "Timetable uploaded successfully",    # NEW
}

# ───────────────────────────────────────────────────────────────
# 🗄️ DATABASE COLLECTIONS
# ───────────────────────────────────────────────────────────────
FIREBASE_COLLECTIONS = {
    # ── Pre-existing (Realtime DB + Firestore) ─────────────────
    "students":    "students",
    "attendance":  "attendance",
    "courses":     "courses",
    "face_embeddings": "face_embeddings",

    # ── Firestore-only collections (2026-04) ───────────────────
    "cie":                "cie",
    "classes":            "classes",
    "periods":            "periods",
    "course_assignments": "course_assignments",
    "faculty":            "faculty",

    # ── NEW (2026-04-30) ───────────────────────────────────────
    # Holds a single document "current_period" updated by PeriodDetectionService
    # on every period transition; frontend subscribes via Firestore snapshots.
    "system_state":       "system_state",
}

# ── Field name constants (unchanged) ──────────────────────────────────────────
DB_FIELD_STUDENT_ID         = "student_id"
DB_FIELD_COURSE_ID          = "course_id"
DB_FIELD_NAME               = "name"
DB_FIELD_EMAIL              = "email"
DB_FIELD_STUDENT_NAME       = DB_FIELD_NAME
DB_FIELD_STUDENT_EMAIL      = DB_FIELD_EMAIL
DB_FIELD_FACE_EMBEDDING     = "face_embedding"
DB_FIELD_TIMESTAMP          = "timestamp"
DB_FIELD_CONFIDENCE         = "confidence_score"
DB_FIELD_CONFIDENCE_SCORE   = DB_FIELD_CONFIDENCE
DB_FIELD_ATTENDANCE_DATE    = "attendance_date"
DB_FIELD_ATTENDANCE_TIME    = "attendance_time"

DB_FIELD_CLASS_ID           = "class_id"
DB_FIELD_FACULTY_ID         = "faculty_id"
DB_FIELD_CIE_ID             = "cie_id"
DB_FIELD_PERIOD_ID          = "period_id"
DB_FIELD_SEMESTER           = "semester"
DB_FIELD_DAY_OF_WEEK        = "day_of_week"
DB_FIELD_START_TIME         = "start_time"
DB_FIELD_END_TIME           = "end_time"
DB_FIELD_ACTIVE_STATUS      = "active_status"
DB_FIELD_DEPARTMENT         = "department"
DB_FIELD_SPECIALIZATION     = "specialization"

ATTENDANCE_RETENTION_DAYS: Final[int] = 365

# ───────────────────────────────────────────────────────────────
# 📅 DAY-OF-WEEK MAPPING
# ───────────────────────────────────────────────────────────────
DAY_OF_WEEK_MAP: Final[dict] = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

DAY_NAME_TO_INT: Final[dict] = {v: k for k, v in DAY_OF_WEEK_MAP.items()}

# ───────────────────────────────────────────────────────────────
# 🔍 FIRESTORE COMPOSITE INDEXES (reference)
# ───────────────────────────────────────────────────────────────
FIRESTORE_COMPOSITE_INDEXES: Final[dict] = {
    # ── periods collection ─────────────────────────────────────
    "periods__day_start": {
        "collection": "periods",
        "fields": [
            {"field": "day_of_week", "order": "ASCENDING"},
            {"field": "start_time",  "order": "ASCENDING"},
        ],
        "used_by": ["get_periods_by_day", "get_active_period", "get_periods_by_day_and_time"],
    },
    "periods__class_day_start": {
        "collection": "periods",
        "fields": [
            {"field": "class_id",    "order": "ASCENDING"},
            {"field": "day_of_week", "order": "ASCENDING"},
            {"field": "start_time",  "order": "ASCENDING"},
        ],
        "used_by": ["get_timetable_by_class"],
    },
    "periods__faculty_day_start": {
        "collection": "periods",
        "fields": [
            {"field": "faculty_id",  "order": "ASCENDING"},
            {"field": "day_of_week", "order": "ASCENDING"},
            {"field": "start_time",  "order": "ASCENDING"},
        ],
        "used_by": ["get_faculty_schedule"],
    },

    # ── NEW: all-active query used by PeriodDetectionService ───
    "periods__active_day_start": {
        "collection": "periods",
        "fields": [
            {"field": "active_status", "order": "ASCENDING"},
            {"field": "day_of_week",   "order": "ASCENDING"},
            {"field": "start_time",    "order": "ASCENDING"},
        ],
        "used_by": ["PeriodDetectionService.get_all_active_periods"],
    },

    # ── cie collection ─────────────────────────────────────────
    "cie__active_start": {
        "collection": "cie",
        "fields": [
            {"field": "active_status", "order": "ASCENDING"},
            {"field": "start_date",    "order": "ASCENDING"},
        ],
        "used_by": ["get_active_cie"],
    },
    "cie__start_range": {
        "collection": "cie",
        "fields": [
            {"field": "start_date", "order": "ASCENDING"},
            {"field": "end_date",   "order": "ASCENDING"},
        ],
        "used_by": ["query_cie_by_date_range"],
    },

    # ── classes collection ─────────────────────────────────────
    "classes__cie_semester": {
        "collection": "classes",
        "fields": [
            {"field": "cie_id",   "order": "ASCENDING"},
            {"field": "semester", "order": "ASCENDING"},
        ],
        "used_by": ["get_classes_by_cie"],
    },

    # ── course_assignments collection ──────────────────────────
    "course_assignments__faculty_semester": {
        "collection": "course_assignments",
        "fields": [
            {"field": "faculty_id", "order": "ASCENDING"},
            {"field": "semester",   "order": "ASCENDING"},
        ],
        "used_by": ["get_faculty_courses"],
    },

    # ── students collection ────────────────────────────────────
    "students__class_name": {
        "collection": "students",
        "fields": [
            {"field": "class_id", "order": "ASCENDING"},
            {"field": "name",     "order": "ASCENDING"},
        ],
        "used_by": ["get_students_by_class"],
    },

    # ── attendance collection ──────────────────────────────────
    "attendance__date_period": {
        "collection": "attendance",
        "fields": [
            {"field": "date",               "order": "ASCENDING"},
            {"field": "metadata.period_id", "order": "ASCENDING"},
        ],
        "used_by": ["get_attendance_for_period"],
    },
}

# ───────────────────────────────────────────────────────────────
# 🔗 API CONFIG
# ───────────────────────────────────────────────────────────────
API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

RESPONSE_SUCCESS = "success"
RESPONSE_DATA    = "data"
RESPONSE_MESSAGE = "message"
RESPONSE_ERROR   = "error"

# ───────────────────────────────────────────────────────────────
# ⚡ CACHE CONFIG
# ───────────────────────────────────────────────────────────────
CACHE_TTL_EMBEDDINGS: Final[int] = 3600
CACHE_TTL_STUDENTS:   Final[int] = 1800
CACHE_TTL_ATTENDANCE: Final[int] = 300
CACHE_TTL_TIMETABLE:  Final[int] = 1800
CACHE_TTL_ACTIVE_PERIOD: Final[int] = 90    # NEW

# ───────────────────────────────────────────────────────────────
# 📂 FILE PATHS
# ───────────────────────────────────────────────────────────────
WEIGHTS_DIR: Final[str] = "weights"
LOGS_DIR:    Final[str] = "logs"
TEMP_DIR:    Final[str] = "/tmp/attendance_system"

# ───────────────────────────────────────────────────────────────
# ⚙️ PERFORMANCE
# ───────────────────────────────────────────────────────────────
MAX_BATCH_SIZE: Final[int] = 32
MAX_WORKERS:    Final[int] = 4
REQUEST_TIMEOUT: Final[int] = 30

# ───────────────────────────────────────────────────────────────
# 📝 LOGGING
# ───────────────────────────────────────────────────────────────
LOG_FORMAT:      Final[str] = "[%(asctime)s] [%(levelname)s] %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

LOG_LEVELS = {
    "DEBUG":    10,
    "INFO":     20,
    "WARNING":  30,
    "ERROR":    40,
    "CRITICAL": 50,
}

# ───────────────────────────────────────────────────────────────
# 🌍 CORS CONFIG
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

if _os.getenv("CORS_ALLOW_ALL_LOCALHOST", "false").lower() == "true":
    CORS_ALLOWED_ORIGINS_PATTERN = _re.compile(r"^https?://localhost(:\d+)?$")
else:
    CORS_ALLOWED_ORIGINS_PATTERN = None

CORS_ALLOWED_METHODS     = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
CORS_ALLOWED_HEADERS     = ["Content-Type", "Authorization", "X-Requested-With"]
CORS_ALLOW_CREDENTIALS: Final[bool] = True

# ───────────────────────────────────────────────────────────────
# 🚀 FEATURE FLAGS
# ───────────────────────────────────────────────────────────────
ENABLE_FAISS_INDEXING:       Final[bool] = True
ENABLE_FACE_TRACKING:        Final[bool] = True
ENABLE_EMBEDDING_CACHE:      Final[bool] = True
ENABLE_DUPLICATE_DETECTION:  Final[bool] = True
ENABLE_CIE_MANAGEMENT:       Final[bool] = True
ENABLE_TIMETABLE_LOOKUP:     Final[bool] = True
ENABLE_PERIOD_DETECTION:     Final[bool] = True   # NEW — controls background service

# ───────────────────────────────────────────────────────────────
# 📄 PAGINATION
# ───────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE:     Final[int] = 100

# ───────────────────────────────────────────────────────────────
# 📅 DATE & TIME
# ───────────────────────────────────────────────────────────────
DATE_FORMAT:     Final[str] = "%Y-%m-%d"
TIME_FORMAT:     Final[str] = "%H:%M:%S"
TIME_FORMAT_HM:  Final[str] = "%H:%M"
DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
TIMEZONE:        Final[str] = "UTC"

# ───────────────────────────────────────────────────────────────
# 🔁 RETRY CONFIG
# ───────────────────────────────────────────────────────────────
MAX_DATABASE_RETRIES:  Final[int]   = 3
DATABASE_RETRY_DELAY:  Final[float] = 1.0
