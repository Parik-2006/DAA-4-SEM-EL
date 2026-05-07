"""
middleware/auth_middleware.py
─────────────────────────────────────────────────────────────────────────────
Two-layer authentication and authorisation system:

Layer 1 — AuthMiddleware (Starlette BaseHTTPMiddleware)
    Runs on EVERY request before any route handler.
    • Extracts the Bearer token (header or _token query-param for dev).
    • Decodes + validates via AuthService.
    • Attaches TokenPayload to request.state.user.
    • Returns HTTP 401 immediately for protected paths with missing/bad tokens.
    • Public paths are explicitly allowed through without a token.

Layer 2 — FastAPI Depends guards (route-level)
    Imported by individual routers to enforce fine-grained access control.
    • get_current_user          — any valid JWT
    • get_current_active_user   — valid JWT (active-account hint)
    • require_role("admin")     — role whitelist
    • require_permission("x")   — single permission check
    • require_any_permission()  — OR across permissions
    • require_own_resource_or_admin() — ownership guard
    • require_section_access()  — teacher section isolation

Usage
-----
    # main.py — register the middleware
    app.add_middleware(AuthMiddleware)

    # router — use Depends guards
    from middleware.auth_middleware import require_permission, require_role

    @router.post("/attendance/mark")
    def mark(user = Depends(require_permission("mark_attendance"))):
        ...

    @router.get("/admin/users")
    def list_users(user = Depends(require_role("admin"))):
        ...

Public paths (no token required)
---------------------------------
    GET/POST  /api/v1/auth/login
    POST      /api/v1/auth/refresh
    POST      /api/v1/user/register
    POST      /api/v1/user/forgot-password
    POST      /api/v1/user/reset-password
    GET       /api/v1/attendance/health
    GET       /api/v1/health
    GET       /  /docs  /redoc  /openapi.json  /docs/*  /openapi*
"""

from __future__ import annotations

import logging
from typing import Callable, FrozenSet, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.auth_service import AuthService, TokenPayload

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public path configuration
# ─────────────────────────────────────────────────────────────────────────────

_PUBLIC_PATHS: FrozenSet[str] = frozenset({
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Auth (token issuance — obviously pre-auth)
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    # User self-service (registration / password reset)
    "/api/v1/user/register",
    "/api/v1/user/forgot-password",
    "/api/v1/user/reset-password",
    # Legacy login compat on /user router
    "/user/register",
    "/user/login",
    "/user/forgot-password",
    "/user/reset-password",
    # Health checks
    "/api/v1/attendance/health",
    "/api/v1/health",
})

# Paths are public if they START WITH one of these prefixes
_PUBLIC_PREFIXES: tuple = ("/docs/", "/openapi")


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    return any(path.startswith(pfx) for pfx in _PUBLIC_PREFIXES)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1 — Starlette BaseHTTPMiddleware  (global, blocking)
# ─────────────────────────────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Global JWT middleware.

    • Sets request.state.user = TokenPayload on success.
    • Sets request.state.user = None on public paths.
    • Returns 401 JSON for protected paths with a missing or invalid token.

    Using BaseHTTPMiddleware (not raw ASGI __call__) so that FastAPI's
    exception handlers and background tasks still fire correctly.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.user = None
        path = request.url.path

        # ── Public paths pass straight through ────────────────────────────────
        if _is_public(path):
            return await call_next(request)

        # ── Extract Bearer token ──────────────────────────────────────────────
        token: Optional[str] = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        # Dev/testing fallback: ?_token=<jwt>  (never enable in production)
        if not token:
            token = request.query_params.get("_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Authentication required. "
                        "Provide a Bearer token in the Authorization header."
                    ),
                    "code": "MISSING_TOKEN",
                },
            )

        # ── Decode + validate ─────────────────────────────────────────────────
        try:
            payload = AuthService.verify_access_token(token)
            request.state.user = payload
            logger.debug(
                "Authenticated: user=%s role=%s → %s",
                payload.user_id, payload.role, path,
            )
        except ValueError as exc:
            logger.warning("JWT validation failed for %s: %s", path, exc)
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid or expired token. Please log in again.",
                    "code": "INVALID_TOKEN",
                },
            )
        except Exception as exc:
            logger.error("Unexpected auth error on %s: %s", path, exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error."},
            )

        return await call_next(request)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 — FastAPI Depends guards  (route-level, fine-grained)
# ─────────────────────────────────────────────────────────────────────────────

# Bearer scheme — auto_error=False so we can return a custom 401 message
_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    """Return the raw token string or raise HTTP 401."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def _decode(token: str) -> TokenPayload:
    """Decode and validate the JWT, mapping ValueError → HTTP 401."""
    try:
        return AuthService.verify_access_token(token)
    except ValueError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Core identity dependency ──────────────────────────────────────────────────

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    FastAPI dependency — requires a valid JWT access token.

    Attaches the decoded payload to request.state.user so downstream
    code (services, audit logging) can access it without re-parsing.

    Raises HTTP 401 if the token is absent, expired, or malformed.
    """
    # AuthMiddleware may have already decoded the token; reuse if available.
    if getattr(request.state, "user", None) is not None:
        return request.state.user

    token = _extract_token(credentials)
    user = _decode(token)
    request.state.user = user
    return user


def get_current_active_user(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """
    Like get_current_user but signals intent to check account-active status.

    The token itself does not carry an is_active flag (it cannot reflect
    post-issuance deactivation). For hard enforcement, add a DB lookup in
    your own dependency chain and call this as its dependency.
    """
    return user


# ── Role guard ────────────────────────────────────────────────────────────────

def require_role(*roles: str):
    """
    Dependency factory — passes if the JWT role is in *roles*.

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


# ── Permission guards ─────────────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Dependency factory — passes only when the user holds *permission*.

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


def require_any_permission(*permissions: str):
    """
    Dependency factory — passes if the user holds AT LEAST ONE permission.

        @router.get("/reports")
        def reports(user = Depends(require_any_permission("view_analytics", "list_all_attendance"))):
            ...
    """
    perm_set = frozenset(permissions)

    def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not any(user.has_permission(p) for p in perm_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires one of: {sorted(perm_set)}.",
            )
        return user

    return _check


# ── Resource ownership guard ──────────────────────────────────────────────────

def require_own_resource_or_admin(path_param: str = "user_id"):
    """
    Passes if the caller is admin OR if the path param matches their user_id.

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


# ── Section isolation guard ───────────────────────────────────────────────────

def require_section_access(path_param: str = "section_id"):
    """
    Passes if the caller is admin OR if the section is in their assigned_sections.

    Used to enforce teacher section isolation at the route level — a teacher
    can never read or write data for a section not in their JWT claims.

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