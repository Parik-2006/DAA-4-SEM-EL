"""
api/auth.py
─────────────────────────────────────────────────────────────────────────────
Public authentication endpoints:

    POST /api/v1/auth/login       — exchange credentials for JWT pair
    POST /api/v1/auth/refresh     — exchange refresh token for new access token
    POST /api/v1/auth/logout      — client-side invalidation hint
    GET  /api/v1/auth/me          — introspect the current token

All endpoints are intentionally decoupled from the /user router so the
/user/register endpoint remains unchanged for backward compatibility.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field

from database.user_repository import UserRepository
from middleware.auth_middleware import get_current_user
from services.auth_service import AuthService, ROLE_PERMISSIONS, TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_user_repo = UserRepository()
_auth_svc = AuthService()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas (local to this module — lightweight)
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="admin@school.edu")
    password: str = Field(..., min_length=1, example="secret")


class TokenPairResponse(BaseModel):
    success: bool = True
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: "UserSummary"


class UserSummary(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    permissions: List[str]
    assigned_sections: List[str]


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    permissions: List[str]
    assigned_sections: List[str]


TokenPairResponse.model_rebuild()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenPairResponse,
    summary="Exchange credentials for a JWT pair",
    description=(
        "Validates email + password and returns an access token (short-lived) "
        "and a refresh token (long-lived).  Include the access token in the "
        "``Authorization: Bearer <token>`` header on subsequent requests."
    ),
)
def login(body: LoginRequest) -> TokenPairResponse:
    # ── 1. Look up user ───────────────────────────────────────────────────────
    user = _user_repo.get_user_by_email(body.email)

    # Use the same error message for missing user and wrong password
    # to prevent email-enumeration attacks.
    _auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise _auth_error

    # ── 2. Verify password ────────────────────────────────────────────────────
    if not AuthService.verify_password(body.password, user.get("password_hash", "")):
        raise _auth_error

    # ── 3. Check account is active ────────────────────────────────────────────
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact your administrator.",
        )

    # ── 4. Validate role ──────────────────────────────────────────────────────
    role = user.get("role", "student")
    if role not in ROLE_PERMISSIONS:
        logger.error("User %s has unknown role '%s'", user["user_id"], role)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role misconfiguration. Contact support.",
        )

    # ── 5. Issue token pair ───────────────────────────────────────────────────
    tokens = AuthService.generate_token_pair(user)
    permissions = AuthService.get_permissions_for_role(role)

    logger.info(
        "Login successful: user=%s role=%s", user["user_id"], role
    )

    import os
    expire_seconds = int(os.getenv("JWT_EXPIRE_MINUTES", "60")) * 60

    return TokenPairResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=expire_seconds,
        user=UserSummary(
            user_id=user["user_id"],
            name=user.get("name", ""),
            email=user["email"],
            role=role,
            permissions=permissions,
            assigned_sections=user.get("assigned_sections", []),
        ),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Obtain a new access token using a refresh token",
)
def refresh_token(body: RefreshRequest) -> RefreshResponse:
    # Decode the refresh token to extract user_id
    try:
        from jose import jwt as _jwt
        import os
        raw = _jwt.decode(
            body.refresh_token,
            os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"),
            algorithms=["HS256"],
        )
        user_id = raw.get("sub")
        token_type = raw.get("token_type")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc

    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided token is not a refresh token.",
        )

    # Fetch fresh user data so the new access token reflects current roles/sections
    user = _user_repo.get_user(user_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    try:
        new_access = AuthService.refresh_access_token(body.refresh_token, user)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed.",
        ) from exc

    logger.info("Token refreshed for user=%s", user_id)
    return RefreshResponse(access_token=new_access)


@router.post(
    "/logout",
    summary="Logout (client-side token invalidation hint)",
    description=(
        "Stateless JWT architecture means the token remains valid until "
        "expiry. Clients MUST discard both tokens on logout. "
        "For hard invalidation, implement a token-blocklist (Redis) and "
        "wire it into AuthService.verify_access_token."
    ),
)
def logout(user: TokenPayload = Depends(get_current_user)) -> dict:
    logger.info("Logout for user=%s", user.user_id)
    return {
        "success": True,
        "message": "Logged out. Please discard your tokens.",
    }


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Introspect the current access token",
)
def me(user: TokenPayload = Depends(get_current_user)) -> MeResponse:
    """Returns the decoded claims from the caller's access token."""
    return MeResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        role=user.role,
        permissions=user.permissions,
        assigned_sections=user.assigned_sections,
    )
