"""
REST API endpoints for attendance system.
Two-step attendance: detect-face (identify only) → confirm-attendance (write to DB).

Optimisations applied (2026-04):
  1. Pre-detection resize to 640 px long-edge  → RAM stays bounded
  2. Blocking ML inference moved to a thread-pool → event loop stays live
  3. Explicit gc.collect() + del after inference  → no tensor/array leaks

Stream additions (2026-04):
  4. POST /streams now accepts classroom_id → passed to RTSPStreamHandler for
     per-classroom student filtering in its FAISS index.
  5. GET  /streams/{stream_id} returns full per-stream metrics.
  6. GET  /streams/{stream_id}/ai-status returns is_ai_active + student-index
     readiness — designed for the teacher dashboard polling loop.
  7. POST /streams/{stream_id}/reload-students triggers a fresh background
     student reload without restarting the stream.
"""

import gc
import logging
import base64
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Body, File, UploadFile, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

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

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB
TARGET_LONG_EDGE = 640                 # resize before YOLO inference
COSINE_THRESHOLD = 0.55


# ── Image pre-processing helper ────────────────────────────────────────────────

def _resize_if_needed(image_array: np.ndarray, long_edge: int = TARGET_LONG_EDGE) -> np.ndarray:
    h, w = image_array.shape[:2]
    max_dim = max(h, w)
    if max_dim <= long_edge:
        return image_array
    import cv2
    scale = long_edge / max_dim
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)
    logger.debug("Resized image %dx%d -> %dx%d (scale=%.2f)", w, h, new_w, new_h, scale)
    return resized


# ── Synchronous inference block (runs in thread, NOT on event loop) ────────────

def _run_detection_and_embedding(image_array: np.ndarray):
    import cv2
    image_array = _resize_if_needed(image_array)
    try:
        detector = ModelManager.get_yolov8_detector()
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        detections = detector.detect(image_bgr)
    except Exception as e:
        logger.error("Face detection error: %s", e)
        return None, {"matched": False, "message": f"Face detection failed: {e}"}
    finally:
        try:
            del image_bgr
        except NameError:
            pass
        gc.collect()

    if not detections:
        return None, {
            "matched": False,
            "message": "No face detected in the image. Ensure your face is clearly visible.",
        }

    best_face = max(detections, key=lambda x: x[4])
    x1, y1, x2, y2, conf = best_face
    h, w = image_array.shape[:2]
    pad_x = int((x2 - x1) * 0.1)
    pad_y = int((y2 - y1) * 0.1)
    x1 = max(0, int(x1) - pad_x)
    y1 = max(0, int(y1) - pad_y)
    x2 = min(w, int(x2) + pad_x)
    y2 = min(h, int(y2) + pad_y)
    face_crop = image_array[y1:y2, x1:x2].copy()

    del image_array, detections
    gc.collect()

    try:
        extractor = ModelManager.get_facenet_extractor()
        embedding = extractor.extract_embedding(face_crop)
    except ImportError:
        return None, {"matched": False, "message": "Face recognition model not loaded on server. Contact admin."}
    except Exception as e:
        logger.error("Embedding extraction error: %s", e)
        return None, {"matched": False, "message": f"Could not process face: {e}"}
    finally:
        del face_crop
        gc.collect()

    if embedding is None:
        return None, {"matched": False, "message": "Could not extract face features from the cropped face."}

    return embedding, None


# ── Async wrapper ─────────────────────────────────────────────────────────────

async def _extract_embedding_from_upload(file: UploadFile):
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file received")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    try:
        from PIL import Image
        image_array = np.array(Image.open(io.BytesIO(contents)).convert("RGB"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
    finally:
        del contents
        gc.collect()

    embedding, error_content = await run_in_threadpool(_run_detection_and_embedding, image_array)
    del image_array
    gc.collect()

    if error_content is not None:
        return None, JSONResponse(status_code=200, content=error_content)
    return embedding, None


# ── Synchronous matching (runs in thread) ─────────────────────────────────────

def _match_embedding_sync(embedding: np.ndarray, firebase, threshold: float = COSINE_THRESHOLD):
    all_students = firebase.get_all_students()
    best_distance = float("inf")
    best_student = None

    for student in all_students:
        stored_embs = FirebaseService.get_all_embeddings(student)
        for arr in stored_embs:
            if arr.shape != embedding.shape:
                continue
            dist = float(cosine(embedding, arr))
            if dist < best_distance:
                best_distance = dist
                best_student = student

    confidence = float(1.0 - min(best_distance, 1.0)) if best_student else 0.0
    return best_student, confidence, best_distance


# ── Step 1: Detect face only ──────────────────────────────────────────────────

@router.post(
    "/detect-face-only",
    status_code=status.HTTP_200_OK,
    summary="Detect and identify face - does NOT write to database",
)
async def detect_face_only(
    file: UploadFile = File(..., description="JPEG or PNG image containing a face"),
):
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    try:
        best_student, confidence, best_distance = await run_in_threadpool(
            _match_embedding_sync, embedding, firebase, COSINE_THRESHOLD
        )
        del embedding
        gc.collect()

        if best_student is None or best_distance > COSINE_THRESHOLD:
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": (
                    "Face not recognised. "
                    f"Best similarity: {max(0.0, 1 - best_distance):.2f} "
                    f"(threshold: {1 - COSINE_THRESHOLD:.2f}). "
                    "Ensure your face is clearly visible and well-lit, "
                    "or ask admin to register your face profile."
                ),
            })

        student_id = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")
        logger.info("Face identified (NOT recorded): %s (%s) conf=%.2f", student_id, student_name, confidence)

        return JSONResponse(status_code=200, content={
            "matched": True,
            "message": f"Face identified: {student_name}",
            "student_name": student_name,
            "student_id": student_id,
            "confidence": round(confidence, 4),
        })
    except ImportError:
        return JSONResponse(status_code=200, content={"matched": False, "message": "Server missing scipy library."})
    except Exception as e:
        logger.error("Matching error: %s", e)
        raise HTTPException(status_code=500, detail=f"Face matching failed: {e}")


# ── Step 2: Confirm attendance ────────────────────────────────────────────────

@router.post(
    "/confirm-attendance",
    status_code=status.HTTP_200_OK,
    summary="Confirm and persist an attendance record after user approval",
)
async def confirm_attendance(
    student_id: str = Body(..., embed=True),
    confidence: float = Body(0.0, embed=True),
):
    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    student = firebase.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found in the system.")

    try:
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id, timestamp=timestamp, confidence=confidence,
            track_id=None, camera_id="web_confirmed",
            metadata={"method": "face_recognition_confirmed", "confirmed_by_user": True}
        )
        student_name = student.get("name", "Unknown")
        return JSONResponse(status_code=200, content={
            "success": True,
            "record_id": result.get("record_id", ""),
            "student_id": student_id,
            "student_name": student_name,
            "confidence": round(confidence, 4),
            "timestamp": timestamp.isoformat(),
            "message": f"Attendance marked successfully for {student_name}",
        })
    except Exception as e:
        logger.error("Failed to save confirmed attendance: %s", e)
        raise HTTPException(status_code=500, detail=f"Attendance recording failed: {e}")


# ── Legacy single-step endpoint ────────────────────────────────────────────────

@router.post(
    "/detect-face",
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Detect face and mark attendance in a single step",
)
async def detect_face_and_mark(
    file: UploadFile = File(..., description="JPEG or PNG image containing a face"),
):
    embedding, err = await _extract_embedding_from_upload(file)
    if err is not None:
        return err

    firebase = get_firebase_service()
    if not firebase:
        raise HTTPException(status_code=503, detail="Firebase service not initialised")

    try:
        best_student, confidence, best_distance = await run_in_threadpool(
            _match_embedding_sync, embedding, firebase, COSINE_THRESHOLD
        )
        del embedding
        gc.collect()

        if best_student is None or best_distance > COSINE_THRESHOLD:
            return JSONResponse(status_code=200, content={
                "matched": False,
                "message": (
                    "Face not recognised. "
                    f"Best similarity: {max(0.0, 1 - best_distance):.2f} "
                    f"(threshold: {1 - COSINE_THRESHOLD:.2f}). "
                    "Ensure your face is clearly visible and well-lit, "
                    "or ask admin to register your face profile."
                ),
            })

        student_id = best_student.get("student_id", "")
        student_name = best_student.get("name", "Unknown")
        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id, timestamp=timestamp, confidence=confidence,
            track_id=None, camera_id="web_upload",
            metadata={"method": "face_recognition_upload", "threshold": COSINE_THRESHOLD, "distance": best_distance}
        )
        return JSONResponse(status_code=200, content={
            "matched": True,
            "message": f"Attendance marked successfully for {student_name}",
            "record_id": result.get("record_id", ""),
            "student_name": student_name,
            "student_id": student_id,
            "confidence": round(confidence, 4),
            "timestamp": timestamp.isoformat(),
        })
    except ImportError:
        return JSONResponse(status_code=200, content={"matched": False, "message": "Server missing scipy library."})
    except Exception as e:
        logger.error("Matching error: %s", e)
        raise HTTPException(status_code=500, detail=f"Face matching failed: {e}")


# ── Student Management ────────────────────────────────────────────────────────

@router.post("/register-student", response_model=StudentRegistrationResponse, status_code=status.HTTP_201_CREATED)
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
            student_id=request.student_id, name=request.name, email=request.email,
            embeddings=embeddings_array, phone=request.phone, metadata=request.metadata
        )
        for emb in request.embeddings[1:]:
            firebase.store_embedding(request.student_id, np.array(emb))
        return StudentRegistrationResponse(success=True, student_id=request.student_id, message="Student registered successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error registering student: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to register student: {e}")


@router.get("/students", response_model=StudentListResponse)
async def get_students(limit: int = Query(1000, ge=1, le=10000), offset: int = Query(0, ge=0)) -> StudentListResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")
        all_students = firebase.get_all_students()
        paginated = all_students[offset:offset + limit]
        students_info = [
            StudentInfo(
                student_id=s.get("student_id", ""), name=s.get("name", ""), email=s.get("email", ""),
                phone=s.get("phone"), registered_at=s.get("registered_at", ""), last_seen=s.get("last_seen"),
                attendance_count=s.get("attendance_count", 0), status=s.get("status", "active"), metadata=s.get("metadata")
            ) for s in paginated
        ]
        return StudentListResponse(success=True, count=len(students_info), students=students_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve students: {e}")


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
            student_id=student.get("student_id", ""), name=student.get("name", ""), email=student.get("email", ""),
            phone=student.get("phone"), registered_at=student.get("registered_at", ""), last_seen=student.get("last_seen"),
            attendance_count=student.get("attendance_count", 0), status=student.get("status", "active"), metadata=student.get("metadata")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get student: {e}")


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
            student_id=request.student_id, timestamp=timestamp, confidence=request.confidence,
            track_id=request.track_id, camera_id=request.camera_id, metadata=request.metadata
        )
        return MarkAttendanceResponse(
            success=True, record_id=result["record_id"], student_id=request.student_id,
            timestamp=timestamp.isoformat(), message="Attendance marked successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {e}")


@router.post("/mark-mobile", response_model=MarkAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def mark_attendance_mobile(student_id: str = Query(...), image_base64: str = Query(...)) -> MarkAttendanceResponse:
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
            image_array = np.array(Image.open(io.BytesIO(image_data)).convert("RGB"))
            del image_data
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
        image_array = _resize_if_needed(image_array)

        def _mobile_inference():
            THRESHOLD = 0.6
            extractor = ModelManager.get_facenet_extractor()
            embedding = extractor.extract_embedding(image_array)
            if embedding is None:
                raise ValueError("No face detected")
            embeddings = FirebaseService.get_all_embeddings(student)
            if not embeddings:
                raise ValueError("No face profile found for student")
            best_match = min(float(cosine(embedding, arr)) for arr in embeddings)
            confidence = float(1.0 - min(best_match, 1.0))
            if best_match > THRESHOLD:
                raise ValueError(f"Face does not match. Confidence: {confidence:.2f}")
            return confidence

        try:
            confidence = await run_in_threadpool(_mobile_inference)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except (ImportError, HTTPException):
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            del image_array
            gc.collect()

        timestamp = datetime.now()
        result = firebase.mark_attendance(
            student_id=student_id, timestamp=timestamp, confidence=confidence,
            track_id=None, camera_id="mobile_app", metadata={"method": "face_recognition_mobile"}
        )
        return MarkAttendanceResponse(
            success=True, record_id=result["record_id"], student_id=student_id,
            timestamp=timestamp.isoformat(), message=f"Attendance marked (confidence: {confidence:.2f})"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {e}")


@router.get("/attendance", response_model=AttendanceListResponse)
async def get_attendance(
    student_id: Optional[str] = Query(None), date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> AttendanceListResponse:
    try:
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(status_code=503, detail="Firebase service not initialized")
        from_date = datetime.fromisoformat(date_from) if date_from else None
        to_date = datetime.fromisoformat(date_to) if date_to else None
        records = firebase.get_attendance_records(
            student_id=student_id, date_from=from_date, date_to=to_date, limit=limit + offset
        )
        paginated = records[offset:offset + limit]
        attendance_records = [
            AttendanceRecord(
                record_id=str(r.get("timestamp", "")), student_id=r.get("student_id", ""),
                timestamp=r.get("timestamp", ""), date=r.get("date", ""), time=r.get("time", ""),
                confidence=r.get("confidence", 0.0), track_id=r.get("track_id"),
                camera_id=r.get("camera_id", "default"), status=r.get("status", "present"), metadata=r.get("metadata")
            ) for r in paginated
        ]
        return AttendanceListResponse(success=True, count=len(attendance_records), records=attendance_records)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve attendance: {e}")


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
        return DailyReportResponse(date=report["date"], total_records=report["total_records"],
                                   unique_students=report["unique_students"], records=[])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")


# ── Stream Management ─────────────────────────────────────────────────────────

@router.post("/streams", response_model=StreamHealth, status_code=status.HTTP_201_CREATED)
async def add_stream(request: StreamConfig) -> StreamHealth:
    """
    Register and optionally start an RTSP stream.

    If classroom_id is present in the request body, only students in that
    classroom are loaded into the stream FAISS recognition index.  Leave it
    null to load all registered students.

    Student embeddings are fetched from Firebase automatically in a background
    thread immediately after the stream starts - the API returns without waiting.

    NOTE: Add  classroom_id: Optional[str] = None  to your StreamConfig schema
    in attendance_schemas.py to enable classroom filtering.
    """
    try:
        manager = get_stream_manager()

        # classroom_id is an optional extension to StreamConfig.
        # getattr with a default means the endpoint works even if the schema
        # field has not been added yet.
        classroom_id: Optional[str] = getattr(request, "classroom_id", None)

        handler = manager.add_stream(
            stream_id=request.stream_id,
            rtsp_url=request.rtsp_url,
            frame_skip=request.frame_skip,
            min_consecutive_frames=request.min_consecutive_frames,
            confidence_threshold=request.confidence_threshold,
            classroom_id=classroom_id,
        )
        if not handler:
            raise HTTPException(status_code=400, detail="Failed to add stream")

        if request.enabled:
            manager.start_stream(request.stream_id)

        return StreamHealth(
            stream_id=request.stream_id,
            status="running" if request.enabled else "idle",
            last_frame=None,
            frames_processed=0,
            fps=0.0,
            errors=0,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add stream: {e}")


@router.get("/streams")
async def get_streams():
    """List all registered streams with their full metrics (includes is_ai_active for each)."""
    try:
        manager = get_stream_manager()
        streams = manager.get_all_streams()
        return {"success": True, "count": len(streams), "streams": streams}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get streams: {e}")


@router.get("/streams/{stream_id}")
async def get_stream(stream_id: str):
    """
    Return full metrics for a single stream.

    Includes is_ai_active, students_loaded, students_loaded_count, and all
    motion/FPS statistics needed by the teacher dashboard.
    """
    try:
        manager = get_stream_manager()
        handler = manager.get_stream(stream_id)
        if handler is None:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {"success": True, "stream": handler.get_metrics()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stream: {e}")


@router.get(
    "/streams/{stream_id}/ai-status",
    summary="AI monitoring status for the teacher dashboard",
)
async def get_stream_ai_status(stream_id: str):
    """
    Lightweight polling endpoint for the teacher dashboard.

    Returns only the fields needed to drive the 'Live Monitoring' / 'System
    Idle' indicator and the student-index readiness banner.  Designed to be
    called every 2-5 seconds without fetching the full metrics payload.

    Response shape
    --------------
    {
      "stream_id": "cam_classroom_a",
      "classroom_id": "CS101",

      // Teacher dashboard indicator
      "is_ai_active": true,            // true -> "Live Monitoring"
      "display_status": "Live Monitoring",
      "last_ai_trigger": "2026-04-29T10:32:01.123456",

      // Student index readiness
      "students_loaded": true,
      "students_loaded_count": 32,
      "student_load_error": null,

      // Supplementary
      "fps": 14.2,
      "active_tracks": 3,
      "marked_students_today": 28,
      "stream_status": "running"
    }

    is_ai_active is True when YOLO + FaceNet ran within the last 3 seconds.
    Once motion stops the indicator stays green for 3 s before flipping to
    "System Idle", preventing rapid flickering on the dashboard.
    """
    try:
        manager = get_stream_manager()
        handler = manager.get_stream(stream_id)
        if handler is None:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")

        m = handler.get_metrics()
        is_ai_active: bool = m.get("is_ai_active", False)

        return JSONResponse(status_code=200, content={
            "stream_id": stream_id,
            "classroom_id": m.get("classroom_id"),

            # Teacher dashboard fields
            "is_ai_active": is_ai_active,
            "display_status": "Live Monitoring" if is_ai_active else "System Idle",
            "last_ai_trigger": m.get("last_ai_trigger"),

            # Student index readiness
            "students_loaded": m.get("students_loaded", False),
            "students_loaded_count": m.get("students_loaded_count", 0),
            "student_load_error": m.get("student_load_error"),

            # Supplementary context
            "fps": m.get("fps", 0.0),
            "active_tracks": m.get("active_tracks", 0),
            "marked_students_today": m.get("marked_students", 0),
            "stream_status": m.get("status", "unknown"),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get AI status: {e}")


@router.post("/streams/{stream_id}/start")
async def start_stream(stream_id: str):
    """
    Start a registered stream.

    Also triggers automatic student loading from Firebase in the background.
    Recognition becomes fully active once students_loaded flips to True
    (check via GET /streams/{stream_id}/ai-status).
    """
    try:
        manager = get_stream_manager()
        if not manager.start_stream(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {
            "success": True,
            "message": f"Stream {stream_id} started. Student embeddings loading in background.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {e}")


@router.post("/streams/{stream_id}/stop")
async def stop_stream(stream_id: str):
    try:
        manager = get_stream_manager()
        if not manager.stop_stream(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {"success": True, "message": f"Stream {stream_id} stopped"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop stream: {e}")


@router.post(
    "/streams/{stream_id}/reload-students",
    summary="Reload student embeddings from Firebase without restarting the stream",
)
async def reload_students(stream_id: str):
    """
    Trigger a background student reload for a running stream.

    Useful after new students are registered mid-session.  The existing FAISS
    index continues to serve recognition requests while the reload runs.
    Poll GET /streams/{stream_id}/ai-status and watch students_loaded to know
    when the new index is ready.
    """
    try:
        manager = get_stream_manager()
        if not manager.reload_students(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        return {
            "success": True,
            "message": f"Student reload triggered for stream {stream_id}. Poll ai-status for readiness.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload students: {e}")


# ── System Health / Stats ─────────────────────────────────────────────────────

@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Pure async - no blocking work.
    Because inference runs in a thread pool, this always responds instantly
    even while face detection is processing.
    """
    try:
        firebase = get_firebase_service()
        manager = get_stream_manager()
        services = {
            "firebase": "healthy" if firebase else "unavailable",
            "streams": "healthy" if manager else "unavailable",
            "models": "healthy" if ModelManager.is_initialized() else "not_initialized",
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
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")
