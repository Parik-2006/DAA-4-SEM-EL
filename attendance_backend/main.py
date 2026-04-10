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
    
    try:
        # Initialize models
        logger.info("Initializing ML models...")
        device = "cuda"  # Use GPU if available
        ModelManager.initialize(device=device)
        logger.info("ML models initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        # Continue anyway - models can be loaded on-demand
    
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
