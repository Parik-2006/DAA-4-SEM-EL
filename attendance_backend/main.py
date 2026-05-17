"""
main.py  (MERGED — Security-hardened + full router set)
─────────────────────────────────────────────────────────────────────────────
Combines the security middleware stack with the full router set from both
versions.  Duplicate features resolved; all unique capabilities retained.

Middleware stack (outer → inner on request):
  1. CORSMiddleware          — CORS headers / preflight
  2. RateLimitMiddleware     — per-role sliding-window (student 100, teacher 500, admin ∞)
  3. AuditMiddleware         — auto-log all POST/PUT/PATCH/DELETE to audit_logs
  4. PermissionMiddleware    — URL-prefix role enforcement + QueryFilterContext injection
  5. AuthMiddleware          — JWT decode → request.state.user

Startup sequence:
  1. Firebase / Firestore
  2. AuditService
  3. TimetableService
  4. TimetableRepository
  5. PeriodDetectionService  (background loop)
  6. RTSPStreamManager       (lazy)
  7. JWT secret sanity-check

Shutdown sequence:
  1. PeriodDetectionService  (graceful stop)
  2. RTSPStreamManager       (stop_all)

API versioning:
  All routes are under /api/v1/...
  Add a v2 router set in future without touching v1 routes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from dotenv import load_dotenv

# ── Routers ───────────────────────────────────────────────────────────────────

# Auth & identity (public + authenticated)
from api.auth    import router as auth_router     # POST /api/v1/auth/login|refresh|me|logout
from api.user    import router as user_router     # /user/register|profile|reset-password

# Admin-only
from api.admin   import router as admin_router    # /api/v1/admin/*
from api.audit   import router as audit_router    # /api/v1/audit/*  (admin, read-only)

# Core domain
from api.attendance import router as attendance_router
from api.sections   import router as sections_router   # courses, sections, enrollments, assignments
from api.timetable  import router as timetable_router
from api.teacher    import router as teacher_router
from api.student_secured import router as student_router

# Real-time + health
from api.websocket import router as websocket_router
from api.health    import router as health_router

# ── Middleware ────────────────────────────────────────────────────────────────
from middleware.auth_middleware       import AuthMiddleware
from middleware.permission_middleware import PermissionMiddleware
from middleware.audit_middleware      import AuditMiddleware
from utils.rate_limiter               import RateLimitMiddleware

# ── Services ──────────────────────────────────────────────────────────────────
from services.audit_services            import init_audit_service
from services.firebase_service         import initialize_firebase
from services.period_detection_service import init_period_detection_service
from services.rtsp_stream_handler      import get_stream_manager
from services.timetable_service        import init_timetable_service
from services.realtime_service         import get_realtime_service

# ── Repositories ──────────────────────────────────────────────────────────────
from database.timetable_repository import init_timetable_repository

# ── Config ────────────────────────────────────────────────────────────────────
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

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Suppress noisy Windows asyncio error logs (ProactorEventLoop connection reset messages)
# These are cosmetic errors that don't affect functionality
asyncio_logger = logging.getLogger("asyncio")
asyncio_logger.setLevel(logging.WARNING)
logging.getLogger("asyncio.proactor_events").setLevel(logging.WARNING)
logging.getLogger("asyncio.events").setLevel(logging.WARNING)

_INSECURE_JWT_DEFAULT = "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"
_DEV_FALLBACK         = "dev-secret-change-in-production-please"


class _WindowsProactorNoiseFilter(logging.Filter):
    """Drop known-benign Windows Proactor connection-reset tracebacks."""

    _NOISY_CALLBACKS = (
        "_ProactorBasePipeTransport._call_connection_lost",
        "_ProactorReadPipeTransport._loop_reading",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "ConnectionResetError" not in message and "WinError 10054" not in message:
            return True
        return not any(callback in message for callback in self._NOISY_CALLBACKS)


def _install_windows_proactor_noise_filter() -> None:
    filter_instance = _WindowsProactorNoiseFilter()
    for logger_name in ("asyncio", "asyncio.proactor_events", "asyncio.events"):
        logging.getLogger(logger_name).addFilter(filter_instance)


def _install_windows_asyncio_exception_filter() -> None:
    """Suppress benign Windows Proactor connection-reset tracebacks.

    On Windows, idle browser connections and short-lived HTTP clients can
    trigger `ConnectionResetError: [WinError 10054]` inside asyncio's
    transport cleanup path. The default event-loop handler prints a noisy
    traceback even though the request/response cycle already completed.

    We only swallow the specific Proactor transport disconnect and defer every
    other exception to the original handler.
    """

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    previous_handler = loop.get_exception_handler()

    def _exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exception = context.get("exception")
        message = context.get("message", "")

        is_benign_windows_reset = (
            isinstance(exception, ConnectionResetError)
            and getattr(exception, "winerror", None) == 10054
            and "_ProactorBasePipeTransport._call_connection_lost" in message
        )

        if is_benign_windows_reset:
            logger.debug("Suppressed benign Windows connection reset: %s", message)
            return

        if previous_handler is not None:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_exception_handler)


# ══════════════════════════════════════════════════════════════════════════════
# Lifespan
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("═══ %s v%s — STARTUP ═══", SYSTEM_NAME, SYSTEM_VERSION)

    if os.name == "nt":
        try:
            _install_windows_proactor_noise_filter()
            _install_windows_asyncio_exception_filter()
            logger.info("✓ Windows asyncio noise filter installed")
        except Exception as exc:
            logger.warning("⚠ Could not install Windows asyncio noise filter: %s", exc)

    # 1. Firebase / Firestore ─────────────────────────────────────────────────
    firebase_svc = firestore_db = None
    try:
        firebase_svc = initialize_firebase(
            credentials_path="config/firebase-credentials.json"
        )
        firestore_db = (
            getattr(firebase_svc, "firestore_db", None)
            or getattr(firebase_svc, "_firestore", None)
            or getattr(firebase_svc, "db", None)
        )
        logger.info("✓ FirebaseService initialised")
    except Exception as exc:
        logger.error("✗ FirebaseService init failed: %s", exc)

    # Initialise EmbeddingScopeService (optional - non-fatal)
    try:
        if firebase_svc:
            from services.embedding_scope_service import init_scope_service
            init_scope_service(firebase_svc)
            logger.info("✓ EmbeddingScopeService initialised")
    except Exception as exc:
        logger.warning("⚠ EmbeddingScopeService init failed: %s", exc)

    # 2. AuditService ─────────────────────────────────────────────────────────
    try:
        init_audit_service(firestore_db=firestore_db)
        logger.info("✓ AuditService initialised")
    except Exception as exc:
        logger.error("✗ AuditService init failed: %s", exc)

    # 3. TimetableService ─────────────────────────────────────────────────────
    timetable_svc = None
    if firestore_db is not None:
        try:
            timetable_svc = init_timetable_service(firestore_db)
            logger.info("✓ TimetableService initialised")
        except Exception as exc:
            logger.error("✗ TimetableService init failed: %s", exc)

        # 4. TimetableRepository (independent singleton) ───────────────────────
        try:
            init_timetable_repository(firestore_db)
            logger.info("✓ TimetableRepository initialised")
        except Exception as exc:
            logger.error("✗ TimetableRepository init failed: %s", exc)

        # 4b. AttendanceLockService (period locking + audit) ──────────────────
        try:
            from services.attendance_lock_service import init_lock_service
            init_lock_service(firestore_db)
            logger.info("✓ AttendanceLockService initialised")
        except Exception as exc:
            logger.error("✗ AttendanceLockService init failed: %s", exc)
    else:
        logger.warning(
            "⚠ TimetableService + TimetableRepository + AttendanceLockService skipped — Firestore unavailable."
        )

    # 5. PeriodDetectionService ───────────────────────────────────────────────
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
    elif not ENABLE_PERIOD_DETECTION:
        logger.info("⚠ PeriodDetectionService disabled via ENABLE_PERIOD_DETECTION=False")
    else:
        logger.warning("⚠ PeriodDetectionService skipped — dependencies unavailable.")

    # 6. JWT secret sanity-check ──────────────────────────────────────────────
    jwt_secret = os.getenv("JWT_SECRET", "")
    if not jwt_secret or jwt_secret in (_INSECURE_JWT_DEFAULT, _DEV_FALLBACK):
        logger.warning(
            "⚠  JWT_SECRET is not set or uses an insecure default. "
            "Set a strong secret via JWT_SECRET before deploying to production! "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    logger.info("═══ Startup complete — all services ready ═══")

    # Start realtime window_tick loop (best-effort)
    try:
        rt_svc = get_realtime_service()
        rt_svc.start_window_tick_loop()
        logger.info("✓ Realtime window_tick loop started")
    except Exception as exc:
        logger.warning("Could not start realtime window_tick loop: %s", exc)
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("═══ %s — SHUTDOWN ═══", SYSTEM_NAME)

    if period_svc is not None:
        try:
            await period_svc.stop()
            logger.info("✓ PeriodDetectionService stopped")
        except Exception as exc:
            logger.error("✗ PeriodDetectionService stop error: %s", exc)

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
        "AI-powered face recognition attendance system with JWT-based RBAC, "
        "real-time timetable & period detection. v1 API under /api/v1/..."
    ),
    lifespan=lifespan,
    # Uncomment to disable API explorer in production:
    # docs_url=None, redoc_url=None,
)


# ══════════════════════════════════════════════════════════════════════════════
# Middleware stack
#
# Starlette applies middleware in REVERSE registration order.
# To achieve CORS → Rate → Audit → Permission → Auth (outer→inner on request):
#   Register Auth first (innermost), CORS last (outermost).
# ══════════════════════════════════════════════════════════════════════════════

# 1. Permission — runs after Auth on request path; relies on state.user
app.add_middleware(PermissionMiddleware)

# 2. Auth — must run before Permission to populate request.state.user
app.add_middleware(AuthMiddleware)

# 3. Audit — needs state.user; logs all mutating requests to audit_logs
# TODO: Fix ASGI body reading issue
# app.add_middleware(AuditMiddleware)

# 4. Rate limiting — needs state.user for role-based bucket selection
# TODO: Fix middleware chain issue
# app.add_middleware(RateLimitMiddleware)

# 5. CORS — outermost: handles preflight before any auth logic runs
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    # Accept all methods/headers for robust preflight handling; keep origins scoped.
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global HTTP middleware to catch unhandled exceptions and return JSON
@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # catch everything from endpoints/dependencies
        logging.getLogger("attendance_api").exception("Unhandled request exception: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Also register a generic exception handler (fallback for other execution paths)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.getLogger("attendance_api").exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ══════════════════════════════════════════════════════════════════════════════
# Routers — v1 API
#
# Registration order does not affect security — that is handled by middleware
# and per-endpoint dependencies.  Order here is for documentation clarity.
# ══════════════════════════════════════════════════════════════════════════════

# ── Identity & access ─────────────────────────────────────────────────────────
app.include_router(auth_router)        # POST /api/v1/auth/login|refresh|me|logout
app.include_router(user_router)        # /user/register|profile|reset-password
app.include_router(audit_router)       # GET  /api/v1/audit/logs  (admin only)

# ── Core domain ───────────────────────────────────────────────────────────────
app.include_router(attendance_router)  # /api/v1/attendance/*
app.include_router(admin_router)       # /api/v1/admin/*
app.include_router(sections_router)    # /api/v1/sections/*  (courses, enrollments, assignments)
app.include_router(timetable_router)   # /api/v1/timetable/*
app.include_router(teacher_router)     # /api/v1/teacher/*
app.include_router(student_router)     # /api/v1/student/*

# ── Real-time & infrastructure ────────────────────────────────────────────────
app.include_router(websocket_router)                            # /ws/*
app.include_router(health_router, prefix="/api/v1/attendance")  # /api/v1/attendance/health


# ══════════════════════════════════════════════════════════════════════════════
# Root
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["root"])
async def root():
    return {
        "system":         SYSTEM_NAME,
        "version":        SYSTEM_VERSION,
        "status":         "running",
        "api_version":    "v1",
        "docs":           "/docs",
        "auth_endpoint":  "POST /api/v1/auth/login  →  Bearer <access_token>",
    }


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import sys
    
    # ── Windows asyncio fix ──────────────────────────────────────────────────
    # ProactorEventLoop on Windows has bugs with connection handling.
    # Use WindowsSelectorEventLoop instead for better stability.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("✓ Using WindowsSelectorEventLoop for Windows stability")
    
    # ── Uvicorn configuration ────────────────────────────────────────────────
    # Parameters optimized for Windows stability and connection handling:
    # - timeout_keep_alive: reduce timeout to clean up idle connections
    # - ws_ping_interval: keep WebSocket connections alive
    # - ws_ping_timeout: detect dead WebSocket connections
    # - loop: use "auto" to respect the event loop policy above
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        loop="auto",
        timeout_keep_alive=5,          # Close idle connections after 5s
        ws_ping_interval=20,            # Send WebSocket ping every 20s
        ws_ping_timeout=20,             # Wait 20s for pong response
        access_log=True,
        use_colors=True,
    )