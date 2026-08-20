"""
Request rate limiting.

Three things the in-process version got wrong:

1. It counted per worker, so N workers allowed N times the configured limit.
2. It keyed on request.client.host. Behind the documented nginx deployment that
   is the proxy's address, identical for every user, so the whole application
   shared one bucket — the limiter throttled everyone at once instead of the
   caller who was actually noisy.
3. Its dict grew a key per address seen and never dropped them.

Counting lives in Redis when reachable, keyed on a fixed window, so all workers
and instances share it. Without Redis each process falls back to a bounded
in-process counter, which is correct for a single worker.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import structlog

from app.core.config import settings

logger = structlog.get_logger()

_client = None
_probed = False


async def _redis():
    """Async client, or None when Redis is not reachable. Probed once."""
    global _client, _probed
    if _probed:
        return _client
    _probed = True
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        logger.info("rate_limit_local_only", reason="REDIS_URL not set")
        return None
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            url, socket_timeout=2, socket_connect_timeout=2, decode_responses=True
        )
        await client.ping()
        _client = client
        logger.info("rate_limit_redis_ready")
    except Exception as e:
        logger.warning("rate_limit_redis_unavailable", error=str(e)[:200])
        _client = None
    return _client


def reset_client_cache() -> None:
    """Force the next call to probe again (tests)."""
    global _client, _probed
    _client = None
    _probed = False


def client_ip(request) -> str:
    """
    The address to rate limit on.

    X-Forwarded-For is attacker-controlled unless a proxy we trust rewrote it,
    so it is only read when TRUSTED_PROXY_HOPS says how many proxies sit in
    front. With one hop the trustworthy entry is the last one — the address
    nginx actually observed — because anything the client sent is to its left.
    """
    hops = max(0, int(getattr(settings, "TRUSTED_PROXY_HOPS", 0) or 0))
    if hops:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
        # Fewer entries than configured hops: the header did not come through
        # the expected chain, so fall back rather than trust it.
        logger.warning("xff_shorter_than_trusted_hops", entries=len(parts), hops=hops)
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Fixed-window counter. Shared through Redis when available."""

    #: Stop the fallback dict from growing without bound.
    MAX_LOCAL_KEYS = 10_000

    def __init__(self, limit: int, window_seconds: int, namespace: str = "rl"):
        self.limit = limit
        self.window = window_seconds
        self.namespace = namespace
        self._local: Dict[str, Tuple[int, int]] = {}  # key -> (bucket, count)

    def _bucket(self, now: float) -> int:
        return int(now // self.window)

    def _retry_after(self, now: float) -> int:
        return max(1, int(self.window - (now % self.window)))

    def _hit_local(self, key: str, now: float) -> Tuple[bool, int]:
        bucket = self._bucket(now)
        if len(self._local) > self.MAX_LOCAL_KEYS:
            self._local = {
                k: v for k, v in self._local.items() if v[0] == bucket
            }
        seen_bucket, count = self._local.get(key, (bucket, 0))
        if seen_bucket != bucket:
            count = 0
        count += 1
        self._local[key] = (bucket, count)
        return count <= self.limit, self._retry_after(now)

    async def hit(self, key: str) -> Tuple[bool, int]:
        """Record a request. Returns (allowed, seconds_until_window_resets)."""
        now = time.time()
        client = await _redis()
        if client is not None:
            redis_key = f"rafaela:{self.namespace}:{self._bucket(now)}:{key}"
            try:
                count = await client.incr(redis_key)
                if count == 1:
                    # Outlive the window slightly so a clock skew cannot strand it.
                    await client.expire(redis_key, self.window + 1)
                return count <= self.limit, self._retry_after(now)
            except Exception as e:
                logger.warning("rate_limit_redis_failed", error=str(e)[:200])
        return self._hit_local(key, now)


_limiter: Optional[RateLimiter] = None


def limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(
            limit=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
    return _limiter


def reset_limiter() -> None:
    """Drop the cached limiter so new settings take effect (tests)."""
    global _limiter
    _limiter = None
