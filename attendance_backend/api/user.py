"""
api/user.py
─────────────────────────────────────────────────────────────────────────────
User registration and profile endpoints.

Changes from original (backward-compatible)
-------------------------------------------
• POST /user/register   — now persists ``assigned_sections`` and validates
                          role against VALID_ROLES.
• POST /user/login      — now returns a JWT access+refresh token pair.
                          The ``token`` field carries the access token so
                          existing clients that only read ``token`` keep working.
• GET  /user/profile/{user_id}   — now includes permissions and sections.
• GET  /user/users/by-role/{role} — unchanged.
• POST /user/forgot-password     — unchanged.
• POST /user/reset-password      — unchanged.
• NEW  PATCH /user/profile/{user_id}  — self-service profile update (name).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from database.user_repository import UserRepository
from middleware.auth_middleware import get_current_user, require_own_resource_or_admin, TokenPayload
from schemas.user_schemas import (
    UserLoginRequest,
    UserLoginResponse,
    UserProfileResponse,
    UserRegistrationRequest,
    UserRegistrationResponse,
    VALID_ROLES,
)
from services.auth_service import AuthService
from services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

_user_repo  = UserRepository()
_auth_svc   = AuthService()
_email_svc  = EmailService()

_JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserRegistrationResponse, status_code=201)
def register_user(request: UserRegistrationRequest):
    """
    Register a new user.

    Role must be one of: admin | teacher | student.
    Teachers may supply ``assigned_sections`` at registration time.
    """
    try:
        # Duplicate email check
        if _user_repo.get_user_by_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        # Role guard (also enforced by Pydantic validator — double-safe)
        if request.role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role must be one of {sorted(VALID_ROLES)}.",
            )

        user_id = str(uuid.uuid4())
        user_data = {
            "email":             request.email,
            "name":              request.name,
            "role":              request.role,
            "password_hash":     AuthService.hash_password(request.password),
            "assigned_sections": request.assigned_sections,   # [] for non-teachers
            "is_active":         True,
            "created_at":        datetime.utcnow().isoformat(),
        }

        if not _user_repo.create_user(user_id, user_data):
            raise HTTPException(status_code=500, detail="Failed to create user.")

        logger.info("User registered: %s role=%s", user_id, request.role)
        return UserRegistrationResponse(
            success=True,
            user_id=user_id,
            message="User registered successfully.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=UserLoginResponse)
def login_user(request: UserLoginRequest):
    """
    Authenticate a user and return a JWT access+refresh token pair.

    The ``token`` field contains the access token for backward compatibility
    with clients that only read that field.
    """
    _auth_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user = _user_repo.get_user_by_email(request.email)
        if not user:
            raise _auth_err

        if not AuthService.verify_password(request.password, user.get("password_hash", "")):
            raise _auth_err

        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Contact your administrator.",
            )

        tokens    = AuthService.generate_token_pair(user)
        perms     = AuthService.get_permissions_for_role(user.get("role", "student"))
        expire_s  = _JWT_EXPIRE_MINUTES * 60

        logger.info("Login: user=%s role=%s", user["user_id"], user.get("role"))
        return UserLoginResponse(
            success=True,
            user_id=user["user_id"],
            role=user.get("role", "student"),
            token=tokens["access_token"],            # backward-compatible field
            refresh_token=tokens["refresh_token"],
            expires_in=expire_s,
            permissions=perms,
            assigned_sections=user.get("assigned_sections", []),
            message="Login successful.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Login error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/profile/{user_id}", response_model=UserProfileResponse)
def get_profile(
    user_id: str,
    caller: TokenPayload = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Fetch user profile by ID.

    Callers may only view their own profile unless they are admin.
    """
    try:
        user = _user_repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        perms = AuthService.get_permissions_for_role(user.get("role", "student"))
        return UserProfileResponse(
            user_id=user_id,
            name=user["name"],
            email=user["email"],
            role=user.get("role", "student"),
            is_active=user.get("is_active", True),
            permissions=perms,
            assigned_sections=user.get("assigned_sections", []),
            created_at=user.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching profile %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.patch("/profile/{user_id}")
def update_own_profile(
    user_id: str,
    name: str,
    caller: TokenPayload = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Self-service name update.

    Students and teachers can update their own name.
    Admins can update any user's name via this endpoint.
    For role/section changes use PATCH /api/v1/admin/users/{user_id}.
    """
    if len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    ok = _user_repo.update_user(user_id, {"name": name.strip()})
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"success": True, "user_id": user_id, "name": name.strip()}


# ─────────────────────────────────────────────────────────────────────────────
# Users by role  (admin utility)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/by-role/{role}")
def get_users_by_role(
    role: str,
    caller: TokenPayload = Depends(get_current_user),
):
    """
    List users by role.

    Admins see any role. Teachers/students are blocked (use admin router instead).
    """
    if caller.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins may list users by role.",
        )
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of {sorted(VALID_ROLES)}.",
        )

    try:
        users = _user_repo.list_users_by_role(role)
        for u in users:
            u.pop("password_hash", None)
            u.pop("reset_token", None)
            u.pop("reset_expires", None)
        return {"success": True, "role": role, "count": len(users), "users": users}
    except Exception as exc:
        logger.error("Error fetching users by role %s: %s", role, exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Password reset
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(email: str):
    """
    Send a password-reset link if the email is registered.

    Always returns success to prevent email enumeration.
    """
    try:
        user = _user_repo.get_user_by_email(email)
        if user:
            token   = str(uuid.uuid4())
            expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
            _user_repo.update_user(user["user_id"], {
                "reset_token":   token,
                "reset_expires": expires,
            })
            _email_svc.send_password_reset(email, token)
            logger.info("Password reset requested: %s", email)
    except Exception as exc:
        logger.error("Forgot-password error: %s", exc)

    # Always return the same response
    return {"success": True, "message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(token: str, new_password: str):
    """Reset password using a valid reset token (expires in 24 h)."""
    if len(new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters.",
        )

    try:
        from database.firebase_client import FirebaseClient
        fb = FirebaseClient()
        users_data: dict = fb.get_reference("users").get() or {}

        user_id = None
        for uid, udata in users_data.items():
            if not isinstance(udata, dict):
                continue
            if udata.get("reset_token") == token:
                expires_raw = udata.get("reset_expires")
                if expires_raw:
                    try:
                        if datetime.fromisoformat(expires_raw) > datetime.utcnow():
                            user_id = uid
                            break
                    except ValueError:
                        pass

        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        _user_repo.update_user(user_id, {
            "password_hash": AuthService.hash_password(new_password),
            "reset_token":   None,
            "reset_expires": None,
        })
        logger.info("Password reset successful: user=%s", user_id)
        return {"success": True, "message": "Password reset. You may now log in."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Reset-password error: %s", exc)
        raise HTTPException(status_code=400, detail="Password reset failed.")