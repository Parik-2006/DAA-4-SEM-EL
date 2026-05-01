"""
schemas/teacher_schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic request / response models used exclusively by api/teacher.py and
the enhanced attendance marking paths.

These supplement the existing attendance_schemas.py without modifying it,
keeping backward compatibility for all existing routes.

Model inventory
---------------
BulkAttendanceItem          — one student row in a bulk-mark request
BulkMarkRequest             — POST /teacher/mark-bulk body
BulkMarkResult              — per-student outcome (in response)
BulkMarkResponse            — full response for mark-bulk

AttendanceEditRequest       — PATCH /teacher/attendance/{record_id} body
AttendanceEditResponse      — response with record + audit trail

WindowStatus                — attendance window open/grace/locked detail
PeriodScheduleItem          — one period row on the teacher dashboard
TeacherDashboardResponse    — full GET /teacher/dashboard response

StudentRosterItem           — one student in the active-class roster
ActiveClassResponse         — GET /teacher/active-class response

LockResponse                — POST /teacher/period/{id}/lock response

AuditEntry                  — single entry in an attendance audit trail
AuditTrailResponse          — GET /teacher/attendance/{id}/audit response

DailyReportPeriodBreakdown  — per-period section of a daily report
DailyReportStudentSummary   — per-student section of a daily report
DailyReportResponse         — full daily report (from attendance_service)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


# ── Shared validators ──────────────────────────────────────────────────────────

_VALID_STATUSES = {"present", "absent", "late", "excused"}


def _validate_status(v: str) -> str:
    v = v.strip().lower()
    if v not in _VALID_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(_VALID_STATUSES)}, got '{v}'"
        )
    return v


def _validate_date(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("date must be YYYY-MM-DD")
    return v


# ══════════════════════════════════════════════════════════════════════════════
# Bulk mark
# ══════════════════════════════════════════════════════════════════════════════

class BulkAttendanceItem(BaseModel):
    """One student row inside a bulk-mark request."""

    student_id: str  = Field(..., min_length=1, max_length=50)
    status:     str  = Field(
        "present",
        description="One of: present, absent, late, excused",
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    note:       Optional[str] = Field(None, max_length=300)

    @validator("status")
    def validate_status(cls, v):
        return _validate_status(v)

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU001",
                "status":     "present",
                "confidence": 0.97,
            }
        }


class BulkMarkRequest(BaseModel):
    """Request body for POST /teacher/mark-bulk."""

    period_id:       str = Field(..., min_length=1, max_length=100)
    class_id:        str = Field(..., min_length=1, max_length=50)
    date:            Optional[str] = Field(
        None,
        description="Date YYYY-MM-DD (defaults to today)",
    )
    attendance_list: List[BulkAttendanceItem] = Field(
        ...,
        min_items=1,
        max_items=500,
        description="List of student attendance entries",
    )

    @validator("date")
    def validate_date(cls, v):
        return _validate_date(v)

    @validator("attendance_list")
    def unique_students(cls, v):
        ids = [item.student_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("attendance_list contains duplicate student_id entries")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "period_id": "CS-A-SEM6_MON_0900",
                "class_id":  "CS-A-SEM6",
                "date":      "2026-04-30",
                "attendance_list": [
                    {"student_id": "STU001", "status": "present", "confidence": 0.97},
                    {"student_id": "STU002", "status": "absent",  "confidence": 0.0},
                    {"student_id": "STU003", "status": "late",    "confidence": 0.85},
                ],
            }
        }


class BulkMarkResult(BaseModel):
    """Per-student outcome returned in the bulk-mark response."""

    student_id: str
    success:    bool
    record_id:  Optional[str] = None
    status:     Optional[str] = None
    error:      Optional[str] = None


class BulkMarkResponse(BaseModel):
    """Response for POST /teacher/mark-bulk."""

    success:   bool
    period_id: str
    date:      str
    accepted:  int
    rejected:  int
    results:   List[BulkMarkResult]
    window:    Dict[str, Any]
    marked_at: str
    message:   str


# ══════════════════════════════════════════════════════════════════════════════
# Attendance edit
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceEditRequest(BaseModel):
    """Request body for PATCH /teacher/attendance/{record_id}."""

    status:     Optional[str] = Field(
        None,
        description="New status: present | absent | late | excused",
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    reason:     Optional[str]   = Field(
        None,
        max_length=500,
        description="Mandatory when editing — stored in audit trail",
    )

    @validator("status")
    def validate_status(cls, v):
        if v is None:
            return v
        return _validate_status(v)

    @validator("reason", always=True)
    def reason_required_with_change(cls, v, values):
        # Soft requirement: warn in docs but do not hard-reject (UI can prompt)
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "status": "excused",
                "reason": "Medical certificate submitted",
            }
        }


class AuditEntry(BaseModel):
    """One entry in an attendance record's audit trail."""

    action:     str
    actor_id:   str
    changed_at: str
    before:     Optional[Dict[str, Any]] = None
    after:      Dict[str, Any]
    reason:     Optional[str] = None


class AttendanceEditResponse(BaseModel):
    """Response for PATCH /teacher/attendance/{record_id}."""

    success:     bool
    record_id:   str
    record:      Dict[str, Any]
    changes:     Dict[str, Any]
    window:      Dict[str, Any]
    audit_trail: List[AuditEntry] = Field(default_factory=list)
    message:     str


class AuditTrailResponse(BaseModel):
    """Response for GET /teacher/attendance/{record_id}/audit."""

    record_id:   str
    entry_count: int
    audit_trail: List[AuditEntry]


# ══════════════════════════════════════════════════════════════════════════════
# Window status
# ══════════════════════════════════════════════════════════════════════════════

class WindowStatus(BaseModel):
    """
    Attendance window status for a period — embedded in dashboard and
    active-class responses so the frontend can drive its UI without
    additional requests.
    """

    is_open:            bool
    can_edit:           bool
    phase:              str  = Field(
        description="before | open | grace | locked"
    )
    time_remaining:     float = Field(description="Minutes until phase changes")
    window_opens_at:    str
    window_closes_at:   str
    lock_at:            str
    is_manually_locked: bool
    is_force_open:      bool
    message:            str  = Field(description="Teacher-friendly status message")
    date:               str
    period_id:          str


# ══════════════════════════════════════════════════════════════════════════════
# Teacher dashboard
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceCounts(BaseModel):
    present:      int = 0
    late:         int = 0
    absent:       int = 0
    total_marked: int = 0


class PeriodScheduleItem(BaseModel):
    """One period on the teacher's dashboard schedule list."""

    period_id:         str
    class_id:          str
    course_id:         Optional[str] = None
    course_name:       Optional[str] = None
    start_time:        str
    end_time:          str
    room:              Optional[str] = None
    period_type:       str = "lecture"
    is_current:        bool = False
    window:            Optional[WindowStatus] = None
    attendance_counts: AttendanceCounts = Field(default_factory=AttendanceCounts)


class TeacherDashboardResponse(BaseModel):
    """Response for GET /teacher/dashboard."""

    faculty_id:    str
    date:          str
    day:           str
    total_periods: int
    schedule:      List[PeriodScheduleItem]
    active_period: Optional[PeriodScheduleItem] = None
    generated_at:  str
    config:        Dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# Active class / roster
# ══════════════════════════════════════════════════════════════════════════════

class StudentRosterItem(BaseModel):
    """One student in the active-class roster."""

    student_id:        str
    name:              str
    email:             Optional[str] = None
    roll_number:       Optional[str] = None
    face_thumbnail:    Optional[str] = Field(
        None,
        description="URL or base64 snippet for face thumbnail",
    )
    attendance_status: Optional[str] = Field(
        None,
        description="present | absent | late | excused | None (not marked)",
    )
    is_marked:         bool = False


class RosterSummary(BaseModel):
    total_students: int = 0
    present:        int = 0
    late:           int = 0
    absent:         int = 0
    not_marked:     int = 0


class ActiveClassResponse(BaseModel):
    """Response for GET /teacher/active-class."""

    is_active:  bool
    period:     Optional[Dict[str, Any]] = None
    window:     Optional[WindowStatus]   = None
    date:       Optional[str] = None
    class_id:   Optional[str] = None
    roster:     List[StudentRosterItem]  = Field(default_factory=list)
    summary:    RosterSummary            = Field(default_factory=RosterSummary)
    checked_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    message:    Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Lock / unlock
# ══════════════════════════════════════════════════════════════════════════════

class LockResponse(BaseModel):
    """Response for POST /teacher/period/{period_id}/lock and /unlock."""

    success:   bool
    period_id: str
    date:      str
    message:   str
    result:    Optional[Dict[str, Any]] = None
    lock:      Optional[Dict[str, Any]] = None


# ══════════════════════════════════════════════════════════════════════════════
# Daily report
# ══════════════════════════════════════════════════════════════════════════════

class DailyReportOverallStats(BaseModel):
    present:        int   = 0
    absent:         int   = 0
    late:           int   = 0
    excused:        int   = 0
    not_marked:     int   = 0
    attendance_pct: float = 0.0


class DailyReportPeriodBreakdown(BaseModel):
    period_id:  str
    course_id:  Optional[str] = None
    start_time: str
    end_time:   str
    present:    int = 0
    absent:     int = 0
    late:       int = 0
    excused:    int = 0
    not_marked: int = 0
    is_locked:  bool = False


class DailyReportStudentSummary(BaseModel):
    student_id:          str
    name:                str
    roll_number:         Optional[str] = None
    periods_present:     int   = 0
    periods_late:        int   = 0
    periods_absent:      int   = 0
    periods_excused:     int   = 0
    periods_not_marked:  int   = 0
    attendance_pct:      float = 0.0


class DailyReportResponse(BaseModel):
    """Full daily report — returned by GET /teacher/report/daily."""

    class_id:          str
    date:              str
    generated_at:      str
    total_students:    int
    total_periods:     int
    overall_stats:     DailyReportOverallStats
    period_breakdown:  List[DailyReportPeriodBreakdown]
    student_summary:   List[DailyReportStudentSummary]
    absent_list:       List[str] = Field(
        description="student_ids absent for ALL periods today"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Attendance-window-aware mark response (enhances existing MarkAttendanceResponse)
# ══════════════════════════════════════════════════════════════════════════════

class WindowAwareMarkResponse(BaseModel):
    """
    Extended mark-attendance response that includes window status and
    teacher-friendly messaging.  Used by the enhanced attendance.py paths.
    """

    success:    bool
    record_id:  Optional[str] = None
    student_id: str
    timestamp:  Optional[str] = None
    status:     str           = "present"
    confidence: float         = 0.0
    window:     Optional[Dict[str, Any]] = None
    message:    str
    audit_id:   Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success":    True,
                "record_id":  "2026-04-30_CS-A-SEM6_MON_0900_STU001",
                "student_id": "STU001",
                "timestamp":  "2026-04-30T09:05:00",
                "status":     "present",
                "confidence": 0.97,
                "message":    "Attendance marked. Window closes in 55 min.",
            }
        }


class WindowClosedResponse(BaseModel):
    """
    Returned with HTTP 423 when a mark/edit is attempted outside the window.
    """

    success:   bool = False
    student_id: Optional[str] = None
    window:    Optional[Dict[str, Any]] = None
    message:   str

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "message": "Attendance window closed. Period is locked.",
                "window":  {
                    "is_open":         False,
                    "phase":           "locked",
                    "time_remaining":  0,
                    "message":         "Attendance window closed. Period is locked.",
                },
            }
        }
