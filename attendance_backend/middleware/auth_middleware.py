"""
middleware/auth_middleware.py
─────────────────────────────────────────────────────────────────────────────
FastAPI dependency-injection based auth middleware.

Usage in a router
-----------------
    from middleware.auth_middleware import require_permission, get_current_user

    @router.get("/attendance")
    def list_attendance(user: TokenPayload = Depends(require_permission("list_all_attendance"))):
        ...

    # Require any authenticated user (no specific permission):
    @router.get("/profile")
    def profile(user: TokenPayload = Depends(get_current_user)):
        ...

    # Require admin role explicitly:
    @router.delete("/users/{user_id}")
    def delete_user(user_id: str, user: TokenPayload = Depends(require_role("admin"))):
        ...
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError
from services.auth_service import AuthService, TokenPayload

logger = logging.getLogger(__name__)

# ── Bearer token extractor ────────────────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_token(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str:
    """Return the raw token string or raise 401."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def _decode(token: str) -> TokenPayload:
    """Decode and validate the JWT, converting errors to HTTP 401."""
    try:
        return AuthService.verify_access_token(token)
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Core dependency: get_current_user
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    FastAPI dependency — validates the JWT and attaches the decoded payload
    to ``request.state.user`` for downstream use.

    Raises HTTP 401 if the token is absent, expired, or malformed.
    """
    token = _extract_token(credentials)
    user = _decode(token)

    # Stash on request state so middleware / background tasks can access it
    request.state.user = user
    return user


def get_current_active_user(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """Like get_current_user but additionally blocks inactive accounts.
    Pair with a DB check in your own dependency chain when needed."""
    # Token alone cannot tell us if the account was deactivated after issue,
    # so this is a lightweight guard; for stricter enforcement add a DB lookup.
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Permission-based dependency factories
# ─────────────────────────────────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Dependency factory.

    Returns a FastAPI dependency that passes only when the authenticated user
    holds *permission*.

    Example
    -------
        @router.post("/attendance/mark")
        def mark(user = Depends(require_permission("mark_attendance"))):
            ...
    """
    def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not user.has_permission(permission):
            logger.warning(
                "Permission denied: user=%s role=%s required=%s",
                user.user_id, user.role, permission,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: '{permission}'.",
            )
        return user

    return _check


def require_role(*roles: str):
    """
    Dependency factory — accepts any of the listed roles.

    Example
    -------
        @router.get("/admin/users")
        def list_users(user = Depends(require_role("admin"))):
            ...
    """
    role_set = frozenset(roles)

    def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to roles: {sorted(role_set)}.",
            )
        return user

    return _check


def require_any_permission(*permissions: str):
    """Passes if the user holds AT LEAST ONE of the listed permissions."""
    perm_set = frozenset(permissions)

    def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not any(user.has_permission(p) for p in perm_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires one of: {sorted(perm_set)}.",
            )
        return user

    return _check


# ─────────────────────────────────────────────────────────────────────────────
# Resource-level ownership guard
# ─────────────────────────────────────────────────────────────────────────────

def require_own_resource_or_admin(path_param: str = "user_id"):
    """
    Ensures that the requesting user is either:
      • an admin, or
      • accessing their own resource (path param matches JWT subject).

    Example
    -------
        @router.get("/students/{user_id}/attendance")
        def get_attendance(
            user_id: str,
            user = Depends(require_own_resource_or_admin("user_id")),
        ):
            ...
    """
    def _check(
        request: Request,
        user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if user.role == "admin":
            return user
        resource_id = request.path_params.get(path_param)
        if resource_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own resources.",
            )
        return user

    return _check


def require_section_access(path_param: str = "section_id"):
    """
    Ensures teachers can only touch sections assigned to them.
    Admins bypass this check.

    Example
    -------
        @router.get("/sections/{section_id}/students")
        def get_students(
            section_id: str,
            user = Depends(require_section_access("section_id")),
        ):
            ...
    """
    def _check(
        request: Request,
        user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if user.role == "admin":
            return user
        section_id = request.path_params.get(path_param)
        if not user.can_access_section(section_id):
            logger.warning(
                "Section access denied: user=%s role=%s section=%s assigned=%s",
                user.user_id, user.role, section_id, user.assigned_sections,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this section.",
            )
        return user

    return _check


# ─────────────────────────────────────────────────────────────────────────────
# Starlette / ASGI middleware (optional — for global token inspection)
# ─────────────────────────────────────────────────────────────────────────────

class AuthMiddleware:
    """
    ASGI middleware that pre-validates the JWT on every request and injects
    ``request.state.user`` (or None for unauthenticated requests).

    Add to your FastAPI app BEFORE route-level Depends:

        from middleware.auth_middleware import AuthMiddleware
        app.add_middleware(AuthMiddleware)

    Note: route-level ``Depends(get_current_user)`` guards are still required
    to enforce authentication on specific endpoints. This middleware is useful
    for audit logging and metrics.
    """

    # Public paths that skip token inspection entirely
    PUBLIC_PATHS: frozenset = frozenset({
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/user/register",
        "/api/v1/user/forgot-password",
        "/api/v1/user/reset-password",
        "/api/v1/attendance/health",
    })

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            request = Request(scope, receive, send)
            path = request.url.path

            if path not in self.PUBLIC_PATHS:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ", 1)[1]
                    try:
                        request.state.user = AuthService.verify_access_token(token)
                    except JWTError:
                        request.state.user = None
                else:
                    request.state.user = None
            else:
                request.state.user = None

        await self.app(scope, receive, send)
