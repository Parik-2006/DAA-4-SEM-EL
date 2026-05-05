"""
schemas/user_schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic schemas for user registration, login, and profile endpoints.

Changes from original
─────────────────────
• UserRegistrationRequest  — validates role against VALID_ROLES; optional
                             assigned_sections for teachers.
• UserRegistrationResponse — unchanged (backward-compatible).
• UserLoginRequest          — unchanged (backward-compatible).
• UserLoginResponse         — adds permissions, assigned_sections, expires_in.
• UserProfileResponse       — adds permissions, assigned_sections, created_at.
• New: PermissionList, RoleInfo  (used by /auth/me and admin endpoints).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Valid roles (must match services/auth_service.ROLE_PERMISSIONS) ────────────
VALID_ROLES: frozenset = frozenset({"admin", "teacher", "student"})


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

class UserRegistrationRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique email address", example="alice@school.edu")
    password: str = Field(..., min_length=6, description="Minimum 6 characters")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    role: str = Field(
        ...,
        description="One of: admin | teacher | student",
        example="teacher",
    )
    # Teachers may be given their section assignments at creation time.
    assigned_sections: List[str] = Field(
        default_factory=list,
        description="Section IDs assigned to this teacher (teachers only)",
        example=["SEC001", "SEC002"],
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v

    @field_validator("assigned_sections")
    @classmethod
    def sections_only_for_teachers(cls, v: List[str], info) -> List[str]:
        # We cannot access `role` at this point in all Pydantic versions,
        # so we just pass through — the API layer enforces the business rule.
        return v

    model_config = {"json_schema_extra": {
        "examples": [{
            "email": "alice@school.edu",
            "password": "securepass",
            "name": "Alice Sharma",
            "role": "teacher",
            "assigned_sections": ["SEC001"],
        }]
    }}


class UserRegistrationResponse(BaseModel):
    success: bool
    user_id: str
    message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Login  (kept backward-compatible; richer response added)
# ─────────────────────────────────────────────────────────────────────────────

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserLoginResponse(BaseModel):
    """
    Backward-compatible login response.

    The `token` field now carries the JWT access token.
    `permissions` and `assigned_sections` are new; clients that do not
    understand them will simply ignore the extra fields.
    """
    success: bool
    user_id: str
    role: str
    token: Optional[str] = Field(None, description="JWT access token (Bearer)")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    expires_in: Optional[int] = Field(None, description="Access token TTL in seconds")
    permissions: List[str] = Field(default_factory=list)
    assigned_sections: List[str] = Field(default_factory=list)
    message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────

class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    is_active: bool = True
    permissions: List[str] = Field(default_factory=list)
    assigned_sections: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Role & permission info  (used by admin / auth/me endpoints)
# ─────────────────────────────────────────────────────────────────────────────

class PermissionList(BaseModel):
    role: str
    permissions: List[str]


class RoleInfo(BaseModel):
    """Returned by GET /admin/roles — describes all roles and their permissions."""
    roles: List[PermissionList]


# ─────────────────────────────────────────────────────────────────────────────
# User update  (admin patching another user's role / sections)
# ─────────────────────────────────────────────────────────────────────────────

class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    assigned_sections: Optional[List[str]] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class UserUpdateResponse(BaseModel):
    success: bool
    user_id: str
    message: Optional[str] = None
