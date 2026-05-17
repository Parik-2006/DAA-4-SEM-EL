"""
services/identity_context_service.py
─────────────────────────────────────
Resolves the correct IdentityScope from a JWT UserContext.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.identity_context import IdentityScopeType, ScopeTarget
from services.auth_service import UserContext

logger = logging.getLogger(__name__)


class IdentityContextService:

    def __init__(self, firebase_client=None, period_detection_service=None) -> None:
        self._fb = firebase_client
        self._pds = period_detection_service

    def resolve(self, user: UserContext, period_id: Optional[str] = None) -> ScopeTarget:
        now_iso = datetime.now().isoformat()
        if user.role == "student":
            return self._resolve_self(user, now_iso)
        if user.role == "teacher":
            return self._resolve_section(user, period_id, now_iso)
        return ScopeTarget(
            scope_type=IdentityScopeType.GLOBAL,
            student_ids=[],
            resolved_by=user.user_id,
            resolved_at=now_iso,
        )

    def _resolve_self(self, user: UserContext, now_iso: str) -> ScopeTarget:
        return ScopeTarget(
            scope_type=IdentityScopeType.SELF,
            student_ids=[user.user_id],
            resolved_by=user.user_id,
            resolved_at=now_iso,
        )

    def _resolve_section(self, user: UserContext, period_id: Optional[str], now_iso: str) -> ScopeTarget:
        section_id: Optional[str] = None
        active_period_id: Optional[str] = period_id

        if not active_period_id and self._pds is not None:
            try:
                payload = self._pds.get_active_period()
                if payload:
                    for p in payload.get("active_periods", []):
                        if p.get("faculty_id") == user.user_id:
                            active_period_id = p.get("period_id")
                            break
            except Exception as exc:
                logger.warning("Could not query period detection service: %s", exc)

        if active_period_id:
            section_id, student_ids = self._students_from_period(active_period_id)
            if student_ids:
                return ScopeTarget(
                    scope_type=IdentityScopeType.SECTION,
                    student_ids=student_ids,
                    resolved_by=user.user_id,
                    resolved_at=now_iso,
                    section_id=section_id,
                    period_id=active_period_id,
                )

        if getattr(user, "assigned_sections", None):
            student_ids = self._students_from_sections(user.assigned_sections)
            if student_ids:
                logger.info(
                    "Teacher %s: using assigned_sections fallback (%d students)",
                    user.user_id, len(student_ids),
                )
                return ScopeTarget(
                    scope_type=IdentityScopeType.SECTION,
                    student_ids=student_ids,
                    resolved_by=user.user_id,
                    resolved_at=now_iso,
                )

        logger.warning("Teacher %s: no section context found — using GLOBAL scope.", user.user_id)
        return ScopeTarget(
            scope_type=IdentityScopeType.GLOBAL,
            student_ids=[],
            resolved_by=user.user_id,
            resolved_at=now_iso,
        )

    def _students_from_period(self, period_id: str):
        section_id: Optional[str] = None
        student_ids: List[str] = []
        if not self._fb:
            return section_id, student_ids
        try:
            db = getattr(self._fb, "firestore_db", None) or getattr(self._fb, "_firestore", None)
            if db:
                pd = db.collection("periods").document(period_id).get()
                if pd.exists:
                    period = pd.to_dict()
                    section_id = period.get("class_id") or period.get("section_id")
                    if section_id:
                        student_ids = self._roster_from_section(db, section_id)
        except Exception as exc:
            logger.warning("Could not load students for period %s: %s", period_id, exc)
        return section_id, student_ids

    def _roster_from_section(self, db: Any, section_id: str) -> List[str]:
        try:
            docs = (
                db.collection("enrollments")
                .where("section_id", "==", section_id)
                .stream()
            )
            ids = [d.to_dict().get("student_id") for d in docs]
            ids = [i for i in ids if i]
            if ids:
                return ids
            cls_doc = db.collection("classes").document(section_id).get()
            if cls_doc.exists:
                return cls_doc.to_dict().get("student_ids", [])
        except Exception as exc:
            logger.warning("Roster fetch failed for %s: %s", section_id, exc)
        return []

    def _students_from_sections(self, section_ids: List[str]) -> List[str]:
        all_ids: List[str] = []
        if not self._fb:
            return all_ids
        try:
            db = getattr(self._fb, "firestore_db", None) or getattr(self._fb, "_firestore", None)
            if db:
                for sid in section_ids:
                    all_ids.extend(self._roster_from_section(db, sid))
        except Exception as exc:
            logger.warning("Multi-section roster failed: %s", exc)
        return list(dict.fromkeys(all_ids))
