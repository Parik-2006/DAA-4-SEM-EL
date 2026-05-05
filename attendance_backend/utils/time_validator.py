"""
utils/time_validator.py

Reusable period-time validation helpers for timetable-driven attendance.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from config.constants import ATTENDANCE_WINDOW_MINUTES


def _dt_for_today(hhmm: str, date_str: Optional[str] = None) -> datetime:
    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M")


def get_period_runtime_status(
    start_time: str,
    end_time: str,
    now: Optional[datetime] = None,
) -> str:
    """
    Return coarse status used by Prompt 2:
    - not_started
    - in_progress
    - finished
    """
    current = now or datetime.now()
    start_dt = _dt_for_today(start_time, current.strftime("%Y-%m-%d"))
    end_dt = _dt_for_today(end_time, current.strftime("%Y-%m-%d"))

    if current < start_dt:
        return "not_started"
    if start_dt <= current <= end_dt:
        return "in_progress"
    return "finished"


def is_marking_allowed(
    start_time: str,
    end_time: str,
    now: Optional[datetime] = None,
    grace_minutes: int = ATTENDANCE_WINDOW_MINUTES,
) -> bool:
    """True when now is within [start_time, end_time + grace_minutes]."""
    current = now or datetime.now()
    start_dt = _dt_for_today(start_time, current.strftime("%Y-%m-%d"))
    end_dt = _dt_for_today(end_time, current.strftime("%Y-%m-%d")) + timedelta(minutes=grace_minutes)
    return start_dt <= current <= end_dt


def get_marking_window_info(
    start_time: str,
    end_time: str,
    now: Optional[datetime] = None,
    grace_minutes: int = ATTENDANCE_WINDOW_MINUTES,
) -> Dict[str, object]:
    """Return Prompt-2-style status info for period marking window."""
    current = now or datetime.now()
    start_dt = _dt_for_today(start_time, current.strftime("%Y-%m-%d"))
    end_dt = _dt_for_today(end_time, current.strftime("%Y-%m-%d"))
    close_dt = end_dt + timedelta(minutes=grace_minutes)

    if current < start_dt:
        return {
            "status": "not_started",
            "is_open": False,
            "minutes_to_start": int((start_dt - current).total_seconds() / 60),
        }

    if start_dt <= current <= end_dt:
        return {
            "status": "in_progress",
            "is_open": True,
            "minutes_to_close": int((close_dt - current).total_seconds() / 60),
        }

    if end_dt < current <= close_dt:
        return {
            "status": "in_progress",
            "is_open": True,
            "phase": "grace",
            "minutes_to_close": int((close_dt - current).total_seconds() / 60),
        }

    return {
        "status": "finished",
        "is_open": False,
        "minutes_to_close": 0,
    }
