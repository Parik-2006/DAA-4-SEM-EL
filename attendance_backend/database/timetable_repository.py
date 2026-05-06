"""
database/timetable_repository.py
──────────────────────────────────────────────────────────────────────────────
Repository layer for period / timetable queries.

Key responsibility: given the current time, tell the caller which periods
are active right now (or coming up soon) for a specific teacher or class.

All public methods return plain dicts — no Firestore types leak out.

Design notes
────────────
• Firestore cannot do a server-side range query on two different string fields
  (start_time <= now <= end_time) in a single compound query because of how
  composite indexes work with inequalities. We therefore query on day_of_week
  + class_id first (cheap), then filter on time client-side.
• Results are cached in-process for CACHE_TTL_SECONDS to reduce reads.
  The cache is a simple dict — no external dependency.
• All time comparisons are done in the Python process using today's date so
  there is no timezone ambiguity (the server's local TZ is used throughout;
  keep it consistent with the timetable data entry).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    DB_FIELD_ACTIVE_STATUS,
    DB_FIELD_CLASS_ID,
    DB_FIELD_DAY_OF_WEEK,
    DB_FIELD_START_TIME,
    DB_FIELD_END_TIME,
    FIREBASE_COLLECTIONS,
    TIME_FORMAT_HM,
)

logger = logging.getLogger(__name__)

PERIODS_COLLECTION = FIREBASE_COLLECTIONS.get("periods", "periods")

# Local in-process cache — avoids hammering Firestore on every HTTP request.
CACHE_TTL_SECONDS = 60          # 1-minute TTL is plenty for a timetable
_cache: Dict[str, Tuple[float, Any]] = {}

# Types that skip attendance (breaks, holidays, exams)
_NO_ATTEND = {"break", "holiday", "exam"}


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.monotonic(), value)


def _hhmm_to_minutes(t: str) -> int:
    """Convert 'HH:MM' → total minutes since midnight."""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _now_hhmm(now: Optional[datetime] = None) -> Tuple[int, int, str]:
    """Return (day_of_week 0-6, minutes_since_midnight, 'HH:MM')."""
    dt = now or datetime.now()
    return (
        dt.weekday(),
        dt.hour * 60 + dt.minute,
        dt.strftime(TIME_FORMAT_HM),
    )


def _is_period_active(
    period: Dict[str, Any],
    current_minutes: int,
    include_grace: bool = True,
) -> bool:
    """
    True if current_minutes falls within the period's attendance window.

    Window = [start_time … end_time + ATTENDANCE_WINDOW_MINUTES]
    Breaks and holidays never return True.
    """
    if period.get("period_type") in _NO_ATTEND:
        return False
    try:
        start = _hhmm_to_minutes(period["start_time"])
        end   = _hhmm_to_minutes(period["end_time"])
    except (KeyError, ValueError):
        return False
    close = end + (ATTENDANCE_WINDOW_MINUTES if include_grace else 0)
    return start <= current_minutes <= close


def _is_period_upcoming(
    period: Dict[str, Any],
    current_minutes: int,
    lookahead_minutes: int = 15,
) -> bool:
    """True if the period starts within the next ``lookahead_minutes``."""
    if period.get("period_type") in _NO_ATTEND:
        return False
    try:
        start = _hhmm_to_minutes(period["start_time"])
    except (KeyError, ValueError):
        return False
    return 0 < (start - current_minutes) <= lookahead_minutes


# ══════════════════════════════════════════════════════════════════════════════
# TimetableRepository
# ══════════════════════════════════════════════════════════════════════════════

class TimetableRepository:
    """
    Read-only queries against the ``periods`` Firestore collection.

    The heavy-lifting TimetableService (services/timetable_service.py) handles
    writes; this repository is optimised purely for fast reads used at
    attendance-marking time.
    """

    def __init__(self, firestore_db: Any) -> None:
        self._db = firestore_db

    # ── Primary query: what's active right now ─────────────────────────────────

    def get_active_periods_for_class(
        self,
        class_id: str,
        now: Optional[datetime] = None,
        include_grace: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return periods that are open for attendance marking right now.

        For CSE 4C at 09:45 on a Monday this returns:
            [{"period_id": "CSE4C_MON_0900", "course_short": "IOT", ...}]

        Args
        ────
        class_id       : e.g. "CSE_4C_SEM4"
        now            : Override current time (useful in tests).
        include_grace  : If True, periods in the grace window also qualify.
        """
        day_of_week, current_min, _ = _now_hhmm(now)

        cache_key = f"active:{class_id}:{day_of_week}:{current_min // 5}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        periods = self._fetch_day_periods(class_id, day_of_week)
        active  = [
            p for p in periods
            if _is_period_active(p, current_min, include_grace)
        ]

        _cache_set(cache_key, active)
        return active

    def get_active_periods_for_teacher(
        self,
        teacher_id: str,
        assigned_class_ids: List[str],
        now: Optional[datetime] = None,
        include_grace: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return active periods across all classes assigned to this teacher,
        further filtered to periods where this teacher is the faculty.

        Result is guaranteed to be only periods the teacher is authorised
        to mark — no extra permission check needed at the API layer.
        """
        now = now or datetime.now()
        day_of_week, current_min, _ = _now_hhmm(now)

        results = []
        for class_id in assigned_class_ids:
            periods = self._fetch_day_periods(class_id, day_of_week)
            for p in periods:
                if p.get("faculty_id") != teacher_id:
                    continue
                if _is_period_active(p, current_min, include_grace):
                    results.append(p)
        return results

    # ── Teacher dashboard: all today's periods ─────────────────────────────────

    def get_today_schedule_for_teacher(
        self,
        teacher_id: str,
        assigned_class_ids: List[str],
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Full day schedule for a teacher — active and upcoming periods,
        annotated with a ``window_phase`` field.

        Returns list sorted by start_time ascending.
        """
        now = now or datetime.now()
        day_of_week, current_min, _ = _now_hhmm(now)

        schedule: List[Dict[str, Any]] = []
        for class_id in assigned_class_ids:
            periods = self._fetch_day_periods(class_id, day_of_week)
            for p in periods:
                if p.get("faculty_id") != teacher_id:
                    continue
                if p.get("period_type") in _NO_ATTEND:
                    continue

                # Annotate phase
                try:
                    start = _hhmm_to_minutes(p["start_time"])
                    end   = _hhmm_to_minutes(p["end_time"])
                except (KeyError, ValueError):
                    continue

                close = end + ATTENDANCE_WINDOW_MINUTES
                if current_min < start:
                    phase = "upcoming"
                elif start <= current_min <= end:
                    phase = "active"
                elif end < current_min <= close:
                    phase = "grace"
                else:
                    phase = "finished"

                schedule.append({**p, "window_phase": phase})

        schedule.sort(key=lambda x: x.get("start_time", "00:00"))
        return schedule

    # ── Find a specific period and validate it ─────────────────────────────────

    def get_period(self, period_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single period document by ID."""
        cache_key = f"period:{period_id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        doc = (
            self._db
            .collection(PERIODS_COLLECTION)
            .document(period_id)
            .get()
        )
        result = doc.to_dict() if doc.exists else None
        if result:
            _cache_set(cache_key, result)
        return result

    def get_period_if_active(
        self,
        period_id: str,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Fetch ``period_id`` and check if it's currently open.

        Returns (period_dict, message).
        period_dict is None if the period doesn't exist or is not active.
        """
        period = self.get_period(period_id)
        if period is None:
            return None, f"Period '{period_id}' not found."

        _, current_min, _ = _now_hhmm(now)
        if _is_period_active(period, current_min):
            return period, "Period is active."
        return None, (
            f"Period '{period_id}' is not open for attendance right now. "
            f"Window: {period.get('start_time')}–"
            f"{period.get('end_time')} + {ATTENDANCE_WINDOW_MINUTES} min grace."
        )

    def validate_teacher_owns_period(
        self,
        period_id: str,
        teacher_id: str,
        assigned_class_ids: List[str],
    ) -> Tuple[bool, str]:
        """
        Confirm that ``teacher_id`` is the assigned faculty for ``period_id``
        AND that the period's class_id is in ``assigned_class_ids``.

        Returns (allowed: bool, reason: str).
        """
        period = self.get_period(period_id)
        if period is None:
            return False, f"Period '{period_id}' not found."

        class_id   = period.get("class_id", "")
        faculty_id = period.get("faculty_id", "")

        if class_id not in assigned_class_ids:
            return (
                False,
                f"Period '{period_id}' belongs to class '{class_id}' "
                f"which is not in your assigned sections.",
            )
        if faculty_id != teacher_id:
            return (
                False,
                f"Period '{period_id}' is assigned to faculty '{faculty_id}', "
                f"not to you ('{teacher_id}').",
            )
        return True, "Access granted."

    # ── Upcoming periods (for reminders / UI countdown) ────────────────────────

    def get_upcoming_periods_for_class(
        self,
        class_id: str,
        now: Optional[datetime] = None,
        lookahead_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Return periods starting within ``lookahead_minutes`` (default 15)."""
        day_of_week, current_min, _ = _now_hhmm(now)
        periods  = self._fetch_day_periods(class_id, day_of_week)
        upcoming = [
            p for p in periods
            if _is_period_upcoming(p, current_min, lookahead_minutes)
        ]
        upcoming.sort(key=lambda x: x.get("start_time", "00:00"))
        return upcoming

    # ── Week-wide fetch (for timetable display) ────────────────────────────────

    def get_full_week(
        self,
        class_id: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return the complete weekly timetable as a dict keyed by day name.

        {
          "Monday":    [...periods...],
          "Tuesday":   [...periods...],
          ...
          "Saturday":  [...periods...],
        }
        """
        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        result: Dict[str, List[Dict[str, Any]]] = {}
        for day_int, day_name in enumerate(day_names[:6]):   # Mon–Sat only
            periods = self._fetch_day_periods(class_id, day_int)
            periods.sort(key=lambda x: x.get("start_time", "00:00"))
            result[day_name] = periods
        return result

    # ── Internal Firestore fetch ───────────────────────────────────────────────

    def _fetch_day_periods(
        self,
        class_id: str,
        day_of_week: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all active periods for ``class_id`` on ``day_of_week``.
        Results are cached per (class_id, day_of_week) for CACHE_TTL_SECONDS.
        """
        cache_key = f"day:{class_id}:{day_of_week}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return list(cached)   # return a copy so caller can mutate freely

        try:
            from google.cloud.firestore_v1 import FieldFilter
            docs = (
                self._db
                .collection(PERIODS_COLLECTION)
                .where(filter=FieldFilter(DB_FIELD_CLASS_ID,    "==", class_id))
                .where(filter=FieldFilter(DB_FIELD_DAY_OF_WEEK, "==", day_of_week))
                .where(filter=FieldFilter(DB_FIELD_ACTIVE_STATUS, "==", True))
                .order_by(DB_FIELD_START_TIME)
                .stream()
            )
            periods = [d.to_dict() for d in docs]
        except Exception as exc:
            logger.error(
                "Firestore fetch failed class=%s day=%d: %s",
                class_id, day_of_week, exc,
            )
            periods = []

        _cache_set(cache_key, periods)
        logger.debug(
            "Fetched %d periods for class=%s day=%d (cached)",
            len(periods), class_id, day_of_week,
        )
        return list(periods)

    def invalidate_cache(self, class_id: Optional[str] = None) -> None:
        """
        Clear cached periods. Call after any timetable write.

        If ``class_id`` is given only that class's entries are cleared;
        otherwise the whole cache is flushed.
        """
        if class_id:
            keys_to_del = [k for k in _cache if class_id in k]
            for k in keys_to_del:
                _cache.pop(k, None)
            logger.debug("Cache cleared for class_id=%s", class_id)
        else:
            _cache.clear()
            logger.debug("Full period cache cleared.")


# ── Module-level singleton ────────────────────────────────────────────────────

_repo_instance: Optional[TimetableRepository] = None


def get_timetable_repository() -> Optional[TimetableRepository]:
    return _repo_instance


def init_timetable_repository(firestore_db: Any) -> TimetableRepository:
    global _repo_instance
    _repo_instance = TimetableRepository(firestore_db)
    logger.info("TimetableRepository initialised.")
    return _repo_instance
