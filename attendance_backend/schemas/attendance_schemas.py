"""
Request and response schemas for attendance API.

Defines Pydantic models for validation and documentation.

Changes (2026-04)
-----------------
- StudentRegistrationRequest / StudentInfo gain ``class_id`` field.
- New schemas: CIESchema, ClassSchema, PeriodSchema / TimetableSchema,
  CourseAssignmentSchema, FacultySchema (create + response variants).
- All new schemas validate required fields and cross-field constraints.
- Backward-compatible: existing fields unchanged.
"""

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, EmailStr, validator, root_validator


# ── Shared helpers ────────────────────────────────────────────────────────────

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_time_str(v: str, field_name: str = "time") -> str:
    if not _TIME_RE.match(v):
        raise ValueError(f"{field_name} must be in HH:MM format (24-hour), got '{v}'")
    h, m = map(int, v.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"{field_name} has invalid hour/minute values")
    return v


def _validate_date_str(v: str, field_name: str = "date") -> str:
    if not _DATE_RE.match(v):
        raise ValueError(f"{field_name} must be ISO date YYYY-MM-DD, got '{v}'")
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError(f"{field_name} is not a valid calendar date")
    return v


# =========================================================================
# EXISTING SCHEMAS — backward-compatible additions only
# =========================================================================

# ── Student Registration ───────────────────────────────────────────────────────

class StudentCreateSchema(BaseModel):
    """Minimal schema for creating a student (simple version)."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    courses: Optional[List[str]] = Field(default_factory=list)


class StudentRegistrationRequest(BaseModel):
    """Request to register a new student."""

    student_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    embeddings: List[List[float]] = Field(
        ..., description="List of face embeddings (128-dimensional)"
    )
    # ── NEW ──────────────────────────────────────────────────────────────────
    class_id: Optional[str] = Field(
        None,
        description="Class the student belongs to (FK → classes collection)"
    )
    # ─────────────────────────────────────────────────────────────────────────
    metadata: Optional[Dict[str, Any]] = Field(None)

    @validator("embeddings")
    def validate_embeddings(cls, v):
        if not v:
            raise ValueError("At least one embedding required")
        for emb in v:
            if len(emb) != 128:
                raise ValueError(
                    f"Each embedding must be 128-dimensional, got {len(emb)}"
                )
        return v

    class Config:
        schema_extra = {
            "example": {
                "student_id": "STU001",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "embeddings": [[0.1] * 128],
                "class_id": "CS-A-SEM6",
                "metadata": {"batch": 2024, "department": "CS"},
            }
        }


class StudentRegistrationResponse(BaseModel):
    success: bool
    student_id: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class StudentInfo(BaseModel):
    """Student information — returned by GET /students and GET /students/{id}."""

    student_id: str
    name: str
    email: str
    phone: Optional[str] = None
    registered_at: str
    last_seen: Optional[str] = None
    attendance_count: int = 0
    status: str = "active"
    # ── NEW ──────────────────────────────────────────────────────────────────
    class_id: Optional[str] = Field(
        None,
        description="Class the student belongs to"
    )
    # ─────────────────────────────────────────────────────────────────────────
    metadata: Optional[Dict[str, Any]] = None


class StudentListResponse(BaseModel):
    success: bool = True
    count: int
    students: List[StudentInfo]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Attendance Marking ────────────────────────────────────────────────────────

class MarkAttendanceRequest(BaseModel):
    student_id: str
    timestamp: Optional[datetime] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    track_id: Optional[int] = None
    camera_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AttendanceRecord(BaseModel):
    record_id: str
    student_id: str
    timestamp: str
    date: str
    time: str
    confidence: float
    track_id: Optional[int] = None
    camera_id: str
    status: str = "present"
    metadata: Optional[Dict[str, Any]] = None


class MarkAttendanceResponse(BaseModel):
    success: bool
    record_id: str
    student_id: str
    timestamp: str
    message: str


class AttendanceListResponse(BaseModel):
    success: bool = True
    count: int
    records: List[AttendanceRecord]
    timestamp: datetime = Field(default_factory=datetime.now)


class DailyReportResponse(BaseModel):
    date: str
    total_records: int
    unique_students: int
    records: List[AttendanceRecord]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Stream Configuration ──────────────────────────────────────────────────────

class StreamConfig(BaseModel):
    stream_id: str
    rtsp_url: str
    camera_name: Optional[str] = None
    location: Optional[str] = None
    enabled: bool = True
    frame_skip: int = Field(2, ge=1, le=5)
    min_consecutive_frames: int = Field(5, ge=1, le=20)
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0)
    # ── NEW ──────────────────────────────────────────────────────────────────
    classroom_id: Optional[str] = Field(
        None,
        description=(
            "Classroom / class identifier for per-classroom student filtering. "
            "When set, only students with matching class_id are loaded into "
            "this stream FAISS index."
        )
    )
    # ─────────────────────────────────────────────────────────────────────────
    metadata: Optional[Dict[str, Any]] = None


class StreamHealth(BaseModel):
    stream_id: str
    status: str
    last_frame: Optional[datetime] = None
    frames_processed: int = 0
    fps: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    uptime_seconds: int = 0


# ── Error Responses ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationErrorResponse(BaseModel):
    success: bool = False
    error: str = "Validation error"
    errors: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Batch Operations ──────────────────────────────────────────────────────────

class BatchRegisterRequest(BaseModel):
    students: List[StudentRegistrationRequest]

    @validator("students")
    def validate_students_list(cls, v):
        if not v:
            raise ValueError("At least one student required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 students per batch")
        return v


class BatchRegisterResponse(BaseModel):
    success: bool
    total: int
    registered: int
    failed: int
    errors: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class BatchMarkAttendanceRequest(BaseModel):
    records: List[MarkAttendanceRequest]

    @validator("records")
    def validate_records_list(cls, v):
        if not v:
            raise ValueError("At least one record required")
        if len(v) > 500:
            raise ValueError("Maximum 500 records per batch")
        return v


class BatchMarkAttendanceResponse(BaseModel):
    success: bool
    total: int
    marked: int
    failed: int
    errors: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Health & Stats ────────────────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, str]
    uptime_seconds: int = 0


class SystemStatsResponse(BaseModel):
    total_students: int = 0
    total_attendance_records: int = 0
    active_streams: int = 0
    total_detections_today: int = 0
    average_confidence: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


# =========================================================================
# NEW SCHEMAS — CIE / Class / Period / CourseAssignment / Faculty
# =========================================================================

# ── CIE (Continuous Internal Evaluation) ─────────────────────────────────────

class CIECreateRequest(BaseModel):
    """
    Request body for POST /cie.

    A CIE represents an examination period (e.g. CIE-1, CIE-2, End-Sem).
    All attendance records taken while a CIE is active are automatically
    associated with it via the attendance metadata.
    """

    cie_id: str = Field(
        ..., min_length=1, max_length=50,
        description="Unique CIE identifier, e.g. 'CIE2026-1'"
    )
    name: str = Field(
        ..., min_length=2, max_length=100,
        description="Human-readable name, e.g. 'CIE-1 April 2026'"
    )
    start_date: str = Field(
        ..., description="ISO date YYYY-MM-DD (inclusive)"
    )
    end_date: str = Field(
        ..., description="ISO date YYYY-MM-DD (inclusive)"
    )
    active_status: bool = Field(True, description="True if this CIE is currently running")
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = None

    @validator("start_date")
    def validate_start_date(cls, v):
        return _validate_date_str(v, "start_date")

    @validator("end_date")
    def validate_end_date(cls, v):
        return _validate_date_str(v, "end_date")

    @root_validator
    def end_after_start(cls, values):
        s, e = values.get("start_date"), values.get("end_date")
        if s and e and e < s:
            raise ValueError("end_date must be on or after start_date")
        return values

    class Config:
        schema_extra = {
            "example": {
                "cie_id": "CIE2026-1",
                "name": "CIE-1 April 2026",
                "start_date": "2026-04-01",
                "end_date": "2026-04-15",
                "active_status": True,
            }
        }


class CIEResponse(BaseModel):
    """CIE document as returned by the API."""

    cie_id: str
    name: str
    start_date: str
    end_date: str
    active_status: bool
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CIEListResponse(BaseModel):
    success: bool = True
    count: int
    cie_list: List[CIEResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Class ─────────────────────────────────────────────────────────────────────

class ClassCreateRequest(BaseModel):
    """
    Request body for POST /classes.

    A Class ties together a group of students, a semester, a section, and a
    CIE period.  Every student document has a ``class_id`` FK to this.
    """

    class_id: str = Field(
        ..., min_length=1, max_length=50,
        description="Unique class ID, e.g. 'CS-A-SEM6'"
    )
    cie_id: str = Field(..., description="FK → CIE this class belongs to")
    semester: int = Field(..., ge=1, le=10, description="Semester number (1–10)")
    section: str = Field(
        ..., min_length=1, max_length=5,
        description="Section label, e.g. 'A', 'B', 'Lab-1'"
    )
    classroom_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Default classroom, e.g. 'Block-B Room 204'"
    )
    capacity: Optional[int] = Field(
        None, ge=1, le=500,
        description="Maximum number of students"
    )
    course_codes: Optional[List[str]] = Field(
        None, description="List of course codes taught in this class"
    )
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "class_id": "CS-A-SEM6",
                "cie_id": "CIE2026-1",
                "semester": 6,
                "section": "A",
                "classroom_name": "Block-B Room 204",
                "capacity": 60,
                "course_codes": ["CS401", "CS402", "CS403"],
            }
        }


class ClassResponse(BaseModel):
    class_id: str
    cie_id: str
    semester: int
    section: str
    classroom_name: str
    capacity: Optional[int] = None
    course_codes: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClassListResponse(BaseModel):
    success: bool = True
    count: int
    classes: List[ClassResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Period / Timetable ────────────────────────────────────────────────────────

class PeriodCreateRequest(BaseModel):
    """
    Request body for POST /periods.

    One row in the timetable: a single class on a specific day/time.
    ``duration_minutes`` is auto-computed from start/end if omitted.
    """

    period_id: str = Field(
        ..., min_length=1, max_length=80,
        description=(
            "Unique period ID. Convention: '{class_id}_{DAY}_{HHMM}', "
            "e.g. 'CS-A-SEM6_MON_0900'"
        )
    )
    class_id: str = Field(..., description="FK → classes")
    day_of_week: int = Field(
        ..., ge=0, le=6,
        description="0=Monday … 6=Sunday"
    )
    start_time: str = Field(..., description="HH:MM (24-hour)")
    end_time: str = Field(..., description="HH:MM (24-hour)")
    course_code: str = Field(..., min_length=1, max_length=20)
    course_name: str = Field(..., min_length=2, max_length=150)
    faculty_id: str = Field(..., description="FK → faculty")
    is_lab_class: bool = Field(False, description="True for lab/practical sessions")
    duration_minutes: Optional[int] = Field(
        None, ge=1, le=480,
        description="Auto-computed from start/end if omitted"
    )
    room_override: Optional[str] = Field(
        None,
        description="Override the class default classroom for this slot"
    )
    metadata: Optional[Dict[str, Any]] = None

    @validator("start_time")
    def validate_start_time(cls, v):
        return _validate_time_str(v, "start_time")

    @validator("end_time")
    def validate_end_time(cls, v):
        return _validate_time_str(v, "end_time")

    @root_validator
    def end_after_start(cls, values):
        s, e = values.get("start_time"), values.get("end_time")
        if s and e and e <= s:
            raise ValueError("end_time must be strictly after start_time")
        # Auto-compute duration_minutes if not provided
        if s and e and values.get("duration_minutes") is None:
            try:
                sh, sm = map(int, s.split(":"))
                eh, em = map(int, e.split(":"))
                values["duration_minutes"] = (eh * 60 + em) - (sh * 60 + sm)
            except Exception:
                pass
        return values

    class Config:
        schema_extra = {
            "example": {
                "period_id": "CS-A-SEM6_MON_0900",
                "class_id": "CS-A-SEM6",
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "10:00",
                "course_code": "CS401",
                "course_name": "Machine Learning",
                "faculty_id": "FAC01",
                "is_lab_class": False,
            }
        }


class PeriodResponse(BaseModel):
    """
    Timetable period as returned by the API.
    Also aliased as ``TimetableSchema`` for semantic clarity in route docs.
    """

    period_id: str
    class_id: str
    day_of_week: int
    start_time: str
    end_time: str
    course_code: str
    course_name: str
    faculty_id: str
    is_lab_class: bool = False
    duration_minutes: Optional[int] = None
    room_override: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def day_name(self) -> str:
        """Human-readable day name derived from day_of_week."""
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
            self.day_of_week
        ]


# Alias so route files can import ``TimetableSchema`` for semantic clarity
TimetableSchema = PeriodResponse


class PeriodListResponse(BaseModel):
    success: bool = True
    count: int
    periods: List[PeriodResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


class ActivePeriodResponse(BaseModel):
    """
    Response for GET /periods/active — what is running right now.

    ``is_active`` is True when a period was found; False means no class
    is currently scheduled (e.g. break, outside hours).
    """

    is_active: bool
    period: Optional[PeriodResponse] = None
    checked_at: datetime = Field(default_factory=datetime.now)
    message: str = ""

    class Config:
        schema_extra = {
            "example": {
                "is_active": True,
                "period": {
                    "period_id": "CS-A-SEM6_MON_0900",
                    "class_id": "CS-A-SEM6",
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "course_code": "CS401",
                    "course_name": "Machine Learning",
                    "faculty_id": "FAC01",
                    "is_lab_class": False,
                    "duration_minutes": 60,
                },
                "checked_at": "2026-04-29T09:30:00",
                "message": "CS401 Machine Learning is currently running",
            }
        }


# ── Course Assignment ─────────────────────────────────────────────────────────

class CourseAssignmentCreateRequest(BaseModel):
    """
    Request body for POST /course-assignments.

    Ties a faculty member to a course and a class for a semester.
    One faculty may have multiple assignments (e.g. teaches ML to two sections).
    """

    assignment_id: str = Field(
        ..., min_length=1, max_length=100,
        description=(
            "Unique assignment ID. Convention: '{faculty_id}_{course_id}_{class_id}', "
            "e.g. 'FAC01_CS401_CS-A-SEM6'"
        )
    )
    faculty_id: str = Field(..., description="FK → faculty")
    course_id: str = Field(..., min_length=1, max_length=20, description="Course code / ID")
    class_id: str = Field(..., description="FK → classes")
    semester: int = Field(..., ge=1, le=10)
    academic_year: Optional[str] = Field(
        None, max_length=20,
        description="e.g. '2025-2026'"
    )
    is_primary: bool = Field(
        True,
        description=(
            "True if this is the primary instructor. "
            "False for co-instructors / TAs."
        )
    )
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "assignment_id": "FAC01_CS401_CS-A-SEM6",
                "faculty_id": "FAC01",
                "course_id": "CS401",
                "class_id": "CS-A-SEM6",
                "semester": 6,
                "academic_year": "2025-2026",
                "is_primary": True,
            }
        }


class CourseAssignmentResponse(BaseModel):
    assignment_id: str
    faculty_id: str
    course_id: str
    class_id: str
    semester: int
    academic_year: Optional[str] = None
    is_primary: bool = True
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CourseAssignmentListResponse(BaseModel):
    success: bool = True
    count: int
    assignments: List[CourseAssignmentResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


# ── Faculty ───────────────────────────────────────────────────────────────────

class FacultyCreateRequest(BaseModel):
    """
    Request body for POST /faculty.

    ``face_embedding`` is optional at creation time and can be added later
    via ``POST /faculty/{faculty_id}/embedding``.  When present it must be
    the same 128-dimensional FaceNet vector format used for students so that
    recognition pipeline code requires no changes.
    """

    faculty_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    department: str = Field(
        ..., min_length=2, max_length=100,
        description="Academic department, e.g. 'Computer Science'"
    )
    specialization: Optional[str] = Field(
        None, max_length=200,
        description="Research / teaching specialization"
    )
    face_embedding: Optional[List[float]] = Field(
        None,
        description="128-dim FaceNet embedding vector (same format as students)"
    )
    metadata: Optional[Dict[str, Any]] = None

    @validator("face_embedding")
    def validate_face_embedding(cls, v):
        if v is not None and len(v) != 128:
            raise ValueError(
                f"face_embedding must be 128-dimensional, got {len(v)}"
            )
        return v

    class Config:
        schema_extra = {
            "example": {
                "faculty_id": "FAC01",
                "name": "Dr. Priya Sharma",
                "email": "priya@college.edu",
                "phone": "+919876543210",
                "department": "Computer Science",
                "specialization": "Machine Learning, Computer Vision",
            }
        }


class FacultyResponse(BaseModel):
    """Faculty member as returned by the API (embedding excluded by default)."""

    faculty_id: str
    name: str
    email: str
    phone: Optional[str] = None
    department: str
    specialization: Optional[str] = None
    status: str = "active"
    has_face_embedding: bool = False
    embedding_updated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "FacultyResponse":
        """
        Build a FacultyResponse from a raw Firestore document dict.

        Converts ``face_embedding`` presence to a boolean so the raw vector
        is never accidentally serialised into an API response.
        """
        return cls(
            faculty_id=doc.get("faculty_id", ""),
            name=doc.get("name", ""),
            email=doc.get("email", ""),
            phone=doc.get("phone"),
            department=doc.get("department", ""),
            specialization=doc.get("specialization"),
            status=doc.get("status", "active"),
            has_face_embedding=bool(doc.get("face_embedding")),
            embedding_updated_at=doc.get("embedding_updated_at"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            metadata=doc.get("metadata"),
        )


class FacultyListResponse(BaseModel):
    success: bool = True
    count: int
    faculty: List[FacultyResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


class FacultyEmbeddingRequest(BaseModel):
    """Request body for POST /faculty/{faculty_id}/embedding."""

    embedding: List[float] = Field(
        ..., description="128-dim FaceNet embedding vector"
    )

    @validator("embedding")
    def validate_embedding(cls, v):
        if len(v) != 128:
            raise ValueError(f"embedding must be 128-dimensional, got {len(v)}")
        return v


# ── Composite response used by teacher dashboard ──────────────────────────────

class ClassTimetableResponse(BaseModel):
    """
    Full timetable for a class — returned by GET /classes/{class_id}/timetable.

    Groups periods by day for easy frontend rendering.
    """

    class_info: ClassResponse
    periods_by_day: Dict[str, List[PeriodResponse]] = Field(
        default_factory=dict,
        description=(
            "Keys are day names ('Monday' … 'Sunday'). "
            "Values are lists of periods ordered by start_time."
        )
    )
    total_periods: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class FacultyDashboardResponse(BaseModel):
    """
    Summary response for GET /faculty/{faculty_id}/dashboard.

    All the data a faculty member's dashboard needs in a single call.
    """

    faculty: FacultyResponse
    classes: List[ClassResponse] = Field(
        default_factory=list,
        description="All classes this faculty teaches"
    )
    today_periods: List[PeriodResponse] = Field(
        default_factory=list,
        description="Periods scheduled for today, ordered by start_time"
    )
    active_period: Optional[PeriodResponse] = Field(
        None,
        description="Currently running period (None if between classes)"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
