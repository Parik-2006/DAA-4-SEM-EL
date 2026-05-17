"""
api/auth.py
─────────────────────────────────────────────────────────────────────────────
Authentication endpoints.

POST /api/v1/auth/login
    Accepts email + password, returns a signed JWT.

POST /api/v1/auth/refresh
    Accepts a valid (non-expired) token and returns a new one with
    a refreshed expiry.  The old token is not blacklisted (stateless
    design — use short expiry + refresh in production).

GET  /api/v1/auth/me
    Returns the authenticated user's profile from the JWT claims.
    Does NOT hit the database — purely derived from the token.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from decorators.auth_decorators import get_current_user
from services.audit_services import get_audit_service
from services.auth_service import ROLE_PERMISSIONS, UserContext, get_auth_service
from services.session_anchor_service import get_anchor_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Request / response schemas ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    email: str
    role: str
    permissions: List[str]
    assigned_sections: List[str]


class MeResponse(BaseModel):
    user_id: str
    email: str
    role: str
    permissions: List[str]
    assigned_sections: List[str]
    issued_at: int
    expires_at: int


class LogoutResponse(BaseModel):
    success: bool
    user_id: str
    released_anchors: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_firestore():
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        if fb is None:
            return None
        return (
            getattr(fb, "firestore_db", None)
            or getattr(fb, "_firestore", None)
        )
    except Exception as exc:
        logger.error("Could not obtain Firestore client: %s", exc)
        return None


def _normalize_assigned_sections(value: Any) -> List[str]:
    """Coerce malformed stored assigned_sections values into a list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/auth/login
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email + password and receive a JWT",
)
async def login(body: LoginRequest, request: Request):
    """
    Authenticates a user against the Firestore ``users`` collection and
    returns a signed JWT containing the user's role and permissions.

    **Roles**: ``admin`` | ``teacher`` | ``student``

    The returned ``access_token`` should be sent in the ``Authorization``
    header of subsequent requests:
    ```
    Authorization: Bearer <access_token>
    ```
    """
    auth_svc = get_auth_service()
    audit_svc = get_audit_service()

    db = _get_firestore()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable.",
        )

    user_doc = auth_svc.authenticate(body.email, body.password, db)

    if user_doc is None:
        # Log failed attempt
        audit_svc.log(
            action="LOGIN_FAILED",
            resource="auth",
            user=None,
            request=request,
            details={"email": body.email},
            success=False,
            error="Invalid credentials",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    user_id: str = user_doc.get("id") or user_doc.get("doc_id", "")
    role: str = user_doc.get("role", "student")
    assigned_sections: List[str] = _normalize_assigned_sections(
        user_doc.get("assigned_sections", [])
    )
    email: str = user_doc.get("email", body.email)

    try:
        token = auth_svc.create_token(
            user_id=user_id,
            email=email,
            role=role,
            assigned_sections=assigned_sections,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Decode to get expiry info
    ctx = auth_svc.decode_token(token)
    expires_in = ctx.expires_at - ctx.issued_at

    # Audit successful login
    audit_svc.log(
        action="LOGIN",
        resource="auth",
        resource_id=user_id,
        request=request,
        details={"email": email, "role": role},
        success=True,
    )

    logger.info("Login: user=%s role=%s", user_id, role)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user_id=user_id,
        email=email,
        role=role,
        permissions=ROLE_PERMISSIONS.get(role, []),
        assigned_sections=assigned_sections,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/auth/refresh
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh a valid JWT (extend expiry)",
)
async def refresh_token(
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Issue a new token with a refreshed expiry for an already-authenticated user.

    The caller must provide their current (valid, not-expired) token in the
    ``Authorization`` header.  A completely new token is returned.
    """
    auth_svc = get_auth_service()

    token = auth_svc.create_token(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        assigned_sections=_normalize_assigned_sections(user.assigned_sections),
    )
    ctx = auth_svc.decode_token(token)
    expires_in = ctx.expires_at - ctx.issued_at

    logger.info("Token refreshed: user=%s", user.user_id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        permissions=user.permissions,
        assigned_sections=_normalize_assigned_sections(user.assigned_sections),
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/auth/me
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/me",
    response_model=MeResponse,
    summary="Return the current user's profile from their JWT",
)
async def get_me(user: UserContext = Depends(get_current_user)):
    """
    Returns the authenticated user's decoded claims.

    No database call — information is derived entirely from the JWT.
    Useful for the frontend to bootstrap the UI after login.
    """
    return MeResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        permissions=user.permissions,
        assigned_sections=user.assigned_sections,
        issued_at=user.issued_at,
        expires_at=user.expires_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/auth/logout
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout current user and release any anchored sessions",
)
async def logout_user(user: UserContext = Depends(get_current_user)):
    """
    Stateless logout.

    The JWT itself is not blacklisted here, but any session anchors created for
    the user are released immediately so the next camera session starts clean.
    """
    anchor_service = get_anchor_service()
    released = anchor_service.release_all_for_user(user.user_id)

    logger.info("Logout: user=%s released_anchors=%d", user.user_id, released)

    return LogoutResponse(
        success=True,
        user_id=user.user_id,
        released_anchors=released,
    )