"""
api/websocket.py
────────────────────────────────────────────────────────────────────────────────
WebSocket and Server-Sent Events (SSE) endpoints for real-time attendance
updates.

Endpoints
---------
WS   /api/v1/realtime/ws/{section_id}
    Persistent bi-directional WebSocket connection.
    Required query params:
      client_id  – identifies the connecting user (student_id or faculty_id)
      role       – "student" | "teacher" | "admin"
      token      – opaque auth token validated server-side

    Role-based access control
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    • admin   → may subscribe to any section_id, plus the synthetic
                section_id "ADMIN_GLOBAL" which receives events from every
                section.
    • teacher → may only subscribe to sections listed in their assignment.
    • student → may only subscribe to their own class_id.

GET  /api/v1/realtime/sse/{section_id}
    Server-Sent Events stream (stateless HTTP, no upgrade required).
    Same query params and access rules as the WS endpoint.
    Preferred for clients that cannot maintain WebSocket connections (e.g.
    some mobile browsers, reverse proxies that buffer chunked responses).

GET  /api/v1/realtime/status
    Returns connection statistics (admin-accessible).

GET  /api/v1/realtime/connections/{section_id}
    Lists active WebSocket clients for a section (admin-accessible).

POST /api/v1/realtime/broadcast
    Manually push an event to a section (admin-only, useful for testing).

Design notes
------------
* Auth is intentionally lightweight here – tokens are looked up in Firebase
  Realtime DB under ``auth_tokens/{token}``.  In production replace with JWT
  verification middleware.
* The ``ADMIN_GLOBAL`` virtual room fan-out is achieved by the broadcast
  helper automatically including any admin clients registered under that key.
* A 5-second in-process cache is maintained per section_id for the teacher
  "active-class" roster.  The cache is busted whenever ``attendance_marked``
  or ``bulk_attendance`` events are broadcast for that section.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.realtime_service import get_realtime_service, _now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])

# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _validate_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate *token* against Firebase Realtime DB ``auth_tokens/{token}``.

    Returns the token document on success, None on failure.

    Stub – replace with JWT verification in production.
    """
    if not token:
        return None
    try:
        from database.firebase_client import FirebaseClient
        fb = FirebaseClient()
        doc = fb.get_reference(f"auth_tokens/{token}").get()
        if doc and isinstance(doc, dict) and not doc.get("revoked"):
            return doc
    except Exception as exc:
        logger.warning("Token validation error: %s", exc)
    # Dev fallback: treat any non-empty token as valid so local testing works
    # REMOVE THIS IN PRODUCTION
    if token.startswith("dev_"):
        parts = token.split("_")  # dev_{role}_{client_id}
        if len(parts) >= 3:
            return {"role": parts[1], "client_id": "_".join(parts[2:]), "revoked": False}
    return None


async def _authorise(
    token: str,
    client_id: str,
    role: str,
    section_id: str,
) -> bool:
    """
    Return True if the requesting client is allowed to subscribe to *section_id*.

    Rules
    -----
    • admin  → any section_id (including ADMIN_GLOBAL)
    • teacher → only sections in their ``course_assignments`` Firebase record
    • student → only their own ``class_id`` Firebase record
    """
    if role == "admin":
        return True

    try:
        from database.firebase_client import FirebaseClient
        fb = FirebaseClient()

        if role == "teacher":
            # Look up faculty assignments
            assignments_raw = fb.get_reference(f"course_assignments").get() or {}
            assigned_sections = {
                v.get("class_id")
                for v in assignments_raw.values()
                if isinstance(v, dict) and v.get("faculty_id") == client_id
            }
            return section_id in assigned_sections

        if role == "student":
            # Student may only watch their own class
            user = fb.get_reference(f"users/{client_id}").get() or {}
            return user.get("class_id") == section_id

    except Exception as exc:
        logger.warning("Authorisation check failed: %s", exc)

    return False


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/{section_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    section_id: str,
    client_id: str = Query(..., description="Connecting user ID"),
    role: str = Query("student", description="user role: student | teacher | admin"),
    token: str = Query(..., description="Auth token"),
):
    """
    Persistent WebSocket connection for real-time attendance events.

    On connect the server sends::

        { "event": "connected", "section_id": "...", "ts": "..." }

    Subsequent messages follow the event contract defined in realtime_service.py.

    Client may send ``"ping"`` text frames; the server echoes ``{"event":"pong"}``.

    Close codes
    -----------
    4001  Invalid or missing token
    4003  Not authorised to subscribe to this section
    """
    svc = get_realtime_service()

    # Auth
    token_doc = await _validate_token(token)
    if not token_doc:
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    # Authorise
    allowed = await _authorise(token, client_id, role, section_id)
    if not allowed:
        await websocket.close(code=4003, reason="Not authorised for this section")
        return

    # Delegate to service (blocks until client disconnects)
    await svc.connect_ws(websocket, section_id=section_id, client_id=client_id, role=role)


# ── SSE endpoint ──────────────────────────────────────────────────────────────

@router.get(
    "/sse/{section_id}",
    summary="Server-Sent Events stream for real-time attendance updates",
    response_description="text/event-stream chunked response",
)
async def sse_endpoint(
    section_id: str,
    client_id: str = Query(..., description="Connecting user ID"),
    role: str = Query("student", description="user role: student | teacher | admin"),
    token: str = Query(..., description="Auth token"),
):
    """
    SSE stream for clients that cannot use WebSockets.

    Returns a ``text/event-stream`` response. Events are JSON-encoded
    ``data:`` frames.

    Keepalive SSE comment lines (``": keepalive"``) are sent every 20 s so
    reverse proxies do not time out idle connections.
    """
    # Auth
    token_doc = await _validate_token(token)
    if not token_doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Authorise
    allowed = await _authorise(token, client_id, role, section_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorised to subscribe to section '{section_id}'",
        )

    svc = get_realtime_service()

    async def _generate():
        async for chunk in svc.sse_stream(section_id, client_id=client_id, role=role):
            yield chunk

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # tell nginx not to buffer
            "Connection": "keep-alive",
        },
    )


# ── Admin introspection endpoints ─────────────────────────────────────────────

@router.get(
    "/status",
    summary="Real-time connection statistics (admin-only)",
)
async def realtime_status(
    token: str = Query(..., description="Admin auth token"),
):
    """Return aggregate statistics for all active WebSocket and SSE connections."""
    token_doc = await _validate_token(token)
    if not token_doc or token_doc.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    svc = get_realtime_service()
    return svc.stats()


@router.get(
    "/connections/{section_id}",
    summary="List active WebSocket clients for a section (admin-only)",
)
async def list_connections(
    section_id: str,
    token: str = Query(..., description="Admin auth token"),
):
    """Returns the list of currently connected WebSocket clients for *section_id*."""
    token_doc = await _validate_token(token)
    if not token_doc or token_doc.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    svc = get_realtime_service()
    return {
        "section_id": section_id,
        "ws_clients": svc.connected_clients(section_id),
        "sse_subscribers": svc.sse_subscriber_count(section_id),
        "ts": _now(),
    }


# ── Manual broadcast endpoint (admin / testing) ───────────────────────────────

class BroadcastRequest(BaseModel):
    section_id: str = Field(..., description="Target section (class_id)")
    event_type: str = Field(..., description="Event name, e.g. 'attendance_marked'")
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/broadcast",
    summary="Manually broadcast an event to a section (admin-only)",
    status_code=200,
)
async def manual_broadcast(
    body: BroadcastRequest,
    token: str = Query(..., description="Admin auth token"),
):
    """
    Push an arbitrary event to all clients subscribed to *section_id*.

    Useful for testing and admin announcements.
    """
    token_doc = await _validate_token(token)
    if not token_doc or token_doc.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    svc = get_realtime_service()
    notified = await svc.broadcast(
        event_type=body.event_type,
        section_id=body.section_id,
        payload=body.payload,
    )
    return {
        "success": True,
        "section_id": body.section_id,
        "event_type": body.event_type,
        "clients_notified": notified,
        "ts": _now(),
    }
