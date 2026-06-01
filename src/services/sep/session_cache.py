"""Thread-scoped SEPSession cache.

Allows the interview Agent to drive question selection via SEP at ask-time
(`pick_sep_adaptive_question` tool) and then have the result-evaluation
service reuse the *same* session at score-time, so question ↔ rubric
matching is exact instead of relying on fuzzy text matching.

Storage is intentionally in-process for the MVP. A Redis-backed adapter
can drop in later by replacing `_CACHE` with anything that satisfies the
get/set/delete protocol.
"""
from __future__ import annotations

import logging
import threading

from src.services.sep import SEPSession

logger = logging.getLogger(__name__)

_CACHE: dict[str, SEPSession] = {}
_LOCK = threading.Lock()


def _make_key(thread_id: str) -> str:
    return str(thread_id or "").strip()


def get_session(thread_id: str) -> SEPSession | None:
    """Return the cached session for thread_id, if any."""
    key = _make_key(thread_id)
    if not key:
        return None
    with _LOCK:
        return _CACHE.get(key)


def get_or_create_session(thread_id: str, position: str) -> SEPSession:
    """Return the cached SEPSession for the thread, creating it if missing.

    `position` is the SEP question-bank slug (backend / frontend / algorithm).
    If the slug is unknown the underlying SEPSession will fall back to the
    backend bank.
    """
    key = _make_key(thread_id)
    if not key:
        # No thread context — return an ephemeral session that won't be reused.
        return SEPSession(position=position or "backend")
    with _LOCK:
        session = _CACHE.get(key)
        if session is None:
            session = SEPSession(position=position or "backend")
            _CACHE[key] = session
            logger.info("Created SEP session for thread={} position={}", key, position)
        return session


def drop_session(thread_id: str) -> None:
    """Forget the session for thread_id (e.g. when the interview is finalised)."""
    key = _make_key(thread_id)
    if not key:
        return
    with _LOCK:
        if _CACHE.pop(key, None) is not None:
            logger.info("Dropped SEP session for thread={}", key)


def snapshot_size() -> int:
    """For diagnostics / tests."""
    with _LOCK:
        return len(_CACHE)
