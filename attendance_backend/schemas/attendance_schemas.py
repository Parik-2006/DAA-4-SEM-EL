"""
Request and response schemas for attendance API.

Defines Pydantic models for validation and documentation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
import numpy as np


# ==================== Student Registration ====================

class StudentCreateSchema(BaseModel):
    """Schema for creating a new student (simple version)."""
    name: str = Field(..., min_length=2, max_length=100, description="Student full name")
    email: EmailStr = Field(..., description="Student email address")
    courses: Optional[List[str]] = Field(default_factory=list, description="List of course IDs")

class StudentRegistrationRequest(BaseModel):
    """Request to register a new student."""
    
    student_id: str = Field(..., min_length=1, max_length=50, description="Unique student ID")
    name: str = Field(..., min_length=2, max_length=100, description="Student full name")
    email: EmailStr = Field(..., description="Student email address")
    phone: Optional[str] = Field(None, max_length=20, description="Student phone number")
    embeddings: List[List[float]] = Field(
        ...,
        description="List of face embeddings (128-dimensional)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional student metadata"
    )
    
    @validator('embeddings')
    def validate_embeddings(cls, v):
        """Validate embeddings format."""
        if not v:
            raise ValueError("At least one embedding required")
        
        for emb in v:
            if len(emb) != 128:
                raise ValueError(f"Each embedding must be 128-dimensional, got {len(emb)}")
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "student_id": "STU001",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "embeddings": [[0.1, 0.2, ...]], # 128 values
                "metadata": {"batch": 2024, "department": "CS"}
            }
        }


class StudentRegistrationResponse(BaseModel):
    """Response after student registration."""
    
    success: bool = Field(..., description="Registration success status")
    student_id: str = Field(..., description="Registered student ID")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "student_id": "STU001",
                "message": "Student registered successfully",
                "timestamp": "2024-04-10T10:30:00"
            }
        }


class StudentInfo(BaseModel):
    """Student information."""
    
    student_id: str = Field(..., description="Unique student ID")
    name: str = Field(..., description="Student name")
    email: str = Field(..., description="Student email")
    phone: Optional[str] = Field(None, description="Student phone")
    registered_at: str = Field(..., description="Registration timestamp")
    last_seen: Optional[str] = Field(None, description="Last attendance timestamp")
    attendance_count: int = Field(0, description="Total attendance count")
    status: str = Field("active", description="Student status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class StudentListResponse(BaseModel):
    """Response with list of students."""
    
    success: bool = Field(True, description="Response success status")
    count: int = Field(..., description="Number of students")
    students: List[StudentInfo] = Field(..., description="List of students")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "count": 100,
                "students": [
                    {
                        "student_id": "STU001",
                        "name": "John Doe",
                        "email": "john@example.com",
                        "phone": "+1234567890",
                        "registered_at": "2024-04-10T09:00:00",
                        "last_seen": "2024-04-10T10:30:00",
                        "attendance_count": 45,
                        "status": "active"
                    }
                ],
                "timestamp": "2024-04-10T10:30:00"
            }
        }


# ==================== Attendance Marking ====================

class MarkAttendanceRequest(BaseModel):
    """Request to mark attendance."""
    
    student_id: str = Field(..., description="Student ID")
    timestamp: Optional[datetime] = Field(
        None,
        description="Attendance timestamp (defaults to current time)"
    )
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Recognition confidence (0-1)"
    )
    track_id: Optional[int] = Field(None, description="Tracking ID from SORT")
    camera_id: Optional[str] = Field(None, description="Camera ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "student_id": "STU001",
                "timestamp": "2024-04-10T10:30:00",
                "confidence": 0.95,
                "track_id": 1,
                "camera_id": "CAM_MAIN",
                "metadata": {"detection_method": "optimized_pipeline"}
            }
        }


class AttendanceRecord(BaseModel):
    """Single attendance record."""
    
    record_id: str = Field(..., description="Unique record ID")
    student_id: str = Field(..., description="Student ID")
    timestamp: str = Field(..., description="Attendance timestamp")
    date: str = Field(..., description="Attendance date (ISO format)")
    time: str = Field(..., description="Attendance time (ISO format)")
    confidence: float = Field(..., description="Recognition confidence")
    track_id: Optional[int] = Field(None, description="Tracking ID")
    camera_id: str = Field(..., description="Camera ID")
    status: str = Field("present", description="Attendance status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class MarkAttendanceResponse(BaseModel):
    """Response after marking attendance."""
    
    success: bool = Field(..., description="Mark success status")
    record_id: str = Field(..., description="Attendance record ID")
    student_id: str = Field(..., description="Student ID")
    timestamp: str = Field(..., description="Marked timestamp")
    message: str = Field(..., description="Response message")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "record_id": "REC123456789",
                "student_id": "STU001",
                "timestamp": "2024-04-10T10:30:00",
                "message": "Attendance marked successfully"
            }
        }


class AttendanceListResponse(BaseModel):
    """Response with attendance records."""
    
    success: bool = Field(True, description="Response success status")
    count: int = Field(..., description="Number of records")
    records: List[AttendanceRecord] = Field(..., description="Attendance records")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
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
        }


class DailyReportResponse(BaseModel):
    """Daily attendance report."""
    
    date: str = Field(..., description="Report date (ISO format)")
    total_records: int = Field(..., description="Total attendance records")
    unique_students: int = Field(..., description="Number of unique students")
    records: List[AttendanceRecord] = Field(..., description="Attendance records")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


# ==================== Stream Configuration ====================

class StreamConfig(BaseModel):
    """Configuration for RTSP stream."""
    
    stream_id: str = Field(..., description="Unique stream identifier")
    rtsp_url: str = Field(..., description="RTSP stream URL")
    camera_name: Optional[str] = Field(None, description="Camera display name")
    location: Optional[str] = Field(None, description="Camera location")
    enabled: bool = Field(True, description="Stream enabled status")
    frame_skip: int = Field(2, ge=1, le=5, description="Frame skip for processing")
    min_consecutive_frames: int = Field(5, ge=1, le=20, description="Min consecutive frames for verification")
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Recognition threshold")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "stream_id": "stream_main_entrance",
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "camera_name": "Main Entrance",
                "location": "Building A, Ground Floor",
                "enabled": True,
                "frame_skip": 2,
                "min_consecutive_frames": 5,
                "confidence_threshold": 0.6
            }
        }


class StreamHealth(BaseModel):
    """Stream health status."""
    
    stream_id: str = Field(..., description="Stream ID")
    status: str = Field(..., description="Stream status (active/inactive/error)")
    last_frame: Optional[datetime] = Field(None, description="Last frame timestamp")
    frames_processed: int = Field(0, description="Total frames processed")
    fps: float = Field(0.0, description="Current FPS")
    errors: int = Field(0, description="Error count")
    last_error: Optional[str] = Field(None, description="Last error message")
    uptime_seconds: int = Field(0, description="Stream uptime in seconds")


# ==================== Error Responses ====================

class ErrorResponse(BaseModel):
    """Standard error response."""
    
    success: bool = Field(False, description="Success status")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "Student not found",
                "error_code": "STUDENT_NOT_FOUND",
                "details": {"student_id": "STU001"},
                "timestamp": "2024-04-10T10:30:00"
            }
        }


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    
    success: bool = Field(False, description="Success status")
    error: str = Field("Validation error", description="Error message")
    errors: List[Dict[str, Any]] = Field(..., description="List of validation errors")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


# ==================== Batch Operations ====================

class BatchRegisterRequest(BaseModel):
    """Request to register multiple students."""
    
    students: List[StudentRegistrationRequest] = Field(..., description="List of students to register")
    
    @validator('students')
    def validate_students_list(cls, v):
        """Validate students list."""
        if not v:
            raise ValueError("At least one student required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 students per batch")
        return v


class BatchRegisterResponse(BaseModel):
    """Response for batch registration."""
    
    success: bool = Field(..., description="Overall success status")
    total: int = Field(..., description="Total students in request")
    registered: int = Field(..., description="Successfully registered")
    failed: int = Field(..., description="Failed registrations")
    errors: Dict[str, str] = Field(default_factory=dict, description="Student ID -> error message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class BatchMarkAttendanceRequest(BaseModel):
    """Request to mark attendance for multiple students."""
    
    records: List[MarkAttendanceRequest] = Field(..., description="Attendance records to mark")
    
    @validator('records')
    def validate_records_list(cls, v):
        """Validate records list."""
        if not v:
            raise ValueError("At least one record required")
        if len(v) > 500:
            raise ValueError("Maximum 500 records per batch")
        return v


class BatchMarkAttendanceResponse(BaseModel):
    """Response for batch attendance marking."""
    
    success: bool = Field(..., description="Overall success status")
    total: int = Field(..., description="Total records in request")
    marked: int = Field(..., description="Successfully marked")
    failed: int = Field(..., description="Failed markings")
    errors: Dict[str, str] = Field(default_factory=dict, description="Record index -> error message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


# ==================== Health & Status ====================

class HealthCheckResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="System status (healthy/degraded/error)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    services: Dict[str, str] = Field(..., description="Service statuses")
    uptime_seconds: int = Field(0, description="System uptime in seconds")


class SystemStatsResponse(BaseModel):
    """System statistics."""
    
    total_students: int = Field(0, description="Total registered students")
    total_attendance_records: int = Field(0, description="Total attendance records")
    active_streams: int = Field(0, description="Active RTSP streams")
    total_detections_today: int = Field(0, description="Total detections today")
    average_confidence: float = Field(0.0, description="Average recognition confidence")
    timestamp: datetime = Field(default_factory=datetime.now, description="Stats timestamp")
