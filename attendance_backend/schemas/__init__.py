"""
Schemas package for request/response models.
"""

from .attendance_schemas import (
    StudentCreateSchema,
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

from .user_schemas import (
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserProfileResponse,
)

__all__ = [
    "StudentCreateSchema",
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
    "UserRegistrationRequest",
    "UserRegistrationResponse",
    "UserLoginRequest",
    "UserLoginResponse",
    "UserProfileResponse",
]
