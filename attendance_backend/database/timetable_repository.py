"""
database/timetable_repository.py

Repository helpers for timetable-driven attendance checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from google.cloud.firestore_v1 import FieldFilter


class TimetableRepository:
    def __init__(self, firestore_db: Any) -> None:
        self._db = firestore_db

    def get_period_by_id(self, period_id: str) -> Optional[Dict[str, Any]]:
        doc = self._db.collection("periods").document(period_id).get()
        return doc.to_dict() if doc.exists else None

    def get_teacher_periods_for_day(
        self,
        faculty_id: str,
        day_of_week: int,
    ) -> List[Dict[str, Any]]:
        docs = (
            self._db.collection("periods")
            .where(filter=FieldFilter("faculty_id", "==", faculty_id))
            .where(filter=FieldFilter("day_of_week", "==", day_of_week))
            .where(filter=FieldFilter("active_status", "==", True))
            .order_by("start_time")
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_active_teacher_periods(
        self,
        faculty_id: str,
        day_of_week: int,
        now_hhmm: str,
    ) -> List[Dict[str, Any]]:
        docs = (
            self._db.collection("periods")
            .where(filter=FieldFilter("faculty_id", "==", faculty_id))
            .where(filter=FieldFilter("day_of_week", "==", day_of_week))
            .where(filter=FieldFilter("active_status", "==", True))
            .where(filter=FieldFilter("start_time", "<=", now_hhmm))
            .order_by("start_time")
            .stream()
        )
        candidates = [doc.to_dict() for doc in docs]
        return [p for p in candidates if p.get("end_time", "00:00") >= now_hhmm]

    def get_teacher_assigned_classes(self, faculty_id: str) -> List[str]:
        docs = (
            self._db.collection("course_assignments")
            .where(filter=FieldFilter("faculty_id", "==", faculty_id))
            .where(filter=FieldFilter("active_status", "==", True))
            .stream()
        )
        class_ids = []
        for doc in docs:
            item = doc.to_dict()
            class_id = item.get("class_id")
            if class_id:
                class_ids.append(class_id)
        return sorted(set(class_ids))
