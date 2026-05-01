"""
services/timetable_service.py
─────────────────────────────────────────────────────────────────────────────
Timetable Service for the Smart Attendance System.

Responsibilities
----------------
1. Parse and validate CSV / JSON timetable uploads.
2. Bulk-insert Period documents into the Firestore ``periods`` collection.
3. Update individual periods with full audit trail written to
   ``periods/{period_id}/audit_log`` sub-collection.
4. Soft-delete periods (sets ``active_status = False`` + writes audit entry)
   so historical data is never lost.
5. Query helpers used by both the API layer and the PeriodDetectionService.

Period document shape (Firestore ``periods`` collection)
---------------------------------------------------------
{
    "period_id":        str,            # auto or supplied
    "class_id":         str,
    "faculty_id":       str,
    "course_id":        str,
    "day_of_week":      int,            # 0 = Mon … 6 = Sun
    "start_time":       str,            # "HH:MM"
    "end_time":         str,            # "HH:MM"
    "period_type":      str,            # "lecture" | "lab" | "tutorial" | "holiday"
    "room":             str | None,
    "active_status":    bool,
    "created_at":       str (ISO-8601),
    "updated_at":       str (ISO-8601),
    "metadata":         dict | None,    # flexible extra fields
}

Audit-log sub-document shape
------------------------------
{
    "action":       str,    # "CREATE" | "UPDATE" | "DELETE"
    "actor_id":     str,
    "changed_at":   str (ISO-8601),
    "changes":      dict,   # {"field": {"before": ..., "after": ...}}
    "reason":       str | None,
}
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

from google.cloud.firestore_v1 import FieldFilter
from config.constants import (
    DATE_FORMAT,
    DATETIME_FORMAT,
    DAY_NAME_TO_INT,
    DAY_OF_WEEK_MAP,
    DB_FIELD_ACTIVE_STATUS,
    DB_FIELD_CLASS_ID,
    DB_FIELD_DAY_OF_WEEK,
    DB_FIELD_END_TIME,
    DB_FIELD_FACULTY_ID,
    DB_FIELD_START_TIME,
    FIREBASE_COLLECTIONS,
    TIME_FORMAT_HM,
)

logger = logging.getLogger(__name__)

# ── Collection alias ───────────────────────────────────────────────────────────
PERIODS_COLLECTION: str = FIREBASE_COLLECTIONS["periods"]

# ── Valid period types ─────────────────────────────────────────────────────────
VALID_PERIOD_TYPES = {"lecture", "lab", "tutorial", "holiday", "break", "exam"}

# ── Required CSV columns ───────────────────────────────────────────────────────
REQUIRED_CSV_COLUMNS = {
    "class_id", "faculty_id", "course_id",
    "day_of_week", "start_time", "end_time",
}

# ── Optional CSV columns with defaults ────────────────────────────────────────
OPTIONAL_CSV_COLUMNS: Dict[str, Any] = {
    "period_type": "lecture",
    "room":        None,
    "metadata":    None,
}


# ══════════════════════════════════════════════════════════════════════════════
# Parsing helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_time(raw: str, field_name: str = "time") -> str:
    """
    Accept "HH:MM", "H:MM", "HH:MM:SS", or integer minutes-from-midnight.
    Returns canonical "HH:MM" string or raises ValueError.
    """
    raw = str(raw).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(raw, fmt).strftime(TIME_FORMAT_HM)
        except ValueError:
            pass
    # integer minutes from midnight
    if raw.isdigit():
        total = int(raw)
        return f"{total // 60:02d}:{total % 60:02d}"
    raise ValueError(f"Cannot parse {field_name}='{raw}' as HH:MM time.")


def _parse_day(raw: str) -> int:
    """
    Accept day name ("Monday"), abbreviated ("Mon"), or integer 0-6.
    Returns 0-based int (Monday = 0).
    """
    raw = str(raw).strip()
    if raw.isdigit():
        val = int(raw)
        if 0 <= val <= 6:
            return val
        raise ValueError(f"day_of_week integer must be 0-6, got {val}.")
    # Full or 3-letter abbreviation
    for name, idx in DAY_NAME_TO_INT.items():
        if name.lower().startswith(raw.lower()[:3]):
            return idx
    raise ValueError(f"Cannot parse day_of_week='{raw}'.")


def _validate_time_order(start: str, end: str) -> None:
    """Raise ValueError if start >= end (unless period_type is holiday/break)."""
    t_start = datetime.strptime(start, TIME_FORMAT_HM).time()
    t_end   = datetime.strptime(end,   TIME_FORMAT_HM).time()
    if t_start >= t_end:
        raise ValueError(
            f"start_time '{start}' must be before end_time '{end}'."
        )


def _build_period_doc(
    raw: Dict[str, Any],
    *,
    period_id: Optional[str] = None,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate a raw dict (from CSV row or JSON body) and return a clean
    Firestore-ready period document.  Raises ValueError on invalid data.
    """
    now_iso = now_iso or datetime.utcnow().isoformat()

    # ── Mandatory fields ───────────────────────────────────────────────────────
    missing = REQUIRED_CSV_COLUMNS - set(raw.keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    day    = _parse_day(raw["day_of_week"])
    start  = _parse_time(raw["start_time"], "start_time")
    end    = _parse_time(raw["end_time"],   "end_time")
    p_type = str(raw.get("period_type", "lecture")).strip().lower()

    if p_type not in VALID_PERIOD_TYPES:
        raise ValueError(
            f"period_type '{p_type}' not in {VALID_PERIOD_TYPES}."
        )

    # Skip time-order check for whole-day types
    if p_type not in {"holiday", "break"}:
        _validate_time_order(start, end)

    doc: Dict[str, Any] = {
        "period_id":     period_id or str(uuid.uuid4()),
        "class_id":      str(raw["class_id"]).strip(),
        "faculty_id":    str(raw["faculty_id"]).strip(),
        "course_id":     str(raw["course_id"]).strip(),
        "day_of_week":   day,
        "start_time":    start,
        "end_time":      end,
        "period_type":   p_type,
        "room":          raw.get("room") or None,
        "active_status": True,
        "created_at":    now_iso,
        "updated_at":    now_iso,
        "metadata":      raw.get("metadata") or {},
    }
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# TimetableService
# ══════════════════════════════════════════════════════════════════════════════

class TimetableService:
    """
    High-level timetable operations.

    All Firestore I/O is injected via ``firestore_db`` so the service can be
    unit-tested with a mock.  Pass the real ``google.cloud.firestore.Client``
    instance (or a compatible async client) in production.
    """

    def __init__(self, firestore_db: Any) -> None:
        self._db = firestore_db

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _periods_col(self):
        return self._db.collection(PERIODS_COLLECTION)

    def _period_doc(self, period_id: str):
        return self._periods_col().document(period_id)

    def _audit_col(self, period_id: str):
        return self._period_doc(period_id).collection("audit_log")

    def _write_audit(
        self,
        period_id: str,
        action: str,
        actor_id: str,
        changes: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> None:
        entry = {
            "action":     action,
            "actor_id":   actor_id,
            "changed_at": datetime.utcnow().isoformat(),
            "changes":    changes,
            "reason":     reason,
        }
        self._audit_col(period_id).add(entry)
        logger.info("Audit [%s] period=%s actor=%s", action, period_id, actor_id)

    # ── CSV parsing ────────────────────────────────────────────────────────────

    def parse_csv(self, csv_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse a CSV upload.

        Returns
        -------
        (valid_rows, errors)
            valid_rows : list of clean period dicts ready for bulk_insert
            errors     : list of human-readable error strings for each bad row
        """
        try:
            text = csv_bytes.decode("utf-8-sig")   # handles BOM
        except UnicodeDecodeError:
            text = csv_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return [], ["CSV file is empty or has no header row."]

        # Normalise header names (lowercase, strip whitespace)
        reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]
        missing_headers = REQUIRED_CSV_COLUMNS - set(reader.fieldnames)
        if missing_headers:
            return [], [
                f"CSV missing required columns: {', '.join(sorted(missing_headers))}"
            ]

        now_iso = datetime.utcnow().isoformat()
        valid_rows: List[Dict[str, Any]] = []
        errors: List[str] = []

        for row_num, raw_row in enumerate(reader, start=2):   # 1-indexed; row 1 = header
            # Normalize keys
            row = {k.strip().lower(): v.strip() if isinstance(v, str) else v
                   for k, v in raw_row.items()}
            try:
                doc = _build_period_doc(row, now_iso=now_iso)
                valid_rows.append(doc)
            except ValueError as exc:
                errors.append(f"Row {row_num}: {exc}")

        logger.info(
            "CSV parsed: %d valid, %d errors", len(valid_rows), len(errors)
        )
        return valid_rows, errors

    # ── JSON parsing ───────────────────────────────────────────────────────────

    def parse_json(
        self, payload: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate a list of period dicts from a JSON body.

        Returns (valid_rows, errors).
        """
        now_iso = datetime.utcnow().isoformat()
        valid_rows: List[Dict[str, Any]] = []
        errors: List[str] = []

        for idx, item in enumerate(payload):
            try:
                doc = _build_period_doc(item, now_iso=now_iso)
                valid_rows.append(doc)
            except (ValueError, TypeError) as exc:
                errors.append(f"Item {idx}: {exc}")

        return valid_rows, errors

    # ── Bulk insert ────────────────────────────────────────────────────────────

    def bulk_insert(
        self,
        periods: List[Dict[str, Any]],
        actor_id: str = "system",
        batch_size: int = 400,   # Firestore max per commit = 500
    ) -> Dict[str, Any]:
        """
        Write ``periods`` to Firestore in batches.

        Returns a summary dict with ``inserted``, ``failed`` counts and any
        ``error_details``.
        """
        inserted = 0
        failed   = 0
        error_details: List[str] = []

        for chunk_start in range(0, len(periods), batch_size):
            chunk = periods[chunk_start: chunk_start + batch_size]
            batch = self._db.batch()

            for doc in chunk:
                pid  = doc["period_id"]
                ref  = self._period_doc(pid)
                batch.set(ref, doc)

            try:
                batch.commit()
                inserted += len(chunk)
                # Audit each period after successful batch
                for doc in chunk:
                    try:
                        self._write_audit(
                            doc["period_id"],
                            action="CREATE",
                            actor_id=actor_id,
                            changes={"period": {"before": None, "after": doc}},
                        )
                    except Exception as audit_exc:
                        logger.warning(
                            "Audit write failed for %s: %s",
                            doc["period_id"], audit_exc,
                        )
            except Exception as exc:
                failed += len(chunk)
                error_details.append(str(exc))
                logger.error("Batch insert failed: %s", exc)

        logger.info(
            "bulk_insert: inserted=%d, failed=%d", inserted, failed
        )
        return {
            "inserted": inserted,
            "failed":   failed,
            "error_details": error_details,
        }

    # ── Fetch helpers ──────────────────────────────────────────────────────────

    def get_periods_by_class(
        self,
        class_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return all periods for a class, ordered by day + start_time."""
        query = (
            self._periods_col()
            .where(filter=FieldFilter(DB_FIELD_CLASS_ID, "==", class_id))
            .order_by(DB_FIELD_DAY_OF_WEEK)
            .order_by(DB_FIELD_START_TIME)
        )
        if not include_inactive:
            query = query.where(filter=FieldFilter(DB_FIELD_ACTIVE_STATUS, "==", True))

        docs = query.stream()
        return [d.to_dict() for d in docs]

    def get_period(self, period_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single period by ID."""
        doc = self._period_doc(period_id).get()
        return doc.to_dict() if doc.exists else None

    def get_all_active_periods(self) -> List[Dict[str, Any]]:
        """Fetch all active periods across all classes (used by PeriodDetectionService)."""
        docs = (
            self._periods_col()
            .where(filter=FieldFilter(DB_FIELD_ACTIVE_STATUS, "==", True))
            .stream()
        )
        return [d.to_dict() for d in docs]

    def get_audit_log(self, period_id: str) -> List[Dict[str, Any]]:
        """Return audit entries for a period, newest first."""
        docs = (
            self._audit_col(period_id)
            .order_by("changed_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]

    # ── Update ─────────────────────────────────────────────────────────────────

    def update_period(
        self,
        period_id: str,
        updates: Dict[str, Any],
        actor_id: str = "system",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Partially update a period document.

        ``updates`` may contain any subset of period fields.  ``period_id``,
        ``created_at``, and ``active_status`` cannot be overridden here
        (use delete_period to deactivate).

        Returns the updated document or raises ValueError / KeyError.
        """
        ref = self._period_doc(period_id)
        existing = ref.get()
        if not existing.exists:
            raise KeyError(f"Period '{period_id}' not found.")

        old_doc = existing.to_dict()

        # Guard immutable fields
        for immutable in ("period_id", "created_at"):
            updates.pop(immutable, None)

        # Re-validate time fields if present
        if "start_time" in updates:
            updates["start_time"] = _parse_time(updates["start_time"], "start_time")
        if "end_time" in updates:
            updates["end_time"] = _parse_time(updates["end_time"], "end_time")
        if "day_of_week" in updates:
            updates["day_of_week"] = _parse_day(updates["day_of_week"])
        if "period_type" in updates:
            pt = str(updates["period_type"]).strip().lower()
            if pt not in VALID_PERIOD_TYPES:
                raise ValueError(f"Invalid period_type '{pt}'.")
            updates["period_type"] = pt

        start = updates.get("start_time", old_doc.get("start_time", "00:00"))
        end   = updates.get("end_time",   old_doc.get("end_time",   "23:59"))
        p_type = updates.get("period_type", old_doc.get("period_type", "lecture"))
        if p_type not in {"holiday", "break"}:
            _validate_time_order(start, end)

        updates["updated_at"] = datetime.utcnow().isoformat()
        ref.update(updates)

        # Build change set for audit
        changes = {
            field: {"before": old_doc.get(field), "after": val}
            for field, val in updates.items()
            if old_doc.get(field) != val and field != "updated_at"
        }
        self._write_audit(period_id, "UPDATE", actor_id, changes, reason)

        new_doc = ref.get().to_dict()
        logger.info("Updated period %s by %s", period_id, actor_id)
        return new_doc

    # ── Soft-delete ────────────────────────────────────────────────────────────

    def delete_period(
        self,
        period_id: str,
        actor_id: str = "system",
        reason: Optional[str] = None,
    ) -> bool:
        """
        Soft-delete a period (sets active_status = False).

        Returns True if successful, raises KeyError if not found.
        """
        ref = self._period_doc(period_id)
        doc = ref.get()
        if not doc.exists:
            raise KeyError(f"Period '{period_id}' not found.")

        old_doc = doc.to_dict()
        now_iso = datetime.utcnow().isoformat()

        ref.update({
            DB_FIELD_ACTIVE_STATUS: False,
            "updated_at":           now_iso,
            "deleted_at":           now_iso,
            "deleted_by":           actor_id,
        })
        self._write_audit(
            period_id,
            "DELETE",
            actor_id,
            {"active_status": {"before": True, "after": False}},
            reason,
        )
        logger.info("Soft-deleted period %s by %s", period_id, actor_id)
        return True

    # ── Overlap detection ──────────────────────────────────────────────────────

    def detect_overlaps(
        self,
        class_id: str,
        new_periods: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return list of overlap descriptors for a class's timetable.

        If ``new_periods`` is supplied, also checks them against existing ones.
        Each descriptor has keys: period_a, period_b, overlap_minutes.
        """
        existing  = self.get_periods_by_class(class_id)
        all_pds   = existing + (new_periods or [])
        overlaps: List[Dict[str, Any]] = []

        def to_minutes(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m

        for i, a in enumerate(all_pds):
            if a.get("period_type") in {"holiday", "break"}:
                continue
            if a.get("day_of_week") is None:
                continue
            for b in all_pds[i + 1:]:
                if b.get("period_type") in {"holiday", "break"}:
                    continue
                if a["day_of_week"] != b.get("day_of_week"):
                    continue
                a_start = to_minutes(a["start_time"])
                a_end   = to_minutes(a["end_time"])
                b_start = to_minutes(b["start_time"])
                b_end   = to_minutes(b["end_time"])
                overlap = min(a_end, b_end) - max(a_start, b_start)
                if overlap > 0:
                    overlaps.append({
                        "period_a":        a.get("period_id"),
                        "period_b":        b.get("period_id"),
                        "day":             DAY_OF_WEEK_MAP.get(a["day_of_week"], "?"),
                        "overlap_minutes": overlap,
                    })

        return overlaps


# ── Module-level singleton factory ─────────────────────────────────────────────

_timetable_service_instance: Optional[TimetableService] = None


def get_timetable_service() -> Optional[TimetableService]:
    return _timetable_service_instance


def init_timetable_service(firestore_db: Any) -> TimetableService:
    global _timetable_service_instance
    _timetable_service_instance = TimetableService(firestore_db)
    logger.info("TimetableService initialised.")
    return _timetable_service_instance
