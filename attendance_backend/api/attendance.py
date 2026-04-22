"""
REST API endpoints for attendance system.

Provides endpoints for:
- Student registration and management
- Attendance marking and retrieval (including file-upload face detection)
- Stream management
- System health and statistics
"""

import logging
import base64
import io
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Body, File, UploadFile, status
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


# ==================== Error Helpers ====================

def error_response(
    error: str,
    error_code: str = "ERROR",
    status_code: int = 400,
    details: Optional[dict] = None
) -> JSONResponse:
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


# ==================== Face Detection / Attendance via File Upload ====================

@router.post(
    "/detect-face",
    status_code=status.HTTP_200_OK,
    summary="Detect face from uploaded image and mark attendance",
    responses={
        200: {"description": "Face detected and matched"},
        400: {"description": "No face detected or invalid image"},
        404: {"description": "No matching student found"},
    }
)
async def detect_face_and_mark(
    file: UploadFile = File(..., description="JPEG or PNG image containing a face"),
):
    """
    Accept a multipart image file, extract face embedding, match against
    all registered students, and mark attendance for the best match.

    Returns JSON:
        {
          "matched": true/false,
          "message": "...",
          "student_name": "...",   # if matched
          "student_id": "...",     # if matched
          "confidence": 0.95       # if matched
        }
    """
    # ── 1. Read uploaded bytes ──────────────────────────────────────────────
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file received")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # ── 2. Decode image ─────────────────────────────────────────────────────
    try:
        from PIL import Image
        import numpy as np

        image = Image.open(io.BytesIO(contents)).convert("RGB")
        image_array = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

    # ── 3. Extract face embedding ────────────────────────────────────────────
    try:
        from models.facenet_extractor import FaceNetExtractor
        extractor = FaceNetExtractor()
        embedding = extractor.extract_embedding(image_array)
        if embedding is None:
            return JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": "No face detected in the image. Ensure your face is clearly visible and well-lit.",
                }
            )
    except ImportError:
        # FaceNet not installed – fall back to a simple "no model" response
        logger.warning("FaceNetExtractor not available; returning unmatched")
        return JSONResponse(
            status_code=200,
            content={
                "matched": False,
                "message": "Face recognition model not loaded on server. Contact admin.",
            }
        )
    except Exception as e:
        logger.error(f"Embedding extraction error: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "matched": False,
                "message": f"Could not process face: {str(e)}",
            }
        )

    # ── 4. Match against all registered students ─────────────────────────────
    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    try:
        from scipy.spatial.distance import cosine
        import numpy as np

        THRESHOLD = 0.55  # lower = stricter

        all_students = firebase.get_all_students()
        best_distance = float("inf")
        best_student = None

        for student in all_students:
            stored_embs = student.get("embeddings", [])
            for stored_emb in stored_embs:
                arr = np.array(stored_emb)
                if arr.shape != embedding.shape:
                    continue
                dist = float(cosine(embedding, arr))
                if dist < best_distance:
                    best_distance = dist
                    best_student = student

        if best_student is None or best_distance > THRESHOLD:
            return JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": (
                        "Face not recognised. "
                        f"Best similarity score: {1 - best_distance:.2f}. "
                        "Please register your face or try with better lighting."
                    ),
                }
            )

        confidence = float(1.0 - best_distance)
        student_id = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")

    except ImportError:
        logger.warning("scipy not installed – cannot compare embeddings")
        return JSONResponse(
            status_code=200,
            content={"matched": False, "message": "Server missing scipy library for face matching."}
        )
    except Exception as e:
        logger.error(f"Matching error: {e}")
        raise HTTPException(status_code=500, detail=f"Face matching failed: {str(e)}")

    # ── 5. Mark attendance ────────────────────────────────────────────────────
    try:
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="web_upload",
            metadata={
                "method": "face_recognition_upload",
                "threshold": THRESHOLD,
                "distance": best_distance,
            }
        )
        logger.info(f"Attendance marked via upload: {student_id} ({student_name}) conf={confidence:.2f}")

        return JSONResponse(
            status_code=200,
            content={
                "matched": True,
                "message": f"Attendance marked successfully for {student_name}",
                "student_name": student_name,
                "student_id": student_id,
                "confidence": round(confidence, 4),
                "record_id": result.get("record_id", ""),
                "timestamp": timestamp.isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Failed to save attendance: {e}")
        raise HTTPException(status_code=500, detail=f"Attendance recording failed: {str(e)}")


# ==================== Student Management ====================

@router.post(
    "/register-student",
    response_model=StudentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student",
)
async def register_student(request: StudentRegistrationRequest) -> StudentRegistrationResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        existing = firebase.get_student(request.student_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Student {request.student_id} already registered")

        import numpy as np
        embeddings_array = np.array(request.embeddings[0])
        firebase.register_student(
            student_id=request.student_id,
            name=request.name,
            email=request.email,
            embeddings=embeddings_array,
            phone=request.phone,
            metadata=request.metadata
        )
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
        raise HTTPException(status_code=500, detail=f"Failed to register student: {str(e)}")


@router.get("/students", response_model=StudentListResponse, summary="Get list of all registered students")
async def get_students(
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> StudentListResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        all_students = firebase.get_all_students()
        paginated = all_students[offset:offset + limit]
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
        return StudentListResponse(success=True, count=len(students_info), students=students_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving students: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve students: {str(e)}")


@router.get("/students/{student_id}", response_model=StudentInfo, summary="Get specific student")
async def get_student(student_id: str) -> StudentInfo:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

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
        raise HTTPException(status_code=500, detail=f"Failed to get student: {str(e)}")


# ==================== Attendance Management ====================

@router.post("/mark-attendance", response_model=MarkAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def mark_attendance(request: MarkAttendanceRequest) -> MarkAttendanceResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        student = firebase.get_student(request.student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student {request.student_id} not found")

        timestamp = request.timestamp or datetime.now()
        result = firebase.mark_attendance(
            student_id=request.student_id,
            timestamp=timestamp,
            confidence=request.confidence,
            track_id=request.track_id,
            camera_id=request.camera_id,
            metadata=request.metadata
        )
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
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.post(
    "/mark",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance with face recognition (JSON body)",
)
async def mark_attendance_with_image(
    student_id: str = Body(...),
    image_base64: str = Body(...)
) -> MarkAttendanceResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

        import numpy as np
        from PIL import Image

        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_array = np.array(image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        try:
            from models.facenet_extractor import FaceNetExtractor
            from scipy.spatial.distance import cosine

            extractor = FaceNetExtractor()
            embedding = extractor.extract_embedding(image_array)
            if embedding is None:
                raise HTTPException(status_code=400, detail="No face detected in image")

            student_embeddings = student.get("embeddings", [])
            if not student_embeddings:
                raise HTTPException(status_code=404, detail="Student has no registered face embeddings")

            THRESHOLD = 0.6
            best_match = None
            for stored_emb in student_embeddings:
                dist = float(cosine(embedding, np.array(stored_emb)))
                if best_match is None or dist < best_match:
                    best_match = dist

            confidence = float(1.0 - min(best_match, 1.0)) if best_match is not None else 0.0
            if best_match > THRESHOLD:
                raise HTTPException(
                    status_code=404,
                    detail=f"Face does not match student. Confidence: {confidence:.2f}"
                )
        except (ImportError, HTTPException):
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Face processing failed: {str(e)}")

        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="web_json",
            metadata={"method": "face_recognition_json"}
        )
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
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.post(
    "/mark-mobile",
    response_model=MarkAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance from mobile app (query-param base64)",
)
async def mark_attendance_mobile(
    student_id: str = Query(...),
    image_base64: str = Query(...)
) -> MarkAttendanceResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

        import numpy as np
        from PIL import Image

        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_array = np.array(image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        try:
            from models.facenet_extractor import FaceNetExtractor
            from scipy.spatial.distance import cosine

            THRESHOLD = 0.6
            extractor = FaceNetExtractor()
            embedding = extractor.extract_embedding(image_array)
            if embedding is None:
                raise HTTPException(status_code=400, detail="No face detected")

            embeddings = student.get("embeddings", [])
            if not embeddings:
                raise HTTPException(status_code=404, detail="No face profile found for student")

            best_match = None
            for stored_emb in embeddings:
                dist = float(cosine(embedding, np.array(stored_emb)))
                if best_match is None or dist < best_match:
                    best_match = dist

            confidence = float(1.0 - min(best_match, 1.0)) if best_match is not None else 0.0
            if best_match > THRESHOLD:
                raise HTTPException(status_code=404, detail=f"Face does not match. Confidence: {confidence:.2f}")
        except (ImportError, HTTPException):
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="mobile_app",
            metadata={"method": "face_recognition_mobile"}
        )
        return MarkAttendanceResponse(
            success=True,
            record_id=result['record_id'],
            student_id=student_id,
            timestamp=timestamp.isoformat(),
            message=f"Attendance marked (confidence: {confidence:.2f})"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mobile attendance error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.get("/attendance", response_model=AttendanceListResponse, summary="Get attendance records")
async def get_attendance(
    student_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> AttendanceListResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        from_date = None
        to_date = None
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format")
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format")

        records = firebase.get_attendance_records(
            student_id=student_id,
            date_from=from_date,
            date_to=to_date,
            limit=limit + offset
        )
        paginated = records[offset:offset + limit]
        attendance_records = [
            AttendanceRecord(
                record_id=str(r.get("timestamp", "")),
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
        return AttendanceListResponse(success=True, count=len(attendance_records), records=attendance_records)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving attendance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve attendance: {str(e)}")


@router.get("/attendance/daily-report", response_model=DailyReportResponse, summary="Daily attendance report")
async def get_daily_report(date: Optional[str] = Query(None)) -> DailyReportResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        report_date = None
        if date:
            try:
                report_date = datetime.fromisoformat(date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format")

        report = firebase.get_daily_report(report_date)
        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])

        return DailyReportResponse(
            date=report["date"],
            total_records=report["total_records"],
            unique_students=report["unique_students"],
            records=[]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


# ==================== Stream Management ====================

@router.post("/streams", response_model=StreamHealth, status_code=status.HTTP_201_CREATED)
async def add_stream(request: StreamConfig) -> StreamHealth:
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
            raise HTTPException(status_code=400, detail="Failed to add stream")
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
        raise HTTPException(status_code=500, detail=f"Failed to add stream: {str(e)}")


@router.get("/streams", summary="Get all streams")
async def get_streams():
    try:
        manager = get_stream_manager()
        streams = manager.get_all_streams()
        return {"success": True, "count": len(streams), "streams": streams}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get streams: {str(e)}")


@router.post("/streams/{stream_id}/start")
async def start_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.start_stream(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {"success": True, "message": f"Stream {stream_id} started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")


@router.post("/streams/{stream_id}/stop")
async def stop_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.stop_stream(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {"success": True, "message": f"Stream {stream_id} stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop stream: {str(e)}")


# ==================== System Health / Stats ====================

@router.get("/health", response_model=HealthCheckResponse, summary="Health check")
async def health_check() -> HealthCheckResponse:
    try:
        firebase = get_firebase_service()
        manager = get_stream_manager()
        services = {
            "firebase": "healthy" if firebase else "unavailable",
            "streams": "healthy" if manager else "unavailable"
        }
        return HealthCheckResponse(status="healthy", services=services, uptime_seconds=0)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheckResponse(status="error", services={"error": str(e)}, uptime_seconds=0)


@router.get("/stats", response_model=SystemStatsResponse, summary="System statistics")
async def get_stats() -> SystemStatsResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            return SystemStatsResponse()

        all_students = firebase.get_all_students()
        attendance_records = firebase.get_attendance_records(limit=10000)
        today = datetime.now().date()
        today_records = []
        for r in attendance_records:
            try:
                if datetime.fromisoformat(str(r.get("date", ""))).date() == today:
                    today_records.append(r)
            except Exception:
                pass

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
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
