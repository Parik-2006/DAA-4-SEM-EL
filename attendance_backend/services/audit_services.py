"""
services/audit_service.py
─────────────────────────────────────────────────────────────────────────────
Writes an immutable audit record to the Firestore ``audit_logs`` collection
for every state-changing action in the attendance system.

Schema per document
-------------------
{
  "log_id"      : str,          # UUID
  "user_id"     : str,          # who performed the action
  "user_role"   : str,          # their role at the time
  "action"      : str,          # e.g. "MARK_ATTENDANCE", "EDIT_RECORD", "LOGIN"
  "resource"    : str,          # e.g. "attendance", "user", "section"
  "resource_id" : str | None,   # specific record ID if applicable
  "before"      : dict | None,  # state before change (None for CREATE)
  "after"       : dict | None,  # state after change (None for DELETE)
  "ip_address"  : str,
  "user_agent"  : str,
  "timestamp"   : str,          # ISO-8601 UTC
  "details"     : dict,         # extra contextual info
  "success"     : bool,
  "error"       : str | None,   # populated on failed actions
}

Usage
-----
  svc = get_audit_service()
  svc.log(
      user=request.state.user,
      action="MARK_ATTENDANCE",
      resource="attendance",
      resource_id=record_id,
      after=record_data,
      request=request,
  )
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from services.auth_service import UserContext

logger = logging.getLogger(__name__)


class AuditService:
    """
    Writes audit log entries to Firestore.

    The service degrades gracefully: if Firestore is unavailable it logs to
    the application log instead of crashing the request.
    """

    # Action constants (use these to avoid magic strings)
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_MARK_ATTENDANCE = "MARK_ATTENDANCE"
    ACTION_EDIT_ATTENDANCE = "EDIT_ATTENDANCE"
    ACTION_DELETE_ATTENDANCE = "DELETE_ATTENDANCE"
    ACTION_BULK_MARK = "BULK_MARK_ATTENDANCE"
    ACTION_LOCK_PERIOD = "LOCK_PERIOD"
    ACTION_UNLOCK_PERIOD = "UNLOCK_PERIOD"
    ACTION_CREATE_USER = "CREATE_USER"
    ACTION_UPDATE_USER = "UPDATE_USER"
    ACTION_DELETE_USER = "DELETE_USER"
    ACTION_UPLOAD_TIMETABLE = "UPLOAD_TIMETABLE"
    ACTION_CONFIG_CHANGE = "CONFIG_CHANGE"
    ACTION_ACCESS_DENIED = "ACCESS_DENIED"
    ACTION_REGISTER_FACE = "REGISTER_FACE"

    def __init__(self, firestore_db: Optional[Any] = None) -> None:
        self._db = firestore_db
        self._collection = "audit_logs"
        self._fallback_logs: list[dict] = []  # in-memory fallback

    def _get_db(self) -> Optional[Any]:
        """Lazy-load Firestore if not injected at construction."""
        if self._db is not None:
            return self._db
        try:
            from services.firebase_service import get_firebase_service
            fb = get_firebase_service()
            if fb:
                self._db = (
                    getattr(fb, "firestore_db", None)
                    or getattr(fb, "_firestore", None)
                )
        except Exception:
            pass
        return self._db

    def _extract_request_meta(self, request: Optional[Request]) -> Dict[str, str]:
        """Pull client IP and User-Agent from a FastAPI Request."""
        if request is None:
            return {"ip_address": "unknown", "user_agent": "unknown"}

        # Respect proxy headers
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )
        ua = request.headers.get("User-Agent", "unknown")
        return {"ip_address": ip, "user_agent": ua}

    def log(
        self,
        *,
        action: str,
        resource: str,
        user: Optional[UserContext] = None,
        resource_id: Optional[str] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> str:
        """
        Write an audit log entry.

        Parameters
        ----------
        action      : One of the ACTION_* constants (or any custom string).
        resource    : Logical resource type, e.g. "attendance", "user".
        user        : The ``UserContext`` performing the action.  Can be None
                      for pre-auth events (e.g. failed logins).
        resource_id : The specific record being acted on.
        before      : State snapshot BEFORE the change.
        after       : State snapshot AFTER the change.
        request     : The current FastAPI Request (for IP / User-Agent).
        details     : Any extra contextual information.
        success     : Whether the action succeeded.
        error       : Error message if ``success=False``.

        Returns
        -------
        str : The generated log_id (UUID).
        """
        log_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        request_meta = self._extract_request_meta(request)

        entry: Dict[str, Any] = {
            "log_id": log_id,
            "user_id": user.user_id if user else "anonymous",
            "user_role": user.role if user else "unknown",
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "before": before,
            "after": after,
            "ip_address": request_meta["ip_address"],
            "user_agent": request_meta["user_agent"],
            "timestamp": now_iso,
            "details": details or {},
            "success": success,
            "error": error,
        }

        # Write to Firestore
        db = self._get_db()
        if db is not None:
            try:
                db.collection(self._collection).document(log_id).set(entry)
                logger.debug("Audit: %s action=%s resource=%s id=%s", log_id, action, resource, resource_id)
                return log_id
            except Exception as exc:
                logger.error("Audit write to Firestore failed: %s — entry=%s", exc, entry)
        else:
            logger.warning(
                "AUDIT (no Firestore) user=%s action=%s resource=%s id=%s",
                entry["user_id"], action, resource, resource_id,
            )

        # Fallback: keep in memory
        self._fallback_logs.append(entry)
        return log_id

    def log_failed_access(
        self,
        *,
        user: Optional[UserContext],
        resource: str,
        resource_id: Optional[str],
        reason: str,
        request: Optional[Request] = None,
    ) -> str:
        """Convenience wrapper for denied access events."""
        return self.log(
            action=self.ACTION_ACCESS_DENIED,
            resource=resource,
            user=user,
            resource_id=resource_id,
            request=request,
            details={"denial_reason": reason},
            success=False,
            error=reason,
        )

    def get_fallback_logs(self) -> list[dict]:
        """Return in-memory logs (useful if Firestore is unavailable)."""
        return list(self._fallback_logs)


# ── Module-level singleton ─────────────────────────────────────────────────────
_audit_service: Optional[AuditService] = None


def init_audit_service(firestore_db: Optional[Any] = None) -> AuditService:
    global _audit_service
    _audit_service = AuditService(firestore_db=firestore_db)
    return _audit_service


def get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service