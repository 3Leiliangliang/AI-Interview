"""Sanity tests for the thread-scoped SEP session cache.

The cache is the linchpin that lets the Agent's ask-time selection and the
service-layer's score-time replay share state. If a fresh `get_or_create_session`
ever forgets a prior pick, evidence chains in the result page silently lie.
"""
from __future__ import annotations

import pytest

from src.services.sep.session_cache import (
    drop_session,
    get_or_create_session,
    get_session,
    snapshot_size,
)


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Each test starts with the cache empty and tidies up after itself."""
    # Snapshot any pre-existing keys (other tests/agents) and drop them.
    # The cache is in-process so the test order matters; this keeps us
    # deterministic.
    pre = snapshot_size()
    yield
    # Try to leave the cache no fuller than it was before the test ran.
    if snapshot_size() > pre:
        # Tests should drop their own keys; if they didn't, dropping unknown
        # keys would mask the bug. So just assert.
        raise AssertionError(
            f"test leaked SEP session cache entries: before={pre}, after={snapshot_size()}"
        )


def test_get_or_create_returns_same_instance_for_same_thread():
    s1 = get_or_create_session("thread-A", "backend")
    s2 = get_or_create_session("thread-A", "backend")
    assert s1 is s2
    drop_session("thread-A")


def test_get_or_create_isolates_threads():
    s1 = get_or_create_session("thread-A", "backend")
    s2 = get_or_create_session("thread-B", "frontend")
    assert s1 is not s2
    assert s1.position == "backend"
    assert s2.position == "frontend"
    drop_session("thread-A")
    drop_session("thread-B")


def test_get_session_returns_none_for_unknown_thread():
    assert get_session("never-seen-thread") is None


def test_get_or_create_with_empty_thread_id_returns_ephemeral():
    """No thread context → still returns a usable session, but not cached."""
    s = get_or_create_session("", "backend")
    assert s.position == "backend"
    assert get_session("") is None


def test_drop_session_removes_from_cache():
    get_or_create_session("thread-X", "algorithm")
    assert get_session("thread-X") is not None
    drop_session("thread-X")
    assert get_session("thread-X") is None
