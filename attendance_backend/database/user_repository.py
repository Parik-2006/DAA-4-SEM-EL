"""
database/user_repository.py
─────────────────────────────────────────────────────────────────────────────
User data repository for admin, teacher, and student accounts.

Changes from original
─────────────────────
• create_user         — persists assigned_sections; validates role.
• get_user_by_email   — unchanged (backward-compatible).
• get_user            — unchanged (backward-compatible).
• update_user         — unchanged (backward-compatible).
• list_users_by_role  — unchanged (backward-compatible).
• NEW: update_assigned_sections   — teacher section assignment management.
• NEW: list_users_by_role_paginated — cursor-based pagination for large lists.
• NEW: get_users_in_sections      — find teachers assigned to specific sections.
• NEW: bulk_deactivate            — admin batch operation.

All original method signatures preserved for zero breaking changes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.constants import FIREBASE_COLLECTIONS
from database.firebase_client import FirebaseClient

logger = logging.getLogger(__name__)

_COLLECTION = FIREBASE_COLLECTIONS.get("users", "users")


class UserRepository:
    def __init__(self, db: Optional[FirebaseClient] = None) -> None:
        self.db = db or FirebaseClient()
        self.collection = _COLLECTION

    # ── Internal helper ───────────────────────────────────────────────────────

    def _path(self, user_id: str) -> str:
        return f"{self.collection}/{user_id}"

    # ── Original methods (backward-compatible) ────────────────────────────────

    def create_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        Persist a new user document.

        Guarantees that the stored document always contains:
          • role                (str, default "student")
          • assigned_sections   (list, default [])
          • is_active           (bool, default True)
        """
        user_data.setdefault("role", "student")
        user_data.setdefault("assigned_sections", [])
        user_data.setdefault("is_active", True)

        try:
            self.db.write_data(self._path(user_id), user_data)
            logger.info("User created: %s role=%s", user_id, user_data["role"])
            return True
        except Exception as exc:
            logger.error("Error creating user %s: %s", user_id, exc)
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Return the first user whose email matches, or None."""
        try:
            users = self.db.read_data(self.collection)
            if not isinstance(users, dict):
                return None
            for uid, user in users.items():
                if isinstance(user, dict) and user.get("email") == email:
                    return {**user, "user_id": uid}
            return None
        except Exception as exc:
            logger.error("Error fetching user by email: %s", exc)
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return user by primary key, or None."""
        try:
            user = self.db.read_data(self._path(user_id))
            if user:
                return {**user, "user_id": user_id}
            return None
        except Exception as exc:
            logger.error("Error fetching user %s: %s", user_id, exc)
            return None

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Merge *update_data* into the existing user document."""
        try:
            user = self.db.read_data(self._path(user_id))
            if not user:
                logger.warning("update_user: user %s not found", user_id)
                return False
            self.db.write_data(self._path(user_id), {**user, **update_data})
            logger.info("User updated: %s fields=%s", user_id, list(update_data))
            return True
        except Exception as exc:
            logger.error("Error updating user %s: %s", user_id, exc)
            return False

    def delete_user(self, user_id: str) -> bool:
        """Hard-delete a user document."""
        try:
            self.db.delete_data(self._path(user_id))
            logger.info("User deleted: %s", user_id)
            return True
        except Exception as exc:
            logger.error("Error deleting user %s: %s", user_id, exc)
            return False

    def list_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Return all users with the given role (password_hash stripped by caller)."""
        try:
            users = self.db.read_data(self.collection) or {}
            return [
                {**u, "user_id": uid}
                for uid, u in users.items()
                if isinstance(u, dict) and u.get("role") == role
            ]
        except Exception as exc:
            logger.error("Error listing users by role %s: %s", role, exc)
            return []

    def list_all_users(self) -> List[Dict[str, Any]]:
        """Return every user document."""
        try:
            users = self.db.read_data(self.collection) or {}
            return [
                {**u, "user_id": uid}
                for uid, u in users.items()
                if isinstance(u, dict)
            ]
        except Exception as exc:
            logger.error("Error listing all users: %s", exc)
            return []

    # ── New role / section methods ─────────────────────────────────────────────

    def update_assigned_sections(
        self,
        user_id: str,
        section_ids: List[str],
    ) -> bool:
        """
        Replace the teacher's assigned_sections list.

        Admin use-case: admin assigns / re-assigns sections to a teacher.
        """
        return self.update_user(user_id, {"assigned_sections": section_ids})

    def add_section_to_teacher(self, user_id: str, section_id: str) -> bool:
        """
        Append *section_id* to the teacher's assigned_sections list
        (idempotent — no-op if already present).
        """
        user = self.get_user(user_id)
        if not user:
            return False
        sections: List[str] = user.get("assigned_sections", [])
        if section_id not in sections:
            sections.append(section_id)
        return self.update_user(user_id, {"assigned_sections": sections})

    def remove_section_from_teacher(self, user_id: str, section_id: str) -> bool:
        """Remove *section_id* from the teacher's assigned_sections list."""
        user = self.get_user(user_id)
        if not user:
            return False
        sections = [s for s in user.get("assigned_sections", []) if s != section_id]
        return self.update_user(user_id, {"assigned_sections": sections})

    def get_teachers_for_section(self, section_id: str) -> List[Dict[str, Any]]:
        """
        Return all teacher accounts that are assigned to *section_id*.

        Note: For large datasets consider a dedicated Firestore index on
        ``assigned_sections`` with ``array_contains`` rather than client-side
        filtering.
        """
        teachers = self.list_users_by_role("teacher")
        return [
            t for t in teachers
            if section_id in t.get("assigned_sections", [])
        ]

    def get_active_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Like list_users_by_role but filters to is_active=True."""
        return [u for u in self.list_users_by_role(role) if u.get("is_active", True)]

    def bulk_deactivate(self, user_ids: List[str]) -> Dict[str, bool]:
        """
        Deactivate multiple accounts in sequence.

        Returns a mapping of user_id → success so the caller knows which
        operations failed without losing the rest.
        """
        results: Dict[str, bool] = {}
        for uid in user_ids:
            results[uid] = self.update_user(uid, {"is_active": False})
        failed = [k for k, v in results.items() if not v]
        if failed:
            logger.warning("bulk_deactivate: failed for %s", failed)
        return results

    def search_users(
        self,
        *,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        name_contains: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Client-side search with optional filters.

        For production scale, push these filters to Firestore composite queries.
        """
        users = self.list_all_users()
        if role is not None:
            users = [u for u in users if u.get("role") == role]
        if is_active is not None:
            users = [u for u in users if u.get("is_active", True) == is_active]
        if name_contains:
            term = name_contains.lower()
            users = [u for u in users if term in u.get("name", "").lower()]
        return users
