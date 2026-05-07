"""
utils/time_validator.py
──────────────────────────────────────────────────────────────────────────────
Standalone helpers that answer the single most important question in the
timetable-driven attendance system:

    "Is a teacher allowed to mark attendance right now?"

All logic is pure Python with no Firestore calls — this makes it fast enough
to run on every incoming HTTP request and trivially unit-testable.

Usage
-----
from utils.time_validator import TimeValidator, MarkingWindow

validator = TimeValidator()
window    = validator.get_window(period)
if not window.is_open:
    raise HTTP 423 with window.message

Functions
---------
TimeValidator.get_window(period, now?)  → MarkingWindow
TimeValidator.compute_status(period, now?) → "present" | "late"
TimeValidator.seconds_until_open(period, now?) → int
TimeValidator.is_teacher_allowed(period, teacher_id, assigned_sections) → bool
validate_period_active(period, now?) → (bool, str)   # simple boolean version
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
)

logger = logging.getLogger(__name__)

# ── Re-export config values so callers import from one place ──────────────────
WINDOW_MINUTES = ATTENDANCE_WINDOW_MINUTES   # grace period after class ends
LATE_MINUTES   = LATE_THRESHOLD_MINUTES      # minutes into class → auto-late

# Period types that never allow attendance
_NO_ATTENDANCE_TYPES = {"break", "holiday", "exam"}


# ══════════════════════════════════════════════════════════════════════════════
# MarkingWindow — the primary return type
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarkingWindow:
    """
    Complete description of whether (and how) attendance marking is allowed
    for a specific period at a specific moment in time.

    Attributes
    ----------
    is_open         : True when new attendance records may be created.
    can_edit        : True when existing records may be modified.
    phase           : "before" | "open" | "grace" | "locked"
    auto_status     : "present" if on-time, "late" if arriving after the
                      LATE_THRESHOLD_MINUTES mark or in grace period.
    time_remaining  : Minutes until the current phase ends (0 when locked).
    opens_at        : HH:MM — when the window opens (= class start time).
    closes_at       : HH:MM — when the window closes (= end + WINDOW_MINUTES).
    message         : Human-readable status for teacher-facing UI.
    checked_at      : Timestamp this window was computed.
    period_id       : Carried from the period dict for convenience.
    """
    is_open:        bool
    can_edit:       bool
    phase:          str                   # "before" | "open" | "grace" | "locked"
    auto_status:    str                   # "present" | "late"
    time_remaining: float                 # minutes
    opens_at:       str                   # HH:MM
    closes_at:      str                   # HH:MM
    message:        str
    checked_at:     datetime = field(default_factory=datetime.now)
    period_id:      str      = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_open":        self.is_open,
            "can_edit":       self.can_edit,
            "phase":          self.phase,
            "auto_status":    self.auto_status,
            "time_remaining": round(max(0.0, self.time_remaining), 1),
            "opens_at":       self.opens_at,
            "closes_at":      self.closes_at,
            "message":        self.message,
            "checked_at":     self.checked_at.isoformat(),
            "period_id":      self.period_id,
        }


# ══════════════════════════════════════════════════════════════════════════════
# TimeValidator
# ══════════════════════════════════════════════════════════════════════════════

class TimeValidator:
    """
    Stateless helper: all methods accept a ``now`` parameter so you can
    test any scenario without mocking the system clock.
    """

    # ── Core window computation ────────────────────────────────────────────────

    def get_window(
        self,
        period: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> MarkingWindow:
        """
        Compute the full MarkingWindow for ``period`` at time ``now``.

        Period must contain: start_time (HH:MM), end_time (HH:MM),
        period_type (str), and optionally period_id (str).
        """
        now       = now or datetime.now()
        period_id = period.get("period_id", "")
        p_type    = str(period.get("period_type", "lecture")).lower()

        # Non-attendance period types
        if p_type in _NO_ATTENDANCE_TYPES:
            return MarkingWindow(
                is_open=False, can_edit=False, phase="locked",
                auto_status="present", time_remaining=0.0,
                opens_at=period.get("start_time", ""),
                closes_at=period.get("end_time", ""),
                message=f"No attendance for period type '{p_type}'.",
                checked_at=now, period_id=period_id,
            )

        try:
            start_dt, end_dt = self._parse_period_times(period, now)
        except ValueError as exc:
            return MarkingWindow(
                is_open=False, can_edit=False, phase="locked",
                auto_status="present", time_remaining=0.0,
                opens_at=period.get("start_time", ""),
                closes_at=period.get("end_time", ""),
                message=f"Invalid period times: {exc}",
                checked_at=now, period_id=period_id,
            )

        close_dt = end_dt + timedelta(minutes=WINDOW_MINUTES)
        closes_at = close_dt.strftime(TIME_FORMAT_HM)

        # ── Phase determination ────────────────────────────────────────────────
        if now < start_dt:
            mins_to_open = (start_dt - now).total_seconds() / 60
            return MarkingWindow(
                is_open=False, can_edit=False, phase="before",
                auto_status="present",
                time_remaining=mins_to_open,
                opens_at=period["start_time"],
                closes_at=closes_at,
                message=(
                    f"Attendance opens at {period['start_time']}. "
                    f"Opens in {mins_to_open:.0f} min."
                ),
                checked_at=now, period_id=period_id,
            )

        if start_dt <= now <= end_dt:
            elapsed_min = (now - start_dt).total_seconds() / 60
            mins_left   = (end_dt - now).total_seconds() / 60
            is_late     = elapsed_min > LATE_MINUTES
            auto_status = "late" if is_late else "present"
            if is_late:
                msg = (
                    f"Window open — students joining now marked LATE. "
                    f"{mins_left:.0f} min left in class."
                )
            else:
                msg = (
                    f"Window open. {mins_left:.0f} min left. "
                    f"Late threshold in "
                    f"{max(0, LATE_MINUTES - elapsed_min):.0f} min."
                )
            return MarkingWindow(
                is_open=True, can_edit=True, phase="open",
                auto_status=auto_status,
                time_remaining=mins_left,
                opens_at=period["start_time"],
                closes_at=closes_at,
                message=msg,
                checked_at=now, period_id=period_id,
            )

        if end_dt < now <= close_dt:
            mins_left = (close_dt - now).total_seconds() / 60
            return MarkingWindow(
                is_open=True, can_edit=True, phase="grace",
                auto_status="late",
                time_remaining=mins_left,
                opens_at=period["start_time"],
                closes_at=closes_at,
                message=(
                    f"Grace period — class ended. "
                    f"All new marks recorded as LATE. "
                    f"Window closes in {mins_left:.0f} min."
                ),
                checked_at=now, period_id=period_id,
            )

        # Past close → locked
        return MarkingWindow(
            is_open=False, can_edit=False, phase="locked",
            auto_status="present", time_remaining=0.0,
            opens_at=period["start_time"],
            closes_at=closes_at,
            message=(
                f"Attendance window closed. "
                f"Period ended at {period['end_time']}, "
                f"grace window was until {closes_at}."
            ),
            checked_at=now, period_id=period_id,
        )

    # ── Convenience helpers ────────────────────────────────────────────────────

    def compute_status(
        self,
        period: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> str:
        """Return "present" or "late" for the current moment in this period."""
        return self.get_window(period, now).auto_status

    def seconds_until_open(
        self,
        period: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> int:
        """
        Seconds until this period's attendance window opens.
        Returns 0 if already open; negative if window has closed.
        """
        now = now or datetime.now()
        try:
            start_dt, _ = self._parse_period_times(period, now)
        except ValueError:
            return -1
        return max(0, int((start_dt - now).total_seconds()))

    def is_teacher_allowed(
        self,
        period: Dict[str, Any],
        teacher_id: str,
        assigned_sections: list[str],
        now: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Combined check: window open AND teacher owns this section.

        Returns (allowed: bool, reason: str).
        """
        # 1. Section ownership
        period_class = period.get("class_id", "")
        if period_class not in assigned_sections:
            return (
                False,
                f"Teacher {teacher_id} is not assigned to class {period_class}.",
            )

        # 2. Time window
        window = self.get_window(period, now)
        if not window.is_open:
            return False, window.message

        return True, window.message

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_period_times(
        period: Dict[str, Any],
        now: datetime,
    ) -> Tuple[datetime, datetime]:
        """
        Parse start_time and end_time from period dict.

        Returns (start_dt, end_dt) anchored to today's date.
        Raises ValueError if the strings can't be parsed.
        """
        date_prefix = now.strftime("%Y-%m-%d ")
        try:
            start_dt = datetime.strptime(
                date_prefix + period["start_time"], "%Y-%m-%d %H:%M"
            )
            end_dt = datetime.strptime(
                date_prefix + period["end_time"], "%Y-%m-%d %H:%M"
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"Cannot parse start_time='{period.get('start_time')}' "
                f"or end_time='{period.get('end_time')}': {exc}"
            )
        if end_dt <= start_dt:
            raise ValueError(
                f"end_time '{period['end_time']}' must be after "
                f"start_time '{period['start_time']}'."
            )
        return start_dt, end_dt


# ── Module-level convenience function ─────────────────────────────────────────

_validator = TimeValidator()


def validate_period_active(
    period: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Lightweight boolean check for use in middleware.

    Returns (is_open: bool, message: str).
    """
    window = _validator.get_window(period, now)
    return window.is_open, window.message


def get_marking_window(
    period: Dict[str, Any],
    now: Optional[datetime] = None,
) -> MarkingWindow:
    """Module-level shortcut — same as TimeValidator().get_window()."""
    return _validator.get_window(period, now)


def infer_attendance_status(
    period: Dict[str, Any],
    now: Optional[datetime] = None,
) -> str:
    """Return 'present' or 'late' without building the full window object."""
    return _validator.compute_status(period, now)
