"""
middleware/audit_middleware.py
─────────────────────────────────────────────────────────────────────────────
Starlette middleware that automatically logs every state-changing API call
(POST, PUT, PATCH, DELETE) to the AuditService.

What gets logged
----------------
• user_id / role (from request.state.user set by AuthMiddleware)
• HTTP method + path
• Response status code
• Client IP + User-Agent
• Request body (sanitised — password fields redacted)
• Timestamp

Read-only requests (GET, HEAD, OPTIONS) are NOT logged here; the AuditService
can still be called explicitly from handlers for sensitive reads (e.g. audit
log access itself).

Order in middleware stack
-------------------------
AuthMiddleware must run BEFORE AuditMiddleware so that request.state.user
is already populated when we reach this layer.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional, Set

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.audit_services import get_audit_service
from services.auth_service import UserContext

logger = logging.getLogger(__name__)

# Methods that mutate state and should always be audited
_AUDITED_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}

# Fields to redact from the logged request body (case-insensitive keys)
_REDACTED_FIELDS: Set[str] = {
    "password", "password_hash", "new_password", "confirm_password",
    "secret", "token", "access_token", "refresh_token",
    "face_image_base64", "image_base64", "embeddings",
}

# Paths whose bodies should be entirely suppressed (too large / sensitive)
_SUPPRESS_BODY_PATHS: Set[str] = {
    "/api/v1/attendance/detect-face",
    "/api/v1/attendance/detect-face-only",
    "/api/v1/attendance/mark-mobile",
    "/api/v1/admin/register-student-face",
    "/api/v1/admin/students/bulk-import",
    "/api/v1/admin/timetable/bulk-import",
}

# Max body size to attempt to read and log (bytes)
_MAX_BODY_LOG_BYTES: int = 8 * 1024  # 8 KB


def _sanitise_body(raw: bytes, path: str) -> Optional[dict]:
    """
    Parse JSON body and redact sensitive fields.
    Returns None if body is empty, too large, or not JSON.
    """
    if path in _SUPPRESS_BODY_PATHS:
        return {"_suppressed": "body suppressed for this endpoint"}

    if not raw or len(raw) > _MAX_BODY_LOG_BYTES:
        size_kb = len(raw) / 1024 if raw else 0
        return {"_suppressed": f"body too large ({size_kb:.1f} KB)"}

    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"_suppressed": "non-JSON body"}

    if not isinstance(body, dict):
        return {"_type": type(body).__name__, "_suppressed": "non-object JSON"}

    def _redact(obj: dict) -> dict:
        result = {}
        for k, v in obj.items():
            if k.lower() in _REDACTED_FIELDS:
                result[k] = "***REDACTED***"
            elif isinstance(v, dict):
                result[k] = _redact(v)
            elif isinstance(v, list) and k.lower() in {"embeddings", "face_data"}:
                result[k] = f"[{len(v)} items — suppressed]"
            else:
                result[k] = v
        return result

    return _redact(body)


def _action_from_request(method: str, path: str) -> str:
    """Derive a human-readable action label from method + path."""
    method = method.upper()
    segments = [s for s in path.split("/") if s and not s.startswith("{")]

    # Common action labels
    action_map = {
        ("POST", "login"):            "LOGIN",
        ("POST", "mark-attendance"):  "MARK_ATTENDANCE",
        ("POST", "mark-bulk"):        "BULK_MARK_ATTENDANCE",
        ("POST", "confirm-attendance"): "CONFIRM_ATTENDANCE",
        ("POST", "detect-face"):      "DETECT_FACE_MARK",
        ("PATCH", "attendance"):      "EDIT_ATTENDANCE",
        ("DELETE", "attendance"):     "DELETE_ATTENDANCE",
        ("POST", "lock"):             "LOCK_PERIOD",
        ("POST", "unlock"):           "UNLOCK_PERIOD",
        ("POST", "register-student"): "REGISTER_STUDENT",
        ("POST", "register-student-face"): "REGISTER_FACE",
        ("POST", "bulk-import"):      "BULK_IMPORT",
        ("POST", "cie"):              "CREATE_CIE",
        ("PUT", "cie"):               "UPDATE_CIE",
        ("DELETE", "cie"):            "DELETE_CIE",
        ("POST", "class"):            "CREATE_CLASS",
        ("PUT", "class"):             "UPDATE_CLASS",
        ("POST", "config"):           "CONFIG_CHANGE",
    }

    for (m, keyword), label in action_map.items():
        if m == method and any(keyword in seg for seg in segments):
            return label

    # Generic fallback
    resource = segments[-1] if segments else "unknown"
    return f"{method}_{resource.upper()}"


def _resource_from_path(path: str) -> str:
    """Best-effort extraction of the resource type from the URL path."""
    segments = [s for s in path.split("/") if s and not s.startswith("{")]
    # e.g. /api/v1/teacher/mark-bulk → "teacher"
    #      /api/v1/admin/cie/abc123  → "cie"
    api_idx = next((i for i, s in enumerate(segments) if s.startswith("v")), -1)
    if api_idx >= 0 and api_idx + 1 < len(segments):
        return segments[api_idx + 1]
    return segments[-1] if segments else "unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Automatically logs all mutating HTTP requests to the AuditService.

    Must be added AFTER AuthMiddleware in the middleware stack so that
    ``request.state.user`` is already populated.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method.upper()

        # Only audit mutating requests
        if method not in _AUDITED_METHODS:
            return await call_next(request)

        path = request.url.path
        start_ts = time.monotonic()

        # ── Read and buffer the request body ──────────────────────────────────
        # Starlette bodies are streams; we must read once and re-inject.
        try:
            raw_body: bytes = await request.body()
        except Exception:
            raw_body = b""

        # Re-inject so the actual handler can still read it
        async def _receive():
            return {"type": "http.request", "body": raw_body, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]

        # ── Execute handler ────────────────────────────────────────────────────
        response: Response = await call_next(request)

        elapsed_ms = int((time.monotonic() - start_ts) * 1000)

        # ── Build audit entry ──────────────────────────────────────────────────
        user: Optional[UserContext] = getattr(request.state, "user", None)
        action = _action_from_request(method, path)
        resource = _resource_from_path(path)

        # Attempt to extract resource_id from path
        path_parts = [s for s in path.split("/") if s]
        resource_id: Optional[str] = None
        for i, part in enumerate(path_parts):
            # UUIDs or IDs that follow known resource keywords
            if part in {"cie", "class", "attendance", "period", "record", "student"} and i + 1 < len(path_parts):
                candidate = path_parts[i + 1]
                # Exclude sub-resources like "lock", "audit", "summary"
                if not candidate.isalpha() or len(candidate) > 20:
                    resource_id = candidate
                break

        success = response.status_code < 400
        error_msg: Optional[str] = None
        if not success:
            try:
                # Try to extract error detail from response body
                body_bytes = b""
                async for chunk in response.body_iterator:  # type: ignore
                    body_bytes += chunk
                error_data = json.loads(body_bytes)
                error_msg = str(error_data.get("detail", response.status_code))

                # Re-inject response body so client still receives it
                async def _iter():
                    yield body_bytes

                response.body_iterator = _iter()  # type: ignore
            except Exception:
                error_msg = f"HTTP {response.status_code}"

        try:
            audit_svc = get_audit_service()
            audit_svc.log(
                action=action,
                resource=resource,
                user=user,
                resource_id=resource_id,
                after=_sanitise_body(raw_body, path),
                request=request,
                details={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "query_params": dict(request.query_params),
                },
                success=success,
                error=error_msg,
            )
        except Exception as exc:
            # Audit must NEVER crash the application
            logger.error("AuditMiddleware write failed: %s", exc)

        return response