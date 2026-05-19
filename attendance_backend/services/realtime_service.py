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
from typing import Any, Dict, FrozenSet, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

TEACHER_CACHE_TTL = 5
WINDOW_TICK_INTERVAL = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class _Subscriber:
    connection_id: str
    section_id:    str
    client_id:     str
    role:          str
    authorized_sections: FrozenSet[str] = field(default_factory=frozenset)
    connected_at: float = field(default_factory=time.time)
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))

    def may_receive(self, event_section_id: str) -> bool:
        if self.role == "admin":
            return True
        if self.section_id == "ADMIN_GLOBAL":
            return True
        if event_section_id in self.authorized_sections:
            return True
        return self.section_id == event_section_id


class RealtimeService:

    def __init__(self) -> None:
        self._ws_connections:  Dict[str, _Subscriber] = {}
        self._sse_connections: Dict[str, _Subscriber] = {}
        self._cache:           Dict[str, tuple[float, Any]] = {}
        self._tick_task:       Optional[asyncio.Task] = None

    # ── Cache helpers ──────────────────────────────────────────────────────

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
        self._cache[key] = (time.monotonic(), value)

    def _invalidate_cache(self, key: str) -> None:
        self._cache.pop(key, None)

    def _invalidate_teacher_caches(self) -> None:
        for key in [k for k in self._cache if k.startswith("teacher_active_")]:
            self._cache.pop(key, None)

    def _build_event(self, event_type: str, section_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event": event_type,
            "section_id": section_id,
            "payload": payload,
            "ts": _now(),
        }

    def _after_publish(self, event_type: str, section_id: str) -> None:
        if event_type in {"attendance_marked", "bulk_attendance", "attendance_updated"}:
            self._invalidate_teacher_caches()
            try:
                from services.embedding_scope_service import get_scope_service
                svc = get_scope_service()
                if svc:
                    svc.invalidate_section(section_id)
            except Exception:
                pass

    # Compatibility: keep section-scope helpers used elsewhere
    def get_section_scope(self, faculty_id: str) -> Optional[Any]:
        return self.cache_get(f"scope_{faculty_id}")

    def set_section_scope(self, faculty_id: str, scope: Any, ttl: int = 90) -> None:
        self.cache_set(f"scope_{faculty_id}", scope, ttl=ttl)

    def invalidate_section_scope(self, faculty_id: str) -> None:
        self._invalidate_cache(f"scope_{faculty_id}")
        self._invalidate_cache(f"teacher_active_{faculty_id}")

    # ── Connection registration ───────────────────────────────────────────

    def _register(
        self,
        registry: Dict[str, _Subscriber],
        section_id: str,
        client_id: str,
        role: str,
        authorized_sections: FrozenSet[str] = frozenset(),
    ) -> _Subscriber:
        subscriber = _Subscriber(
            connection_id=str(uuid.uuid4()),
            section_id=section_id,
            client_id=client_id,
            role=role,
            authorized_sections=authorized_sections,
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

    # ── Public API ────────────────────────────────────────────────────────

    async def connect_ws(
        self,
        websocket: WebSocket,
        section_id: str,
        client_id: str,
        role: str,
        authorized_sections: FrozenSet[str] = frozenset(),
    ) -> None:
        await websocket.accept()
        subscriber = self._register(
            self._ws_connections, section_id, client_id, role, authorized_sections
        )
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

    async def sse_stream(
        self,
        section_id: str,
        client_id: str,
        role: str,
        authorized_sections: FrozenSet[str] = frozenset(),
    ):
        subscriber = self._register(
            self._sse_connections, section_id, client_id, role, authorized_sections
        )
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

    def publish_now(self, event_type: str, section_id: str, payload: Dict[str, Any]) -> int:
        """
        Synchronously enqueue an event for WebSocket/SSE clients.

        RTSP stream handlers run in worker threads, outside FastAPI's async
        request path. This method lets those CCTV workers emit the same
        realtime attendance events as normal API requests without needing an
        event loop in the stream thread.
        """
        event = self._build_event(event_type, section_id, payload)
        count = 0
        for sub in list(self._ws_connections.values()) + list(self._sse_connections.values()):
            if sub.may_receive(section_id):
                self._enqueue(sub, event)
                count += 1

        self._after_publish(event_type, section_id)
        return count

    async def broadcast(self, event_type: str, section_id: str, payload: Dict[str, Any]) -> int:
        return self.publish_now(event_type, section_id, payload)

    # ── window_tick background loop ───────────────────────────────────────

    def start_window_tick_loop(self) -> None:
        if self._tick_task and not self._tick_task.done():
            return
        self._tick_task = asyncio.create_task(self._window_tick_loop())
        logger.info("window_tick loop started")

    async def _window_tick_loop(self) -> None:
        while True:
            await asyncio.sleep(WINDOW_TICK_INTERVAL)
            try:
                await self._emit_window_ticks()
            except Exception as exc:
                logger.warning("window_tick_loop error (swallowed): %s", exc)

    async def _emit_window_ticks(self) -> None:
        from services.attendance_lock_service import get_lock_service
        from services.firebase_service import get_firebase_service

        lock_svc = get_lock_service()
        if lock_svc is None:
            return

        active_sections: Set[str] = set()
        for sub in list(self._ws_connections.values()) + list(self._sse_connections.values()):
            if sub.section_id and sub.section_id != "ADMIN_GLOBAL":
                active_sections.add(sub.section_id)

        if not active_sections:
            return

        try:
            fb = get_firebase_service()
            db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
            if db is None:
                return
        except Exception:
            return

        for section_id in active_sections:
            try:
                from google.cloud.firestore_v1 import FieldFilter
                now_str = datetime.now().strftime("%H:%M")
                dow     = datetime.now().weekday()
                docs    = (
                    db.collection("periods")
                    .where(filter=FieldFilter("class_id",     "==", section_id))
                    .where(filter=FieldFilter("day_of_week",  "==", dow))
                    .where(filter=FieldFilter("active_status","==", True))
                    .where(filter=FieldFilter("start_time",   "<=", now_str))
                    .limit(1)
                    .stream()
                )
                periods = [d.to_dict() for d in docs]
                if not periods:
                    continue

                period = periods[0]
                window = lock_svc.get_window_status(period)

                await self.broadcast(
                    event_type="window_tick",
                    section_id=section_id,
                    payload={
                        "period_id":       period.get("period_id"),
                        "phase":           window.get("phase"),
                        "is_open":         window.get("is_open"),
                        "time_remaining":  window.get("time_remaining"),
                        "window_closes_at": window.get("window_closes_at"),
                        "message":         window.get("message"),
                    },
                )
            except Exception as exc:
                logger.debug("window_tick for section %s failed: %s", section_id, exc)

    # ── Stats / introspection ─────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        sections: Set[str] = {sub.section_id for sub in self._ws_connections.values()} | {sub.section_id for sub in self._sse_connections.values()}
        return {
            "total_ws_connections":  len(self._ws_connections),
            "total_sse_connections": len(self._sse_connections),
            "sections": {
                sid: {
                    "ws_clients":      sum(1 for s in self._ws_connections.values()  if s.section_id == sid),
                    "sse_subscribers": sum(1 for s in self._sse_connections.values() if s.section_id == sid),
                }
                for sid in sorted(sections)
            },
            "generated_at": _now(),
        }

    def connected_clients(self, section_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "connection_id": s.connection_id,
                "client_id":     s.client_id,
                "role":          s.role,
                "connected_at":  datetime.fromtimestamp(s.connected_at, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            for s in self._ws_connections.values()
            if s.section_id == section_id
        ]

    def sse_subscriber_count(self, section_id: str) -> int:
        return sum(1 for s in self._sse_connections.values() if s.section_id == section_id)

    # ── Internals ─────────────────────────────────────────────────────────

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
