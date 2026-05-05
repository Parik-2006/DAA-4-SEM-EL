"""
Middleware package for the attendance system.

Provides FastAPI middleware components for authentication, logging, and request handling.
"""

from middleware.auth_middleware import (
    AuthMiddleware,
    get_current_user,
    get_current_active_user,
    require_permission,
    require_role,
    require_any_permission,
    require_own_resource_or_admin,
    require_section_access,
)

__all__ = [
    "AuthMiddleware",
    "get_current_user",
    "get_current_active_user",
    "require_permission",
    "require_role",
    "require_any_permission",
    "require_own_resource_or_admin",
    "require_section_access",
]
