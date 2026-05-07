"""
utils/rate_limiter.py
─────────────────────────────────────────────────────────────────────────────
In-process sliding-window rate limiter with per-role limits.

Limits (requests per 60-second window)
---------------------------------------
  student   : 100 req / min
  teacher   : 500 req / min
  admin     : unlimited  (None)
  anonymous : 20  req / min  (covers public endpoints like /login)

Implementation
--------------
Uses a deque of timestamps per (ip, role) bucket.  On each request:
  1. Remove timestamps older than the window.
  2. If the bucket size >= limit → reject with HTTP 429.
  3. Otherwise append current timestamp and allow.

The bucket key is ``ip:role`` so that a single IP acting as both a
teacher and a student (unlikely, but possible in testing) gets separate
counters.

FastAPI integration
-------------------
Use as a Starlette middleware:

    from utils.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

Or as a FastAPI dependency:

    from utils.rate_limiter import check_rate_limit
    @router.post("/mark")
    async def mark(request: Request, _=Depends(check_rate_limit)):
        ...
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional, Tuple

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.auth_service import UserContext

logger = logging.getLogger(__name__)

# ── Per-role limits (requests per window) ─────────────────────────────────────
RATE_LIMITS: Dict[str, Optional[int]] = {
    "admin":     None,   # unlimited
    "teacher":   500,
    "student":   100,
    "anonymous": 20,     # unauthenticated (public endpoints)
}

WINDOW_SECONDS: int = 60  # sliding window size

# Paths excluded from rate limiting entirely
_EXEMPT_PATHS = frozenset({"/", "/docs", "/redoc", "/openapi.json", "/api/v1/health"})

# ── Sliding window store: key → deque of timestamps ───────────────────────────
# Format: "ip:role" → deque[float]
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting reverse-proxy headers."""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("X-Real-IP", "")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def _check_limit(ip: str, role: str) -> Tuple[bool, int, int]:
    """
    Check if the (ip, role) bucket has capacity.

    Returns
    -------
    (allowed, remaining, retry_after_seconds)
    """
    limit = RATE_LIMITS.get(role)
    if limit is None:
        return True, -1, 0  # unlimited

    key = f"{ip}:{role}"
    now = time.monotonic()
    bucket = _buckets[key]

    # Evict expired timestamps
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()

    current_count = len(bucket)
    remaining = max(0, limit - current_count)

    if current_count >= limit:
        # Time until the oldest request leaves the window
        retry_after = int(WINDOW_SECONDS - (now - bucket[0])) + 1
        return False, 0, retry_after

    bucket.append(now)
    return True, remaining - 1, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter middleware.

    Reads the authenticated user from ``request.state.user`` (set by
    AuthMiddleware) so it can apply role-based limits.  Falls back to
    the "anonymous" bucket for unauthenticated requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if path in _EXEMPT_PATHS or path.endswith("/health"):
            return await call_next(request)

        user: Optional[UserContext] = getattr(request.state, "user", None)
        role = user.role if user else "anonymous"
        ip = _get_client_ip(request)

        allowed, remaining, retry_after = _check_limit(ip, role)

        if not allowed:
            logger.warning(
                "Rate limit exceeded: ip=%s role=%s path=%s retry_after=%ds",
                ip, role, path, retry_after,
            )
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(RATE_LIMITS.get(role, 0)),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                },
                content={
                    "detail": (
                        f"Rate limit exceeded. "
                        f"Maximum {RATE_LIMITS.get(role)} requests per {WINDOW_SECONDS}s "
                        f"for role '{role}'. "
                        f"Retry after {retry_after} seconds."
                    ),
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after_seconds": retry_after,
                },
            )

        response = await call_next(request)

        # Inject rate-limit headers into successful responses
        limit_val = RATE_LIMITS.get(role)
        if limit_val is not None:
            response.headers["X-RateLimit-Limit"] = str(limit_val)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = f"{WINDOW_SECONDS}s"

        return response


# ── FastAPI dependency variant ─────────────────────────────────────────────────

async def check_rate_limit(request: Request) -> None:
    """
    FastAPI dependency for per-endpoint rate limiting.

    Usage::

        @router.post("/expensive-op")
        async def op(request: Request, _=Depends(check_rate_limit)):
            ...
    """
    from fastapi import HTTPException

    user: Optional[UserContext] = getattr(request.state, "user", None)
    role = user.role if user else "anonymous"
    ip = _get_client_ip(request)

    allowed, _, retry_after = _check_limit(ip, role)
    if not allowed:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Rate limit exceeded. Retry after {retry_after}s.",
                "retry_after_seconds": retry_after,
            },
        )