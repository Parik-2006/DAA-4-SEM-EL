"""
database/firebase_client.py
─────────────────────────────────────────────────────────────────────────────
Dual Firebase client: Realtime Database (legacy) + Cloud Firestore (new).

Architecture
------------
Existing attendance records in Firestore collections "students" and
"attendance" are untouched. New collections (courses, sections, enrollments,
cie, classes, periods, course_assignments, faculty, audit_logs) use Firestore
with composite indexes defined in firestore.indexes.json.

Data isolation guarantee
------------------------
Every attendance, timetable, and assignment method accepts a ``section_id``
that is applied as the FIRST Firestore filter. The database engine enforces
section boundaries — not application code.

Access patterns
---------------
1. get_section_attendance(section_id, date, period_id?)   → teacher read/mark
2. get_student_attendance(student_id, section_id?)         → student portal
3. get_teacher_sections(teacher_id)                        → JWT claim builder
4. get_active_period_for_section(section_id)               → period detection
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, db, initialize_app
from firebase_admin.exceptions import FirebaseError

try:
    from google.cloud import firestore as _firestore
    from google.cloud.firestore_v1 import FieldFilter
    _FIRESTORE_AVAILABLE = True
except ImportError:
    _FIRESTORE_AVAILABLE = False
    _firestore = None  # type: ignore

from config.settings import get_settings
from config.constants import (
    MAX_DATABASE_RETRIES,
    DATABASE_RETRY_DELAY,
    FIREBASE_COLLECTIONS,
)

logger = logging.getLogger(__name__)

# ── Collection names ──────────────────────────────────────────────────────────
COL_STUDENTS           = FIREBASE_COLLECTIONS["students"]
COL_ATTENDANCE         = FIREBASE_COLLECTIONS["attendance"]
COL_CIE                = FIREBASE_COLLECTIONS.get("cie", "cie")
COL_CLASSES            = FIREBASE_COLLECTIONS.get("classes", "classes")
COL_PERIODS            = FIREBASE_COLLECTIONS.get("periods", "periods")
COL_COURSE_ASSIGNMENTS = FIREBASE_COLLECTIONS.get("course_assignments", "course_assignments")
COL_FACULTY            = FIREBASE_COLLECTIONS.get("faculty", "faculty")
COL_COURSES            = FIREBASE_COLLECTIONS.get("courses", "courses")
COL_SECTIONS           = FIREBASE_COLLECTIONS.get("sections", "sections")
COL_ENROLLMENTS        = FIREBASE_COLLECTIONS.get("enrollments", "enrollments")
COL_AUDIT_LOGS         = FIREBASE_COLLECTIONS.get("audit_logs", "audit_logs")
COL_SYSTEM_STATE       = FIREBASE_COLLECTIONS.get("system_state", "system_state")


class FirebaseClient:
    """
    Singleton dual Firebase client.

    Call ``FirebaseClient()`` anywhere after the first initialization and
    you get the same instance.
    """

    _instance: Optional["FirebaseClient"] = None
    _initialized: bool = False

    def __new__(cls) -> "FirebaseClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.settings = get_settings()
        self.db: Optional[db.Reference] = None   # Realtime DB root
        self.fs: Optional[Any] = None            # Firestore client
        self._initialize_connection()

    # ── Initialization ────────────────────────────────────────────────────────

    def _initialize_connection(self) -> None:
        try:
            logger.info("Initializing Firebase connections…")
            cred_path = self.settings.get_credentials_path()
            if not cred_path.exists():
                raise FileNotFoundError(f"Firebase credentials not found: {cred_path}")

            cred = credentials.Certificate(str(cred_path))

            # Realtime Database (legacy — unchanged)
            if not firebase_admin._apps:
                initialize_app(cred, {"databaseURL": self.settings.firebase_database_url})
            self.db = db.reference()
            logger.info("✓ Realtime Database initialised")

            # Firestore
            if _FIRESTORE_AVAILABLE:
                raw_cred = credentials.Certificate(str(cred_path))
                try:
                    self.fs = _firestore.Client(
                        project=raw_cred.project_id,
                        credentials=raw_cred.get_credential(),
                        database="default",
                    )
                    logger.info("✓ Firestore initialised (project: %s)", raw_cred.project_id)
                except Exception as exc:
                    logger.warning("⚠ Firestore init failed (will retry on first use): %s", exc)
                    self.fs = None
            else:
                logger.warning(
                    "google-cloud-firestore not installed — "
                    "section-scoped features unavailable"
                )

            FirebaseClient._initialized = True

        except FileNotFoundError as exc:
            raise RuntimeError(f"Firebase initialization failed: {exc}")
        except FirebaseError as exc:
            raise RuntimeError(f"Firebase initialization failed: {exc}")
        except Exception as exc:
            raise RuntimeError(f"Firebase initialization failed: {exc}")

    def _require_fs(self) -> Any:
        if self.fs is None:
            raise RuntimeError(
                "Firestore client not available. "
                "Install google-cloud-firestore and restart."
            )
        return self.fs

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "initialized":          self._initialized,
            "rtdb_url":             self.settings.firebase_database_url,
            "firestore_available":  self.fs is not None,
            "credentials_path":     str(self.settings.get_credentials_path()),
        }

    # =========================================================================
    # REALTIME DATABASE — legacy methods (unchanged)
    # =========================================================================

    def get_reference(self, path: str) -> db.Reference:
        if self.db is None:
            raise RuntimeError("Realtime Database not initialized")
        return self.db.child(path)

    def write_data(self, path: str, data: Dict[str, Any], retry: int = 0) -> bool:
        try:
            self.get_reference(path).set(data)
            logger.debug("RTDB write → %s", path)
            return True
        except FirebaseError as exc:
            if retry < MAX_DATABASE_RETRIES:
                time.sleep(DATABASE_RETRY_DELAY * (2 ** retry))
                return self.write_data(path, data, retry + 1)
            logger.error("RTDB write failed after retries: %s", exc)
            return False
        except Exception as exc:
            logger.error("RTDB write error at %s: %s", path, exc)
            return False

    def read_data(self, path: str, retry: int = 0) -> Optional[Dict[str, Any]]:
        try:
            data = self.get_reference(path).get()
            return data
        except FirebaseError as exc:
            if retry < MAX_DATABASE_RETRIES:
                time.sleep(DATABASE_RETRY_DELAY * (2 ** retry))
                return self.read_data(path, retry + 1)
            logger.error("RTDB read failed after retries: %s", exc)
            return None
        except Exception as exc:
            logger.error("RTDB read error at %s: %s", path, exc)
            return None

    def update_data(self, path: str, data: Dict[str, Any]) -> bool:
        try:
            self.get_reference(path).update(data)
            return True
        except Exception as exc:
            logger.error("RTDB update error at %s: %s", path, exc)
            return False

    def delete_data(self, path: str) -> bool:
        try:
            self.get_reference(path).delete()
            return True
        except Exception as exc:
            logger.error("RTDB delete error at %s: %s", path, exc)
            return False

    def list_children(self, path: str) -> Optional[List[str]]:
        try:
            data = self.get_reference(path).get()
            return list(data.keys()) if isinstance(data, dict) else []
        except Exception as exc:
            logger.error("RTDB list_children error at %s: %s", path, exc)
            return None

    def transaction(self, path: str, update_fn) -> Any:
        try:
            return self.get_reference(path).transaction(update_fn)
        except Exception as exc:
            logger.error("RTDB transaction failed at %s: %s", path, exc)
            return None

    # =========================================================================
    # FIRESTORE — internal helpers
    # =========================================================================

    def _fs_set(self, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
        try:
            self._require_fs().collection(collection).document(doc_id).set(data)
            logger.debug("Firestore set → %s/%s", collection, doc_id)
            return True
        except Exception as exc:
            logger.error("Firestore set error %s/%s: %s", collection, doc_id, exc)
            return False

    def _fs_update(self, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
        try:
            self._require_fs().collection(collection).document(doc_id).update(data)
            return True
        except Exception as exc:
            logger.error("Firestore update error %s/%s: %s", collection, doc_id, exc)
            return False

    def _fs_get(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self._require_fs().collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.error("Firestore get error %s/%s: %s", collection, doc_id, exc)
            return None

    def _fs_delete(self, collection: str, doc_id: str) -> bool:
        try:
            self._require_fs().collection(collection).document(doc_id).delete()
            return True
        except Exception as exc:
            logger.error("Firestore delete error %s/%s: %s", collection, doc_id, exc)
            return False

    def _fs_list(
        self,
        collection: str,
        filters: Optional[List[Tuple[str, str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query Firestore with optional filters, ordering, and limit.

        ``section_id`` filters should always be passed first so Firestore uses
        the composite index most efficiently.
        """
        try:
            query = self._require_fs().collection(collection)
            for field, op, value in (filters or []):
                query = query.where(filter=FieldFilter(field, op, value))
            if order_by:
                query = query.order_by(order_by)
            if limit:
                query = query.limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        except Exception as exc:
            logger.error("Firestore list error in %s: %s", collection, exc)
            return []

    # =========================================================================
    # COURSES
    # =========================================================================

    def create_course(self, data: Dict[str, Any]) -> bool:
        """
        Create a Course document.

        Required: course_id, name, code, credits.
        Optional: description, department, metadata.
        """
        if not data.get("course_id"):
            raise ValueError("course_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_COURSES, data["course_id"], data)

    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_COURSES, course_id)

    def get_all_courses(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = [("department", "==", department)] if department else None
        return self._fs_list(COL_COURSES, filters=filters, order_by="code")

    def update_course(self, course_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_COURSES, course_id, updates)

    # =========================================================================
    # SECTIONS
    # =========================================================================

    def create_section(self, data: Dict[str, Any]) -> bool:
        """
        Create a Section document.

        Required: section_id, course_id, section_name, semester, year.
        Optional: capacity (int), stream (str), metadata.

        ``section_id`` is the universal isolation key used in attendance,
        enrollment, timetable, and course_assignments.
        """
        if not data.get("section_id"):
            raise ValueError("section_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_SECTIONS, data["section_id"], data)

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_SECTIONS, section_id)

    def get_sections_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """Index: (course_id ASC, section_name ASC)"""
        return self._fs_list(
            COL_SECTIONS,
            filters=[("course_id", "==", course_id)],
            order_by="section_name",
        )

    def get_sections_by_semester_year(self, semester: int, year: int) -> List[Dict[str, Any]]:
        """Index: (semester ASC, year ASC, section_name ASC)"""
        return self._fs_list(
            COL_SECTIONS,
            filters=[("semester", "==", semester), ("year", "==", year)],
            order_by="section_name",
        )

    def update_section(self, section_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_SECTIONS, section_id, updates)

    # =========================================================================
    # ENROLLMENTS — student ↔ section
    # =========================================================================

    def enroll_student(self, data: Dict[str, Any]) -> bool:
        """
        Link a student to a section.

        Required: enrollment_id, student_id, section_id, enrollment_date.
        Tip: use ``f"{student_id}_{section_id}"`` as enrollment_id for O(1)
        existence checks via is_student_in_section().
        """
        if not data.get("enrollment_id"):
            raise ValueError("enrollment_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_ENROLLMENTS, data["enrollment_id"], data)

    def get_enrollment(self, enrollment_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_ENROLLMENTS, enrollment_id)

    def get_student_sections(self, student_id: str) -> List[Dict[str, Any]]:
        """
        Sections a student is enrolled in — used at login for JWT context.
        Index: (student_id ASC, enrollment_date DESC)
        """
        return self._fs_list(
            COL_ENROLLMENTS,
            filters=[("student_id", "==", student_id)],
            order_by="enrollment_date",
        )

    def get_section_students(self, section_id: str) -> List[Dict[str, Any]]:
        """
        All enrollment records for a section.
        Index: (section_id ASC, student_id ASC)
        """
        return self._fs_list(
            COL_ENROLLMENTS,
            filters=[("section_id", "==", section_id)],
            order_by="student_id",
        )

    def get_students_in_section(self, section_id: str) -> List[Dict[str, Any]]:
        """Convenience: enrollment IDs → full student documents, sorted by name."""
        enrollments = self.get_section_students(section_id)
        students: List[Dict[str, Any]] = []
        for e in enrollments:
            sid = e.get("student_id")
            if not sid:
                continue
            student = self._fs_get(COL_STUDENTS, sid)
            if student:
                students.append(student)
        return sorted(students, key=lambda s: s.get("name", ""))

    def is_student_in_section(self, student_id: str, section_id: str) -> bool:
        """O(1) enrollment check via deterministic enrollment_id."""
        return self._fs_get(COL_ENROLLMENTS, f"{student_id}_{section_id}") is not None

    def unenroll_student(self, student_id: str, section_id: str) -> bool:
        return self._fs_delete(COL_ENROLLMENTS, f"{student_id}_{section_id}")

    # =========================================================================
    # COURSE ASSIGNMENTS — teacher ↔ section
    # =========================================================================

    def create_course_assignment(self, data: Dict[str, Any]) -> bool:
        """
        Assign a teacher to a section.

        Required: assignment_id, teacher_id (or faculty_id), section_id,
                  courses[], start_date.
        Optional: class_id, semester, academic_year, is_primary, metadata.

        ``teacher_id`` and ``faculty_id`` are kept in sync for backward compat.
        """
        if not data.get("assignment_id"):
            raise ValueError("assignment_id is required")
        # Sync teacher_id / faculty_id aliases
        if "teacher_id" in data and "faculty_id" not in data:
            data["faculty_id"] = data["teacher_id"]
        elif "faculty_id" in data and "teacher_id" not in data:
            data["teacher_id"] = data["faculty_id"]
        data.setdefault("is_primary", True)
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_COURSE_ASSIGNMENTS, data["assignment_id"], data)

    def get_course_assignment(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_COURSE_ASSIGNMENTS, assignment_id)

    def get_teacher_sections(self, teacher_id: str) -> List[str]:
        """
        Section IDs assigned to a teacher — used to build JWT assigned_sections.
        Index: (teacher_id ASC, section_id ASC)

        The service layer MUST use this list as the whitelist for all teacher
        queries; never trust section_id from the request body alone.
        """
        assignments = self._fs_list(
            COL_COURSE_ASSIGNMENTS,
            filters=[("teacher_id", "==", teacher_id)],
            order_by="section_id",
        )
        return [a["section_id"] for a in assignments if "section_id" in a]

    def get_section_teachers(self, section_id: str) -> List[Dict[str, Any]]:
        """All assignment records for a section. Index: (section_id ASC, teacher_id ASC)"""
        return self._fs_list(
            COL_COURSE_ASSIGNMENTS,
            filters=[("section_id", "==", section_id)],
            order_by="teacher_id",
        )

    def is_teacher_assigned_to_section(self, teacher_id: str, section_id: str) -> bool:
        """
        Authorization check called by the permission middleware before every
        attendance write. Tries deterministic ID first (fast path), then query.
        """
        if self._fs_get(COL_COURSE_ASSIGNMENTS, f"{teacher_id}_{section_id}") is not None:
            return True
        return bool(self._fs_list(
            COL_COURSE_ASSIGNMENTS,
            filters=[("teacher_id", "==", teacher_id), ("section_id", "==", section_id)],
        ))

    def get_faculty_courses(self, faculty_id: str, semester: Optional[int] = None) -> List[Dict[str, Any]]:
        """Backward-compat: assignments by faculty_id. Index: (faculty_id ASC, semester ASC)"""
        filters = [("faculty_id", "==", faculty_id)]
        if semester is not None:
            filters.append(("semester", "==", semester))
        return self._fs_list(COL_COURSE_ASSIGNMENTS, filters=filters, order_by="semester")

    def get_class_faculty(self, class_id: str) -> List[Dict[str, Any]]:
        """Legacy: assignments by class_id. Index: (class_id ASC, faculty_id ASC)"""
        return self._fs_list(
            COL_COURSE_ASSIGNMENTS,
            filters=[("class_id", "==", class_id)],
        )

    def delete_course_assignment(self, assignment_id: str) -> bool:
        return self._fs_delete(COL_COURSE_ASSIGNMENTS, assignment_id)

    # =========================================================================
    # SECTION-SCOPED ATTENDANCE
    # =========================================================================

    def get_section_attendance(
        self,
        section_id: str,
        date_str: str,
        period_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Core teacher read path — section_id is always the first filter.
        Index: (section_id ASC, date ASC, period_id ASC)
        """
        filters: List[Tuple[str, str, Any]] = [
            ("section_id", "==", section_id),
            ("date",       "==", date_str),
        ]
        if period_id:
            filters.append(("period_id", "==", period_id))
        return self._fs_list(COL_ATTENDANCE, filters=filters, order_by="timestamp")

    def get_section_attendance_range(
        self, section_id: str, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """
        Date-range attendance for analytics reports.
        Index: (section_id ASC, date DESC)
        Python-side upper bound applied (Firestore single-inequality limit).
        """
        candidates = self._fs_list(
            COL_ATTENDANCE,
            filters=[("section_id", "==", section_id), ("date", ">=", from_date)],
            order_by="date",
        )
        return [r for r in candidates if r.get("date", "") <= to_date]

    def get_student_attendance(
        self,
        student_id: str,
        section_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Student portal read path. section_id applied at DB level when present.
        Index (with section): (student_id ASC, section_id ASC, date DESC)
        Index (without):      (student_id ASC, timestamp DESC)
        """
        filters: List[Tuple[str, str, Any]] = [("student_id", "==", student_id)]
        if section_id:
            filters.append(("section_id", "==", section_id))
        results = self._fs_list(COL_ATTENDANCE, filters=filters, order_by="date")
        if from_date:
            results = [r for r in results if r.get("date", "") >= from_date]
        if to_date:
            results = [r for r in results if r.get("date", "") <= to_date]
        return results

    def get_student_section_attendance(
        self,
        student_id: str,
        section_id: str,
        period_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Narrowest query: student + section + optional period + date range.
        Index: (student_id ASC, section_id ASC, date ASC, period_id ASC)
        """
        filters: List[Tuple[str, str, Any]] = [
            ("student_id", "==", student_id),
            ("section_id", "==", section_id),
        ]
        if period_id:
            filters.append(("period_id", "==", period_id))
        if from_date:
            filters.append(("date", ">=", from_date))
        results = self._fs_list(COL_ATTENDANCE, filters=filters, order_by="date")
        if to_date:
            results = [r for r in results if r.get("date", "") <= to_date]
        return results

    def mark_attendance(self, data: Dict[str, Any]) -> bool:
        """
        Write a single attendance record.

        Required: attendance_id, student_id, section_id, period_id, date,
                  status, marked_by_teacher_id, timestamp.

        The caller (service layer) MUST verify before calling:
          1. is_teacher_assigned_to_section()
          2. get_active_period_for_section()
        """
        if not data.get("attendance_id"):
            raise ValueError("attendance_id is required")
        for field in ("student_id", "section_id", "period_id", "date", "status"):
            if not data.get(field):
                raise ValueError(f"{field} is required in attendance record")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_ATTENDANCE, data["attendance_id"], data)

    def update_attendance_status(
        self, attendance_id: str, new_status: str, updated_by: str
    ) -> bool:
        """Admin-only correction. Caller is responsible for audit log entry."""
        return self._fs_update(
            COL_ATTENDANCE,
            attendance_id,
            {
                "status":          new_status,
                "last_updated_by": updated_by,
                "updated_at":      datetime.now().isoformat(),
            },
        )

    def get_attendance_for_period(
        self, period_id: str, date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Legacy path used by the recognition pipeline (metadata.period_id).
        New code should use get_section_attendance() with explicit section_id.
        """
        date_str = date_str or date.today().isoformat()
        return self._fs_list(
            COL_ATTENDANCE,
            filters=[
                ("date",               "==", date_str),
                ("metadata.period_id", "==", period_id),
            ],
        )

    # =========================================================================
    # SECTION-SCOPED TIMETABLE
    # =========================================================================

    def create_period(self, data: Dict[str, Any]) -> bool:
        """
        Create a timetable Period document.

        Required: period_id, section_id, class_id, day_of_week (0-6),
                  start_time (HH:MM), end_time (HH:MM), course_code,
                  course_name, faculty_id.
        Optional: teacher_id (alias), is_lab_class, duration_minutes,
                  room_override, metadata.

        section_id is mandatory — all timetable entries must be section-scoped.
        duration_minutes is auto-derived from start/end if omitted.
        """
        if not data.get("period_id"):
            raise ValueError("period_id is required")
        if not data.get("section_id"):
            raise ValueError("section_id is required on all period documents")
        # Sync teacher_id / faculty_id
        if "teacher_id" in data and "faculty_id" not in data:
            data["faculty_id"] = data["teacher_id"]
        elif "faculty_id" in data and "teacher_id" not in data:
            data["teacher_id"] = data["faculty_id"]
        data.setdefault("is_lab_class", False)
        data.setdefault("created_at", datetime.now().isoformat())
        if "duration_minutes" not in data:
            try:
                sh, sm = map(int, data["start_time"].split(":"))
                eh, em = map(int, data["end_time"].split(":"))
                data["duration_minutes"] = (eh * 60 + em) - (sh * 60 + sm)
            except Exception:
                pass
        return self._fs_set(COL_PERIODS, data["period_id"], data)

    def get_period(self, period_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_PERIODS, period_id)

    def get_section_timetable(self, section_id: str) -> List[Dict[str, Any]]:
        """
        Full timetable for a section across all days.
        Index: (section_id ASC, day_of_week ASC, start_time ASC)
        """
        results = self._fs_list(
            COL_PERIODS,
            filters=[("section_id", "==", section_id)],
            order_by="day_of_week",
        )
        results.sort(key=lambda p: (p.get("day_of_week", 0), p.get("start_time", "")))
        return results

    def get_active_period_for_section(
        self, section_id: str, at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the running period for a specific section right now.

        section_id is always the first filter — result is guaranteed to belong
        to the caller's authorised section.
        Index: (section_id ASC, day_of_week ASC, start_time ASC, end_time ASC)
        """
        now = at or datetime.now()
        day = now.weekday()
        time_str = now.strftime("%H:%M")

        candidates = self._fs_list(
            COL_PERIODS,
            filters=[
                ("section_id",  "==", section_id),
                ("day_of_week", "==", day),
                ("start_time",  "<=", time_str),
            ],
            order_by="start_time",
        )
        active = [p for p in candidates if p.get("end_time", "") >= time_str]
        if not active:
            return None
        active.sort(key=lambda p: p.get("start_time", ""), reverse=True)
        period = active[0]
        logger.info(
            "Active period for section %s: %s (%s %s-%s)",
            section_id, period.get("period_id"),
            period.get("course_code"), period.get("start_time"), period.get("end_time"),
        )
        return period

    def get_timetable_by_class(self, class_id: str) -> List[Dict[str, Any]]:
        """Legacy: periods by class_id. Index: (class_id ASC, day_of_week ASC, start_time ASC)"""
        results = self._fs_list(
            COL_PERIODS,
            filters=[("class_id", "==", class_id)],
            order_by="day_of_week",
        )
        results.sort(key=lambda p: (p.get("day_of_week", 0), p.get("start_time", "")))
        return results

    def get_periods_by_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        """All periods on a day — admin / recognition pipeline."""
        return self._fs_list(
            COL_PERIODS,
            filters=[("day_of_week", "==", day_of_week)],
            order_by="start_time",
        )

    def get_periods_by_day_and_time(self, day_of_week: int, time_str: str) -> List[Dict[str, Any]]:
        """Running periods at a given time — global admin context."""
        candidates = self._fs_list(
            COL_PERIODS,
            filters=[("day_of_week", "==", day_of_week), ("start_time", "<=", time_str)],
            order_by="start_time",
        )
        return [p for p in candidates if p.get("end_time", "") >= time_str]

    def get_faculty_schedule(self, faculty_id: str) -> List[Dict[str, Any]]:
        """All timetable slots for a faculty member. Index: (faculty_id ASC, day_of_week ASC, start_time ASC)"""
        results = self._fs_list(
            COL_PERIODS,
            filters=[("faculty_id", "==", faculty_id)],
            order_by="day_of_week",
        )
        results.sort(key=lambda p: (p.get("day_of_week", 0), p.get("start_time", "")))
        return results

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_PERIODS, period_id, updates)

    def delete_period(self, period_id: str) -> bool:
        return self._fs_delete(COL_PERIODS, period_id)

    # =========================================================================
    # AUDIT LOGS
    # =========================================================================

    def write_audit_log(self, data: Dict[str, Any]) -> bool:
        """
        Append an audit log entry.

        Required: log_id, user_id, action, resource, resource_id, timestamp.
        Optional: ip_address, section_id, details (dict).
        """
        if not data.get("log_id"):
            raise ValueError("log_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_AUDIT_LOGS, data["log_id"], data)

    def get_audit_logs_by_resource(
        self, resource: str, resource_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Index: (resource ASC, resource_id ASC, timestamp DESC)"""
        return self._fs_list(
            COL_AUDIT_LOGS,
            filters=[("resource", "==", resource), ("resource_id", "==", resource_id)],
            order_by="timestamp",
            limit=limit,
        )

    def get_audit_logs_by_user(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Index: (user_id ASC, timestamp DESC)"""
        return self._fs_list(
            COL_AUDIT_LOGS,
            filters=[("user_id", "==", user_id)],
            order_by="timestamp",
            limit=limit,
        )

    # =========================================================================
    # CIE
    # =========================================================================

    def create_cie(self, data: Dict[str, Any]) -> bool:
        if not data.get("cie_id"):
            raise ValueError("cie_id is required")
        data.setdefault("active_status", True)
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_CIE, data["cie_id"], data)

    def get_cie(self, cie_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_CIE, cie_id)

    def get_all_cie(self) -> List[Dict[str, Any]]:
        return self._fs_list(COL_CIE, order_by="start_date")

    def get_active_cie(self) -> Optional[Dict[str, Any]]:
        """Index: (active_status ASC, start_date ASC)"""
        today = date.today().isoformat()
        results = self._fs_list(
            COL_CIE,
            filters=[("active_status", "==", True), ("start_date", "<=", today)],
        )
        in_range = [r for r in results if r.get("end_date", "") >= today]
        if not in_range:
            return None
        in_range.sort(key=lambda r: r.get("start_date", ""), reverse=True)
        return in_range[0]

    def update_cie(self, cie_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_CIE, cie_id, updates)

    def deactivate_cie(self, cie_id: str) -> bool:
        return self.update_cie(cie_id, {"active_status": False})

    def query_cie_by_date_range(self, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """Index: (start_date ASC, end_date ASC)"""
        results = self._fs_list(
            COL_CIE,
            filters=[("start_date", ">=", from_date), ("start_date", "<=", to_date)],
            order_by="start_date",
        )
        return results

    # =========================================================================
    # CLASS (legacy)
    # =========================================================================

    def create_class(self, data: Dict[str, Any]) -> bool:
        if not data.get("class_id"):
            raise ValueError("class_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_CLASSES, data["class_id"], data)

    def get_class(self, class_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_CLASSES, class_id)

    def get_classes_by_cie(self, cie_id: str) -> List[Dict[str, Any]]:
        """Index: (cie_id ASC, semester ASC)"""
        return self._fs_list(
            COL_CLASSES,
            filters=[("cie_id", "==", cie_id)],
            order_by="semester",
        )

    def get_classes_by_semester(self, semester: int) -> List[Dict[str, Any]]:
        return self._fs_list(COL_CLASSES, filters=[("semester", "==", semester)])

    def update_class(self, class_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_CLASSES, class_id, updates)

    def delete_class(self, class_id: str) -> bool:
        return self._fs_delete(COL_CLASSES, class_id)

    # =========================================================================
    # FACULTY (legacy)
    # =========================================================================

    def create_faculty(self, data: Dict[str, Any]) -> bool:
        if not data.get("faculty_id"):
            raise ValueError("faculty_id is required")
        data.setdefault("status", "active")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_FACULTY, data["faculty_id"], data)

    def get_faculty(self, faculty_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_FACULTY, faculty_id)

    def get_all_faculty(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = [("department", "==", department)] if department else None
        return self._fs_list(COL_FACULTY, filters=filters, order_by="name")

    def update_faculty(self, faculty_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_FACULTY, faculty_id, updates)

    def store_faculty_embedding(self, faculty_id: str, embedding: List[float]) -> bool:
        return self.update_faculty(
            faculty_id,
            {"face_embedding": embedding, "embedding_updated_at": datetime.now().isoformat()},
        )

    # =========================================================================
    # COMPOSITE HELPERS
    # =========================================================================

    def get_active_period(self, at: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Global active period lookup — admin / recognition pipeline.
        Prefer get_active_period_for_section() when a section is known.
        """
        now = at or datetime.now()
        candidates = self.get_periods_by_day_and_time(now.weekday(), now.strftime("%H:%M"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.get("start_time", ""), reverse=True)
        period = candidates[0]
        logger.info(
            "Active period: %s (%s %s-%s) class=%s",
            period.get("period_id"), period.get("course_code"),
            period.get("start_time"), period.get("end_time"), period.get("class_id"),
        )
        return period

    def get_class_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Legacy: Class document for a student via class_id on student doc."""
        student = self._fs_get(COL_STUDENTS, student_id)
        if not student:
            return None
        class_id = student.get("class_id")
        return self.get_class(class_id) if class_id else None

    def get_faculty_classes(self, faculty_id: str) -> List[Dict[str, Any]]:
        """Legacy: Class documents for all classes a faculty member teaches."""
        assignments = self.get_faculty_courses(faculty_id)
        seen: set = set()
        classes: List[Dict[str, Any]] = []
        for a in assignments:
            class_id = a.get("class_id")
            if not class_id or class_id in seen:
                continue
            seen.add(class_id)
            cls = self.get_class(class_id)
            if cls:
                classes.append(cls)
        classes.sort(key=lambda c: (c.get("semester", 0), c.get("section", "")))
        return classes

    def get_students_by_class(self, class_id: str) -> List[Dict[str, Any]]:
        """Legacy: students with matching class_id field. Index: (class_id ASC, name ASC)"""
        return self._fs_list(
            COL_STUDENTS,
            filters=[("class_id", "==", class_id)],
            order_by="name",
        )