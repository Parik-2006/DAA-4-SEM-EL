"""
services/session_anchor_store.py
─────────────────────────────────
Process-wide singleton for the SessionAnchorStore introduced in
scoped_embedding_search.py.

Why a separate module
─────────────────────
``SessionAnchorStore`` lives in ``scoped_embedding_search.py`` because that
is where anchoring logic naturally sits.  But *any* layer that wants to read
or mutate the active anchor (the API router, the RTSP handler, a WebSocket
handler) would create import cycles if they imported directly from each other.
This thin module breaks the cycle by owning the singleton reference.

Usage
─────
::

    # At app startup (e.g. main.py or lifespan hook):
    from services.session_anchor_store import init_anchor_store
    init_anchor_store()

    # Anywhere else:
    from services.session_anchor_store import get_anchor_store
    store = get_anchor_store()          # never None after init
    anchor = store.get(stream_id)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from attendance_backend.services.scoped_embedding_search import SessionAnchorStore
except ImportError:
    from services.scoped_embedding_search import SessionAnchorStore  # type: ignore

_store: Optional[SessionAnchorStore] = None


def init_anchor_store() -> SessionAnchorStore:
    """
    Create (or replace) the process-wide ``SessionAnchorStore``.

    Call once from the app lifespan / startup hook.  Safe to call again
    (e.g. in tests) — the old store is discarded.
    """
    global _store
    _store = SessionAnchorStore()
    logger.info("SessionAnchorStore initialised.")
    return _store


def get_anchor_store() -> SessionAnchorStore:
    """
    Return the singleton store, creating it lazily if ``init_anchor_store``
    was not called at startup.

    The lazy path is safe for single-process deployments.  For multi-worker
    deployments call ``init_anchor_store()`` explicitly at startup so all
    workers share the same in-memory state (or swap the backend for Redis).
    """
    global _store
    if _store is None:
        logger.warning(
            "SessionAnchorStore accessed before init_anchor_store() — "
            "creating lazily.  Call init_anchor_store() at startup to avoid this."
        )
        _store = SessionAnchorStore()
    return _store