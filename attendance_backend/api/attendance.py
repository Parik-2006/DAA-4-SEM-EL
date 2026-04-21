"""
REST API endpoints for attendance system.

Provides endpoints for:
- Student registration and management
- Attendance marking and retrieval
- Stream management
- System health and statistics
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Body, status
from fastapi.responses import JSONResponse

from schemas.attendance_schemas import (
    StudentRegistrationRequest, StudentRegistrationResponse,
    StudentListResponse, StudentInfo,
    MarkAttendanceRequest, MarkAttendanceResponse, AttendanceListResponse,
    AttendanceRecord, DailyReportResponse,
    ErrorResponse, ValidationErrorResponse,
    BatchRegisterRequest, BatchRegisterResponse,
    BatchMarkAttendanceRequest, BatchMarkAttendanceResponse,
    StreamConfig, StreamHealth,
    HealthCheckResponse, SystemStatsResponse
)
from services.firebase_service import get_firebase_service
from services.rtsp_stream_handler import get_stream_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ==================== Error Handlers ====================

def error_response(
    error: str,
    error_code: str = "ERROR",
    status_code: int = 400,
    details: Optional[dict] = None
) -> JSONResponse:
    """
    Create standardized error response.
    
    Args:
        error: Error message
        error_code: Error code
        status_code: HTTP status code
        details: Error details
    
    Returns:
        JSONResponse
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error,
            "error_code": error_code,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
    )


# ==================== Student Management ====================

@router.post(
    "/register-student",
    response_model=StudentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student",
    responses={
        201: {"model": StudentRegistrationResponse},
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse}
    }
)
async def register_student(request: StudentRegistrationRequest) -> StudentRegistrationResponse:
    """
    Register a new student with face embeddings.
    
    This endpoint:
    1. Validates student information and embeddings
    2. Stores embeddings in Firebase
    3. Creates student record with metadata
    
    Args:
        request: Student registration request
    
    Returns:
        StudentRegistrationResponse with student ID
    
    Raises:
        400: Invalid request data
        409: Student already registered
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Check if student already exists
        existing = firebase.get_student(request.student_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Student {request.student_id} already registered"
            )
        
        # Convert embeddings to numpy array
        import numpy as np
        embeddings_array = np.array(request.embeddings[0])  # Use first embedding
        
        # Register student
        firebase.register_student(
            student_id=request.student_id,
            name=request.name,
            email=request.email,
            embeddings=embeddings_array,
            phone=request.phone,
            metadata=request.metadata
        )
        
        # Store additional embeddings
        for emb in request.embeddings[1:]:
            firebase.store_embedding(request.student_id, np.array(emb))
        
        logger.info(f"Student registered: {request.student_id}")
        
        return StudentRegistrationResponse(
            success=True,
            student_id=request.student_id,
            message="Student registered successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering student: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register student: {str(e)}"
        )


@router.get(
    "/students",
    response_model=StudentListResponse,
    summary="Get list of all registered students",
    responses={
        200: {"model": StudentListResponse},
        500: {"model": ErrorResponse}
    }
)
async def get_students(
    limit: int = Query(1000, ge=1, le=10000, description="Max students to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
) -> StudentListResponse:
    """
    Retrieve list of all registered students.
    
    Supports pagination with limit and offset.
    
    Args:
        limit: Maximum students to return
        offset: Pagination offset
    
    Returns:
        StudentListResponse with student list
    
    Raises:
        500: Database error
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Get all students
        all_students = firebase.get_all_students()
        
        # Apply pagination
        paginated = all_students[offset:offset+limit]
        
        # Convert to StudentInfo objects
        students_info = [
            StudentInfo(
                student_id=s.get("student_id", ""),
                name=s.get("name", ""),
                email=s.get("email", ""),
                phone=s.get("phone"),
                registered_at=s.get("registered_at", ""),
                last_seen=s.get("last_seen"),
                attendance_count=s.get("attendance_count", 0),
                status=s.get("status", "active"),
                metadata=s.get("metadata")
            )
            for s in paginated
        ]
        
        logger.info(f"Retrieved {len(students_info)} students")
        
        return StudentListResponse(
            success=True,
            count=len(students_info),
            students=students_info
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving students: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve students: {str(e)}"
        )


@router.get(
    "/students/{student_id}",
    response_model=StudentInfo,
    summary="Get specific student",
    responses={
        200: {"model": StudentInfo},
        404: {"model": ErrorResponse}
    }
)
async def get_student(student_id: str) -> StudentInfo:
    """
    Get details for a specific student.
    
    Args:
        student_id: Student ID
    
    Returns:
        StudentInfo object
    
    Raises:
        404: Student not found
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        student = firebase.get_student(student_id)
        
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"Student {student_id} not found"
            )
        
        return StudentInfo(
            student_id=student.get("student_id", ""),
            name=student.get("name", ""),
            email=student.get("email", ""),
            phone=student.get("phone"),
            registered_at=student.get("registered_at", ""),
            last_seen=student.get("last_seen"),
            attendance_count=student.get("attendance_count", 0),
            status=student.get("status", "active"),
            metadata=student.get("metadata")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get student: {str(e)}"
        )


# ==================== Attendance Management ====================

@router.post(
    "/mark-attendance",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark student attendance",
    responses={
        201: {"model": MarkAttendanceResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def mark_attendance(request: MarkAttendanceRequest) -> MarkAttendanceResponse:
    """
    Mark attendance for a recognized student.
    
    This endpoint:
    1. Validates student exists
    2. Creates attendance record with timestamp
    3. Updates student's last_seen and attendance_count
    
    Args:
        request: Attendance marking request
    
    Returns:
        MarkAttendanceResponse with record ID
    
    Raises:
        400: Invalid request
        404: Student not found
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Verify student exists
        student = firebase.get_student(request.student_id)
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"Student {request.student_id} not found"
            )
        
        # Mark attendance
        timestamp = request.timestamp or datetime.now()
        
        result = firebase.mark_attendance(
            student_id=request.student_id,
            timestamp=timestamp,
            confidence=request.confidence,
            track_id=request.track_id,
            camera_id=request.camera_id,
            metadata=request.metadata
        )
        
        logger.info(f"Attendance marked for {request.student_id}: {result['record_id']}")
        
        return MarkAttendanceResponse(
            success=True,
            record_id=result['record_id'],
            student_id=request.student_id,
            timestamp=timestamp.isoformat(),
            message="Attendance marked successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking attendance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark attendance: {str(e)}"
        )


@router.post(
    "/mark",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance with face recognition",
    responses={
        201: {"model": MarkAttendanceResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def mark_attendance_with_image(
    student_id: str = Body(..., description="Student ID"),
    image_base64: str = Body(..., description="Base64 encoded image")
) -> MarkAttendanceResponse:
    """
    Mark attendance using face recognition from image.
    
    This endpoint:
    1. Decodes the base64 image
    2. Extracts face embedding from image
    3. Matches against student's stored embeddings
    4. Marks attendance if confidence > threshold
    
    Args:
        student_id: Student ID
        image_base64: Base64 encoded image
    
    Returns:
        MarkAttendanceResponse with attendance status
    
    Raises:
        400: Invalid image or no face detected
        404: Student not found or no match
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Verify student exists
        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"Student {student_id} not found"
            )
        
        # Decode image
        import base64
        import io
        from PIL import Image
        import numpy as np
        
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image format: {str(e)}"
            )
        
        # Extract face embedding
        from models.facenet_extractor import FaceNetExtractor
        
        try:
            extractor = FaceNetExtractor()
            embedding = extractor.extract_embedding(image_array)
            
            if embedding is None:
                raise HTTPException(
                    status_code=400,
                    detail="No face detected in image"
                )
        except Exception as e:
            logger.warning(f"Face extraction error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Face extraction failed: {str(e)}"
            )
        
        # Get student's stored embeddings
        student_embeddings = student.get("embeddings", [])
        if not student_embeddings:
            raise HTTPException(
                status_code=404,
                detail="Student has no registered face embeddings"
            )
        
        # Compare embeddings
        from scipy.spatial.distance import cosine
        
        CONFIDENCE_THRESHOLD = 0.6  # Cosine distance threshold
        
        best_distance = float('inf')
        best_match = None
        
        for stored_emb in student_embeddings:
            if isinstance(stored_emb, list):
                stored_emb = np.array(stored_emb)
            
            distance = cosine(embedding, stored_emb)
            if distance < best_distance:
                best_distance = distance
                best_match = distance
        
        # Convert distance to confidence (lower distance = higher confidence)
        confidence = 1.0 - min(best_match, 1.0) if best_match is not None else 0.0
        
        if best_match > CONFIDENCE_THRESHOLD:
            raise HTTPException(
                status_code=404,
                detail=f"Face does not match student. Confidence: {confidence:.2f}"
            )
        
        # Mark attendance
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="mobile_app",
            metadata={
                "method": "face_recognition",
                "threshold": CONFIDENCE_THRESHOLD,
                "distance": float(best_match)
            }
        )
        
        logger.info(f"Attendance marked via face recognition: {student_id} (confidence: {confidence:.2f})")
        
        return MarkAttendanceResponse(
            success=True,
            record_id=result['record_id'],
            student_id=student_id,
            timestamp=timestamp.isoformat(),
            message=f"Attendance marked successfully (confidence: {confidence:.2f})"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking attendance with image: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark attendance: {str(e)}"
        )


@router.post(
    "/mark-mobile",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance with face recognition (Mobile App)",
    responses={
        201: {"model": MarkAttendanceResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def mark_attendance_mobile(
    student_id: str = Query(..., description="Student ID"),
    image_base64: str = Query(..., description="Base64 encoded image")
) -> MarkAttendanceResponse:
    """
    Mark attendance using face recognition from mobile camera.
    
    This endpoint accepts query parameters for mobile app integration.
    
    Args:
        student_id: Student ID
        image_base64: Base64 encoded image
    
    Returns:
        MarkAttendanceResponse with attendance status
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Verify student exists
        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"Student {student_id} not found"
            )
        
        # Decode image
        import base64
        import io
        from PIL import Image
        import numpy as np
        
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image format: {str(e)}"
            )
        
        # Extract face embedding
        from models.facenet_extractor import FaceNetExtractor
        from scipy.spatial.distance import cosine
        
        CONFIDENCE_THRESHOLD = 0.6
        
        try:
            extractor = FaceNetExtractor()
            embedding = extractor.extract_embedding(image_array)
            
            if embedding is None:
                raise HTTPException(
                    status_code=400,
                    detail="No face detected in image"
                )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract face: {str(e)}"
            )
        
        # Get stored embeddings
        embeddings = student.get("embeddings", [])
        if not embeddings:
            raise HTTPException(
                status_code=404,
                detail="No face profile found for student. Please register face first."
            )
        
        # Find best match
        best_match = None
        for stored_emb in embeddings:
            distance = cosine(embedding, stored_emb)
            if best_match is None or distance < best_match:
                best_match = distance
        
        # Convert distance to confidence (lower distance = higher confidence)
        confidence = 1.0 - min(best_match, 1.0) if best_match is not None else 0.0
        
        if best_match > CONFIDENCE_THRESHOLD:
            raise HTTPException(
                status_code=404,
                detail=f"Face does not match student. Confidence: {confidence:.2f}"
            )
        
        # Mark attendance
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="mobile_app",
            metadata={
                "method": "face_recognition_mobile",
                "threshold": CONFIDENCE_THRESHOLD,
                "distance": float(best_match)
            }
        )
        
        logger.info(f"Mobile attendance marked: {student_id} (confidence: {confidence:.2f})")
        
        return MarkAttendanceResponse(
            success=True,
            record_id=result['record_id'],
            student_id=student_id,
            timestamp=timestamp.isoformat(),
            message=f"Attendance marked successfully (confidence: {confidence:.2f})"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking mobile attendance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark attendance: {str(e)}"
        )


@router.get(
    "/attendance",
    response_model=AttendanceListResponse,
    summary="Get attendance records",
    responses={
        200: {"model": AttendanceListResponse},
        400: {"model": ErrorResponse}
    }
)
async def get_attendance(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
) -> AttendanceListResponse:
    """
    Retrieve attendance records with optional filtering.
    
    Supports filtering by:
    - Student ID
    - Date range
    - Pagination
    
    Args:
        student_id: Optional student ID filter
        date_from: Optional start date
        date_to: Optional end date
        limit: Maximum records to return
        offset: Pagination offset
    
    Returns:
        AttendanceListResponse with records
    
    Raises:
        400: Invalid date format
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Parse dates
        from_date = None
        to_date = None
        
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date_from format (use ISO format)"
                )
        
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date_to format (use ISO format)"
                )
        
        # Get records
        records = firebase.get_attendance_records(
            student_id=student_id,
            date_from=from_date,
            date_to=to_date,
            limit=limit + offset  # Get extra for offset
        )
        
        # Apply offset
        paginated = records[offset:offset+limit]
        
        # Convert to AttendanceRecord objects
        attendance_records = [
            AttendanceRecord(
                record_id=str(r.get("timestamp", "")),  # Use timestamp as ID
                student_id=r.get("student_id", ""),
                timestamp=r.get("timestamp", ""),
                date=r.get("date", ""),
                time=r.get("time", ""),
                confidence=r.get("confidence", 0.0),
                track_id=r.get("track_id"),
                camera_id=r.get("camera_id", "default"),
                status=r.get("status", "present"),
                metadata=r.get("metadata")
            )
            for r in paginated
        ]
        
        logger.info(f"Retrieved {len(attendance_records)} attendance records")
        
        return AttendanceListResponse(
            success=True,
            count=len(attendance_records),
            records=attendance_records
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving attendance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve attendance: {str(e)}"
        )


@router.get(
    "/attendance/daily-report",
    response_model=DailyReportResponse,
    summary="Get daily attendance report"
)
async def get_daily_report(
    date: Optional[str] = Query(None, description="Report date (ISO format, default: today)")
) -> DailyReportResponse:
    """
    Get attendance report for a specific date.
    
    Args:
        date: Date for report (ISO format)
    
    Returns:
        DailyReportResponse
    """
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not initialized"
            )
        
        # Parse date
        report_date = None
        if date:
            try:
                report_date = datetime.fromisoformat(date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format (use ISO format)"
                )
        
        report = firebase.get_daily_report(report_date)
        
        if "error" in report:
            raise HTTPException(
                status_code=500,
                detail=report["error"]
            )
        
        return DailyReportResponse(
            date=report["date"],
            total_records=report["total_records"],
            unique_students=report["unique_students"],
            records=[]  # TODO: Convert to proper format
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


# ==================== Stream Management ====================

@router.post(
    "/streams",
    response_model=StreamHealth,
    status_code=status.HTTP_201_CREATED,
    summary="Add RTSP stream"
)
async def add_stream(request: StreamConfig) -> StreamHealth:
    """
    Add new RTSP stream for processing.
    
    Args:
        request: Stream configuration
    
    Returns:
        Stream health status
    """
    try:
        manager = get_stream_manager()
        
        handler = manager.add_stream(
            stream_id=request.stream_id,
            rtsp_url=request.rtsp_url,
            frame_skip=request.frame_skip,
            min_consecutive_frames=request.min_consecutive_frames,
            confidence_threshold=request.confidence_threshold
        )
        
        if not handler:
            raise HTTPException(
                status_code=400,
                detail="Failed to add stream"
            )
        
        # Start stream
        if request.enabled:
            manager.start_stream(request.stream_id)
        
        metrics = handler.get_metrics()
        
        return StreamHealth(
            stream_id=request.stream_id,
            status=metrics["status"],
            last_frame=None,
            frames_processed=0,
            fps=0.0,
            errors=0
        )
    
    except Exception as e:
        logger.error(f"Error adding stream: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add stream: {str(e)}"
        )


@router.get(
    "/streams",
    summary="Get all streams"
)
async def get_streams():
    """Get status of all RTSP streams."""
    try:
        manager = get_stream_manager()
        streams = manager.get_all_streams()
        
        return {
            "success": True,
            "count": len(streams),
            "streams": streams
        }
    
    except Exception as e:
        logger.error(f"Error getting streams: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get streams: {str(e)}"
        )


@router.post(
    "/streams/{stream_id}/start",
    summary="Start stream"
)
async def start_stream(stream_id: str):
    """Start a stream."""
    try:
        manager = get_stream_manager()
        
        if not manager.start_stream(stream_id):
            raise HTTPException(
                status_code=404,
                detail=f"Stream {stream_id} not found"
            )
        
        return {"success": True, "message": f"Stream {stream_id} started"}
    
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start stream: {str(e)}"
        )


@router.post(
    "/streams/{stream_id}/stop",
    summary="Stop stream"
)
async def stop_stream(stream_id: str):
    """Stop a stream."""
    try:
        manager = get_stream_manager()
        
        if not manager.stop_stream(stream_id):
            raise HTTPException(
                status_code=404,
                detail=f"Stream {stream_id} not found"
            )
        
        return {"success": True, "message": f"Stream {stream_id} stopped"}
    
    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop stream: {str(e)}"
        )


# ==================== System Health ====================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check"
)
async def health_check() -> HealthCheckResponse:
    """
    System health check.
    
    Returns:
        HealthCheckResponse status
    """
    try:
        firebase = get_firebase_service()
        manager = get_stream_manager()
        
        services = {
            "firebase": "healthy" if firebase else "unavailable",
            "streams": "healthy" if manager else "unavailable"
        }
        
        return HealthCheckResponse(
            status="healthy",
            services=services,
            uptime_seconds=0  # TODO: Calculate uptime
        )
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheckResponse(
            status="error",
            services={"error": str(e)},
            uptime_seconds=0
        )


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="System statistics"
)
async def get_stats() -> SystemStatsResponse:
    """Get system statistics."""
    try:
        firebase = get_firebase_service()
        
        if not firebase:
            return SystemStatsResponse()
        
        # Get statistics
        all_students = firebase.get_all_students()
        attendance_records = firebase.get_attendance_records(limit=10000)
        
        # Calculate stats
        today = datetime.now().date()
        today_records = [
            r for r in attendance_records
            if datetime.fromisoformat(r.get("date", "")).date() == today
        ]
        
        return SystemStatsResponse(
            total_students=len(all_students),
            total_attendance_records=len(attendance_records),
            total_detections_today=len(today_records),
            average_confidence=(
                sum(r.get("confidence", 0) for r in attendance_records) / 
                len(attendance_records) if attendance_records else 0
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )
