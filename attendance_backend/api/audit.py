"""
api/audit.py
─────────────────────────────────────────────────────────────────────────────
Admin-only endpoints for querying the audit log collection.

GET /api/v1/audit/logs
    Paginated, filterable list of all audit log entries.

GET /api/v1/audit/logs/{log_id}
    Single log entry by ID.

GET /api/v1/audit/attendance/{record_id}
    All audit entries for a specific attendance record.

GET /api/v1/audit/user/{user_id}
    All audit entries for a specific user.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
try:
    from google.cloud.firestore_v1 import FieldFilter
except Exception:
    FieldFilter = None

from decorators.auth_decorators import require_admin
from services.auth_service import UserContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_firestore():
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        if fb:
            return getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
    except Exception as exc:
        logger.error("Firestore unavailable: %s", exc)
    return None


def _doc_to_dict(doc) -> Dict[str, Any]:
    d = doc.to_dict() or {}
    d["_doc_id"] = doc.id
    return d


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/audit/logs
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/logs",
    summary="[Admin] Paginated audit log with optional filters",
)
async def list_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action, e.g. MARK_ATTENDANCE"),
    resource: Optional[str] = Query(None, description="Filter by resource type, e.g. attendance"),
    success: Optional[bool] = Query(None, description="Filter by success/failure"),
    date_from: Optional[str] = Query(None, description="ISO-8601 start timestamp (inclusive)"),
    date_to: Optional[str] = Query(None, description="ISO-8601 end timestamp (inclusive)"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: UserContext = require_admin,
):
    """
    Returns a paginated list of audit log entries.

    **Admin only.** All filters are optional and combinable.

    Sorted by ``timestamp`` descending (most recent first).
    """
    db = _get_firestore()
    if db is None:
        raise HTTPException(503, "Firestore not available")

    try:
        query = db.collection("audit_logs")

        if user_id:
            query = query.where(filter=FieldFilter("user_id", "==", user_id))
        if action:
            query = query.where(filter=FieldFilter("action", "==", action.upper()))
        if resource:
            query = query.where(filter=FieldFilter("resource", "==", resource))
        if success is not None:
            query = query.where(filter=FieldFilter("success", "==", success))
        if date_from:
            query = query.where(filter=FieldFilter("timestamp", ">=", date_from))
        if date_to:
            query = query.where(filter=FieldFilter("timestamp", "<=", date_to))

        query = query.order_by("timestamp", direction="DESCENDING")

        docs = list(query.stream())
        total = len(docs)

        start = (page - 1) * limit
        page_docs = docs[start: start + limit]

        entries = [_doc_to_dict(d) for d in page_docs]

    except Exception as exc:
        logger.error("Audit log query failed: %s", exc)
        raise HTTPException(500, f"Failed to query audit logs: {exc}")

    return JSONResponse(status_code=200, content={
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
        "data": entries,
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/audit/logs/{log_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/logs/{log_id}",
    summary="[Admin] Single audit log entry",
)
async def get_audit_log(
    log_id: str,
    admin: UserContext = require_admin,
):
    db = _get_firestore()
    if db is None:
        raise HTTPException(503, "Firestore not available")

    try:
        doc = db.collection("audit_logs").document(log_id).get()
        if not doc.exists:
            raise HTTPException(404, f"Audit log '{log_id}' not found.")
        return _doc_to_dict(doc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch log: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/audit/attendance/{record_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/attendance/{record_id}",
    summary="[Admin] Audit trail for a specific attendance record",
)
async def get_attendance_audit_trail(
    record_id: str,
    admin: UserContext = require_admin,
):
    """
    Returns all audit entries related to a specific attendance record,
    including its original creation, any edits, and lock events.

    Sorted by ``timestamp`` ascending (chronological order).
    """
    db = _get_firestore()
    if db is None:
        raise HTTPException(503, "Firestore not available")

    try:
        docs = (
            db.collection("audit_logs")
            .where(filter=FieldFilter("resource_id", "==", record_id))
            .order_by("timestamp")
            .stream()
        )
        entries = [_doc_to_dict(d) for d in docs]
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch audit trail: {exc}")

    return JSONResponse(status_code=200, content={
        "record_id": record_id,
        "entry_count": len(entries),
        "audit_trail": entries,
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/audit/user/{user_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/user/{user_id}",
    summary="[Admin] All audit entries for a specific user",
)
async def get_user_audit_trail(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: UserContext = require_admin,
):
    """
    Returns all audit log entries where ``user_id`` matches.

    Useful for reviewing a specific user's activity history.
    Sorted most-recent-first.
    """
    db = _get_firestore()
    if db is None:
        raise HTTPException(503, "Firestore not available")

    try:
        docs = list(
            db.collection("audit_logs")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .order_by("timestamp", direction="DESCENDING")
            .stream()
        )
        total = len(docs)
        start = (page - 1) * limit
        entries = [_doc_to_dict(d) for d in docs[start: start + limit]]
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch user audit trail: {exc}")

    return JSONResponse(status_code=200, content={
        "user_id": user_id,
        "total": total,
        "page": page,
        "limit": limit,
        "data": entries,
    })