"""
REST API endpoints for attendance system.
Two-step attendance: detect-face (identify only) → confirm-attendance (write to DB).
"""

import logging
import base64
import io
from datetime import datetime
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
import numpy as np
from scipy.spatial.distance import cosine
from services.firebase_service import get_firebase_service, FirebaseService
from services.rtsp_stream_handler import get_stream_manager
from models.model_manager import ModelManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ── Shared face-extraction helper ─────────────────────────────────────────────

async def _extract_embedding_from_upload(file: UploadFile):
    """
    Read an uploaded image file, detect the face with YOLOv8, crop it,
    and return (embedding: np.ndarray, error_response: JSONResponse | None).
    On any failure the embedding is None and error_response carries the reply.
    """
    MAX_BYTES = 10 * 1024 * 1024
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file received")
        if len(contents) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    try:
        from PIL import Image
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        image_array = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

    try:
        import cv2
        detector = ModelManager.get_yolov8_detector()
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        detections = detector.detect(image_bgr)

        if not detections:
            return None, JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": "No face detected in the image. Ensure your face is clearly visible.",
                }
            )

        best_face = max(detections, key=lambda x: x[4])
        x1, y1, x2, y2, conf = best_face
        h, w = image_array.shape[:2]
        pad_x = int((x2 - x1) * 0.1)
        pad_y = int((y2 - y1) * 0.1)
        x1 = max(0, int(x1) - pad_x)
        y1 = max(0, int(y1) - pad_y)
        x2 = min(w, int(x2) + pad_x)
        y2 = min(h, int(y2) + pad_y)
        face_crop = image_array[y1:y2, x1:x2]
    except Exception as e:
        logger.error(f"Face detection error: {e}")
        return None, JSONResponse(
            status_code=200,
            content={"matched": False, "message": f"Face detection failed: {str(e)}"}
        )

    try:
        extractor = ModelManager.get_facenet_extractor()
        embedding = extractor.extract_embedding(face_crop)
        if embedding is None:
            return None, JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": "Could not extract face features from the cropped face.",
                }
            )
        return embedding, None
    except ImportError:
        return None, JSONResponse(
            status_code=200,
            content={
                "matched": False,
                "message": "Face recognition model not loaded on server. Contact admin.",
            }
        )
    except Exception as e:
        logger.error(f"Embedding extraction error: {e}")
        return None, JSONResponse(
            status_code=200,
            content={"matched": False, "message": f"Could not process face: {str(e)}"}
        )


def _match_embedding(embedding: np.ndarray, firebase, threshold: float = 0.55):
    """
    Compare embedding against all registered students.
    Returns (best_student | None, confidence: float, best_distance: float).
    """
    all_students = firebase.get_all_students()
    best_distance = float("inf")
    best_student = None

    for student in all_students:
        stored_embs = FirebaseService.get_all_embeddings(student)
        for arr in stored_embs:
            if arr.shape != embedding.shape:
                logger.debug(
                    f"Shape mismatch for {student.get('student_id')}: "
                    f"{arr.shape} vs {embedding.shape}"
                )
                continue
            dist = float(cosine(embedding, arr))
            if dist < best_distance:
                best_distance = dist
                best_student = student

    confidence = float(1.0 - min(best_distance, 1.0)) if best_student else 0.0
    return best_student, confidence, best_distance


# ── Step 1: Detect face only (NO database write) ──────────────────────────────

@router.post(
    "/detect-face-only",
    status_code=status.HTTP_200_OK,
    summary="Detect and identify face — does NOT write to database",
)
async def detect_face_only(
    file: UploadFile = File(..., description="JPEG or PNG image containing a face"),
):
    """
    Step 1 of the two-step attendance flow.

    Accepts a **multipart/form-data** image (field ``file``), extracts the face
    embedding, and matches it against registered students.

    **No attendance record is written.** The caller receives identification
    data and must call ``POST /confirm-attendance`` to persist the record.

    Returns:
        {
          "matched": true/false,
          "message": "...",
          "student_name": "Alice Smith",   # if matched
          "student_id": "STU001",          # if matched
          "confidence": 0.97               # if matched
        }
    """
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    try:
        THRESHOLD = 0.55
        best_student, confidence, best_distance = _match_embedding(
            embedding, firebase, THRESHOLD
        )

        if best_student is None or best_distance > THRESHOLD:
            return JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": (
                        "Face not recognised. "
                        f"Best similarity: {max(0.0, 1 - best_distance):.2f} "
                        f"(threshold: {1 - THRESHOLD:.2f}). "
                        "Ensure your face is clearly visible and well-lit, "
                        "or ask admin to register your face profile."
                    ),
                }
            )

        student_id = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")

        logger.info(
            f"Face identified (detection only, NOT recorded): "
            f"{student_id} ({student_name}) conf={confidence:.2f}"
        )

        return JSONResponse(
            status_code=200,
            content={
                "matched": True,
                "message": f"Face identified: {student_name}",
                "student_name": student_name,
                "student_id": student_id,
                "confidence": round(confidence, 4),
            }
        )

    except ImportError:
        return JSONResponse(
            status_code=200,
            content={"matched": False, "message": "Server missing scipy library for face matching."}
        )
    except Exception as e:
        logger.error(f"Matching error: {e}")
        raise HTTPException(status_code=500, detail=f"Face matching failed: {str(e)}")


# ── Step 2: Confirm attendance (writes to database) ───────────────────────────

@router.post(
    "/confirm-attendance",
    status_code=status.HTTP_200_OK,
    summary="Confirm and persist an attendance record after user approval",
)
async def confirm_attendance(
    student_id: str = Body(..., embed=True),
    confidence: float = Body(0.0, embed=True),
):
    """
    Step 2 of the two-step attendance flow.

    Called **only after the user has confirmed** the detected identity in the
    frontend UI. Writes the attendance record to Firestore / Realtime DB.

    Body (JSON):
        {
          "student_id": "STU001",
          "confidence": 0.97
        }

    Returns:
        {
          "success": true,
          "record_id": "...",
          "student_id": "STU001",
          "student_name": "Alice Smith",
          "timestamp": "2026-04-27T10:00:00"
        }
    """
    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    student = firebase.get_student(student_id)
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"Student {student_id} not found in the system."
        )

    try:
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id,
            timestamp=timestamp,
            confidence=confidence,
            track_id=None,
            camera_id="web_confirmed",
            metadata={
                "method": "face_recognition_confirmed",
                "confirmed_by_user": True,
            }
        )

        student_name = student.get("name", "Unknown")
        logger.info(
            f"Attendance confirmed and recorded: {student_id} ({student_name}) "
            f"conf={confidence:.2f} record={result.get('record_id', '')}"
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "record_id": result.get("record_id", ""),
                "student_id": student_id,
                "student_name": student_name,
                "confidence": round(confidence, 4),
                "timestamp": timestamp.isoformat(),
                "message": f"Attendance marked successfully for {student_name}",
            }
        )
    except Exception as e:
        logger.error(f"Failed to save confirmed attendance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Attendance recording failed: {str(e)}"
        )


# ── Legacy: Detect + mark in one step (kept for backward compat) ──────────────

@router.post(
    "/detect-face",
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Detect face and mark attendance in a single step",
)
async def detect_face_and_mark(
    file: UploadFile = File(..., description="JPEG or PNG image containing a face"),
):
    """
    Legacy single-step endpoint. Prefer the two-step flow:
      POST /detect-face-only  →  user confirms  →  POST /confirm-attendance

    Kept for backward compatibility with older integrations.
    """
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    try:
        THRESHOLD = 0.55
        best_student, confidence, best_distance = _match_embedding(
            embedding, firebase, THRESHOLD
        )

        if best_student is None or best_distance > THRESHOLD:
            return JSONResponse(
                status_code=200,
                content={
                    "matched": False,
                    "message": (
                        "Face not recognised. "
                        f"Best similarity: {max(0.0, 1 - best_distance):.2f} "
                        f"(threshold: {1 - THRESHOLD:.2f}). "
                        "Ensure your face is clearly visible and well-lit, "
                        "or ask admin to register your face profile."
                    ),
                }
            )

        student_id = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")

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
        logger.info(
            f"Attendance marked via legacy upload: {student_id} ({student_name}) "
            f"conf={confidence:.2f}"
        )

        return JSONResponse(
            status_code=200,
            content={
                "matched": True,
                "message": f"Attendance marked successfully for {student_name}",
                "record_id": result.get("record_id", ""),
                "student_name": student_name,
                "student_id": student_id,
                "confidence": round(confidence, 4),
                "timestamp": timestamp.isoformat(),
            }
        )
    except ImportError:
        return JSONResponse(
            status_code=200,
            content={"matched": False, "message": "Server missing scipy library for face matching."}
        )
    except Exception as e:
        logger.error(f"Matching error: {e}")
        raise HTTPException(status_code=500, detail=f"Face matching failed: {str(e)}")


# ── Student Management ────────────────────────────────────────────────────────

@router.post(
    "/register-student",
    response_model=StudentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_student(request: StudentRegistrationRequest) -> StudentRegistrationResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        existing = firebase.get_student(request.student_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Student {request.student_id} already registered")

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


@router.get("/students", response_model=StudentListResponse)
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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve students: {str(e)}")


@router.get("/students/{student_id}", response_model=StudentInfo)
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
        raise HTTPException(status_code=500, detail=f"Failed to get student: {str(e)}")


# ── Attendance Management ─────────────────────────────────────────────────────

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
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.post("/mark-mobile", response_model=MarkAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def mark_attendance_mobile(
    student_id: str = Query(...),
    image_base64: str = Query(...)
) -> MarkAttendanceResponse:
    """Mark attendance from mobile app (query-param base64). Legacy endpoint — kept for Flutter app."""
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        student = firebase.get_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

        from PIL import Image
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_array = np.array(image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        try:
            THRESHOLD = 0.6
            extractor = ModelManager.get_facenet_extractor()
            embedding = extractor.extract_embedding(image_array)
            if embedding is None:
                raise HTTPException(status_code=400, detail="No face detected")

            embeddings = FirebaseService.get_all_embeddings(student)
            if not embeddings:
                raise HTTPException(status_code=404, detail="No face profile found for student")

            best_match = None
            for arr in embeddings:
                dist = float(cosine(embedding, arr))
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
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.get("/attendance", response_model=AttendanceListResponse)
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

        from_date = datetime.fromisoformat(date_from) if date_from else None
        to_date = datetime.fromisoformat(date_to) if date_to else None

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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve attendance: {str(e)}")


@router.get("/attendance/daily-report", response_model=DailyReportResponse)
async def get_daily_report(date: Optional[str] = Query(None)) -> DailyReportResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")

        report_date = datetime.fromisoformat(date) if date else None
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
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


# ── Stream Management ─────────────────────────────────────────────────────────

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
        return StreamHealth(stream_id=request.stream_id, status="idle", last_frame=None, frames_processed=0, fps=0.0, errors=0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add stream: {str(e)}")


@router.get("/streams")
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


# ── System Health / Stats ─────────────────────────────────────────────────────

@router.get("/health", response_model=HealthCheckResponse)
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
        return HealthCheckResponse(status="error", services={"error": str(e)}, uptime_seconds=0)


@router.get("/stats", response_model=SystemStatsResponse)
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
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
