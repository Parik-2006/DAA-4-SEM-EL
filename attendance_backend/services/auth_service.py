"""
services/auth_service.py
─────────────────────────────────────────────────────────────────────────────
JWT token creation and validation for the Smart Attendance System.

Roles:  admin | teacher | student
Token claims:
  user_id           : str
  email             : str
  role              : "admin" | "teacher" | "student"
  assigned_sections : list[str]   (teachers only; empty list otherwise)
  permissions       : list[str]   (derived from role at issue time)
  iat               : int  (issued-at, UNIX timestamp)
  exp               : int  (expiry, UNIX timestamp)

Usage
-----
  svc = AuthService()
  token = svc.create_token(user)
  claims = svc.decode_token(token)        # raises if invalid / expired
  user = svc.authenticate(email, password, db)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()
try:
    from google.cloud.firestore_v1 import FieldFilter
except Exception:
    FieldFilter = None

logger = logging.getLogger(__name__)

# ── JWT secret (set JWT_SECRET in env for production) ─────────────────────────
_JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production-please")
_JWT_ALGORITHM: str = "HS256"
_TOKEN_EXPIRY_SECONDS: int = int(os.getenv("JWT_EXPIRY_SECONDS", str(8 * 3600)))  # 8 h

# ── Role → permission mapping ──────────────────────────────────────────────────
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "list_all_students",
        "list_all_attendance",
        "manage_users",
        "manage_sections",
        "view_analytics",
        "upload_timetable",
        "view_audit_logs",
        "manage_system_config",
    ],
    "teacher": [
        "list_assigned_students",
        "list_assigned_attendance",
        "mark_attendance",
        "view_section_analytics",
    ],
    "student": [
        "view_own_attendance",
        "view_own_analytics",
    ],
}

VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())


@dataclass
class UserContext:
    """
    Deserialized, validated JWT payload attached to every authenticated request.
    Stored in ``request.state.user`` by AuthMiddleware.
    """
    user_id: str
    email: str
    role: str
    assigned_sections: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    issued_at: int = 0
    expires_at: int = 0


    # ── Convenience helpers ────────────────────────────────────────────────────

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def can_access_section(self, section_id: str) -> bool:
        if self.role == "admin":
            return True
        if self.role == "teacher":
            return section_id in self.assigned_sections
        return False  # students cannot access sections directly

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_teacher(self) -> bool:
        return self.role == "teacher"

    def is_student(self) -> bool:
        return self.role == "student"


# Backward-compatible alias used throughout the codebase.
TokenPayload = UserContext


# ── Minimal pure-Python HS256 JWT (no PyJWT dependency required) ───────────────
import base64
import json


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def _sign(header_b64: str, payload_b64: str, secret: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)

# Detailed auth logger for debugging token issues
_auth_log = logging.getLogger("attendance_backend.services.auth_service")


class AuthService:
    """Handles JWT issuance and validation."""

    def __init__(self, secret: str = _JWT_SECRET, expiry: int = _TOKEN_EXPIRY_SECONDS):
        self._secret = secret
        self._expiry = expiry

    # ── Token creation ─────────────────────────────────────────────────────────

    def create_token(
        self,
        user_id: str,
        email: str,
        role: str,
        assigned_sections: Optional[List[str]] = None,
    ) -> str:
        """
        Issue a signed JWT for the given user.

        Permissions are derived automatically from the role.
        """
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of {sorted(VALID_ROLES)}")

        now = int(time.time())
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "assigned_sections": assigned_sections or [],
            "permissions": ROLE_PERMISSIONS.get(role, []),
            "iat": now,
            "exp": now + self._expiry,
        }
        header = {"alg": _JWT_ALGORITHM, "typ": "JWT"}
        h64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        p64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        sig = _sign(h64, p64, self._secret)
        return f"{h64}.{p64}.{sig}"

    # ── Token validation ───────────────────────────────────────────────────────

    def decode_token(self, token: str) -> UserContext:
        """
        Decode and validate a JWT.

        Raises
        ------
        ValueError  : malformed token, bad signature, expired.
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                _auth_log.debug("Malformed token parts: %s", parts)
                raise ValueError("Malformed token: expected 3 parts")
            h64, p64, sig = parts

            # Verify signature
            expected_sig = _sign(h64, p64, self._secret)
            if not hmac.compare_digest(sig, expected_sig):
                _auth_log.warning("Token signature mismatch. expected=%s received=%s", expected_sig, sig)
                raise ValueError("Invalid token signature")

            try:
                payload: Dict[str, Any] = json.loads(_b64url_decode(p64))
            except Exception as exc:
                _auth_log.exception("Failed to decode payload b64: %s", exc)
                raise

            # Check expiry
            if int(time.time()) > payload.get("exp", 0):
                _auth_log.info("Token expired for user=%s exp=%s now=%s", payload.get("user_id"), payload.get("exp"), int(time.time()))
                raise ValueError("Token has expired")

            _auth_log.debug("Token payload validated for user=%s", payload.get("user_id"))
            return UserContext(
                user_id=payload["user_id"],
                email=payload.get("email", ""),
                role=payload.get("role", ""),
                assigned_sections=payload.get("assigned_sections", []),
                permissions=payload.get("permissions", []),
                issued_at=payload.get("iat", 0),
                expires_at=payload.get("exp", 0),
            )
        except ValueError:
            raise
        except Exception as exc:
            _auth_log.exception("Unexpected error decoding token: %s", exc)
            raise ValueError(f"Token decode failed: {exc}") from exc

    # ── Static method for middleware (wraps decode_token) ─────────────────────

    @staticmethod
    def verify_access_token(token: str) -> UserContext:
        """
        Static method for middleware to verify and decode a JWT token.

        Raises
        ------
        ValueError  : malformed token, bad signature, expired.
        """
        service = get_auth_service()
        return service.decode_token(token)

    # ── Password hashing helpers ───────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Return SHA-256 hex digest (use bcrypt in production)."""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return hmac.compare_digest(
            hashlib.sha256(password.encode()).hexdigest(), password_hash
        )

    # ── Authenticate against Firestore ────────────────────────────────────────

    def authenticate(self, email: str, password: str, firestore_db: Any) -> Optional[Dict[str, Any]]:
        """
        Look up user by email in Firestore ``users`` collection, verify password.

        Returns the user dict on success, None on failure.
        """
        try:
            docs = (
                firestore_db.collection("users")
                .where(filter=FieldFilter("email", "==", email))
                .limit(1)
                .stream()
            )
            for doc in docs:
                user = doc.to_dict()
                stored_hash = user.get("password_hash", "")
                if stored_hash and self.verify_password(password, stored_hash):
                    return {**user, "doc_id": doc.id}
            return None
        except Exception as exc:
            logger.error("Authentication query failed: %s", exc)
            return None


# Module-level singleton
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service