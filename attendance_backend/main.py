"""
main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application entry-point for the Smart Attendance System.

Startup sequence
----------------
1. Initialise Firebase / Firestore client
2. Initialise ModelManager (YOLOv8 + FaceNet) — done lazily on first request
3. Initialise FirebaseService singleton
4. Initialise TimetableService (requires Firestore client)
5. Initialise PeriodDetectionService (requires TimetableService)
6. Start PeriodDetectionService background loop (async task)
7. Initialise RTSPStreamManager

Shutdown sequence
-----------------
1. Stop PeriodDetectionService (graceful cancel + join)
2. Stop all RTSP streams
3. Clean up model resources

All services expose module-level get_*() functions so routers can access
singletons without circular imports.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Routers ────────────────────────────────────────────────────────────────────
from api.admin      import router as admin_router
from api.attendance import router as attendance_router
from api.timetable  import router as timetable_router   # NEW
from api.teacher    import router as teacher_router    # NEW (Module 3)
from api.student    import router as student_router    # NEW (Module 4)
from api.health     import router as health_router     # NEW

# ── Services ───────────────────────────────────────────────────────────────────
from services.firebase_service        import initialize_firebase
from services.rtsp_stream_handler     import get_stream_manager
from services.timetable_service       import init_timetable_service        # NEW
from services.period_detection_service import init_period_detection_service  # NEW

# ── Config ─────────────────────────────────────────────────────────────────────
from config.constants import (
    CORS_ALLOWED_HEADERS,
    CORS_ALLOWED_METHODS,
    CORS_ALLOWED_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    ENABLE_PERIOD_DETECTION,
    PERIOD_DETECTION_POLL_INTERVAL,
    SYSTEM_NAME,
    SYSTEM_VERSION,
)

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ══════════════════════════════════════════════════════════════════════════════
# Lifespan (replaces deprecated on_event)
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager that owns the full service lifecycle.

    Everything before ``yield`` runs at startup; everything after at shutdown.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # STARTUP
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("═══ %s v%s — STARTUP ═══", SYSTEM_NAME, SYSTEM_VERSION)

    # 1. Firebase / Firestore
    firebase_svc = None
    firestore_db = None
    try:
        firebase_svc = initialize_firebase(credentials_path="config/firebase-credentials.json")
        # Obtain the Firestore client from the service (adjust to your impl)
        firestore_db = (
            getattr(firebase_svc, "firestore_db", None)
            or getattr(firebase_svc, "_firestore", None)
            or getattr(firebase_svc, "db", None)
        )
        logger.info("✓ FirebaseService initialised")
    except Exception as exc:
        logger.error("✗ FirebaseService init failed: %s", exc)

    # 2. TimetableService  [NEW]
    timetable_svc = None
    if firestore_db is not None:
        try:
            timetable_svc = init_timetable_service(firestore_db)
            logger.info("✓ TimetableService initialised")
        except Exception as exc:
            logger.error("✗ TimetableService init failed: %s", exc)
    else:
        logger.warning(
            "⚠ TimetableService skipped — Firestore client unavailable."
        )

    # 3. PeriodDetectionService  [NEW]
    period_svc = None
    if ENABLE_PERIOD_DETECTION and timetable_svc is not None and firestore_db is not None:
        try:
            period_svc = init_period_detection_service(
                firestore_db=firestore_db,
                timetable_service=timetable_svc,
                poll_interval=PERIOD_DETECTION_POLL_INTERVAL,
            )
            await period_svc.start()
            logger.info(
                "✓ PeriodDetectionService started (poll=%ds)",
                PERIOD_DETECTION_POLL_INTERVAL,
            )
        except Exception as exc:
            logger.error("✗ PeriodDetectionService start failed: %s", exc)
    else:
        if not ENABLE_PERIOD_DETECTION:
            logger.info(
                "⚠ PeriodDetectionService disabled via ENABLE_PERIOD_DETECTION=False"
            )
        else:
            logger.warning(
                "⚠ PeriodDetectionService skipped — dependencies unavailable."
            )

    logger.info("═══ Startup complete — all services ready ═══")

    # ──────────────────────────────────────────────────────────────────────────
    # HAND CONTROL TO FASTAPI
    # ──────────────────────────────────────────────────────────────────────────
    yield

    # ──────────────────────────────────────────────────────────────────────────
    # SHUTDOWN
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("═══ %s — SHUTDOWN ═══", SYSTEM_NAME)

    if period_svc is not None:
        try:
            await period_svc.stop()
            logger.info("✓ PeriodDetectionService stopped")
        except Exception as exc:
            logger.error("✗ PeriodDetectionService stop error: %s", exc)

    # Stop all RTSP streams (if the manager exposes a shutdown method)
    try:
        mgr = get_stream_manager()
        if mgr and hasattr(mgr, "stop_all"):
            mgr.stop_all()
            logger.info("✓ All RTSP streams stopped")
    except Exception as exc:
        logger.error("✗ RTSP shutdown error: %s", exc)

    logger.info("═══ Shutdown complete ═══")


# ══════════════════════════════════════════════════════════════════════════════
# Application
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title=SYSTEM_NAME,
    version=SYSTEM_VERSION,
    description=(
        "AI-powered face recognition attendance system with real-time "
        "timetable & period detection."
    ),
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=CORS_ALLOWED_HEADERS,
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(attendance_router)
app.include_router(admin_router)
app.include_router(timetable_router)    # NEW (Module 2)
app.include_router(teacher_router)      # NEW (Module 3)
app.include_router(student_router)      # NEW (Module 4)
app.include_router(health_router, prefix="/api/v1/attendance")  # NEW (match frontend expectation)

# ── Root health check ──────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    return {
        "system": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
        "status": "running",
        "docs": "/docs",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )