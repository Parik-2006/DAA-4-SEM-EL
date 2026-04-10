"""
Schemas package for request/response models.
"""

from .attendance_schemas import (
    StudentRegistrationRequest,
    StudentRegistrationResponse,
    StudentInfo,
    StudentListResponse,
    MarkAttendanceRequest,
    MarkAttendanceResponse,
    AttendanceRecord,
    AttendanceListResponse,
    DailyReportResponse,
    ErrorResponse,
    ValidationErrorResponse,
    BatchRegisterRequest,
    BatchRegisterResponse,
    BatchMarkAttendanceRequest,
    BatchMarkAttendanceResponse,
    StreamConfig,
    StreamHealth,
    HealthCheckResponse,
    SystemStatsResponse,
)

__all__ = [
    "StudentRegistrationRequest",
    "StudentRegistrationResponse",
    "StudentInfo",
    "StudentListResponse",
    "MarkAttendanceRequest",
    "MarkAttendanceResponse",
    "AttendanceRecord",
    "AttendanceListResponse",
    "DailyReportResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    "BatchRegisterRequest",
    "BatchRegisterResponse",
    "BatchMarkAttendanceRequest",
    "BatchMarkAttendanceResponse",
    "StreamConfig",
    "StreamHealth",
    "HealthCheckResponse",
    "SystemStatsResponse",
]
