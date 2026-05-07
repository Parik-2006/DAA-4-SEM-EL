"""
database/attendance_repository.py
────────────────────────────────────────────────────────────────────────────────
Attendance Data Repository.

Provides operations for recording and querying attendance records.

Changes (role-aware pass)
-------------------------
New public methods added alongside existing ones — no existing signatures
were changed:

  get_section_attendance(class_id, date, faculty_id)
      Fetch all attendance records for a specific section on a date.
      Enforces teacher-level access: only records whose class_id matches
      the provided class_id are returned.  The caller must have already
      verified that faculty_id owns class_id (see teacher.py).

  get_section_attendance_summary(class_id, date)
      Aggregated present/late/absent counts for a section on a date.
      Suitable for the teacher dashboard card and real-time updates.

  get_student_attendance_safe(student_id, ...)
      Thin wrapper around get_student_attendance that also strips
      class-level fields irrelevant to the student.

  get_admin_daily_summary(date)
      Cross-section summary keyed by class_id → counts.
      Admin-only: returns data across ALL sections.

  upsert_attendance_record(record)
      Create or overwrite a single record and return the saved document.
      Used internally by bulk-mark and edit flows to ensure a consistent
      write path with predictable record_id generation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from config.constants import (
    ATTENDANCE_RETENTION_DAYS,
    FIREBASE_COLLECTIONS,
    AttendanceStatus,
    DB_FIELD_ATTENDANCE_DATE,
    DB_FIELD_ATTENDANCE_TIME,
    DB_FIELD_CONFIDENCE_SCORE,
    DB_FIELD_COURSE_ID,
    DB_FIELD_STUDENT_ID,
    DB_FIELD_TIMESTAMP,
)
from database.firebase_client import FirebaseClient

logger = logging.getLogger(__name__)


class AttendanceRepository:
    """
    Repository for attendance record operations.

    Handles recording and querying attendance data in Firebase.

    All query methods that accept a ``student_id`` only return records
    belonging to that student — no cross-student data is ever returned.
    Methods that accept a ``class_id`` scope their results to that section.
    """

    def __init__(self):
        self.db = FirebaseClient()
        self.collection = FIREBASE_COLLECTIONS["attendance"]

    # ── Write ─────────────────────────────────────────────────────────────────

    def mark_attendance(
        self,
        student_id: str,
        course_id: str,
        confidence_score: float,
        status: str = AttendanceStatus.PRESENT,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record attendance for a student.

        Args:
            student_id:       Student identifier.
            course_id:        Course identifier.
            confidence_score: Face recognition confidence (0-1).
            status:           Attendance status (present / absent / late / …).
            timestamp:        Record timestamp (uses current UTC if None).
            metadata:         Extra metadata to store with the record.

        Returns:
            True if the write succeeded, False otherwise.
        """
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()

            record_id = f"{student_id}_{timestamp.isoformat()}"

            data: Dict[str, Any] = {
                DB_FIELD_STUDENT_ID:       student_id,
                DB_FIELD_COURSE_ID:        course_id,
                DB_FIELD_ATTENDANCE_DATE:  timestamp.strftime("%Y-%m-%d"),
                DB_FIELD_ATTENDANCE_TIME:  timestamp.strftime("%H:%M:%S"),
                DB_FIELD_TIMESTAMP:        timestamp.isoformat(),
                "status":                  status,
                DB_FIELD_CONFIDENCE_SCORE: confidence_score,
            }

            if metadata:
                data.update(metadata)

            path    = f"{self.collection}/{record_id}"
            success = self.db.write_data(path, data)

            if success:
                logger.info("Marked attendance for %s in %s", student_id, course_id)
            else:
                logger.error("Failed to mark attendance for %s", student_id)

            return success

        except Exception as exc:
            logger.error("Error marking attendance: %s", exc)
            return False

    def upsert_attendance_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create or overwrite a single attendance record.

        ``record`` must contain at least ``student_id``, ``date``, and
        ``period_id``.  A deterministic ``record_id`` is derived from these
        three fields so the same (student, period, date) triple always maps
        to the same document — preventing duplicates on retry.

        Returns the saved record dict, or None on failure.
        """
        try:
            student_id = record.get("student_id", "")
            period_id  = record.get("period_id", "")
            rec_date   = record.get("date", datetime.utcnow().strftime("%Y-%m-%d"))

            if not (student_id and period_id):
                logger.error("upsert_attendance_record: missing student_id or period_id")
                return None

            record_id = f"{rec_date}_{period_id}_{student_id}"
            record["record_id"] = record_id

            path = f"{self.collection}/{record_id}"
            if self.db.write_data(path, record):
                return record
            return None

        except Exception as exc:
            logger.error("upsert_attendance_record failed: %s", exc)
            return None

    # ── Student-scoped queries ────────────────────────────────────────────────

    def get_student_attendance(
        self,
        student_id: str,
        course_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records for *student_id*.

        Only records whose ``student_id`` field matches are returned — this
        is an immutable guarantee; callers cannot retrieve another student's
        records by passing a different student_id.

        Args:
            student_id:  The student whose records to fetch.
            course_id:   Optional course code filter.
            start_date:  Optional start of date range (inclusive).
            end_date:    Optional end of date range (inclusive).

        Returns:
            List of attendance record dicts.
        """
        try:
            data = self.db.read_data(self.collection)
            if not data:
                return []

            records = [
                r for r in data.values()
                if isinstance(r, dict) and r.get(DB_FIELD_STUDENT_ID) == student_id
            ]

            if course_id:
                records = [r for r in records if r.get(DB_FIELD_COURSE_ID) == course_id]

            if start_date or end_date:
                records = self._filter_by_date_range(records, start_date, end_date)

            logger.debug("Retrieved %d records for %s", len(records), student_id)
            return records

        except Exception as exc:
            logger.error("Error retrieving attendance for %s: %s", student_id, exc)
            return []

    def get_student_attendance_safe(
        self,
        student_id: str,
        course_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Same as ``get_student_attendance`` but strips fields irrelevant or
        potentially sensitive for the student view:
          - removes ``class_id`` (student doesn't need raw class ref)
          - removes ``faculty_id``
          - removes ``confidence`` (optional, kept here for student awareness)

        Suitable for direct serialisation into student-facing API responses.
        """
        records = self.get_student_attendance(
            student_id, course_id, start_date, end_date
        )
        student_safe_fields = {
            DB_FIELD_STUDENT_ID,
            DB_FIELD_COURSE_ID,
            DB_FIELD_ATTENDANCE_DATE,
            DB_FIELD_ATTENDANCE_TIME,
            DB_FIELD_TIMESTAMP,
            "status",
            DB_FIELD_CONFIDENCE_SCORE,
            "period_id",
            "record_id",
        }
        return [
            {k: v for k, v in r.items() if k in student_safe_fields}
            for r in records
        ]

    # ── Section-scoped queries (teacher-level) ────────────────────────────────

    def get_section_attendance(
        self,
        class_id: str,
        date_filter: Optional[str] = None,
        faculty_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all attendance records for *class_id* on the given date.

        Access contract
        ~~~~~~~~~~~~~~~
        *faculty_id* is optional but should always be supplied by the teacher
        API layer, which has already validated that this faculty owns the
        section.  The repository performs a secondary filter to ensure only
        records with matching ``class_id`` are returned — it does NOT
        re-validate faculty ownership (that is the API layer's job).

        Args:
            class_id:    The section whose records to fetch.
            date_filter: ISO date string ``YYYY-MM-DD``.  Defaults to today.
            faculty_id:  Informational; stored in audit log but not used to
                         further filter records.

        Returns:
            List of attendance record dicts for the section.
        """
        target_date = date_filter or datetime.now().strftime("%Y-%m-%d")

        try:
            # Try Realtime DB path attendance/{date}
            rt_ref = self.db.get_reference(f"attendance/{target_date}")
            raw = rt_ref.get() or {}

            records = [
                r for r in raw.values()
                if isinstance(r, dict) and r.get("class_id") == class_id
            ]

            logger.debug(
                "get_section_attendance: class=%s date=%s records=%d",
                class_id, target_date, len(records),
            )
            return records

        except Exception as exc:
            logger.error("get_section_attendance failed: %s", exc)
            return []

    def get_section_attendance_summary(
        self,
        class_id: str,
        date_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate attendance counts for *class_id* on *date_filter*.

        Returns::

            {
              "class_id":     "CS-A-SEM6",
              "date":         "2026-04-30",
              "present":      18,
              "late":         3,
              "absent":       4,
              "not_marked":   5,   # derived from total_students - marked
              "total_marked": 25,
              "total_students": 30,
              "attendance_rate": 70.0,
            }

        ``total_students`` is derived from the class record in Firebase.
        """
        target_date = date_filter or datetime.now().strftime("%Y-%m-%d")
        records = self.get_section_attendance(class_id, target_date)

        present = sum(1 for r in records if r.get("status") == "present")
        late    = sum(1 for r in records if r.get("status") == "late")
        absent  = sum(1 for r in records if r.get("status") == "absent")
        total_marked = present + late + absent

        # Load total_students from classes/{class_id}
        total_students = total_marked   # floor fallback
        try:
            cls = self.db.get_reference(f"classes/{class_id}").get() or {}
            enrolled = cls.get("student_ids", [])
            total_students = len(enrolled) if enrolled else total_marked
        except Exception:
            pass

        not_marked    = max(0, total_students - total_marked)
        rate          = round((present + late) / total_students * 100, 1) if total_students else 0.0

        return {
            "class_id":       class_id,
            "date":           target_date,
            "present":        present,
            "late":           late,
            "absent":         absent,
            "not_marked":     not_marked,
            "total_marked":   total_marked,
            "total_students": total_students,
            "attendance_rate": rate,
        }

    # ── Course-scoped queries (existing) ──────────────────────────────────────

    def get_course_attendance(
        self,
        course_id: str,
        date_filter: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all attendance records for a course.

        Args:
            course_id:   Course identifier.
            date_filter: Filter to a specific date (optional).

        Returns:
            List of attendance records for the course.
        """
        try:
            data = self.db.read_data(self.collection)
            if not data:
                return []

            records = [
                r for r in data.values()
                if isinstance(r, dict) and r.get(DB_FIELD_COURSE_ID) == course_id
            ]

            if date_filter:
                date_str = date_filter.strftime("%Y-%m-%d")
                records = [r for r in records if r.get(DB_FIELD_ATTENDANCE_DATE) == date_str]

            logger.debug("Retrieved %d records for course %s", len(records), course_id)
            return records

        except Exception as exc:
            logger.error("Error retrieving course attendance: %s", exc)
            return []

    # ── Admin-scoped queries ──────────────────────────────────────────────────

    def get_admin_daily_summary(self, date_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Cross-section attendance summary for admin analytics.

        Returns a dict of::

            {
              "date": "2026-04-30",
              "total_present":  120,
              "total_late":     18,
              "total_absent":   42,
              "total_marked":   180,
              "by_section": {
                "CS-A-SEM6": {"present": 28, "late": 4, "absent": 3},
                ...
              }
            }

        This method is ADMIN ONLY — the caller (admin API layer) is responsible
        for verifying admin privileges before calling this method.  The
        repository itself does not enforce role checks.
        """
        target_date = date_filter or datetime.now().strftime("%Y-%m-%d")

        total_present = total_late = total_absent = 0
        by_section: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"present": 0, "late": 0, "absent": 0}
        )

        try:
            rt_ref = self.db.get_reference(f"attendance/{target_date}")
            raw = rt_ref.get() or {}

            for rec in raw.values():
                if not isinstance(rec, dict):
                    continue
                s   = rec.get("status", "")
                cid = rec.get("class_id", "_unknown")

                if s == "present":
                    total_present += 1
                    by_section[cid]["present"] += 1
                elif s == "late":
                    total_late += 1
                    by_section[cid]["late"] += 1
                elif s == "absent":
                    total_absent += 1
                    by_section[cid]["absent"] += 1

        except Exception as exc:
            logger.error("get_admin_daily_summary failed: %s", exc)

        return {
            "date":           target_date,
            "total_present":  total_present,
            "total_late":     total_late,
            "total_absent":   total_absent,
            "total_marked":   total_present + total_late + total_absent,
            "by_section":     dict(by_section),
        }

    # ── Statistics (existing) ─────────────────────────────────────────────────

    def get_attendance_statistics(
        self,
        student_id: str,
        course_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get attendance statistics for *student_id* in *course_id*.

        Returns counts per status, overall percentage, and average confidence.
        """
        try:
            records = self.get_student_attendance(
                student_id, course_id, start_date, end_date
            )

            status_counts: Dict[str, int] = {}
            for st in AttendanceStatus:
                status_counts[st.value] = sum(
                    1 for r in records if r.get("status") == st.value
                )

            total   = len(records)
            present = status_counts.get(AttendanceStatus.PRESENT.value, 0)
            pct     = (present / total * 100) if total > 0 else 0

            return {
                "student_id":          student_id,
                "course_id":           course_id,
                "total_records":       total,
                "status_counts":       status_counts,
                "attendance_percent":  round(pct, 2),
                "average_confidence":  self._calculate_avg_confidence(records),
            }

        except Exception as exc:
            logger.error("Error calculating attendance statistics: %s", exc)
            return {}

    # ── Housekeeping (existing) ───────────────────────────────────────────────

    def delete_old_records(self, days_to_keep: int = ATTENDANCE_RETENTION_DAYS) -> int:
        """
        Delete attendance records older than *days_to_keep* days.

        Returns the number of records deleted.
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).date()
            data        = self.db.read_data(self.collection)
            if not data:
                return 0

            deleted_count = 0
            for record_id, record in data.items():
                if isinstance(record, dict):
                    date_str = record.get(DB_FIELD_ATTENDANCE_DATE)
                    if date_str:
                        try:
                            rec_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                            if rec_date < cutoff_date:
                                if self.db.delete_data(f"{self.collection}/{record_id}"):
                                    deleted_count += 1
                        except ValueError:
                            logger.warning("Invalid date in record: %s", record_id)

            logger.info("Deleted %d old attendance records", deleted_count)
            return deleted_count

        except Exception as exc:
            logger.error("Error deleting old records: %s", exc)
            return 0

    # ── Private helpers ───────────────────────────────────────────────────────

    def _filter_by_date_range(
        self,
        records: List[Dict[str, Any]],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """Filter *records* to those within [start_date, end_date]."""
        if not start_date and not end_date:
            return records

        filtered = []
        for record in records:
            date_str = record.get(DB_FIELD_ATTENDANCE_DATE)
            if not date_str:
                continue
            try:
                rec_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if start_date and rec_date < start_date:
                    continue
                if end_date and rec_date > end_date:
                    continue
                filtered.append(record)
            except ValueError:
                logger.warning("Invalid date format in record: %s", date_str)

        return filtered

    def _calculate_avg_confidence(self, records: List[Dict[str, Any]]) -> float:
        """Calculate average confidence score across *records*."""
        scores = [
            r.get(DB_FIELD_CONFIDENCE_SCORE, 0.0)
            for r in records
            if DB_FIELD_CONFIDENCE_SCORE in r
        ]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 3)
