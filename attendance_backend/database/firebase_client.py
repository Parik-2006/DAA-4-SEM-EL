"""
Firebase Database Client.

Provides connection and initialization for both:
  - Firebase Realtime Database  (legacy path — unchanged for backward compat)
  - Cloud Firestore             (new path — all CIE/Class/Period/Faculty data)

Architecture note
-----------------
The existing attendance records written via ``firebase_service.py`` already
live in Firestore collections "students" and "attendance".  Those collections
are untouched.  New collections (cie, classes, periods, course_assignments,
faculty) are also stored in Firestore and use composite indexes for the
day/time and faculty queries.

Composite index definitions are in ``database/firestore.indexes.json`` —
deploy them once with ``firebase deploy --only firestore:indexes``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, date, time as dtime
from pathlib import Path
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


# ── Collection name constants ──────────────────────────────────────────────────
# Kept here so query methods never have magic strings.

COL_STUDENTS          = FIREBASE_COLLECTIONS["students"]
COL_ATTENDANCE        = FIREBASE_COLLECTIONS["attendance"]
COL_CIE               = FIREBASE_COLLECTIONS.get("cie", "cie")
COL_CLASSES           = FIREBASE_COLLECTIONS.get("classes", "classes")
COL_PERIODS           = FIREBASE_COLLECTIONS.get("periods", "periods")
COL_COURSE_ASSIGNMENTS = FIREBASE_COLLECTIONS.get("course_assignments", "course_assignments")
COL_FACULTY           = FIREBASE_COLLECTIONS.get("faculty", "faculty")


# ── FirebaseClient ─────────────────────────────────────────────────────────────

class FirebaseClient:
    """
    Dual Firebase client: Realtime Database (legacy) + Firestore (new).

    Singleton.  Call ``FirebaseClient()`` anywhere after the first
    ``_initialize_connection()`` and you get the same instance.

    Realtime Database
    -----------------
    All existing RTDB methods (``write_data``, ``read_data``, …) are unchanged.
    They are the authoritative path for old code that calls them directly.

    Firestore
    ---------
    All CIE / Class / Period / CourseAssignment / Faculty CRUD goes through
    Firestore so we can use composite indexes and range queries.  The
    ``self.fs`` attribute is the ``google.cloud.firestore.Client`` instance.
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

    # ── Initialization ─────────────────────────────────────────────────────────

    def _initialize_connection(self) -> None:
        """
        Initialize both RTDB and Firestore connections.

        RTDB init is kept unchanged for backward compatibility.
        Firestore is layered on top using the same service-account credentials.
        """
        try:
            logger.info("Initializing Firebase connection…")
            cred_path = self.settings.get_credentials_path()
            if not cred_path.exists():
                raise FileNotFoundError(
                    f"Firebase credentials file not found: {cred_path}"
                )

            cred = credentials.Certificate(str(cred_path))

            # ── Realtime Database (unchanged) ──────────────────────────────
            if not firebase_admin._apps:
                initialize_app(cred, {"databaseURL": self.settings.firebase_database_url})
            self.db = db.reference()
            logger.info("✓ Realtime Database initialised")

            # ── Firestore (new) ────────────────────────────────────────────
            if _FIRESTORE_AVAILABLE:
                raw_cred = credentials.Certificate(str(cred_path))
                self.fs = _firestore.Client(
                    project=raw_cred.project_id,
                    credentials=raw_cred.get_credential(),
                )
                logger.info("✓ Firestore initialised (project: %s)", raw_cred.project_id)
            else:
                logger.warning(
                    "google-cloud-firestore not installed — "
                    "CIE/Class/Period features will be unavailable"
                )

            FirebaseClient._initialized = True
            logger.info("Firebase connections ready")

        except FileNotFoundError as exc:
            logger.error("Credentials file error: %s", exc)
            raise RuntimeError(f"Firebase initialization failed: {exc}")
        except FirebaseError as exc:
            logger.error("Firebase error: %s", exc)
            raise RuntimeError(f"Firebase initialization failed: {exc}")
        except Exception as exc:
            logger.error("Unexpected Firebase init error: %s", exc)
            raise RuntimeError(f"Firebase initialization failed: {exc}")

    def _require_fs(self) -> Any:
        """Return the Firestore client or raise if unavailable."""
        if self.fs is None:
            raise RuntimeError(
                "Firestore client not available. "
                "Install google-cloud-firestore and restart."
            )
        return self.fs

    # =========================================================================
    # REALTIME DATABASE — unchanged legacy methods
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
            if data is None:
                logger.debug("RTDB no data at %s", path)
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
            logger.debug("RTDB update → %s", path)
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

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "rtdb_url": self.settings.firebase_database_url,
            "firestore_available": self.fs is not None,
            "credentials_path": str(self.settings.get_credentials_path()),
        }

    # =========================================================================
    # FIRESTORE — internal helpers
    # =========================================================================

    def _fs_set(self, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
        """Create or overwrite a Firestore document."""
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
        Query a Firestore collection with optional equality/range filters.

        ``filters`` is a list of (field, operator, value) triples.
        Operators: ``==``, ``<``, ``<=``, ``>``, ``>=``, ``in``, ``array-contains``.

        Composite-index-backed queries (day_of_week + start_time, etc.) work
        because the index file declares them.  See firestore.indexes.json.
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
    # CIE — Continuous Internal Evaluation
    # =========================================================================

    def create_cie(self, data: Dict[str, Any]) -> bool:
        """
        Create a CIE document.

        Required fields: cie_id, name, start_date (ISO str), end_date (ISO str).
        Optional fields: active_status (bool, default True), description, metadata.

        Example
        -------
        >>> client.create_cie({
        ...     "cie_id": "CIE2026-1",
        ...     "name": "CIE-1 April 2026",
        ...     "start_date": "2026-04-01",
        ...     "end_date": "2026-04-15",
        ...     "active_status": True,
        ... })
        """
        cie_id = data.get("cie_id")
        if not cie_id:
            raise ValueError("cie_id is required")
        data.setdefault("active_status", True)
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_CIE, cie_id, data)

    def get_cie(self, cie_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single CIE by ID."""
        return self._fs_get(COL_CIE, cie_id)

    def get_all_cie(self) -> List[Dict[str, Any]]:
        """Return all CIE documents ordered by start_date descending."""
        return self._fs_list(COL_CIE, order_by="start_date")

    def get_active_cie(self) -> Optional[Dict[str, Any]]:
        """
        Return the currently active CIE (active_status == True and date in range).

        If multiple match, the most recently started one is returned.
        """
        today = date.today().isoformat()
        results = self._fs_list(
            COL_CIE,
            filters=[
                ("active_status", "==", True),
                ("start_date", "<=", today),
            ],
        )
        # Python-side filter: end_date >= today
        # (Firestore only allows one inequality field per query)
        in_range = [r for r in results if r.get("end_date", "") >= today]
        if not in_range:
            return None
        # Most recently started first
        in_range.sort(key=lambda r: r.get("start_date", ""), reverse=True)
        return in_range[0]

    def update_cie(self, cie_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_CIE, cie_id, updates)

    def deactivate_cie(self, cie_id: str) -> bool:
        return self.update_cie(cie_id, {"active_status": False})

    def query_cie_by_date_range(
        self, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """
        Return CIEs whose start_date falls within [from_date, to_date].
        Requires composite index: (start_date ASC).
        """
        results = self._fs_list(
            COL_CIE,
            filters=[
                ("start_date", ">=", from_date),
                ("start_date", "<=", to_date),
            ],
            order_by="start_date",
        )
        return results

    # =========================================================================
    # CLASS
    # =========================================================================

    def create_class(self, data: Dict[str, Any]) -> bool:
        """
        Create a Class document.

        Required fields: class_id, cie_id, semester, section, classroom_name.
        Optional fields: capacity (int), course_codes (list), metadata.

        Example
        -------
        >>> client.create_class({
        ...     "class_id": "CS-A-SEM6",
        ...     "cie_id": "CIE2026-1",
        ...     "semester": 6,
        ...     "section": "A",
        ...     "classroom_name": "Lab Block 201",
        ...     "capacity": 60,
        ... })
        """
        class_id = data.get("class_id")
        if not class_id:
            raise ValueError("class_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        return self._fs_set(COL_CLASSES, class_id, data)

    def get_class(self, class_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_CLASSES, class_id)

    def get_classes_by_cie(self, cie_id: str) -> List[Dict[str, Any]]:
        """
        Return all classes belonging to a CIE.
        Requires composite index: (cie_id ASC, semester ASC).
        """
        return self._fs_list(
            COL_CLASSES,
            filters=[("cie_id", "==", cie_id)],
            order_by="semester",
        )

    def get_classes_by_semester(self, semester: int) -> List[Dict[str, Any]]:
        return self._fs_list(
            COL_CLASSES,
            filters=[("semester", "==", semester)],
        )

    def update_class(self, class_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_CLASSES, class_id, updates)

    def delete_class(self, class_id: str) -> bool:
        return self._fs_delete(COL_CLASSES, class_id)

    # =========================================================================
    # PERIOD / TIMETABLE
    # =========================================================================

    def create_period(self, data: Dict[str, Any]) -> bool:
        """
        Create a Period (timetable slot) document.

        Required fields
        ---------------
        period_id       Unique ID, e.g. ``"CS-A-SEM6_MON_0900"``
        class_id        FK → classes
        day_of_week     int 0–6 (0 = Monday … 6 = Sunday)
        start_time      "HH:MM"  24-hour string
        end_time        "HH:MM"  24-hour string
        course_code     e.g. "CS401"
        course_name     e.g. "Machine Learning"
        faculty_id      FK → faculty

        Optional fields
        ---------------
        is_lab_class    bool (default False)
        duration_minutes int  (derived from start/end if omitted)
        room_override   str  (overrides class classroom_name for this slot)
        metadata        dict

        Composite indexes required (see firestore.indexes.json)
        --------------------------------------------------------
        - (day_of_week ASC, start_time ASC)          ← get_active_period()
        - (class_id ASC, day_of_week ASC, start_time ASC)  ← get_timetable_by_class()
        - (faculty_id ASC, day_of_week ASC)           ← get_faculty_schedule()
        """
        period_id = data.get("period_id")
        if not period_id:
            raise ValueError("period_id is required")
        data.setdefault("is_lab_class", False)
        data.setdefault("created_at", datetime.now().isoformat())

        # Auto-compute duration_minutes if not provided
        if "duration_minutes" not in data:
            try:
                sh, sm = map(int, data["start_time"].split(":"))
                eh, em = map(int, data["end_time"].split(":"))
                data["duration_minutes"] = (eh * 60 + em) - (sh * 60 + sm)
            except Exception:
                pass

        return self._fs_set(COL_PERIODS, period_id, data)

    def get_period(self, period_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_PERIODS, period_id)

    def get_timetable_by_class(self, class_id: str) -> List[Dict[str, Any]]:
        """
        Return all periods for a class, ordered by day then start time.

        Composite index required: (class_id ASC, day_of_week ASC, start_time ASC)
        """
        results = self._fs_list(
            COL_PERIODS,
            filters=[("class_id", "==", class_id)],
            order_by="day_of_week",
        )
        # Secondary sort by start_time in Python (Firestore only supports
        # one order_by when using equality filter on a different field)
        results.sort(key=lambda p: (p.get("day_of_week", 0), p.get("start_time", "")))
        return results

    def get_periods_by_day(self, day_of_week: int) -> List[Dict[str, Any]]:
        """
        Return all periods scheduled on a given day, ordered by start_time.

        day_of_week: 0 = Monday … 6 = Sunday.
        Composite index required: (day_of_week ASC, start_time ASC)
        """
        return self._fs_list(
            COL_PERIODS,
            filters=[("day_of_week", "==", day_of_week)],
            order_by="start_time",
        )

    def get_periods_by_day_and_time(
        self, day_of_week: int, time_str: str
    ) -> List[Dict[str, Any]]:
        """
        Return periods on ``day_of_week`` whose start_time <= ``time_str``.

        The Python-side filter then removes periods whose end_time < time_str,
        leaving only currently-running periods.

        This is the building block used by ``get_active_period()``.

        Firestore limitation
        --------------------
        Firestore does not support two inequality operators on different fields
        in a single query.  We apply the inequality on start_time in Firestore
        and filter end_time in Python.

        Composite index required: (day_of_week ASC, start_time ASC)
        """
        candidates = self._fs_list(
            COL_PERIODS,
            filters=[
                ("day_of_week", "==", day_of_week),
                ("start_time",  "<=", time_str),
            ],
            order_by="start_time",
        )
        # Python-side: keep only periods that haven't ended yet
        active = [p for p in candidates if p.get("end_time", "") >= time_str]
        return active

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_PERIODS, period_id, updates)

    def delete_period(self, period_id: str) -> bool:
        return self._fs_delete(COL_PERIODS, period_id)

    def get_faculty_schedule(self, faculty_id: str) -> List[Dict[str, Any]]:
        """
        Return all timetable slots assigned to a faculty member.

        Composite index required: (faculty_id ASC, day_of_week ASC, start_time ASC)
        """
        results = self._fs_list(
            COL_PERIODS,
            filters=[("faculty_id", "==", faculty_id)],
            order_by="day_of_week",
        )
        results.sort(key=lambda p: (p.get("day_of_week", 0), p.get("start_time", "")))
        return results

    # =========================================================================
    # COURSE ASSIGNMENT
    # =========================================================================

    def create_course_assignment(self, data: Dict[str, Any]) -> bool:
        """
        Create a CourseAssignment document.

        Required fields: assignment_id, faculty_id, course_id, class_id, semester.
        Optional fields: academic_year, is_primary (bool), metadata.

        Example
        -------
        >>> client.create_course_assignment({
        ...     "assignment_id": "FAC01_CS401_CS-A-SEM6",
        ...     "faculty_id": "FAC01",
        ...     "course_id": "CS401",
        ...     "class_id": "CS-A-SEM6",
        ...     "semester": 6,
        ... })
        """
        assignment_id = data.get("assignment_id")
        if not assignment_id:
            raise ValueError("assignment_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        data.setdefault("is_primary", True)
        return self._fs_set(COL_COURSE_ASSIGNMENTS, assignment_id, data)

    def get_course_assignment(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_COURSE_ASSIGNMENTS, assignment_id)

    def get_faculty_courses(self, faculty_id: str, semester: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Return all course assignments for a faculty member.

        If ``semester`` is given, filters further.
        Composite index required: (faculty_id ASC, semester ASC)
        """
        filters = [("faculty_id", "==", faculty_id)]
        if semester is not None:
            filters.append(("semester", "==", semester))
        return self._fs_list(COL_COURSE_ASSIGNMENTS, filters=filters, order_by="semester")

    def get_class_faculty(self, class_id: str) -> List[Dict[str, Any]]:
        """Return all faculty assigned to a class."""
        return self._fs_list(
            COL_COURSE_ASSIGNMENTS,
            filters=[("class_id", "==", class_id)],
        )

    def delete_course_assignment(self, assignment_id: str) -> bool:
        return self._fs_delete(COL_COURSE_ASSIGNMENTS, assignment_id)

    # =========================================================================
    # FACULTY
    # =========================================================================

    def create_faculty(self, data: Dict[str, Any]) -> bool:
        """
        Create or overwrite a Faculty document.

        Required fields: faculty_id, name, email.
        Optional fields: department, specialization, phone, face_embedding
                         (list[float] — same 128-dim FaceNet vector as students),
                         metadata.

        face_embedding is stored in the same format as student embeddings so
        the existing ``_match_embedding_sync`` and FAISS pipelines can
        optionally recognise faculty faces too.

        Example
        -------
        >>> client.create_faculty({
        ...     "faculty_id": "FAC01",
        ...     "name": "Dr. Priya Sharma",
        ...     "email": "priya@college.edu",
        ...     "department": "Computer Science",
        ...     "specialization": "Machine Learning",
        ... })
        """
        faculty_id = data.get("faculty_id")
        if not faculty_id:
            raise ValueError("faculty_id is required")
        data.setdefault("created_at", datetime.now().isoformat())
        data.setdefault("status", "active")
        return self._fs_set(COL_FACULTY, faculty_id, data)

    def get_faculty(self, faculty_id: str) -> Optional[Dict[str, Any]]:
        return self._fs_get(COL_FACULTY, faculty_id)

    def get_all_faculty(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = []
        if department:
            filters.append(("department", "==", department))
        return self._fs_list(COL_FACULTY, filters=filters or None, order_by="name")

    def update_faculty(self, faculty_id: str, updates: Dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.now().isoformat()
        return self._fs_update(COL_FACULTY, faculty_id, updates)

    def store_faculty_embedding(
        self, faculty_id: str, embedding: List[float]
    ) -> bool:
        """
        Store or update a faculty member's face embedding.

        Stored as ``face_embedding`` (list[float]) — same schema used for
        students — so the recognition pipeline requires no changes.
        """
        return self.update_faculty(
            faculty_id,
            {
                "face_embedding": embedding,
                "embedding_updated_at": datetime.now().isoformat(),
            },
        )

    # =========================================================================
    # COMPOSITE HELPER METHODS
    # =========================================================================

    def get_active_period(
        self,
        at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the timetable period that is currently running.

        Algorithm
        ---------
        1. Determine day_of_week (0=Mon … 6=Sun) and current "HH:MM" string.
        2. Query Firestore: day_of_week == today AND start_time <= now.
           (Composite index: day_of_week ASC, start_time ASC)
        3. Python filter: keep only periods where end_time >= now.
        4. Return the period with the latest start_time (most specific match).

        Parameters
        ----------
        at
            Datetime to check against.  Defaults to ``datetime.now()``.
            Pass an explicit value for testing or historical lookups.

        Returns
        -------
        Period dict or None if no class is running right now.
        """
        now = at or datetime.now()
        day_of_week = now.weekday()           # 0 = Monday
        time_str = now.strftime("%H:%M")

        candidates = self.get_periods_by_day_and_time(day_of_week, time_str)
        if not candidates:
            logger.debug(
                "get_active_period: no running period on day=%d at %s",
                day_of_week, time_str,
            )
            return None

        # Most recently started period wins (handles overlapping lab slots)
        candidates.sort(key=lambda p: p.get("start_time", ""), reverse=True)
        period = candidates[0]
        logger.info(
            "Active period: %s (%s %s–%s) class=%s",
            period.get("period_id"),
            period.get("course_code"),
            period.get("start_time"),
            period.get("end_time"),
            period.get("class_id"),
        )
        return period

    def get_class_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the Class document that a student belongs to.

        The student document (in the "students" Firestore collection already
        maintained by ``firebase_service.py``) must have a ``class_id`` field.
        This method reads that field and then fetches the corresponding Class
        document.

        Returns None if the student has no class_id or the class doesn't exist.
        """
        try:
            student_doc = self._fs_get(COL_STUDENTS, student_id)
            if student_doc is None:
                logger.warning("get_class_by_student_id: student %s not found", student_id)
                return None

            class_id = student_doc.get("class_id")
            if not class_id:
                logger.debug(
                    "get_class_by_student_id: student %s has no class_id", student_id
                )
                return None

            return self.get_class(class_id)

        except Exception as exc:
            logger.error("get_class_by_student_id error for %s: %s", student_id, exc)
            return None

    def get_faculty_classes(self, faculty_id: str) -> List[Dict[str, Any]]:
        """
        Return all Class documents for classes that a faculty member teaches.

        Walks the CourseAssignment collection to find all class_ids for this
        faculty, then fetches each Class document.  Duplicates are removed
        (a faculty may teach multiple courses in the same class).

        Returns a list of Class dicts sorted by semester then section.
        """
        try:
            assignments = self.get_faculty_courses(faculty_id)
            seen_class_ids: set = set()
            classes: List[Dict[str, Any]] = []

            for assignment in assignments:
                class_id = assignment.get("class_id")
                if not class_id or class_id in seen_class_ids:
                    continue
                seen_class_ids.add(class_id)
                cls = self.get_class(class_id)
                if cls:
                    classes.append(cls)

            classes.sort(
                key=lambda c: (c.get("semester", 0), c.get("section", ""))
            )
            logger.info(
                "get_faculty_classes: faculty %s teaches %d class(es)", faculty_id, len(classes)
            )
            return classes

        except Exception as exc:
            logger.error("get_faculty_classes error for %s: %s", faculty_id, exc)
            return []

    def get_students_by_class(self, class_id: str) -> List[Dict[str, Any]]:
        """
        Return all students that belong to a given class.

        Requires composite index: (class_id ASC) on the students collection.
        """
        return self._fs_list(
            COL_STUDENTS,
            filters=[("class_id", "==", class_id)],
            order_by="name",
        )

    def get_attendance_for_period(
        self,
        period_id: str,
        date_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return attendance records for a specific period on a given date.

        Attendance records written by ``firebase_service.py`` include a
        ``metadata.period_id`` field when marked via the RTSP pipeline.
        This method queries the existing attendance collection without
        changing its structure.

        date_str: ISO date string "YYYY-MM-DD".  Defaults to today.
        """
        date_str = date_str or date.today().isoformat()
        return self._fs_list(
            COL_ATTENDANCE,
            filters=[
                ("date", "==", date_str),
                ("metadata.period_id", "==", period_id),
            ],
        )
