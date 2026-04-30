"""
services/period_detection_service.py
─────────────────────────────────────────────────────────────────────────────
Background service that runs every 60 seconds and determines which timetable
period is currently active.

Design goals
------------
* Zero external dependencies beyond what already exists in the project.
  Uses a plain dict cache by default; transparently upgrades to Redis when
  the ``REDIS_URL`` environment variable is set.
* Handles edge-cases:
    - Lab periods spanning 2+ hours
    - Holiday / break periods (always returned as the active period when they
      match the current day, never superseded by a normal period)
    - Overlapping periods → all matches returned; the earliest-starting one
      is designated the "primary" active period
    - Attendance window: configurable minutes *after* period end during which
      late attendance is still accepted
    - Late threshold: configurable minutes *into* a period beyond which a
      student is marked "late" instead of "present"
* Emits a Firestore ``system_state/current_period`` document update on every
  period transition so the frontend can subscribe via Firestore snapshots.
* Logs every transition (period start / period end) at INFO level with
  structured fields suitable for log aggregation.

Public interface
----------------
    svc = PeriodDetectionService(firestore_db, timetable_service)
    await svc.start()      # begins background polling loop
    await svc.stop()       # graceful shutdown
    svc.get_active_period()   # sync snapshot from cache
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    DAY_OF_WEEK_MAP,
    LATE_THRESHOLD_MINUTES,
    NOTIFICATION_TRIGGER_MINUTES,
    TIME_FORMAT_HM,
)
from services.timetable_service import TimetableService

logger = logging.getLogger(__name__)

# ── Cache backend ──────────────────────────────────────────────────────────────

class _DictCache:
    """Simple in-process dict-based cache (no TTL needed here)."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _RedisCache:
    """Redis-backed cache using redis-py (optional dep)."""

    def __init__(self, redis_url: str) -> None:
        import redis, json as _json
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._json = _json

    def set(self, key: str, value: Any) -> None:
        import json as _json
        self._r.set(key, _json.dumps(value, default=str))

    def get(self, key: str, default: Any = None) -> Any:
        import json as _json
        raw = self._r.get(key)
        if raw is None:
            return default
        try:
            return _json.loads(raw)
        except Exception:
            return default

    def delete(self, key: str) -> None:
        self._r.delete(key)


def _make_cache():
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            cache = _RedisCache(redis_url)
            logger.info("PeriodDetectionService using Redis cache: %s", redis_url)
            return cache
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s), falling back to dict cache.", exc
            )
    return _DictCache()


# ── Cache keys ─────────────────────────────────────────────────────────────────
CACHE_KEY_ACTIVE_PERIOD    = "period:active"
CACHE_KEY_UPCOMING_PERIOD  = "period:upcoming"
CACHE_KEY_LAST_CHECK       = "period:last_check"
CACHE_KEY_ALL_PERIODS      = "period:all_active"


# ══════════════════════════════════════════════════════════════════════════════
# PeriodDetectionService
# ══════════════════════════════════════════════════════════════════════════════

class PeriodDetectionService:
    """
    Background service that detects the current active timetable period.

    Parameters
    ----------
    firestore_db :
        A Firestore client instance used for event emission.
    timetable_service :
        An initialised TimetableService for querying periods.
    poll_interval :
        How often (seconds) to re-check the timetable. Default: 60.
    """

    SYSTEM_STATE_COLLECTION = "system_state"
    CURRENT_PERIOD_DOC      = "current_period"

    def __init__(
        self,
        firestore_db: Any,
        timetable_service: TimetableService,
        poll_interval: int = 60,
    ) -> None:
        self._db              = firestore_db
        self._timetable       = timetable_service
        self._poll_interval   = poll_interval
        self._cache           = _make_cache()
        self._task: Optional[asyncio.Task] = None
        self._running         = False

        # Track last active period ID to detect transitions
        self._last_period_id: Optional[str] = None
        self._last_period_type: Optional[str] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            logger.warning("PeriodDetectionService already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="period_detection")
        logger.info(
            "PeriodDetectionService started (interval=%ds).", self._poll_interval
        )

    async def stop(self) -> None:
        """Gracefully stop the background polling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PeriodDetectionService stopped.")

    # ── Background loop ────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("PeriodDetectionService tick error: %s", exc, exc_info=True)
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise

    async def _tick(self) -> None:
        """One detection cycle: query Firestore, update cache, emit if changed."""
        now = datetime.now()
        self._cache.set(CACHE_KEY_LAST_CHECK, now.isoformat())

        # Fetch all active periods (done in a thread so we don't block the loop)
        loop = asyncio.get_event_loop()
        periods: List[Dict[str, Any]] = await loop.run_in_executor(
            None, self._timetable.get_all_active_periods
        )
        self._cache.set(CACHE_KEY_ALL_PERIODS, periods)

        active_periods = self._match_active_periods(now, periods)
        upcoming       = self._find_upcoming_period(now, periods)

        # Primary = holiday > earliest start among active
        primary = self._pick_primary(active_periods)

        # Annotate each active period with attendance status
        annotated = [self._annotate(p, now) for p in active_periods]

        payload = {
            "checked_at":       now.isoformat(),
            "current_day":      DAY_OF_WEEK_MAP.get(now.weekday(), "?"),
            "current_time":     now.strftime(TIME_FORMAT_HM),
            "is_period_active": bool(active_periods),
            "active_periods":   annotated,
            "primary_period":   self._annotate(primary, now) if primary else None,
            "upcoming_period":  upcoming,
        }

        self._cache.set(CACHE_KEY_ACTIVE_PERIOD,   payload)
        self._cache.set(CACHE_KEY_UPCOMING_PERIOD,  upcoming)

        # Detect transition and emit to Firestore
        new_period_id = primary.get("period_id") if primary else None
        if new_period_id != self._last_period_id:
            self._handle_transition(
                old_id=self._last_period_id,
                new_period=primary,
                now=now,
            )
            self._last_period_id   = new_period_id
            self._last_period_type = primary.get("period_type") if primary else None

            await loop.run_in_executor(None, self._emit_to_firestore, payload)

    # ── Matching logic ─────────────────────────────────────────────────────────

    def _match_active_periods(
        self,
        now: datetime,
        periods: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Return all periods whose time window contains ``now``.

        Rules
        -----
        * Holiday / break periods match the whole day (or the declared window).
        * Lab periods may span multiple hours — handled naturally since we
          compare actual start/end times.
        * Attendance window: a period is still "active" for
          ATTENDANCE_WINDOW_MINUTES after its end_time so late submissions
          are accepted.
        """
        today_dow = now.weekday()          # 0 = Monday
        now_time  = now.time()
        results: List[Dict[str, Any]] = []

        for p in periods:
            if not p.get("active_status", True):
                continue
            if p.get("day_of_week") != today_dow:
                continue

            p_type = p.get("period_type", "lecture")

            # Holiday / break = matches entire day
            if p_type in {"holiday", "break"}:
                results.append(p)
                continue

            try:
                start = datetime.strptime(p["start_time"], TIME_FORMAT_HM).time()
                end   = datetime.strptime(p["end_time"],   TIME_FORMAT_HM).time()
            except (KeyError, ValueError):
                continue

            # Extend end by attendance window for matching purposes
            end_extended = (
                datetime.combine(now.date(), end)
                + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
            ).time()

            if start <= now_time <= end_extended:
                results.append(p)

        # Sort by start_time so the first element is earliest
        def _sort_key(p: Dict[str, Any]) -> str:
            return p.get("start_time", "00:00")

        results.sort(key=_sort_key)
        return results

    def _pick_primary(
        self, active_periods: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Among active periods, choose the "primary":
        1. Holidays/breaks always win (they define the day).
        2. Else the earliest-starting period.
        """
        if not active_periods:
            return None
        for p in active_periods:
            if p.get("period_type") in {"holiday", "break"}:
                return p
        return active_periods[0]

    def _find_upcoming_period(
        self,
        now: datetime,
        periods: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Return the next period that will start within the next
        NOTIFICATION_TRIGGER_MINUTES minutes (for pre-class notifications).
        """
        today_dow = now.weekday()
        now_time  = now.time()
        candidates = []

        for p in periods:
            if p.get("day_of_week") != today_dow:
                continue
            if p.get("period_type") in {"holiday", "break"}:
                continue
            try:
                start = datetime.strptime(p["start_time"], TIME_FORMAT_HM).time()
            except (KeyError, ValueError):
                continue
            start_dt = datetime.combine(now.date(), start)
            diff_min = (start_dt - now).total_seconds() / 60
            if 0 < diff_min <= NOTIFICATION_TRIGGER_MINUTES:
                candidates.append((diff_min, p))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return {**candidates[0][1], "starts_in_minutes": round(candidates[0][0], 1)}

    def _annotate(
        self,
        period: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        """
        Add attendance-related annotations to a period dict:
        - ``attendance_open``   : bool  - within valid attendance window
        - ``is_late_threshold`` : bool  - past the late threshold
        - ``minutes_elapsed``   : int   - minutes since period started
        - ``minutes_remaining`` : int   - minutes until period ends (0 if past)
        - ``attendance_status_hint`` : "on_time" | "late" | "grace_period" | "closed"
        """
        p = dict(period)
        p_type = p.get("period_type", "lecture")

        if p_type in {"holiday", "break"}:
            p.update({
                "attendance_open":        False,
                "is_late_threshold":      False,
                "minutes_elapsed":        0,
                "minutes_remaining":      0,
                "attendance_status_hint": "holiday",
            })
            return p

        try:
            start = datetime.combine(now.date(), datetime.strptime(p["start_time"], TIME_FORMAT_HM).time())
            end   = datetime.combine(now.date(), datetime.strptime(p["end_time"],   TIME_FORMAT_HM).time())
        except (KeyError, ValueError):
            return p

        elapsed   = int((now - start).total_seconds() / 60)
        remaining = max(0, int((end - now).total_seconds() / 60))
        in_window = now <= end + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
        is_late   = elapsed > LATE_THRESHOLD_MINUTES

        if now < start:
            hint = "not_started"
        elif now <= end and not is_late:
            hint = "on_time"
        elif now <= end and is_late:
            hint = "late"
        elif now <= end + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES):
            hint = "grace_period"
        else:
            hint = "closed"

        p.update({
            "attendance_open":        in_window,
            "is_late_threshold":      is_late,
            "minutes_elapsed":        max(0, elapsed),
            "minutes_remaining":      remaining,
            "attendance_status_hint": hint,
        })
        return p

    # ── Transition handling ────────────────────────────────────────────────────

    def _handle_transition(
        self,
        old_id: Optional[str],
        new_period: Optional[Dict[str, Any]],
        now: datetime,
    ) -> None:
        new_id   = new_period.get("period_id") if new_period else None
        new_type = new_period.get("period_type") if new_period else None
        new_name = (
            f"{new_period.get('course_id','?')} "
            f"({new_period.get('period_type','?')} "
            f"{new_period.get('start_time','')}–{new_period.get('end_time','')})"
        ) if new_period else "none"

        if old_id and not new_id:
            logger.info(
                "PERIOD ENDED   | %s → [no active period] | %s",
                old_id, now.isoformat(),
            )
        elif not old_id and new_id:
            logger.info(
                "PERIOD STARTED | → %s (%s) | %s",
                new_id, new_name, now.isoformat(),
            )
        else:
            logger.info(
                "PERIOD CHANGE  | %s → %s (%s) | %s",
                old_id, new_id, new_name, now.isoformat(),
            )

        # Special log lines for specific period types
        if new_type == "holiday":
            logger.info("Today is marked as a HOLIDAY/OFF day: %s", new_name)
        elif new_type == "lab":
            logger.info(
                "LAB session started (may span multiple hours): %s", new_name
            )

    # ── Firestore event emission ───────────────────────────────────────────────

    def _emit_to_firestore(self, payload: Dict[str, Any]) -> None:
        """
        Write the current period state to ``system_state/current_period``
        in Firestore so the frontend can receive real-time updates via
        Firestore snapshot listeners.

        This method is called in a thread-pool executor (not on the event loop).
        """
        try:
            doc_ref = (
                self._db
                .collection(self.SYSTEM_STATE_COLLECTION)
                .document(self.CURRENT_PERIOD_DOC)
            )
            doc_ref.set(payload, merge=False)
            logger.debug(
                "Emitted period state to Firestore system_state/current_period"
            )
        except Exception as exc:
            logger.error("Failed to emit period state to Firestore: %s", exc)

    # ── Public read interface ──────────────────────────────────────────────────

    def get_active_period(self) -> Optional[Dict[str, Any]]:
        """
        Synchronous snapshot of the current period state from cache.
        Returns None if no tick has completed yet.
        """
        return self._cache.get(CACHE_KEY_ACTIVE_PERIOD)

    def get_upcoming_period(self) -> Optional[Dict[str, Any]]:
        """Return the next upcoming period within the notification window."""
        return self._cache.get(CACHE_KEY_UPCOMING_PERIOD)

    def get_last_check_time(self) -> Optional[str]:
        """ISO-8601 string of the last successful tick."""
        return self._cache.get(CACHE_KEY_LAST_CHECK)

    def force_refresh(self) -> None:
        """
        Invalidate the cached period list so the next tick fetches fresh data.
        Useful after bulk timetable uploads.
        """
        self._cache.delete(CACHE_KEY_ALL_PERIODS)
        logger.info("PeriodDetectionService cache invalidated (force_refresh).")

    def is_attendance_open(self, period_id: str) -> bool:
        """
        Quick check: is the given period currently accepting attendance?
        Uses only the in-memory cache — no Firestore I/O.
        """
        payload = self.get_active_period()
        if not payload:
            return False
        for p in payload.get("active_periods", []):
            if p.get("period_id") == period_id:
                return bool(p.get("attendance_open", False))
        return False


# ── Module-level singleton ─────────────────────────────────────────────────────

_period_detection_service: Optional[PeriodDetectionService] = None


def get_period_detection_service() -> Optional[PeriodDetectionService]:
    return _period_detection_service


def init_period_detection_service(
    firestore_db: Any,
    timetable_service: TimetableService,
    poll_interval: int = 60,
) -> PeriodDetectionService:
    global _period_detection_service
    _period_detection_service = PeriodDetectionService(
        firestore_db=firestore_db,
        timetable_service=timetable_service,
        poll_interval=poll_interval,
    )
    logger.info("PeriodDetectionService initialised (poll=%ds).", poll_interval)
    return _period_detection_service
