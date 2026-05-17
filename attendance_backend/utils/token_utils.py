"""
utils/token_utils.py
─────────────────────────────────────────────────────────────────────────────
JWT token creation and validation utilities for development and testing.

This module provides helper functions for token generation with proper
exception handling and logging.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TokenGenerationError(Exception):
    """Raised when token generation fails."""
    pass


class TokenValidationError(Exception):
    """Raised when token validation fails."""
    pass


def create_admin_token(
    user_id: str = "admin1",
    email: str = "admin@local",
    assigned_sections: Optional[List[str]] = None
) -> str:
    """
    Create a JWT token for an admin user.
    
    Parameters
    ----------
    user_id : str
        The user ID (default: "admin1")
    email : str
        The user email (default: "admin@local")
    assigned_sections : list[str], optional
        Sections assigned to the admin (default: empty list)
    
    Returns
    -------
    str
        The JWT token
    
    Raises
    ------
    TokenGenerationError
        If token generation fails
    """
    try:
        from services.auth_service import AuthService
        
        service = AuthService()
        token = service.create_token(
            user_id=user_id,
            email=email,
            role="admin",
            assigned_sections=assigned_sections or []
        )
        logger.debug("Generated admin token for user=%s", user_id)
        return token
    except ValueError as exc:
        logger.error("Invalid parameters for admin token: %s", exc)
        raise TokenGenerationError(f"Failed to generate admin token: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error generating admin token: %s", exc, exc_info=True)
        raise TokenGenerationError(f"Token generation failed: {exc}") from exc


def create_teacher_token(
    user_id: str = "teacher1",
    email: str = "teacher@test.local",
    assigned_sections: Optional[List[str]] = None
) -> str:
    """
    Create a JWT token for a teacher user.
    
    Parameters
    ----------
    user_id : str
        The teacher ID (default: "teacher1")
    email : str
        The teacher email (default: "teacher@test.local")
    assigned_sections : list[str], optional
        Sections assigned to the teacher (default: ["TEST_SECTION"])
    
    Returns
    -------
    str
        The JWT token
    
    Raises
    ------
    TokenGenerationError
        If token generation fails
    """
    try:
        from services.auth_service import AuthService
        
        if assigned_sections is None:
            assigned_sections = ["TEST_SECTION"]
        
        service = AuthService()
        token = service.create_token(
            user_id=user_id,
            email=email,
            role="teacher",
            assigned_sections=assigned_sections
        )
        logger.debug("Generated teacher token for user=%s", user_id)
        return token
    except ValueError as exc:
        logger.error("Invalid parameters for teacher token: %s", exc)
        raise TokenGenerationError(f"Failed to generate teacher token: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error generating teacher token: %s", exc, exc_info=True)
        raise TokenGenerationError(f"Token generation failed: {exc}") from exc


def create_student_token(
    user_id: str = "student_001",
    email: str = "student@test.local"
) -> str:
    """
    Create a JWT token for a student user.
    
    Parameters
    ----------
    user_id : str
        The student ID (default: "student_001")
    email : str
        The student email (default: "student@test.local")
    
    Returns
    -------
    str
        The JWT token
    
    Raises
    ------
    TokenGenerationError
        If token generation fails
    """
    try:
        from services.auth_service import AuthService
        
        service = AuthService()
        token = service.create_token(
            user_id=user_id,
            email=email,
            role="student",
            assigned_sections=[]
        )
        logger.debug("Generated student token for user=%s", user_id)
        return token
    except ValueError as exc:
        logger.error("Invalid parameters for student token: %s", exc)
        raise TokenGenerationError(f"Failed to generate student token: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error generating student token: %s", exc, exc_info=True)
        raise TokenGenerationError(f"Token generation failed: {exc}") from exc


def validate_token(token: str) -> dict:
    """
    Validate and decode a JWT token.
    
    Parameters
    ----------
    token : str
        The JWT token to validate
    
    Returns
    -------
    dict
        The decoded token claims
    
    Raises
    ------
    TokenValidationError
        If token validation fails
    """
    try:
        from services.auth_service import AuthService
        
        service = AuthService()
        user_context = service.decode_token(token)
        
        claims = {
            "user_id": user_context.user_id,
            "email": user_context.email,
            "role": user_context.role,
            "assigned_sections": user_context.assigned_sections,
            "permissions": user_context.permissions,
        }
        logger.debug("Token validated for user=%s", user_context.user_id)
        return claims
    except ValueError as exc:
        logger.warning("Token validation failed: %s", exc)
        raise TokenValidationError(f"Invalid token: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error validating token: %s", exc, exc_info=True)
        raise TokenValidationError(f"Token validation failed: {exc}") from exc
