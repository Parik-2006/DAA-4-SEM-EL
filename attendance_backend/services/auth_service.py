"""
services/auth_service.py
─────────────────────────────────────────────────────────────────────────────
JWT-based authentication and authorisation service.

Replaces the UUID-token stub in the original auth_service.py with a proper
HS256 JWT that embeds role, permissions, and section assignments so every
downstream middleware can make access-control decisions without a DB round-trip.

Dependencies (add to requirements.txt):
    python-jose[cryptography]>=3.3.0
    passlib[bcrypt]>=1.7.4
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ── Secret & algorithm ────────────────────────────────────────────────────────
# Override JWT_SECRET in production via environment variable.
_JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING")
_JWT_ALGORITHM: str = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_DAYS", "7"))

# ── Password hashing ──────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Role → permission matrix ──────────────────────────────────────────────────
# Single source of truth.  constants.py re-exports ROLE_PERMISSIONS from here.
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "list_all_students",
        "list_all_attendance",
        "list_all_analytics",
        "manage_users",
        "manage_sections",
        "manage_courses",
        "upload_timetable",
        "view_analytics",
        "mark_attendance",          # admins may override marks
        "delete_attendance",
        "view_audit_logs",
    ],
    "teacher": [
        "list_assigned_students",
        "list_assigned_attendance",
        "mark_attendance",
        "view_section_analytics",
        "view_analytics",
    ],
    "student": [
        "view_own_attendance",
        "view_own_analytics",
    ],
}

VALID_ROLES: frozenset = frozenset(ROLE_PERMISSIONS.keys())


class TokenPayload:
    """Typed wrapper around a decoded JWT payload."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.user_id: str = raw["sub"]
        self.email: str = raw.get("email", "")
        self.role: str = raw.get("role", "student")
        self.name: str = raw.get("name", "")
        self.permissions: List[str] = raw.get("permissions", [])
        self.assigned_sections: List[str] = raw.get("assigned_sections", [])
        self.token_type: str = raw.get("token_type", "access")
        self.exp: int = raw.get("exp", 0)
        # Keep raw dict for future-proofing
        self._raw = raw

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def can_access_section(self, section_id: str) -> bool:
        """Admin can access every section; teachers only their own."""
        if self.role == "admin":
            return True
        return section_id in self.assigned_sections

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TokenPayload user={self.user_id} role={self.role}>"


class AuthService:
    """Centralised authentication and authorisation helpers."""

    # ── Password helpers ──────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Return bcrypt hash of *password*."""
        return _pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Return True if *plain* matches *hashed*."""
        try:
            return _pwd_context.verify(plain, hashed)
        except Exception:
            return False

    # ── Token generation ──────────────────────────────────────────────────────

    @staticmethod
    def _build_claims(
        user: Dict[str, Any],
        token_type: str = "access",
        expires_delta: Optional[timedelta] = None,
    ) -> Dict[str, Any]:
        role: str = user.get("role", "student")
        permissions: List[str] = ROLE_PERMISSIONS.get(role, [])
        now = datetime.now(tz=timezone.utc)

        if expires_delta is None:
            expires_delta = (
                timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
                if token_type == "access"
                else timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
            )

        return {
            # Standard claims
            "sub": user["user_id"],
            "iat": now,
            "exp": now + expires_delta,
            # Custom claims
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "role": role,
            "permissions": permissions,
            "assigned_sections": user.get("assigned_sections", []),
            "token_type": token_type,
        }

    @classmethod
    def generate_access_token(cls, user: Dict[str, Any]) -> str:
        """Return a signed JWT access token for *user*."""
        claims = cls._build_claims(user, token_type="access")
        return jwt.encode(claims, _JWT_SECRET, algorithm=_JWT_ALGORITHM)

    @classmethod
    def generate_refresh_token(cls, user: Dict[str, Any]) -> str:
        """Return a signed JWT refresh token for *user*."""
        claims = cls._build_claims(user, token_type="refresh")
        return jwt.encode(claims, _JWT_SECRET, algorithm=_JWT_ALGORITHM)

    @classmethod
    def generate_token_pair(cls, user: Dict[str, Any]) -> Dict[str, str]:
        """Return both access and refresh tokens."""
        return {
            "access_token": cls.generate_access_token(user),
            "refresh_token": cls.generate_refresh_token(user),
            "token_type": "bearer",
        }

    # ── Token validation ──────────────────────────────────────────────────────

    @classmethod
    def decode_token(cls, token: str) -> TokenPayload:
        """
        Decode and validate *token*.

        Raises
        ------
        JWTError
            If the token is expired, tampered with, or malformed.
        """
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return TokenPayload(payload)

    @classmethod
    def verify_access_token(cls, token: str) -> TokenPayload:
        """Decode token and assert it is an access token."""
        payload = cls.decode_token(token)
        if payload.token_type != "access":
            raise JWTError("Expected access token, got refresh token")
        return payload

    @classmethod
    def refresh_access_token(cls, refresh_token: str, user: Dict[str, Any]) -> str:
        """
        Validate *refresh_token* and issue a fresh access token.

        Parameters
        ----------
        refresh_token:
            The refresh JWT from the client.
        user:
            Current user dict fetched from DB (authoritative source of role/sections).
        """
        payload = cls.decode_token(refresh_token)
        if payload.token_type != "refresh":
            raise JWTError("Expected refresh token")
        if payload.user_id != user["user_id"]:
            raise JWTError("Token subject mismatch")
        return cls.generate_access_token(user)

    # ── Convenience ───────────────────────────────────────────────────────────

    @staticmethod
    def get_permissions_for_role(role: str) -> List[str]:
        """Return the canonical permission list for a role."""
        return ROLE_PERMISSIONS.get(role, [])
