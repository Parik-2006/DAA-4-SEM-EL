"""
Configuration package for the attendance system.

Provides centralized access to application settings, constants, and logging.
"""

from config.settings import Settings, get_settings
from config.logging_config import LoggerConfig, setup_logging, logger
from config.constants import (
    HTTPStatus,
    AttendanceStatus,
    ERROR_MESSAGES,
    SUCCESS_MESSAGES,
    FACEBOOK_COLLECTIONS,
    API_PREFIX,
)

__all__ = [
    # Settings
    "Settings",
    "get_settings",
    
    # Logging
    "LoggerConfig",
    "setup_logging",
    "logger",
    
    # Constants - Enums
    "HTTPStatus",
    "AttendanceStatus",
    
    # Constants - Messages
    "ERROR_MESSAGES",
    "SUCCESS_MESSAGES",
    
    # Constants - Database
    "FACEBOOK_COLLECTIONS",
    
    # Constants - API
    "API_PREFIX",
]
