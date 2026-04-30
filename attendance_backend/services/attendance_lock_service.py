"""
services/attendance_lock_service.py
─────────────────────────────────────────────────────────────────────────────
Centralised period-locking logic consumed by both api/teacher.py and
api/attendance.py.

Lock lifecycle
--------------
  OPEN        → Within (period_start … period_end + ATTENDANCE_WINDOW_MINUTES)
  GRACE       → Past period_end, still within attendance window
  LOCKED      → Past the window OR manually locked by a teacher
  FORCE_OPEN  → Admin has manually unlocked a locked period

State stored in Firestore
--------------------------
Collection : ``attendance_locks``
Document ID: ``{YYYY-MM-DD}_{period_id}``

Lock document shape
--------------------
{
    "date":         "YYYY-MM-DD",
    "period_id":    str,
    "class_id":     str,
    "locked":       bool,
    "lock_reason":  str | None,   # "auto" | "manual" | "admin_override"
    "locked_at":    str | None,   # ISO-8601
    "locked_by":    str | None,   # actor_id
    "force_open":   bool,         # admin override
    "created_at":   str,
    "updated_at":   str,
}

Attendance audit sub-collection
---------------------------------
Path: ``attendance_audits/{record_id}/changes``

Change document shape
----------------------
{
    "action":       str,          # "CREATE" | "UPDATE" | "LOCK_OVERRIDE"
    "actor_id":     str,
    "changed_at":   str (ISO-8601),
    "before":       dict | None,
    "after":        dict,
    "reason":       str | None,
}
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    LATE_THRESHOLD_MINUTES,
    TIME_FORMAT_HM,
)

logger = logging.getLogger(__name__)

# ── Lock collection names ──────────────────────────────────────────────────────
LOCK_COLLECTION     = "attendance_locks"
AUDIT_COLLECTION    = "attendance_audits"
CHANGE_SUBCOLLECTION = "changes"

# Lock delay constants (env-overridable via constants already; use the same value)
LOCK_DELAY_MINUTES  = ATTENDANCE_WINDOW_MINUTES   # lock fires at end of grace window


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _lock_doc_id(date: str, period_id: str) -> str:
    """Stable Firestore document ID for a period's lock record."""
    return f"{date}_{period_id}"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _parse_hhmm(t: str) -> datetime:
    """Parse 'HH:MM' into a today-anchored datetime."""
    return datetime.strptime(datetime.now().strftime("%Y-%m-%d ") + t, "%Y-%m-%d %H:%M")


def _minutes_until(target: datetime) -> float:
    return (target - datetime.now()).total_seconds() / 60.0


# ══════════════════════════════════════════════════════════════════════════════
# AttendanceLockService
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceLockService:
    """
    Manages attendance window status and period locks.

    Inject the same Firestore client used by TimetableService.
    """

    def __init__(self, firestore_db: Any) -> None:
        self._db = firestore_db

    # ── Internal references ────────────────────────────────────────────────────

    def _lock_ref(self, date: str, period_id: str):
        return self._db.collection(LOCK_COLLECTION).document(
            _lock_doc_id(date, period_id)
        )

    def _audit_ref(self, record_id: str):
        return (
            self._db
            .collection(AUDIT_COLLECTION)
            .document(record_id)
            .collection(CHANGE_SUBCOLLECTION)
        )

    # ── Window / lock status ───────────────────────────────────────────────────

    def get_window_status(
        self,
        period: Dict[str, Any],
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate the real-time attendance window status for a period.

        Parameters
        ----------
        period :
            Period document dict (must contain ``start_time``, ``end_time``,
            ``period_id``, and optionally ``class_id``).
        date :
            Date string YYYY-MM-DD.  Defaults to today.

        Returns
        -------
        dict with keys:
            is_open          : bool   – True if marking is allowed right now
            can_edit         : bool   – True if editing existing records is allowed
            phase            : str    – "before" | "open" | "grace" | "locked"
            time_remaining   : float  – minutes until phase changes (negative = past)
            window_opens_at  : str    – HH:MM
            window_closes_at : str    – HH:MM  (end + window minutes)
            lock_at          : str    – HH:MM
            is_manually_locked : bool
            is_force_open    : bool
            message          : str    – human-readable status for teacher UI
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        period_id = period.get("period_id", "")
        p_type    = period.get("period_type", "lecture")

        # Holidays / breaks are never open for attendance
        if p_type in {"holiday", "break"}:
            return self._closed_status(
                period, date, reason="Holiday / break — no attendance"
            )

        try:
            start_dt   = _parse_hhmm(period["start_time"])
            end_dt     = _parse_hhmm(period["end_time"])
        except (KeyError, ValueError) as exc:
            return self._closed_status(period, date, reason=f"Invalid period times: {exc}")

        window_close_dt = end_dt + timedelta(minutes=ATTENDANCE_WINDOW_MINUTES)
        now = datetime.now()

        # Check manual lock state in Firestore
        lock_doc    = self._lock_ref(date, period_id).get()
        lock_data   = lock_doc.to_dict() if lock_doc.exists else {}
        manually_locked = lock_data.get("locked", False)
        force_open      = lock_data.get("force_open", False)

        # Compute phase
        if now < start_dt:
            phase = "before"
            is_open   = False
            can_edit  = False
            time_rem  = _minutes_until(start_dt)
            message   = (
                f"Attendance opens at {period['start_time']}. "
                f"Starts in {time_rem:.0f} min."
            )

        elif start_dt <= now <= end_dt:
            elapsed = (now - start_dt).total_seconds() / 60
            is_late  = elapsed > LATE_THRESHOLD_MINUTES
            phase    = "open"
            is_open  = True
            can_edit = True
            time_rem = _minutes_until(end_dt)
            if is_late:
                message = (
                    f"Attendance open — students joining now will be marked LATE. "
                    f"{time_rem:.0f} min remaining."
                )
            else:
                message = (
                    f"Attendance window open. {time_rem:.0f} min remaining."
                )

        elif end_dt < now <= window_close_dt:
            phase    = "grace"
            is_open  = True
            can_edit = True
            time_rem = _minutes_until(window_close_dt)
            message  = (
                f"Grace period — class ended, attendance closes in {time_rem:.0f} min. "
                "New records marked LATE."
            )

        else:
            phase    = "locked"
            is_open  = False
            can_edit = False
            time_rem = 0.0
            message  = "Attendance window closed. Period is locked."

        # Apply overrides
        if manually_locked and not force_open:
            is_open  = False
            can_edit = False
            phase    = "locked"
            message  = (
                f"Attendance manually locked by "
                f"{lock_data.get('locked_by', 'admin')}. "
                f"Reason: {lock_data.get('lock_reason', 'not specified')}."
            )

        if force_open:
            is_open  = True
            can_edit = True
            phase    = "open"  # override
            message  = "⚠ Attendance force-opened by admin override."

        return {
            "is_open":           is_open,
            "can_edit":          can_edit,
            "phase":             phase,
            "time_remaining":    round(max(0.0, time_rem), 1),
            "window_opens_at":   period.get("start_time", ""),
            "window_closes_at":  window_close_dt.strftime(TIME_FORMAT_HM),
            "lock_at":           window_close_dt.strftime(TIME_FORMAT_HM),
            "is_manually_locked": manually_locked,
            "is_force_open":     force_open,
            "message":           message,
            "date":              date,
            "period_id":         period_id,
        }

    def _closed_status(
        self,
        period: Dict[str, Any],
        date: str,
        reason: str = "Closed",
    ) -> Dict[str, Any]:
        return {
            "is_open":           False,
            "can_edit":          False,
            "phase":             "locked",
            "time_remaining":    0.0,
            "window_opens_at":   period.get("start_time", ""),
            "window_closes_at":  period.get("end_time", ""),
            "lock_at":           period.get("end_time", ""),
            "is_manually_locked": False,
            "is_force_open":     False,
            "message":           reason,
            "date":              date,
            "period_id":         period.get("period_id", ""),
        }

    # ── Period locking ─────────────────────────────────────────────────────────

    def lock_period(
        self,
        period_id: str,
        class_id: str,
        date: Optional[str] = None,
        actor_id: str = "system",
        reason: str = "auto",
    ) -> Dict[str, Any]:
        """
        Lock a period so no new attendance records can be created or edited.

        Returns the lock document dict.
        """
        date    = date or datetime.now().strftime("%Y-%m-%d")
        now_iso = _now_iso()
        doc     = {
            "date":        date,
            "period_id":   period_id,
            "class_id":    class_id,
            "locked":      True,
            "lock_reason": reason,
            "locked_at":   now_iso,
            "locked_by":   actor_id,
            "force_open":  False,
            "created_at":  now_iso,
            "updated_at":  now_iso,
        }
        self._lock_ref(date, period_id).set(doc, merge=True)
        logger.info(
            "Period LOCKED: period=%s date=%s actor=%s reason=%s",
            period_id, date, actor_id, reason,
        )
        return doc

    def unlock_period(
        self,
        period_id: str,
        date: Optional[str] = None,
        actor_id: str = "admin",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Unlock a period.

        If ``force=True`` the period is force-opened even if the natural window
        has expired (admin override).
        """
        date    = date or datetime.now().strftime("%Y-%m-%d")
        now_iso = _now_iso()
        updates = {
            "locked":     False,
            "force_open": force,
            "updated_at": now_iso,
            "unlocked_by": actor_id,
            "unlocked_at": now_iso,
        }
        self._lock_ref(date, period_id).set(updates, merge=True)
        logger.info(
            "Period UNLOCKED: period=%s date=%s actor=%s force=%s",
            period_id, date, actor_id, force,
        )
        return {**updates, "period_id": period_id, "date": date}

    def is_locked(self, period_id: str, date: Optional[str] = None) -> bool:
        """Fast check — True if the period is manually locked (no time math)."""
        date     = date or datetime.now().strftime("%Y-%m-%d")
        doc      = self._lock_ref(date, period_id).get()
        lock_data = doc.to_dict() if doc.exists else {}
        return lock_data.get("locked", False) and not lock_data.get("force_open", False)

    def auto_lock_if_expired(
        self,
        period: Dict[str, Any],
        date: Optional[str] = None,
    ) -> bool:
        """
        Check if the period's attendance window has expired and auto-lock it.

        Returns True if the period was locked by this call.
        """
        status = self.get_window_status(period, date)
        if status["phase"] == "locked" and not status["is_manually_locked"]:
            self.lock_period(
                period_id=period["period_id"],
                class_id=period.get("class_id", ""),
                date=date,
                actor_id="system",
                reason="auto",
            )
            return True
        return False

    # ── Audit trail ────────────────────────────────────────────────────────────

    def write_audit(
        self,
        record_id: str,
        action: str,
        actor_id: str,
        after: Dict[str, Any],
        before: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Append an immutable change entry to ``attendance_audits/{record_id}/changes``.

        Parameters
        ----------
        record_id : Attendance record identifier.
        action    : "CREATE" | "UPDATE" | "BULK_MARK" | "LOCK_OVERRIDE" | "DELETE"
        actor_id  : Who performed the action.
        after     : New state of the record.
        before    : Previous state (None for CREATE).
        reason    : Optional human note.
        """
        entry = {
            "action":     action,
            "actor_id":   actor_id,
            "changed_at": _now_iso(),
            "before":     before,
            "after":      after,
            "reason":     reason,
        }
        self._audit_ref(record_id).add(entry)
        logger.debug("Audit[%s] record=%s actor=%s", action, record_id, actor_id)

    def get_audit_trail(self, record_id: str) -> List[Dict[str, Any]]:
        """Return full audit trail for a record, newest-first."""
        docs = (
            self._audit_ref(record_id)
            .order_by("changed_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]


# ── Module-level singleton ─────────────────────────────────────────────────────

_lock_service: Optional[AttendanceLockService] = None


def get_lock_service() -> Optional[AttendanceLockService]:
    return _lock_service


def init_lock_service(firestore_db: Any) -> AttendanceLockService:
    global _lock_service
    _lock_service = AttendanceLockService(firestore_db)
    logger.info("AttendanceLockService initialised.")
    return _lock_service
