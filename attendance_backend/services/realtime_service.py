"""
services/realtime_service.py
──────────────────────────────────────────────────────────────────────────────
In-memory realtime broadcaster for section-scoped attendance events.

This service supports the prompt-3 integration points used by:
- attendance_backend/api/websocket.py
- attendance_backend/api/teacher.py

It provides:
- WebSocket connection management
- Server-Sent Events streaming
- Broadcast fan-out by section_id
- A tiny in-process cache used by teacher dashboard polling
- Connection stats for admin introspection

The implementation is intentionally lightweight and self-contained so it can
run without adding external dependencies or new infrastructure.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

TEACHER_CACHE_TTL = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class _Subscriber:
    connection_id: str
    section_id: str
    client_id: str
    role: str
    connected_at: float = field(default_factory=time.time)
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))


class RealtimeService:
    def __init__(self) -> None:
        self._ws_connections: Dict[str, _Subscriber] = {}
        self._sse_connections: Dict[str, _Subscriber] = {}
        self._cache: Dict[str, tuple[float, Any]] = {}

    # ------------------------------------------------------------------
    # Cache helpers used by teacher.py
    # ------------------------------------------------------------------

    def cache_get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        created_at, value = entry
        if (time.monotonic() - created_at) > TEACHER_CACHE_TTL:
            self._cache.pop(key, None)
            return None
        return value

    def cache_set(self, key: str, value: Any, ttl: int = TEACHER_CACHE_TTL) -> None:
        _ = ttl  # kept for call-site compatibility
        self._cache[key] = (time.monotonic(), value)

    def _invalidate_cache(self, key: str) -> None:
        self._cache.pop(key, None)

    def _invalidate_teacher_caches(self) -> None:
        keys = [key for key in self._cache if key.startswith("teacher_active_")]
        for key in keys:
            self._cache.pop(key, None)

    # ------------------------------------------------------------------
    # Connection registration
    # ------------------------------------------------------------------

    def _register(self, registry: Dict[str, _Subscriber], section_id: str, client_id: str, role: str) -> _Subscriber:
        subscriber = _Subscriber(
            connection_id=str(uuid.uuid4()),
            section_id=section_id,
            client_id=client_id,
            role=role,
        )
        registry[subscriber.connection_id] = subscriber
        return subscriber

    def _unregister(self, registry: Dict[str, _Subscriber], subscriber: _Subscriber) -> None:
        registry.pop(subscriber.connection_id, None)

    def _registry_snapshot(self, section_id: str, registry: Dict[str, _Subscriber]) -> List[Dict[str, Any]]:
        return [
            {
                "connection_id": sub.connection_id,
                "client_id": sub.client_id,
                "role": sub.role,
                "connected_at": datetime.fromtimestamp(sub.connected_at, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            for sub in registry.values()
            if sub.section_id == section_id
        ]

    # ------------------------------------------------------------------
    # Public API used by routers
    # ------------------------------------------------------------------

    async def connect_ws(self, websocket: WebSocket, section_id: str, client_id: str, role: str) -> None:
        await websocket.accept()
        subscriber = self._register(self._ws_connections, section_id, client_id, role)
        await websocket.send_json({
            "event": "connected",
            "section_id": section_id,
            "client_id": client_id,
            "role": role,
            "ts": _now(),
        })

        async def _sender() -> None:
            try:
                while True:
                    event = await subscriber.queue.get()
                    try:
                        await websocket.send_json(event)
                    except Exception as e:
                        # Connection closed or broken — stop sender
                        logger.debug("WebSocket send failed: %s", type(e).__name__)
                        raise

            except (ConnectionResetError, BrokenPipeError, RuntimeError) as e:
                logger.debug("WebSocket connection lost during send: %s", type(e).__name__)
            except asyncio.CancelledError:
                pass

        async def _receiver() -> None:
            try:
                while True:
                    message = await websocket.receive_text()
                    if message.strip().lower() == "ping":
                        try:
                            await websocket.send_json({"event": "pong", "ts": _now()})
                        except Exception:
                            break
            except (ConnectionResetError, BrokenPipeError, RuntimeError):
                logger.debug("WebSocket connection lost during receive")
            except asyncio.CancelledError:
                pass

        sender_task = asyncio.create_task(_sender())
        receiver_task = asyncio.create_task(_receiver())

        try:
            done, pending = await asyncio.wait(
                {sender_task, receiver_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in done:
                try:
                    exc = task.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        logger.debug("WebSocket connection ended: %s", type(exc).__name__)
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            logger.debug("WebSocket error during wait: %s", type(e).__name__)
        finally:
            for task in (sender_task, receiver_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._unregister(self._ws_connections, subscriber)

    async def sse_stream(self, section_id: str, client_id: str, role: str):
        subscriber = self._register(self._sse_connections, section_id, client_id, role)
        try:
            yield self._format_sse({
                "event": "connected",
                "section_id": section_id,
                "client_id": client_id,
                "role": role,
                "ts": _now(),
            })
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.queue.get(), timeout=20)
                    yield self._format_sse(event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._unregister(self._sse_connections, subscriber)

    async def broadcast(self, event_type: str, section_id: str, payload: Dict[str, Any]) -> int:
        event = {
            "event": event_type,
            "section_id": section_id,
            "payload": payload,
            "ts": _now(),
        }

        recipients = self._recipients_for_section(section_id)
        for subscriber in recipients:
            self._enqueue(subscriber, event)

        if event_type in {"attendance_marked", "bulk_attendance"}:
            self._invalidate_teacher_caches()

        return len(recipients)

    def stats(self) -> Dict[str, Any]:
        sections: Set[str] = {
            sub.section_id for sub in self._ws_connections.values()
        } | {
            sub.section_id for sub in self._sse_connections.values()
        }

        return {
            "total_ws_connections": len(self._ws_connections),
            "total_sse_connections": len(self._sse_connections),
            "sections": {
                section_id: {
                    "ws_clients": len([s for s in self._ws_connections.values() if s.section_id == section_id]),
                    "sse_subscribers": len([s for s in self._sse_connections.values() if s.section_id == section_id]),
                }
                for section_id in sorted(sections)
            },
            "generated_at": _now(),
        }

    def connected_clients(self, section_id: str) -> List[Dict[str, Any]]:
        return self._registry_snapshot(section_id, self._ws_connections)

    def sse_subscriber_count(self, section_id: str) -> int:
        return len([s for s in self._sse_connections.values() if s.section_id == section_id])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recipients_for_section(self, section_id: str) -> List[_Subscriber]:
        recipients = [
            sub for sub in self._ws_connections.values()
            if sub.section_id == section_id or sub.section_id == "ADMIN_GLOBAL"
        ]
        recipients.extend(
            sub for sub in self._sse_connections.values()
            if sub.section_id == section_id or sub.section_id == "ADMIN_GLOBAL"
        )
        return recipients

    def _enqueue(self, subscriber: _Subscriber, event: Dict[str, Any]) -> None:
        try:
            subscriber.queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                subscriber.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                subscriber.queue.put_nowait(event)

    @staticmethod
    def _format_sse(event: Dict[str, Any]) -> str:
        return f"event: {event.get('event', 'message')}\ndata: {json.dumps(event)}\n\n"


_realtime_service: Optional[RealtimeService] = None


def get_realtime_service() -> RealtimeService:
    global _realtime_service
    if _realtime_service is None:
        _realtime_service = RealtimeService()
    return _realtime_service