"""
services/embedding_scope_service.py
──────────────────────────────────────────────────────────────────────────────
Resolves the face-embedding search scope based on caller identity.

Two modes
---------
SELF_VERIFY  (student)
    Search space = exactly the authenticated student's stored embeddings.
    No Firebase full-scan. O(1) lookup.

SECTION_ROSTER (teacher)
    Search space = embeddings for every student enrolled in the teacher's
    currently active section period.
    Cached for ROSTER_CACHE_TTL seconds and busted on bulk_attendance events.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

ROSTER_CACHE_TTL = 30          # seconds — teacher roster cache lifetime
SELF_VERIFY_TTL  = 300         # seconds — student's own embeddings cache


@dataclass
class EmbeddingScope:
    """
    Resolved search scope ready for the matcher.

    candidates : list of (student_dict, np.ndarray[]) pairs
                 Each entry is one student and ALL their registered embeddings.
    mode        : "self_verify" | "section_roster"
    section_id  : class_id that was resolved (may be "" for self_verify)
    resolved_at : monotonic timestamp for TTL tracking
    """
    candidates:   List[Tuple[Dict[str, Any], List[np.ndarray]]]
    mode:         str
    section_id:   str
    resolved_at:  float = field(default_factory=time.monotonic)


class EmbeddingScopeService:
    """
    Resolves and caches face-embedding search scopes.

    Injected with the same FirebaseService used by attendance.py.
    """

    def __init__(self, firebase_service: Any) -> None:
        self._fb = firebase_service
        # Cache keyed by student_id (self_verify) or section_id (roster)
        self._cache: Dict[str, Tuple[float, EmbeddingScope]] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def resolve_student_scope(self, student_id: str) -> EmbeddingScope:
        """
        SELF_VERIFY mode: only this student's embeddings.
        Cache per student_id for SELF_VERIFY_TTL.
        """
        cache_key = f"sv_{student_id}"
        cached = self._get_cached(cache_key, SELF_VERIFY_TTL)
        if cached:
            return cached

        student = self._fb.get_student(student_id)
        if not student:
            return EmbeddingScope(candidates=[], mode="self_verify", section_id="")

        from services.firebase_service import FirebaseService
        embeddings = FirebaseService.get_all_embeddings(student)
        scope = EmbeddingScope(
            candidates=[(student, embeddings)] if embeddings else [],
            mode="self_verify",
            section_id="",
        )
        self._set_cached(cache_key, scope)
        logger.debug("SELF_VERIFY scope: student=%s, %d embedding(s)", student_id, len(embeddings))
        return scope

    def resolve_section_scope(
        self, section_id: str, period_id: Optional[str] = None
    ) -> EmbeddingScope:
        """
        SECTION_ROSTER mode: all enrolled students in section_id.
        Cache per section_id for ROSTER_CACHE_TTL.
        Falls back to the teacher's active period if section_id is unknown.
        """
        cache_key = f"sr_{section_id}"
        cached = self._get_cached(cache_key, ROSTER_CACHE_TTL)
        if cached:
            return cached

        students = self._load_section_students(section_id)
        from services.firebase_service import FirebaseService
        candidates = []
        for stu in students:
            embs = FirebaseService.get_all_embeddings(stu)
            if embs:
                candidates.append((stu, embs))

        scope = EmbeddingScope(
            candidates=candidates,
            mode="section_roster",
            section_id=section_id,
        )
        self._set_cached(cache_key, scope)
        logger.debug(
            "SECTION_ROSTER scope: section=%s, %d students with embeddings",
            section_id, len(candidates),
        )
        return scope

    def invalidate_section(self, section_id: str) -> None:
        """Call this when bulk_attendance or roster-change events fire."""
        key = f"sr_{section_id}"
        self._cache.pop(key, None)
        logger.debug("Invalidated section scope cache: %s", section_id)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _load_section_students(self, section_id: str) -> List[Dict[str, Any]]:
        try:
            db = getattr(self._fb, "firestore_db", None) or getattr(self._fb, "_firestore", None)
            if db is None:
                return []
            from google.cloud.firestore_v1 import FieldFilter
            docs = (
                db.collection("students")
                .where(filter=FieldFilter("class_id", "==", section_id))
                .where(filter=FieldFilter("active_status", "==", True))
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception as exc:
            logger.error("Section student load failed for %s: %s", section_id, exc)
            return []

    def _get_cached(self, key: str, ttl: float) -> Optional[EmbeddingScope]:
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < ttl:
            return entry[1]
        return None

    def _set_cached(self, key: str, scope: EmbeddingScope) -> None:
        self._cache[key] = (time.monotonic(), scope)


# ── Module-level singleton ─────────────────────────────────────────────────────

_scope_service: Optional[EmbeddingScopeService] = None


def get_scope_service() -> Optional[EmbeddingScopeService]:
    return _scope_service


def init_scope_service(firebase_service: Any) -> EmbeddingScopeService:
    global _scope_service
    _scope_service = EmbeddingScopeService(firebase_service)
    logger.info("EmbeddingScopeService initialised.")
    return _scope_service
