"""
StateStore: OAuth records must survive across workers, and degrade sanely.

Runs against whatever backend is configured. When Redis is reachable the shared
path is exercised; otherwise the local fallback is. Both must behave the same,
which is the point of the abstraction.
"""

import time

import pytest

from app.services import state_store
from app.services.state_store import StateStore


@pytest.fixture
def store():
    return StateStore(f"test-{time.time()}", ttl_seconds=60)


def test_put_then_pop_round_trips(store):
    store.put("k", {"user_id": "u1", "provider": "google"})
    assert store.pop("k") == {"user_id": "u1", "provider": "google"}


def test_records_are_single_use(store):
    store.put("k", {"user_id": "u1"})
    store.pop("k")
    assert store.pop("k") is None


def test_unknown_key_is_none(store):
    assert store.pop("never-issued") is None


def test_blank_key_is_none(store):
    assert store.pop("") is None


def test_namespaces_do_not_collide():
    a = StateStore("ns-a", 60)
    b = StateStore("ns-b", 60)
    a.put("same-key", {"user_id": "from-a"})
    assert b.pop("same-key") is None
    assert a.pop("same-key") == {"user_id": "from-a"}


def test_internal_created_marker_is_not_returned(store):
    store.put("k", {"user_id": "u1"})
    assert "_created" not in (store.pop("k") or {})


# --- shared-backend behaviour (the actual P2-7 fix) ---

def test_two_instances_share_records_when_redis_is_available():
    """
    Separate StateStore objects stand in for separate workers: with Redis they
    see each other's records, which is exactly what a second worker needs.
    """
    if state_store._redis() is None:
        pytest.skip("Redis not reachable; local fallback covered elsewhere")
    writer = StateStore("shared-ns", 60)
    reader = StateStore("shared-ns", 60)
    writer.put("handoff", {"user_id": "u1"})
    assert reader.pop("handoff") == {"user_id": "u1"}


def test_without_redis_each_instance_is_isolated(monkeypatch):
    """Single-worker fallback: correct in-process, and no worse than before."""
    monkeypatch.setattr(state_store, "_redis", lambda: None)
    writer = StateStore("local-ns", 60)
    reader = StateStore("local-ns", 60)
    writer.put("handoff", {"user_id": "u1"})
    assert reader.pop("handoff") is None
    assert writer.pop("handoff") == {"user_id": "u1"}


# --- degradation ---

def test_expired_records_are_dropped(monkeypatch):
    monkeypatch.setattr(state_store, "_redis", lambda: None)
    s = StateStore("ttl-ns", ttl_seconds=1)
    s.put("k", {"user_id": "u1"})
    real = time.time
    monkeypatch.setattr(state_store.time, "time", lambda: real() + 5)
    assert s.pop("k") is None


def test_falls_back_to_local_when_redis_write_fails(monkeypatch):
    class Broken:
        def setex(self, *a, **k):
            raise RuntimeError("redis down")

        def getdel(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(state_store, "_redis", lambda: Broken())
    s = StateStore("broken-ns", 60)
    s.put("k", {"user_id": "u1"})
    # The flow still completes on this worker rather than failing outright.
    assert s.pop("k") == {"user_id": "u1"}
