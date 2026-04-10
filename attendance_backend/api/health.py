"""
Health check endpoints.

Provides system health status and diagnostics endpoints.
"""

from typing import Dict, Any
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from config.settings import get_settings
from config.constants import SYSTEM_NAME, SYSTEM_VERSION
from models.model_manager import ModelManager
from database.firebase_client import FirebaseClient


logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    system: str
    version: str
    timestamp: str
    components: Dict[str, Any]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check system health status"
)
async def health_check() -> HealthResponse:
    """
    Check system health and component status.
    
    Returns:
        HealthResponse: System health status and component info
    """
    try:
        from datetime import datetime
        
        settings = get_settings()
        
        # Check components
        components = {
            "database": check_database_health(),
            "models": check_models_health(),
            "config": {
                "status": "ok",
                "environment": settings.fastapi_env,
            }
        }
        
        # Overall status
        overall_status = "healthy"
        if any(c.get("status") != "ok" for c in components.values()):
            overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            system=SYSTEM_NAME,
            version=SYSTEM_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            components=components,
        )
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        )


@router.get(
    "/health/models",
    summary="Model Status",
    description="Check ML model status"
)
async def get_models_status() -> Dict[str, Any]:
    """
    Get detailed model status.
    
    Returns:
        Dictionary with model information
    """
    try:
        status_info = ModelManager.get_status()
        return {
            "status": "ready" if status_info["initialized"] else "not_initialized",
            "details": status_info
        }
    
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving model status"
        )


@router.get(
    "/health/database",
    summary="Database Status",
    description="Check database connection status"
)
async def get_database_status() -> Dict[str, Any]:
    """
    Get database connection status.
    
    Returns:
        Dictionary with database info
    """
    try:
        db = FirebaseClient()
        return {
            "status": "connected" if db._initialized else "disconnected",
            "connection_info": db.get_connection_status()
        }
    
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving database status"
        )


@router.get(
    "/health/config",
    summary="Configuration Status",
    description="Get current configuration"
)
async def get_config_status() -> Dict[str, Any]:
    """
    Get current configuration status.
    
    Returns:
        Dictionary with config information
    """
    try:
        settings = get_settings()
        return {
            "environment": settings.fastapi_env,
            "debug": settings.fastapi_debug,
            "api_prefix": settings.api_prefix,
            "server": f"{settings.host}:{settings.port}",
        }
    
    except Exception as e:
        logger.error(f"Error getting config status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving configuration"
        )


# Helper functions

def check_database_health() -> Dict[str, Any]:
    """Check database health."""
    try:
        db = FirebaseClient()
        return {
            "status": "ok" if db._initialized else "error",
            "message": "Firebase connected" if db._initialized else "Firebase not initialized"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database check failed: {str(e)}"
        }


def check_models_health() -> Dict[str, Any]:
    """Check model health."""
    try:
        status_info = ModelManager.get_status()
        if status_info["initialized"]:
            return {
                "status": "ok",
                "message": "All models loaded",
                "models": {
                    "yolov8": status_info.get("yolov8_info", {}),
                    "facenet": status_info.get("facenet_info", {}),
                }
            }
        else:
            return {
                "status": "warning",
                "message": "Models not yet initialized"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Model check failed: {str(e)}"
        }
