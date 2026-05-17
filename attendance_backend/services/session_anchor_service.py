"""
services/session_anchor_service.py
─────────────────────────────────────────────────────────────────────────────
Session-scoped identity anchoring for the SELF_VERIFY-first pipeline.

When a student (or teacher acting on behalf of a student) calls
  POST /api/v1/attendance/anchor
their ``user_id`` is pinned to a ``session_id`` (camera tab / device session).

Subsequent calls to ``detect-face-only`` that carry the same ``session_id``
will:
  1. Run SELF_VERIFY against **only that student's embeddings** first (O(1)).
  2. Return immediately on match — skipping the expensive section-roster scan.
  3. Fall back to SECTION_ROSTER on miss (unless ``force_scope=true``).

This eliminates the O(N) embedding scan for the common single-user webcam
case while preserving the full-roster fallback for edge cases (bad lighting,
recently updated embeddings, etc.).

Thread-safety
─────────────
All mutations go through a single ``threading.RLock``.  Reads take a
dict snapshot so eviction never races with a concurrent lookup.

TTL / eviction
──────────────
Anchors expire after ``ANCHOR_TTL_SECONDS`` (default 2 h). A lightweight
background daemon wakes every ``CLEANUP_INTERVAL_SECONDS`` and purges stale
entries.  The daemon starts lazily on first use of the singleton.

Anchor identity guarantee
─────────────────────────
``release()`` accepts an optional ``owner_id`` parameter.  When supplied,
the anchor is only removed if ``entry.user_id == owner_id``, preventing
one user from inadvertently releasing another user's session.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
ANCHOR_TTL_SECONDS       = 7_200   # 2 hours — refresh on each new request
CLEANUP_INTERVAL_SECONDS = 120     # 2 minutes — background sweep cadence
MAX_ANCHORS_PER_USER     = 10      # guard against runaway session creation


# ══════════════════════════════════════════════════════════════════════════════
# Data model
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnchorEntry:
    """One pinned (session_id, user_id) pair with a monotonic expiry clock."""

    user_id:     str
    session_id:  str
    period_id:   Optional[str]          = None   # optional period context
    anchored_at: float                  = field(default_factory=time.monotonic)
    ttl:         float                  = ANCHOR_TTL_SECONDS

    # ── Expiry ────────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.anchored_at) > self.ttl

    @property
    def remaining_seconds(self) -> float:
        remaining = self.ttl - (time.monotonic() - self.anchored_at)
        return max(0.0, remaining)

    def refresh(self) -> None:
        """Reset the expiry clock (called when the user re-anchors the same session)."""
        self.anchored_at = time.monotonic()

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id":        self.session_id,
            "user_id":           self.user_id,
            "period_id":         self.period_id,
            "ttl_seconds":       int(self.ttl),
            "remaining_seconds": int(self.remaining_seconds),
            "is_expired":        self.is_expired,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class SessionAnchorService:
    """
    Thread-safe, TTL-aware store mapping ``session_id → AnchorEntry``.

    Usage
    -----
    ::

        svc = get_anchor_service()

        # Pin the current user to their webcam session
        entry = svc.anchor("tab_abc123", user_id="student_42", period_id="p_001")

        # Look up the anchor inside detect-face-only
        anchor = svc.get_anchor("tab_abc123")
        if anchor:
            ...run SELF_VERIFY for anchor.user_id...

        # Release on logout / window close
        svc.release("tab_abc123", owner_id="student_42")
    """

    def __init__(self) -> None:
        # Primary store: session_id → AnchorEntry
        self._store: Dict[str, AnchorEntry] = {}
        # Reverse index: user_id → set[session_id] (for per-user cap enforcement)
        self._user_sessions: Dict[str, set] = {}
        self._lock  = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._start_cleanup_daemon()

    # ── Public API ─────────────────────────────────────────────────────────────

    def anchor(
        self,
        session_id: str,
        user_id:    str,
        period_id:  Optional[str] = None,
        ttl:        float         = ANCHOR_TTL_SECONDS,
    ) -> AnchorEntry:
        """
        Pin ``user_id`` to ``session_id``.

        If a live anchor already exists for this session:
        - Same user  → refresh the TTL and update ``period_id`` (idempotent).
        - Diff user  → overwrite (the new caller takes over the session).

        Raises ``ValueError`` if the user already has ≥ ``MAX_ANCHORS_PER_USER``
        active sessions (protects against resource exhaustion).
        """
        with self._lock:
            existing = self._store.get(session_id)

            if existing and not existing.is_expired and existing.user_id == user_id:
                # Same user re-anchoring the same session → just refresh
                existing.period_id = period_id or existing.period_id
                existing.refresh()
                logger.debug(
                    "Anchor refreshed: session=%s user=%s remaining=%ds",
                    session_id, user_id, int(existing.remaining_seconds),
                )
                return existing

            # Cap check (new anchor for this user)
            user_sessions = self._user_sessions.get(user_id, set())
            live_count = sum(
                1 for sid in user_sessions
                if sid in self._store and not self._store[sid].is_expired
            )
            if live_count >= MAX_ANCHORS_PER_USER:
                # Evict the oldest session for this user to make room
                oldest_sid = self._oldest_session_for_user(user_id, user_sessions)
                if oldest_sid:
                    self._remove_session(oldest_sid)
                    logger.warning(
                        "Evicted oldest anchor for user %s (cap=%d): %s",
                        user_id, MAX_ANCHORS_PER_USER, oldest_sid,
                    )

            # Remove any stale anchor from a previous user of this session
            if existing:
                self._remove_session(session_id)

            # Create new entry
            entry = AnchorEntry(
                user_id=user_id,
                session_id=session_id,
                period_id=period_id,
                ttl=ttl,
            )
            self._store[session_id] = entry
            self._user_sessions.setdefault(user_id, set()).add(session_id)

        logger.info(
            "Session anchored: session=%s → user=%s period=%s ttl=%ds",
            session_id, user_id, period_id or "–", int(ttl),
        )
        return entry

    def release(
        self,
        session_id: str,
        owner_id:   Optional[str] = None,
    ) -> bool:
        """
        Remove the anchor for ``session_id``.

        Parameters
        ----------
        session_id:
            The session to release.
        owner_id:
            When supplied the anchor is only removed if ``entry.user_id ==
            owner_id``, preventing one user from releasing another's session.

        Returns ``True`` if an anchor was actually removed.
        """
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                logger.debug("release() called for unknown session: %s", session_id)
                return False
            if owner_id is not None and entry.user_id != owner_id:
                logger.warning(
                    "Anchor release denied: session=%s owner=%s requester=%s",
                    session_id, entry.user_id, owner_id,
                )
                return False
            removed_user = entry.user_id
            self._remove_session(session_id)

        logger.info(
            "Session anchor released: session=%s (was user=%s)",
            session_id, removed_user,
        )
        return True

    def release_all_for_user(self, user_id: str) -> int:
        """
        Remove all active anchors belonging to ``user_id`` (e.g. on logout).
        Returns the number of sessions released.
        """
        with self._lock:
            sessions = list(self._user_sessions.get(user_id, set()))
            released = 0
            for sid in sessions:
                entry = self._store.get(sid)
                if entry and entry.user_id == user_id:
                    self._remove_session(sid)
                    released += 1
        if released:
            logger.info(
                "Released %d anchor(s) for user=%s on logout", released, user_id
            )
        return released

    def get_anchor(self, session_id: str) -> Optional[AnchorEntry]:
        """
        Return the live anchor for ``session_id``, or ``None`` if absent or
        expired (lazy eviction fires on expired hits).
        """
        with self._lock:
            entry = self._store.get(session_id)

        if entry is None:
            return None

        if entry.is_expired:
            with self._lock:
                # Double-check under the lock before evicting
                current = self._store.get(session_id)
                if current is entry:          # nobody replaced it
                    self._remove_session(session_id)
            logger.debug("Anchor expired (lazy eviction): session=%s", session_id)
            return None

        return entry

    def list_anchors(self) -> Dict[str, dict]:
        """
        Return a snapshot of all live anchors as
        ``{session_id: AnchorEntry.to_dict()}``.

        Expired entries are excluded.
        """
        with self._lock:
            snapshot = dict(self._store)
        return {
            sid: e.to_dict()
            for sid, e in snapshot.items()
            if not e.is_expired
        }

    def count(self) -> int:
        """Number of currently live anchors."""
        return len(self.list_anchors())

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _remove_session(self, session_id: str) -> None:
        """Remove session from both _store and _user_sessions. Must hold _lock."""
        entry = self._store.pop(session_id, None)
        if entry:
            user_set = self._user_sessions.get(entry.user_id)
            if user_set:
                user_set.discard(session_id)
                if not user_set:
                    del self._user_sessions[entry.user_id]

    def _oldest_session_for_user(
        self, user_id: str, sessions: set
    ) -> Optional[str]:
        """Return the session_id with the earliest ``anchored_at``."""
        candidates: List[tuple] = []
        for sid in sessions:
            entry = self._store.get(sid)
            if entry and entry.user_id == user_id:
                candidates.append((entry.anchored_at, sid))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    # ── Background eviction daemon ─────────────────────────────────────────────

    def _start_cleanup_daemon(self) -> None:
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            return
        t = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="session-anchor-cleanup",
        )
        t.start()
        self._cleanup_thread = t
        logger.debug(
            "Session anchor cleanup daemon started (interval=%ds)",
            CLEANUP_INTERVAL_SECONDS,
        )

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(CLEANUP_INTERVAL_SECONDS)
            try:
                self._evict_expired()
            except Exception as exc:
                logger.debug("Anchor cleanup error (swallowed): %s", exc)

    def _evict_expired(self) -> None:
        with self._lock:
            expired = [
                sid for sid, e in list(self._store.items()) if e.is_expired
            ]
            for sid in expired:
                self._remove_session(sid)
        if expired:
            logger.debug(
                "Evicted %d expired session anchor(s): %s", len(expired), expired
            )


# ── Module-level singleton ─────────────────────────────────────────────────────

_anchor_service: Optional[SessionAnchorService] = None
_singleton_lock = threading.Lock()


def get_anchor_service() -> SessionAnchorService:
    """Return the process-wide ``SessionAnchorService`` singleton (lazy init)."""
    global _anchor_service
    if _anchor_service is None:
        with _singleton_lock:
            if _anchor_service is None:
                _anchor_service = SessionAnchorService()
                logger.info("SessionAnchorService initialised.")
    return _anchor_service