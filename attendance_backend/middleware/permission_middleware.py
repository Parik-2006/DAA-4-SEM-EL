"""
middleware/permission_middleware.py
─────────────────────────────────────────────────────────────────────────────
Route-level permission enforcement middleware.

What it does
------------
1. Matches the incoming request path to a permission rule (role requirement).
2. If the authenticated user does not meet the requirement, returns HTTP 403.
3. Injects a ``QueryFilterContext`` into ``request.state.query_filter``
   containing the section / student ID filters the route handlers must apply
   when querying Firestore.  This keeps authorization logic out of every
   individual handler.

QueryFilterContext
------------------
Attached as ``request.state.query_filter`` — a dataclass available to any
downstream handler or repository:

    ctx = request.state.query_filter
    # ctx.section_ids  → list[str] | None   (None = no filter / admin sees all)
    # ctx.student_id   → str | None         (only for student-scoped routes)
    # ctx.is_admin     → bool
    # ctx.is_teacher   → bool
    # ctx.is_student   → bool

Route permission table
----------------------
Pattern matching is prefix-based, longest prefix wins.

    Pattern                       Required role(s)
    ────────────────────────────  ─────────────────
    /api/v1/admin/*               admin
    /api/v1/teacher/*             teacher | admin
    /api/v1/student/*             student | teacher | admin
    /api/v1/attendance/*          teacher | admin  (write); any (read)
    (everything else)             any authenticated user
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.auth_service import UserContext

logger = logging.getLogger(__name__)

# ── Route permission rules (prefix → required roles) ──────────────────────────
# Ordered by specificity (longer prefixes first)
_ROUTE_RULES: List[Tuple[str, FrozenSet[str]]] = [
    ("/api/v1/auth/",          frozenset()),                              # public
    ("/api/v1/admin/",         frozenset({"admin"})),
    ("/api/v1/teacher/",       frozenset({"teacher", "admin"})),
    ("/api/v1/student/",       frozenset({"student", "teacher", "admin"})),
    # Attendance reads are open to all authenticated users;
    # writes are enforced in the handler via decorators
    ("/api/v1/attendance/health",  frozenset()),                          # public
    ("/api/v1/attendance/window-status", frozenset({"student", "teacher", "admin"})),
    ("/api/v1/attendance/",    frozenset({"student", "teacher", "admin"})),
    ("/api/v1/timetable/",     frozenset({"student", "teacher", "admin"})),
    ("/api/v1/health",         frozenset()),                              # public
]

# Paths that completely bypass this middleware (already public via AuthMiddleware)
_FULLY_PUBLIC: FrozenSet[str] = frozenset({
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/user/register",
    "/api/v1/user/forgot-password",
    "/api/v1/user/reset-password",
    "/user/register",
    "/user/login",
    "/user/forgot-password",
    "/user/reset-password",
    "/api/v1/attendance/health",
    "/api/v1/health",
})


@dataclass
class QueryFilterContext:
    """
    Carries automatic Firestore query-filter parameters derived from the
    authenticated user's role and assignments.

    Handlers simply read these values and apply them to queries — no need
    to duplicate role-checking logic in every endpoint.
    """
    is_admin: bool = False
    is_teacher: bool = False
    is_student: bool = False

    # Sections the user may query (None = unrestricted / admin)
    section_ids: Optional[List[str]] = None

    # For student-role: the authenticated student's own ID
    student_id: Optional[str] = None

    # Raw user context (for ad-hoc checks in handlers)
    user: Optional[UserContext] = None

    def allows_section(self, section_id: str) -> bool:
        if self.is_admin or self.section_ids is None:
            return True
        return section_id in (self.section_ids or [])

    def allows_student(self, student_id: str) -> bool:
        if self.is_admin or self.is_teacher:
            return True
        return student_id == self.student_id

    def to_firestore_section_filter(self) -> Optional[List[str]]:
        """
        Return the list to use in a Firestore ``where('section_id', 'in', ...)``
        clause, or None if no filter should be applied (admin).
        """
        if self.is_admin:
            return None
        return self.section_ids or []

    def to_firestore_student_filter(self) -> Optional[str]:
        """
        Return the student_id to use in ``where('student_id', '==', ...)`` for
        student-scoped queries, or None for no filter.
        """
        if self.is_admin or self.is_teacher:
            return None
        return self.student_id


def _build_filter_context(user: Optional[UserContext]) -> QueryFilterContext:
    """Derive a QueryFilterContext from a UserContext."""
    if user is None:
        return QueryFilterContext()

    ctx = QueryFilterContext(
        is_admin=user.is_admin(),
        is_teacher=user.is_teacher(),
        is_student=user.is_student(),
        user=user,
    )

    if user.is_admin():
        ctx.section_ids = None  # unrestricted
    elif user.is_teacher():
        ctx.section_ids = list(user.assigned_sections)
    else:
        # Student: no section filter needed; use student_id instead
        ctx.section_ids = []
        ctx.student_id = user.user_id

    return ctx


def _required_roles_for_path(path: str) -> Optional[FrozenSet[str]]:
    """
    Return the set of roles allowed for the given path.
    Returns None if the path is fully public (no auth required).
    Returns empty frozenset if authenticated but any role is acceptable.
    """
    if path in _FULLY_PUBLIC or any(path.startswith(p) for p in _FULLY_PUBLIC if p != "/"):
        return None

    # Match longest prefix first (rules are already ordered)
    for prefix, roles in _ROUTE_RULES:
        if path.startswith(prefix):
            return roles

    # Default: any authenticated user
    return frozenset()


class PermissionMiddleware(BaseHTTPMiddleware):
    """
    Route-level permission enforcement and query-filter injection.

    Must run AFTER AuthMiddleware (needs request.state.user).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Always attach a (possibly empty) filter context
        user: Optional[UserContext] = getattr(request.state, "user", None)
        request.state.query_filter = _build_filter_context(user)

        # ── Public paths bypass role check ─────────────────────────────────────
        required_roles = _required_roles_for_path(path)
        if required_roles is None:
            return await call_next(request)

        # ── Must be authenticated ──────────────────────────────────────────────
        if user is None:
            # AuthMiddleware should have blocked this; belt-and-suspenders
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required.", "code": "UNAUTHENTICATED"},
            )

        # ── Role check ─────────────────────────────────────────────────────────
        if required_roles and user.role not in required_roles:
            logger.warning(
                "Permission denied: user=%s role=%s path=%s required=%s",
                user.user_id, user.role, path, required_roles,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        f"You do not have permission to access this resource. "
                        f"Required role(s): {sorted(required_roles)}. "
                        f"Your role: {user.role}."
                    ),
                    "code": "PERMISSION_DENIED",
                    "required_roles": sorted(required_roles),
                    "your_role": user.role,
                },
            )

        return await call_next(request)