"""
decorators/auth_decorators.py
─────────────────────────────────────────────────────────────────────────────
FastAPI dependency factories for role-based and resource-level authorization.

Usage in endpoints
------------------

    from decorators.auth_decorators import (
        get_current_user,
        require_role,
        require_admin,
        require_teacher,
        require_student,
        require_section_access,
        require_own_student_data,
    )

    # Any authenticated user
    @router.get("/me")
    async def profile(user: UserContext = Depends(get_current_user)):
        return {"user_id": user.user_id}

    # Admin only
    @router.get("/admin/users")
    async def list_users(user: UserContext = Depends(require_admin)):
        ...

    # Teacher or admin
    @router.post("/attendance/mark")
    async def mark(
        section_id: str,
        user: UserContext = Depends(require_teacher),
        _: None = Depends(require_section_access("section_id")),
    ):
        ...

    # Student reading own data
    @router.get("/student/attendance")
    async def my_attendance(
        student_id: str = Query(...),
        user: UserContext = Depends(require_student),
        _: None = Depends(require_own_student_data("student_id")),
    ):
        ...
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, Optional, Sequence, Tuple

from fastapi import Depends, HTTPException, Query, Request

from services.auth_service import UserContext

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Base dependency: extract user from request.state
# ══════════════════════════════════════════════════════════════════════════════

async def get_current_user(request: Request) -> UserContext:
    """
    FastAPI dependency that returns the ``UserContext`` set by ``AuthMiddleware``.

    Raises HTTP 401 if no authenticated user is present on the request.
    """
    user: Optional[UserContext] = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )
    return user


async def get_optional_user(request: Request) -> Optional[UserContext]:
    """Like get_current_user but returns None instead of raising for public endpoints."""
    return getattr(request.state, "user", None)


# ══════════════════════════════════════════════════════════════════════════════
# Role dependencies
# ══════════════════════════════════════════════════════════════════════════════

def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory: ensures the authenticated user has one of the given roles.

        user = Depends(require_role("admin", "teacher"))
    """
    async def _dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed_roles:
            logger.warning(
                "Role check failed: user=%s role=%s required=%s",
                user.user_id, user.role, allowed_roles,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient permissions. "
                    f"Required role: {' or '.join(allowed_roles)}. "
                    f"Your role: {user.role}."
                ),
            )
        return user

    return Depends(_dependency)


# Convenience shortcuts
require_admin = require_role("admin")
require_teacher = require_role("teacher", "admin")   # admin can do teacher things
require_student = require_role("student")
require_teacher_only = require_role("teacher")       # excludes admin


def require_permission(permission: str) -> Callable:
    """
    Dependency factory: ensures the user has a specific permission string.

        _ = Depends(require_permission("mark_attendance"))
    """
    async def _dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Missing required permission: '{permission}'.",
            )
        return user

    return Depends(_dependency)


# ══════════════════════════════════════════════════════════════════════════════
# Resource-level authorization dependencies
# ══════════════════════════════════════════════════════════════════════════════

def require_section_access(section_id_param: str = "section_id") -> Callable:
    """
    Dependency factory: validates that the requesting teacher is assigned to
    the section specified by the query/path parameter named ``section_id_param``.

    Admins bypass this check (they have global access).

    Usage
    -----
        @router.post("/attendance/mark")
        async def mark(
            section_id: str = Query(...),
            user: UserContext = Depends(require_teacher),
            _: None = Depends(require_section_access("section_id")),
        ): ...
    """
    async def _dependency(
        request: Request,
        user: UserContext = Depends(get_current_user),
    ) -> None:
        if user.is_admin():
            return  # Admins have unrestricted access

        # Pull section_id from query params, path params, or request body cache
        section_id = (
            request.query_params.get(section_id_param)
            or request.path_params.get(section_id_param)
        )
        if section_id is None:
            # If not found in params, skip (body-based validation happens in handler)
            return

        if not user.can_access_section(section_id):
            logger.warning(
                "Section access denied: user=%s sections=%s requested=%s",
                user.user_id, user.assigned_sections, section_id,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"You are not authorized to access section '{section_id}'. "
                    f"Your assigned sections: {user.assigned_sections}."
                ),
            )

    return Depends(_dependency)


def require_own_student_data(student_id_param: str = "student_id") -> Callable:
    """
    Dependency factory: ensures a student can only access their own data.

    Admins and teachers bypass this check (they have broader access within
    their scope, enforced by ``require_section_access``).

    Usage
    -----
        @router.get("/student/attendance")
        async def my_attendance(
            student_id: str = Query(...),
            user: UserContext = Depends(require_student),
            _: None = Depends(require_own_student_data("student_id")),
        ): ...
    """
    async def _dependency(
        request: Request,
        user: UserContext = Depends(get_current_user),
    ) -> None:
        # Admins/teachers can see any student data
        if user.role in ("admin", "teacher"):
            return

        # Students may only see their own record
        student_id = (
            request.query_params.get(student_id_param)
            or request.path_params.get(student_id_param)
        )
        if student_id is None:
            return

        if student_id != user.user_id:
            logger.warning(
                "Cross-student access denied: authenticated=%s requested=%s",
                user.user_id, student_id,
            )
            raise HTTPException(
                status_code=403,
                detail="You may only access your own attendance data.",
            )

    return Depends(_dependency)


def require_faculty_access(faculty_id_param: str = "faculty_id") -> Callable:
    """
    Dependency: a teacher can only act as themselves; admin can act as any faculty.
    """
    async def _dependency(
        request: Request,
        user: UserContext = Depends(get_current_user),
    ) -> None:
        if user.is_admin():
            return

        faculty_id = (
            request.query_params.get(faculty_id_param)
            or request.path_params.get(faculty_id_param)
        )
        if faculty_id is None:
            return

        if faculty_id != user.user_id:
            raise HTTPException(
                status_code=403,
                detail="You may only perform actions as yourself.",
            )

    return Depends(_dependency)


# ══════════════════════════════════════════════════════════════════════════════
# Section filtering helper (for query-time injection)
# ══════════════════════════════════════════════════════════════════════════════

def get_section_filter(user: UserContext) -> Optional[list]:
    """
    Return the list of section IDs the user is allowed to see, or None for
    unrestricted access (admin).

    Used inside repository / service calls to automatically scope queries.

        allowed = get_section_filter(user)
        if allowed is not None:
            query = query.where("section_id", "in", allowed)
    """
    if user.is_admin():
        return None  # No filter → see everything
    if user.is_teacher():
        return user.assigned_sections or []
    # Students get section access through their own student_id filter
    return []