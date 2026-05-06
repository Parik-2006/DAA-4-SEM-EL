"""
schemas/attendance_schemas.py
────────────────────────────────────────────────────────────────────────────────
Request and response schemas for the attendance API.

Changelog
---------
2026-04 (original)
  • StudentRegistrationRequest / StudentInfo gain ``class_id``.
  • CIE / Class / Period / CourseAssignment / Faculty schemas.
  • AttendanceStatus enum + STATUS_COLORS / BAND_COLORS constants.
  • Student-dashboard schemas: PeriodCardSchema, DashboardSummarySchema,
    StudentDashboardResponse, CourseColorSchema, TimetableResponse,
    CourseAttendanceStat, AttendanceSummaryResponse,
    EnrichedAttendanceRecord, PaginatedAttendanceHistoryResponse,
    AttendanceWarningsResponse.

2026-04 (role-specific pass)
  • AdminDashboardResponse, AdminTodayBreakdown — system-wide KPIs.
  • SectionAttendanceEntry, AdminSectionBreakdownResponse — section table.
  • TrendPoint, AdminTrendResponse — 7/30-day trend for admin charts.
  • AttendanceWindowSchema — open/grace/locked window descriptor.
  • TeacherRosterStudentEntry, TeacherRosterSummary,
    TeacherActiveClassResponse — teacher marking-UI roster.
  • TeacherDashboardPeriodSummary, TeacherDashboardAttendanceCounts,
    TeacherDashboardResponse — full teacher dashboard payload.
  • StudentSafeAttendanceRecord — student-facing record (sensitive fields stripped).
  • RealtimeTokenResponse — WebSocket/SSE token payload.

All existing schemas are backward-compatible (no fields removed).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, root_validator, validator


# ── Shared helpers ────────────────────────────────────────────────────────────

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_time_str(v: str, field_name: str = "time") -> str:
    if not _TIME_RE.match(v):
        raise ValueError(f"{field_name} must be HH:MM (24-hour), got '{v}'")
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


# ── Shared colour constants ───────────────────────────────────────────────────

class AttendanceStatus(str, Enum):
    """Possible attendance states for a student in a given period."""
    present = "present"
    absent  = "absent"
    late    = "late"
    pending = "pending"   # period in progress or not yet started


STATUS_COLORS: Dict[str, str] = {
    AttendanceStatus.present: "#22C55E",   # green-500
    AttendanceStatus.absent:  "#EF4444",   # red-500
    AttendanceStatus.late:    "#F59E0B",   # amber-500
    AttendanceStatus.pending: "#94A3B8",   # slate-400
}


class AttendanceBand(str, Enum):
    safe    = "safe"     # >= 85 %
    warning = "warning"  # 75-85 %
    danger  = "danger"   # < 75 %


BAND_COLORS: Dict[str, str] = {
    AttendanceBand.safe:    "#22C55E",
    AttendanceBand.warning: "#F59E0B",
    AttendanceBand.danger:  "#EF4444",
}


# =========================================================================
# STUDENT REGISTRATION & INFO
# =========================================================================

class StudentCreateSchema(BaseModel):
    """Minimal schema for creating a student."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    courses: Optional[List[str]] = Field(default_factory=list)


class StudentRegistrationRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    embeddings: List[List[float]] = Field(
        ..., description="List of face embeddings (128-dimensional)"
    )
    class_id: Optional[str] = Field(
        None, description="Class the student belongs to (FK -> classes collection)"
    )
    metadata: Optional[Dict[str, Any]] = None

    @validator("embeddings")
    def validate_embeddings(cls, v):
        if not v:
            raise ValueError("At least one embedding required")
        for emb in v:
            if len(emb) != 128:
                raise ValueError(f"Each embedding must be 128-dim, got {len(emb)}")
        return v

    class Config:
        json_schema_extra = {"example": {
            "student_id": "STU001", "name": "John Doe",
            "email": "john@example.com", "phone": "+1234567890",
            "embeddings": [[0.1] * 128], "class_id": "CS-A-SEM6",
        }}


class StudentRegistrationResponse(BaseModel):
    success: bool
    student_id: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class StudentInfo(BaseModel):
    student_id: str
    name: str
    email: str
    phone: Optional[str] = None
    registered_at: str
    last_seen: Optional[str] = None
    attendance_count: int = 0
    status: str = "active"
    class_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StudentListResponse(BaseModel):
    success: bool = True
    count: int
    students: List[StudentInfo]
    timestamp: datetime = Field(default_factory=datetime.now)


# =========================================================================
# ATTENDANCE MARKING
# =========================================================================

class MarkAttendanceRequest(BaseModel):
    student_id: str
    section_id: Optional[str] = None  # Optional for backward compatibility, should become required
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


# =========================================================================
# STREAM CONFIGURATION
# =========================================================================

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


# =========================================================================
# ERROR / BATCH / HEALTH
# =========================================================================

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
# CIE
# =========================================================================

class CIECreateRequest(BaseModel):
    cie_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    start_date: str = Field(..., description="ISO date YYYY-MM-DD (inclusive)")
    end_date: str = Field(..., description="ISO date YYYY-MM-DD (inclusive)")
    active_status: bool = True
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = None

    @validator("start_date")
    def val_start(cls, v): return _validate_date_str(v, "start_date")

    @validator("end_date")
    def val_end(cls, v): return _validate_date_str(v, "end_date")

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


# =========================================================================
# CLASS
# =========================================================================

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


# =========================================================================
# PERIOD / TIMETABLE
# =========================================================================

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
    def val_start(cls, v): return _validate_time_str(v, "start_time")

    @validator("end_time")
    def val_end(cls, v): return _validate_time_str(v, "end_time")

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


# Alias kept for backward compatibility
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


# =========================================================================
# COURSE ASSIGNMENT
# =========================================================================

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


# =========================================================================
# FACULTY
# =========================================================================

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
            raise ValueError(f"face_embedding must be 128-dim, got {len(v)}")
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
            raise ValueError(f"embedding must be 128-dim, got {len(v)}")
        return v


# =========================================================================
# COMPOSITE RESPONSES (timetable / faculty dashboard)
# =========================================================================

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
# STUDENT-FACING SCHEMAS
# =========================================================================

class PeriodCardSchema(BaseModel):
    """
    A single period enriched with display metadata.

    Used in both the dashboard (today only) and the full weekly timetable.
    ``course_color`` is a deterministic hex colour for UI tinting.
    ``status`` / ``status_color`` are only populated by the dashboard endpoint.
    ``countdown_seconds`` is set for the currently-active period only.
    """
    period_id:         str
    start_time:        str
    end_time:          str
    duration_minutes:  Optional[int] = None
    course_code:       str
    course_name:       str
    faculty_id:        str
    faculty_name:      str
    is_lab_class:      bool = False
    room:              Optional[str] = None
    course_color:      str = Field(..., description="Hex colour for UI, e.g. '#6366F1'")
    # Dashboard-only fields
    status:            Optional[AttendanceStatus] = None
    status_color:      Optional[str] = None
    is_active:         Optional[bool] = None
    countdown_seconds: Optional[int] = Field(
        None, description="Seconds remaining in the active period"
    )

    class Config:
        use_enum_values = True


class DashboardSummarySchema(BaseModel):
    """Count of today's periods broken down by status."""
    total:   int = 0
    present: int = 0
    absent:  int = 0
    late:    int = 0
    pending: int = 0


class OverallAttendanceSchema(BaseModel):
    """Compact attendance stat block used in the dashboard header."""
    percentage: float = Field(..., description="0.0 - 100.0")
    present:    int
    late:       int
    absent:     int
    total:      int
    band:       AttendanceBand
    color:      str = Field(..., description="Hex colour for band indicator")

    class Config:
        use_enum_values = True


class StudentDashboardResponse(BaseModel):
    """Full payload for GET /api/v1/student/dashboard."""
    today_date:         str
    day_name:           str
    active_period:      Optional[PeriodCardSchema] = None
    periods_today:      List[PeriodCardSchema]
    summary:            DashboardSummarySchema
    overall_attendance: OverallAttendanceSchema
    generated_at:       datetime = Field(default_factory=datetime.now)


class CourseColorSchema(BaseModel):
    """Minimal course meta for the timetable legend."""
    name:  str
    color: str


class TimetableResponse(BaseModel):
    """
    Full payload for GET /api/v1/student/timetable.

    ``days`` keys are day names (Monday ... Sunday).
    ``all_courses`` is a lookup map for the legend / filter chips.
    """
    class_id:     Optional[str]
    days:         Dict[str, List[PeriodCardSchema]]
    all_courses:  Dict[str, CourseColorSchema]
    generated_at: datetime = Field(default_factory=datetime.now)


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
            "Minimum consecutive classes to attend to return to 75%. "
            "0 when already at or above threshold."
        )
    )
    is_critical:   bool = Field(False, description="True when percentage < 75%")

    class Config:
        use_enum_values = True


class AttendanceSummaryResponse(BaseModel):
    """Payload for GET /api/v1/student/attendance-summary."""
    overall:          OverallAttendanceSchema
    course_breakdown: List[CourseAttendanceStat]
    has_critical:     bool = False
    critical_courses: List[CourseAttendanceStat] = Field(default_factory=list)
    generated_at:     datetime = Field(default_factory=datetime.now)


class EnrichedAttendanceRecord(BaseModel):
    """Single attendance record as returned by the history endpoint."""
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
    """Payload for GET /api/v1/student/attendance-history."""
    page:        int
    page_size:   int
    total:       int
    total_pages: int
    records:     List[EnrichedAttendanceRecord]
    generated_at: datetime = Field(default_factory=datetime.now)


class BandLegendEntry(BaseModel):
    label: str
    color: str


class AttendanceWarningsResponse(BaseModel):
    """
    Payload for GET /api/v1/student/warnings.

    ``has_critical_warning`` is True if at least one course is below 75%.
    ``messages`` are human-readable strings ready to display in a banner.
    ``courses`` is a complete list (all bands) sorted by percentage asc.
    ``legend`` provides the colour key for the frontend badge renderer.
    """
    has_critical_warning: bool
    messages:             List[str]
    courses:              List[CourseAttendanceStat]
    legend: Dict[str, BandLegendEntry] = Field(
        default_factory=lambda: {
            "safe":    BandLegendEntry(label="> 85%",  color="#22C55E"),
            "warning": BandLegendEntry(label="75-85%", color="#F59E0B"),
            "danger":  BandLegendEntry(label="< 75%",  color="#EF4444"),
        }
    )
    generated_at: datetime = Field(default_factory=datetime.now)


# =========================================================================
# ADMIN SCHEMAS
# =========================================================================

class AdminTodayBreakdown(BaseModel):
    """Detailed today counts for the admin KPI card."""
    present:        int = 0
    late:           int = 0
    absent:         int = 0
    pending:        int = 0
    total_expected: int = 0
    total_marked:   int = 0


class AdminDashboardResponse(BaseModel):
    """
    System-wide KPI response for GET /api/v1/admin/analytics/overview.

    Fields
    ------
    total_students          - registered student count
    total_sections          - active (non-deleted) class count
    overall_attendance_rate - (present+late) / total_students for today
    today_breakdown         - detailed counts for today
    active_periods_now      - number of periods currently in progress
    generated_at            - ISO-8601 UTC
    """
    total_students:          int
    total_sections:          int
    overall_attendance_rate: float = Field(..., description="0.0 - 100.0")
    today_breakdown:         AdminTodayBreakdown
    active_periods_now:      int = 0
    generated_at:            str


class SectionAttendanceEntry(BaseModel):
    """
    One row of the admin section-breakdown table.

    Returned by GET /api/v1/admin/analytics/sections.
    """
    section_id:      str
    section_name:    str
    course_code:     str
    course_name:     str
    semester:        str
    section_label:   str
    faculty_id:      str
    total_students:  int
    present:         int
    late:            int
    absent:          int
    pending:         int
    attendance_rate: float = Field(..., description="0.0 - 100.0")


class AdminSectionBreakdownResponse(BaseModel):
    """Payload for GET /api/v1/admin/analytics/sections."""
    date:           str
    total_sections: int
    sections:       List[SectionAttendanceEntry]
    generated_at:   str


class TrendPoint(BaseModel):
    """Single data point in the attendance trend series."""
    date:         str
    present:      int
    late:         int
    absent:       int
    total_marked: int
    rate:         float = Field(..., description="Attendance rate 0.0 - 100.0")


class AdminTrendResponse(BaseModel):
    """Payload for GET /api/v1/admin/analytics/trends."""
    days:           int
    total_students: int
    trend:          List[TrendPoint]
    generated_at:   str


# =========================================================================
# TEACHER SCHEMAS
# =========================================================================

class AttendanceWindowSchema(BaseModel):
    """
    Describes the open/grace/locked state of an attendance window.

    Mirrors the dict returned by AttendanceLockService.get_window_status().
    """
    is_open:   bool
    phase:     str = Field(..., description="open | grace | locked")
    can_edit:  bool
    message:   str
    opens_at:  Optional[str] = None
    closes_at: Optional[str] = None
    locked_at: Optional[str] = None


class TeacherRosterStudentEntry(BaseModel):
    """
    Single student row in the teacher's active-class roster.

    ``attendance_status`` is None when not yet marked.
    """
    student_id:        str
    name:              str
    email:             str
    roll_number:       Optional[str] = None
    face_thumbnail:    Optional[str] = Field(
        None, description="URL or base64 preview for face recognition UI"
    )
    attendance_status: Optional[AttendanceStatus] = Field(
        None, description="None = not yet marked"
    )
    is_marked:         bool = False

    class Config:
        use_enum_values = True


class TeacherRosterSummary(BaseModel):
    total_students: int
    present:        int
    late:           int
    absent:         int
    not_marked:     int


class TeacherActiveClassResponse(BaseModel):
    """
    Payload for GET /api/v1/teacher/active-class.

    This is the roster view shown in the teacher's marking UI.
    Only students enrolled in the teacher's assigned section appear here.
    """
    is_active: bool
    period:    Optional[Dict[str, Any]] = None
    window:    Optional[AttendanceWindowSchema] = None
    date:      str
    class_id:  str
    roster:    List[TeacherRosterStudentEntry]
    summary:   TeacherRosterSummary
    checked_at: str

    class Config:
        populate_by_name = True


class TeacherDashboardAttendanceCounts(BaseModel):
    present:      int = 0
    late:         int = 0
    absent:       int = 0
    total_marked: int = 0


class TeacherDashboardPeriodSummary(BaseModel):
    """
    Period card enriched with live attendance counts.

    Used in the teacher dashboard schedule list.
    """
    period_id:         str
    course_code:       str
    course_name:       str
    start_time:        str
    end_time:          str
    class_id:          str
    day_of_week:       int
    is_lab_class:      bool = False
    window:            Optional[AttendanceWindowSchema] = None
    attendance_counts: TeacherDashboardAttendanceCounts
    is_current:        bool = False


class TeacherDashboardResponse(BaseModel):
    """
    Full payload for GET /api/v1/teacher/dashboard.

    Scoped to sections assigned to the teacher - no foreign sections included.
    """
    faculty_id:        str
    date:              str
    day:               str
    assigned_sections: List[str] = Field(description="class_ids this teacher owns")
    total_periods:     int
    schedule:          List[TeacherDashboardPeriodSummary]
    active_period:     Optional[TeacherDashboardPeriodSummary] = None
    generated_at:      str
    config:            Dict[str, Any] = Field(
        default_factory=dict,
        description="System config echoed for the frontend (window/late thresholds)"
    )


# =========================================================================
# STUDENT SAFE-VIEW SCHEMAS
# =========================================================================

class StudentSafeAttendanceRecord(BaseModel):
    """
    A single attendance record safe to return to the authenticated student.

    Strips: class_id, faculty_id, method, internal keys.
    Exposes period_id so the student can correlate with their timetable.
    """
    date:         str
    time:         Optional[str] = None
    period_id:    Optional[str] = None
    course_code:  Optional[str] = None
    status:       AttendanceStatus
    status_color: str = Field(
        ..., description="Hex colour matching status for direct frontend use"
    )
    confidence:   Optional[float] = Field(
        None, description="Face recognition confidence - shown as informational hint"
    )

    class Config:
        use_enum_values = True

    @classmethod
    def from_record(cls, rec: Dict[str, Any]) -> "StudentSafeAttendanceRecord":
        status = rec.get("status", AttendanceStatus.pending)
        marked_at = rec.get("markedAt", "")
        time_val = rec.get("time") or (marked_at[:8] if marked_at else None)
        return cls(
            date=rec.get("date", ""),
            time=time_val,
            period_id=rec.get("period_id"),
            course_code=rec.get("course_code") or rec.get("metadata", {}).get("course_code"),
            status=status,
            status_color=STATUS_COLORS.get(status, "#94A3B8"),
            confidence=rec.get("confidence"),
        )


# =========================================================================
# REAL-TIME TOKEN
# =========================================================================

class RealtimeTokenResponse(BaseModel):
    """
    Payload for GET /api/v1/student/realtime/token.

    The student uses ``ws_url`` or ``sse_url`` to connect to the real-time
    stream for their classroom. Tokens expire after 60 minutes.
    """
    token:      str = Field(..., description="Short-lived real-time auth token")
    section_id: str = Field(..., description="class_id the token is scoped to")
    expires_at: str = Field(..., description="ISO-8601 UTC expiry timestamp")
    ws_url:     str = Field(..., description="WebSocket URL including token in query string")
    sse_url:    str = Field(..., description="SSE URL including token in query string")