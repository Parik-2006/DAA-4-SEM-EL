"""
Main FastAPI application for Smart Attendance System.

Entry point for the face recognition attendance backend API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import get_settings
from config.constants import API_PREFIX, CORS_ALLOWED_ORIGINS, SYSTEM_NAME, SYSTEM_VERSION
from config.logging_config import setup_logging
from models.model_manager import ModelManager
from api import health
from api import attendance
from api import user
from api import admin
from api import student
from api import admin_students
from api import courses
from api import qr_attendance
from services.firebase_service import initialize_firebase
from services.rtsp_stream_handler import get_stream_manager


# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {SYSTEM_NAME} v{SYSTEM_VERSION}")
    
    settings = get_settings()
    
    # Initialize Firebase
    try:
        if settings.firebase_credentials_path:
            logger.info("Initializing Firebase...")
            initialize_firebase(
                credentials_path=settings.firebase_credentials_path,
                database_url=getattr(settings, 'firebase_database_url', None),
                storage_bucket=getattr(settings, 'firebase_storage_bucket', None),
                use_firestore=getattr(settings, 'use_firestore', True)
            )
            logger.info("✓ Firebase initialized successfully")
        else:
            logger.warning("Firebase credentials path not configured")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        logger.warning("Operating without Firebase (data won't be persisted)")
    
    try:
        # Initialize models — use CPU if CUDA is not available
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing ML models on device: {device}")
        ModelManager.initialize(device=device)
        logger.info("✓ ML models initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        # Continue anyway - models can be loaded on-demand
    
    # Initialize stream manager
    try:
        logger.info("Initializing stream manager...")
        stream_manager = get_stream_manager()
        logger.info("✓ Stream manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize stream manager: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        ModelManager.cleanup()
        logger.info("Models cleaned up")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")
    
    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=SYSTEM_NAME,
    description="Face Recognition Attendance System API",
    version=SYSTEM_VERSION,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Root Endpoints ============

@app.get(
    "/",
    tags=["root"],
    summary="API Root",
    description="Get API information"
)
async def root() -> Dict[str, Any]:
    """
    Get API root information.
    
    Returns:
        Dictionary with API metadata
    """
    return {
        "name": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
        "docs": "/docs",
        "api_prefix": API_PREFIX,
    }


@app.get(
    "/info",
    tags=["root"],
    summary="System Information",
    description="Get detailed system information"
)
async def system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        Dictionary with system details
    """
    settings = get_settings()
    
    return {
        "system": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
        "environment": settings.fastapi_env,
        "api_prefix": API_PREFIX,
        "server": {
            "host": settings.host,
            "port": settings.port,
        },
        "models": ModelManager.get_status(),
    }


# ============ Route Registration ============

# Include health routes
app.include_router(health.router, prefix=API_PREFIX, tags=["health"])

# Include attendance routes
app.include_router(attendance.router, prefix=API_PREFIX, tags=["attendance"])

# Include user routes
app.include_router(user.router, prefix=API_PREFIX, tags=["user"])

# Include admin routes
app.include_router(admin.router, tags=["admin"])

# Include student routes
app.include_router(student.router, tags=["student"])

# Include admin student management routes
app.include_router(admin_students.router, prefix=API_PREFIX, tags=["admin-students"])

# Include course management routes
app.include_router(courses.router, prefix=API_PREFIX, tags=["admin-courses"])
# Backward compatibility for frontend calls using /api/v1/admin/courses
app.include_router(courses.router, prefix=f"{API_PREFIX}/admin", tags=["admin-courses"])

# Include QR attendance routes
app.include_router(qr_attendance.router, prefix=API_PREFIX, tags=["qr-attendance"])


# ============ Error Handlers ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors.
    
    Args:
        request: Request object
        exc: Exception that occurred
    
    Returns:
        JSON error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
        }
    )


# ============ Startup Event ============

@app.on_event("startup")
async def startup_event():
    """
    Handle startup events.
    """
    settings = get_settings()
    logger.info(f"API started in {settings.fastapi_env} mode")
    logger.info(f"Listening on {settings.host}:{settings.port}")


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    # Run development server
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.fastapi_reload,
        log_level=settings.log_level.lower(),
    )
