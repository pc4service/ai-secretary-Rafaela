"""Rate limiting: one shared budget, keyed on the real caller."""

import pytest

from app.core.config import settings
from app.services import rate_limit
from app.services.rate_limit import RateLimiter, client_ip


class FakeRequest:
    def __init__(self, peer="10.0.0.1", headers=None):
        self.headers = headers or {}
        self.client = type("C", (), {"host": peer})() if peer else None


# --- who gets counted ---

def test_uses_peer_address_when_no_proxy_is_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    req = FakeRequest(peer="10.0.0.1", headers={"x-forwarded-for": "1.2.3.4"})
    # The header is attacker-controlled here, so it must be ignored.
    assert client_ip(req) == "10.0.0.1"


def test_spoofed_header_cannot_shift_the_bucket(monkeypatch):
    """Without a trusted proxy, varying XFF must not create fresh budgets."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    keys = {
        client_ip(FakeRequest(peer="10.0.0.1", headers={"x-forwarded-for": f"9.9.9.{i}"}))
        for i in range(5)
    }
    assert keys == {"10.0.0.1"}


def test_one_trusted_proxy_uses_the_address_it_observed(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    # nginx appends what it saw; anything to the left came from the client.
    req = FakeRequest(peer="172.18.0.5", headers={"x-forwarded-for": "1.2.3.4, 203.0.113.9"})
    assert client_ip(req) == "203.0.113.9"


def test_two_trusted_proxies_step_back_one_more(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    req = FakeRequest(
        peer="172.18.0.5",
        headers={"x-forwarded-for": "1.2.3.4, 203.0.113.9, 172.18.0.4"},
    )
    assert client_ip(req) == "203.0.113.9"


def test_short_header_falls_back_to_peer(monkeypatch):
    """Fewer entries than configured hops means the chain is not as expected."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    req = FakeRequest(peer="172.18.0.5", headers={"x-forwarded-for": "1.2.3.4"})
    assert client_ip(req) == "172.18.0.5"


def test_missing_client_is_still_a_usable_key(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert client_ip(FakeRequest(peer=None)) == "unknown"


# --- counting ---

@pytest.mark.asyncio
async def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(limit=3, window_seconds=60, namespace=f"t{id(object())}")
    results = [await limiter.hit("caller") for _ in range(4)]
    assert [allowed for allowed, _ in results] == [True, True, True, False]


@pytest.mark.asyncio
async def test_callers_have_separate_budgets():
    limiter = RateLimiter(limit=1, window_seconds=60, namespace=f"t{id(object())}")
    assert (await limiter.hit("a"))[0] is True
    assert (await limiter.hit("b"))[0] is True
    assert (await limiter.hit("a"))[0] is False


@pytest.mark.asyncio
async def test_blocked_response_says_when_to_retry():
    limiter = RateLimiter(limit=1, window_seconds=60, namespace=f"t{id(object())}")
    await limiter.hit("caller")
    allowed, retry_after = await limiter.hit("caller")
    assert allowed is False
    assert 1 <= retry_after <= 60


@pytest.mark.asyncio
async def test_two_instances_share_one_budget_via_redis():
    """Standing in for two workers: the limit is global, not per process."""
    if await rate_limit._redis() is None:
        pytest.skip("Redis not reachable")
    ns = f"shared{id(object())}"
    worker_a = RateLimiter(limit=2, window_seconds=60, namespace=ns)
    worker_b = RateLimiter(limit=2, window_seconds=60, namespace=ns)
    assert (await worker_a.hit("caller"))[0] is True
    assert (await worker_b.hit("caller"))[0] is True
    # Third request anywhere in the cluster is over budget.
    assert (await worker_b.hit("caller"))[0] is False


# --- degradation ---

@pytest.mark.asyncio
async def test_falls_back_to_local_counting_when_redis_fails(monkeypatch):
    class Broken:
        async def incr(self, *a):
            raise RuntimeError("redis down")

        async def expire(self, *a):
            raise RuntimeError("redis down")

    async def broken(*_a):
        return Broken()

    monkeypatch.setattr(rate_limit, "_redis", broken)
    limiter = RateLimiter(limit=1, window_seconds=60, namespace="broken")
    assert (await limiter.hit("caller"))[0] is True
    assert (await limiter.hit("caller"))[0] is False


@pytest.mark.asyncio
async def test_local_fallback_does_not_grow_without_bound(monkeypatch):
    async def none(*_a):
        return None

    monkeypatch.setattr(rate_limit, "_redis", none)
    limiter = RateLimiter(limit=100, window_seconds=60, namespace="bounded")
    limiter.MAX_LOCAL_KEYS = 50
    for i in range(200):
        await limiter.hit(f"caller-{i}")
    assert len(limiter._local) <= 201  # pruned, not one entry per caller forever
    assert len(limiter._local) > 0
