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

Changes (2026-04 — student dashboard pass)
------------------------------------------
- AttendanceStatus enum + STATUS_COLORS / BAND_COLORS constants.
- New response schemas for student-facing endpoints:
    PeriodCardSchema, DashboardSummarySchema, StudentDashboardResponse,
    CourseColorSchema, TimetableResponse,
    CourseAttendanceStat, AttendanceSummaryResponse,
    EnrichedAttendanceRecord, PaginatedAttendanceHistoryResponse,
    AttendanceWarningCourse, AttendanceWarningsResponse.
"""

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, validator, root_validator, model_validator


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
# SHARED CONSTANTS — colour maps used by student-facing schemas
# =========================================================================

class AttendanceStatus(str, Enum):
    """Possible attendance states for a student in a given period."""
    present = "present"
    absent  = "absent"
    late    = "late"
    pending = "pending"   # period in progress or not yet started


# Hex colours for each status — consumed directly by frontend renderers.
STATUS_COLORS: Dict[str, str] = {
    AttendanceStatus.present: "#22C55E",   # green-500
    AttendanceStatus.absent:  "#EF4444",   # red-500
    AttendanceStatus.late:    "#F59E0B",   # amber-500
    AttendanceStatus.pending: "#94A3B8",   # slate-400
}

class AttendanceBand(str, Enum):
    safe    = "safe"      # ≥ 85 %
    warning = "warning"   # 75 – 85 %
    danger  = "danger"    # < 75 %

BAND_COLORS: Dict[str, str] = {
    AttendanceBand.safe:    "#22C55E",
    AttendanceBand.warning: "#F59E0B",
    AttendanceBand.danger:  "#EF4444",
}


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
    class_id: Optional[str] = Field(
        None,
        description="Class the student belongs to (FK → classes collection)"
    )
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
        json_schema_extra = {
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
    class_id: Optional[str] = Field(None, description="Class the student belongs to")
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
    classroom_id: Optional[str] = Field(
        None,
        description=(
            "Classroom / class identifier for per-classroom student filtering. "
            "When set, only students with matching class_id are loaded into "
            "this stream FAISS index."
        )
    )
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

# ── CIE ──────────────────────────────────────────────────────────────────────

class CIECreateRequest(BaseModel):
    cie_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    start_date: str = Field(..., description="ISO date YYYY-MM-DD (inclusive)")
    end_date: str = Field(..., description="ISO date YYYY-MM-DD (inclusive)")
    active_status: bool = Field(True)
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = None

    @validator("start_date")
    def validate_start_date(cls, v):
        return _validate_date_str(v, "start_date")

    @validator("end_date")
    def validate_end_date(cls, v):
        return _validate_date_str(v, "end_date")

    @root_validator(skip_on_failure=True)
    def end_after_start(cls, values):
        s, e = values.get("start_date"), values.get("end_date")
        if s and e and e < s:
            raise ValueError("end_date must be on or after start_date")
        return values


class CIEResponse(BaseModel):
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
    class_id: str = Field(..., min_length=1, max_length=50)
    cie_id: str
    semester: int = Field(..., ge=1, le=10)
    section: str = Field(..., min_length=1, max_length=5)
    classroom_name: str = Field(..., min_length=1, max_length=100)
    capacity: Optional[int] = Field(None, ge=1, le=500)
    course_codes: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


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
    period_id: str = Field(..., min_length=1, max_length=80)
    class_id: str
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str
    end_time: str
    course_code: str = Field(..., min_length=1, max_length=20)
    course_name: str = Field(..., min_length=2, max_length=150)
    faculty_id: str
    is_lab_class: bool = False
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    room_override: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("start_time")
    def validate_start_time(cls, v):
        return _validate_time_str(v, "start_time")

    @validator("end_time")
    def validate_end_time(cls, v):
        return _validate_time_str(v, "end_time")

    @root_validator(skip_on_failure=True)
    def end_after_start(cls, values):
        s, e = values.get("start_time"), values.get("end_time")
        if s and e and e <= s:
            raise ValueError("end_time must be strictly after start_time")
        if s and e and values.get("duration_minutes") is None:
            try:
                sh, sm = map(int, s.split(":"))
                eh, em = map(int, e.split(":"))
                values["duration_minutes"] = (eh * 60 + em) - (sh * 60 + sm)
            except Exception:
                pass
        return values


class PeriodResponse(BaseModel):
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
        return ["Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"][self.day_of_week]


TimetableSchema = PeriodResponse


class PeriodListResponse(BaseModel):
    success: bool = True
    count: int
    periods: List[PeriodResponse]
    timestamp: datetime = Field(default_factory=datetime.now)


class ActivePeriodResponse(BaseModel):
    is_active: bool
    period: Optional[PeriodResponse] = None
    checked_at: datetime = Field(default_factory=datetime.now)
    message: str = ""


# ── Course Assignment ─────────────────────────────────────────────────────────

class CourseAssignmentCreateRequest(BaseModel):
    assignment_id: str = Field(..., min_length=1, max_length=100)
    faculty_id: str
    course_id: str = Field(..., min_length=1, max_length=20)
    class_id: str
    semester: int = Field(..., ge=1, le=10)
    academic_year: Optional[str] = Field(None, max_length=20)
    is_primary: bool = True
    metadata: Optional[Dict[str, Any]] = None


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
    faculty_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    department: str = Field(..., min_length=2, max_length=100)
    specialization: Optional[str] = Field(None, max_length=200)
    face_embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("face_embedding")
    def validate_face_embedding(cls, v):
        if v is not None and len(v) != 128:
            raise ValueError(f"face_embedding must be 128-dimensional, got {len(v)}")
        return v


class FacultyResponse(BaseModel):
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
    embedding: List[float] = Field(..., description="128-dim FaceNet embedding vector")

    @validator("embedding")
    def validate_embedding(cls, v):
        if len(v) != 128:
            raise ValueError(f"embedding must be 128-dimensional, got {len(v)}")
        return v


# ── Composite responses ───────────────────────────────────────────────────────

class ClassTimetableResponse(BaseModel):
    class_info: ClassResponse
    periods_by_day: Dict[str, List[PeriodResponse]] = Field(default_factory=dict)
    total_periods: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class FacultyDashboardResponse(BaseModel):
    faculty: FacultyResponse
    classes: List[ClassResponse] = Field(default_factory=list)
    today_periods: List[PeriodResponse] = Field(default_factory=list)
    active_period: Optional[PeriodResponse] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# =========================================================================
# NEW: Student-facing response schemas
# =========================================================================

# ── Period card (used by dashboard and timetable) ─────────────────────────────

class PeriodCardSchema(BaseModel):
    """
    A single period enriched with display metadata.

    Used in both the dashboard (today only) and the full weekly timetable.
    ``course_color`` is a deterministic hex colour for UI tinting.
    ``status`` / ``status_color`` are only populated by the dashboard endpoint.
    ``countdown_seconds`` is set for the currently-active period only.
    """
    period_id:          str
    start_time:         str
    end_time:           str
    duration_minutes:   Optional[int] = None
    course_code:        str
    course_name:        str
    faculty_id:         str
    faculty_name:       str
    is_lab_class:       bool = False
    room:               Optional[str] = None
    course_color:       str = Field(..., description="Hex colour for UI, e.g. '#6366F1'")
    # Dashboard-only fields
    status:             Optional[AttendanceStatus] = None
    status_color:       Optional[str] = Field(
        None, description="Hex colour matching status"
    )
    is_active:          Optional[bool] = None
    countdown_seconds:  Optional[int] = Field(
        None, description="Seconds remaining in the active period"
    )

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "period_id":         "CS-A-SEM6_MON_0900",
                "start_time":        "09:00",
                "end_time":          "10:00",
                "duration_minutes":  60,
                "course_code":       "CS401",
                "course_name":       "Machine Learning",
                "faculty_id":        "FAC01",
                "faculty_name":      "Dr. Priya Sharma",
                "is_lab_class":      False,
                "room":              None,
                "course_color":      "#6366F1",
                "status":            "present",
                "status_color":      "#22C55E",
                "is_active":         False,
                "countdown_seconds": None,
            }
        }


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardSummarySchema(BaseModel):
    """Count of today's periods broken down by status."""
    total:   int = 0
    present: int = 0
    absent:  int = 0
    late:    int = 0
    pending: int = 0


class OverallAttendanceSchema(BaseModel):
    """Compact attendance stat block used in the dashboard header."""
    percentage: float = Field(..., description="0.0 – 100.0")
    present:    int
    late:       int
    absent:     int
    total:      int
    band:       AttendanceBand
    color:      str = Field(..., description="Hex colour for band indicator")

    class Config:
        use_enum_values = True


class StudentDashboardResponse(BaseModel):
    """
    Full payload for GET /api/v1/student/dashboard.

    ``active_period`` is None between classes.
    ``countdown_seconds`` inside the active_period card is the seconds
    remaining until the class ends — intended for a live frontend timer.
    """
    today_date:          str
    day_name:            str
    active_period:       Optional[PeriodCardSchema] = None
    periods_today:       List[PeriodCardSchema]
    summary:             DashboardSummarySchema
    overall_attendance:  OverallAttendanceSchema
    generated_at:        datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "today_date":    "2026-04-30",
                "day_name":      "Thursday",
                "active_period": None,
                "periods_today": [],
                "summary":       {"total": 5, "present": 3, "absent": 1, "late": 0, "pending": 1},
                "overall_attendance": {
                    "percentage": 82.5, "present": 33, "late": 2,
                    "absent": 7, "total": 42, "band": "warning", "color": "#F59E0B"
                },
            }
        }


# ── Timetable ─────────────────────────────────────────────────────────────────

class CourseColorSchema(BaseModel):
    """Minimal course meta for the timetable legend."""
    name:  str
    color: str


class TimetableResponse(BaseModel):
    """
    Full payload for GET /api/v1/student/timetable.

    ``days`` keys are day names (Monday … Sunday).
    ``all_courses`` is a lookup map for the legend / filter chips.
    """
    class_id:    Optional[str]
    days:        Dict[str, List[PeriodCardSchema]]
    all_courses: Dict[str, CourseColorSchema]
    generated_at: datetime = Field(default_factory=datetime.now)


# ── Attendance summary ────────────────────────────────────────────────────────

class CourseAttendanceStat(BaseModel):
    """Per-course attendance stat line used in summary and warnings."""
    course_code:   str
    course_name:   str
    color:         str = Field(..., description="Course colour (timetable-consistent)")
    percentage:    float
    present:       int
    late:          int
    absent:        int
    total:         int
    band:          AttendanceBand
    band_color:    str
    required_consecutive_to_reach_75: int = Field(
        0,
        description=(
            "Minimum number of consecutive classes to attend to return to 75 %. "
            "0 when already at or above threshold."
        )
    )
    is_critical:   bool = Field(False, description="True when percentage < 75 %")

    class Config:
        use_enum_values = True


class AttendanceSummaryResponse(BaseModel):
    """Payload for GET /api/v1/student/attendance-summary."""
    overall:          OverallAttendanceSchema
    course_breakdown: List[CourseAttendanceStat]
    has_critical:     bool = False
    critical_courses: List[CourseAttendanceStat] = Field(default_factory=list)
    generated_at:     datetime = Field(default_factory=datetime.now)


# ── Paginated history ─────────────────────────────────────────────────────────

class EnrichedAttendanceRecord(BaseModel):
    """
    Single attendance record as returned by the history endpoint.

    Adds ``status_color`` and ``marked_by_name`` on top of the raw record
    stored in Firebase.
    """
    date:           str
    time:           Optional[str] = None
    timestamp:      Optional[str] = None
    course_code:    Optional[str] = None
    course_name:    Optional[str] = None
    status:         AttendanceStatus = AttendanceStatus.present
    status_color:   str
    confidence:     Optional[float] = None
    camera_id:      Optional[str] = None
    marked_by:      Optional[str] = None
    marked_by_name: Optional[str] = None
    track_id:       Optional[int] = None
    metadata:       Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True


class PaginatedAttendanceHistoryResponse(BaseModel):
    """Payload for GET /api/v1/student/attendance-history (enhanced)."""
    page:        int
    page_size:   int
    total:       int
    total_pages: int
    records:     List[EnrichedAttendanceRecord]
    generated_at: datetime = Field(default_factory=datetime.now)


# ── Warnings ──────────────────────────────────────────────────────────────────

class BandLegendEntry(BaseModel):
    label: str
    color: str


class AttendanceWarningsResponse(BaseModel):
    """
    Payload for GET /api/v1/student/warnings.

    ``has_critical_warning`` is True if at least one course is below 75 %.
    ``messages`` are human-readable strings ready to display in a banner.
    ``courses`` is a complete list (all bands) sorted by percentage asc.
    ``legend`` provides the colour key for the frontend badge renderer.
    """
    has_critical_warning: bool
    messages:             List[str]
    courses:              List[CourseAttendanceStat]
    legend: Dict[str, BandLegendEntry] = Field(
        default_factory=lambda: {
            "safe":    BandLegendEntry(label="> 85%",   color="#22C55E"),
            "warning": BandLegendEntry(label="75–85%",  color="#F59E0B"),
            "danger":  BandLegendEntry(label="< 75%",   color="#EF4444"),
        }
    )
    generated_at: datetime = Field(default_factory=datetime.now)
