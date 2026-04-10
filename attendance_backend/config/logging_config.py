"""
Logging configuration for the attendance system.

This module provides structured logging setup with file and console handlers,
ensuring consistent logging across the entire application.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from config.constants import LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVELS, LOGS_DIR


class LoggerConfig:
    """
    Manages logging configuration for the entire application.
    
    Provides methods to configure both console and file logging with appropriate
    formatters, handlers, and log levels based on environment settings.
    """
    
    _logger: Optional[logging.Logger] = None
    _configured: bool = False
    
    @classmethod
    def configure_logging(cls) -> logging.Logger:
        """
        Configure and return the root logger.
        
        Sets up both console and file handlers with appropriate formatters.
        Should be called once at application startup.
        
        Returns:
            logging.Logger: Configured root logger instance
        """
        if cls._configured:
            return cls._logger
        
        settings = get_settings()
        
        # Create logs directory if it doesn't exist
        log_dir = Path(LOGS_DIR)
        log_dir.mkdir(exist_ok=True, parents=True)
        
        # Get root logger
        logger = logging.getLogger()
        logger.setLevel(LOG_LEVELS.get(settings.log_level, logging.INFO))
        
        # Create formatters
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        
        # Remove existing handlers to prevent duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVELS.get(settings.log_level, logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler (rotating logs to prevent disk space issues)
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                filename=settings.log_file,
                maxBytes=10_485_760,  # 10 MB
                backupCount=5,  # Keep 5 backup files
                encoding='utf-8'
            )
            file_handler.setLevel(LOG_LEVELS.get(settings.log_level, logging.INFO))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            logger.warning(f"Failed to configure file handler: {e}")
        
        # Error File Handler (separate file for errors)
        try:
            error_handler = logging.handlers.RotatingFileHandler(
                filename=log_dir / "errors.log",
                maxBytes=10_485_760,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)
        except (IOError, OSError) as e:
            logger.warning(f"Failed to configure error handler: {e}")
        
        cls._logger = logger
        cls._configured = True
        
        logger.info(f"Logging configured. Level: {settings.log_level}, File: {settings.log_file}")
        return logger
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger with the specified name.
        
        Args:
            name: Name for the logger (typically __name__)
        
        Returns:
            logging.Logger: Logger instance for the specified name
        """
        if not cls._configured:
            cls.configure_logging()
        return logging.getLogger(name)


def setup_logging() -> None:
    """
    Initialize logging at application startup.
    
    This should be called once during FastAPI app initialization.
    """
    LoggerConfig.configure_logging()


# Create module-level logger
logger = LoggerConfig.get_logger(__name__)
