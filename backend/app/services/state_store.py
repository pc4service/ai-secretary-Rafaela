"""
Short-lived shared state for OAuth flows.

These records are written when a flow starts and read when the provider
redirects back. With more than one worker those two requests can land on
different processes, so an in-process dict silently breaks login and connect
under any real deployment. Redis is the shared home; when it is unavailable
(local runs, CI) each process falls back to its own dict, which is correct for
a single worker and no worse than what came before.

Calls are synchronous: one tiny round trip per OAuth flow, not per request, so
the blocking cost is negligible and every call site stays unchanged.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger()

_client: Any = None
_probed = False


def _redis():
    """Shared client, or None when Redis is not reachable. Probed once."""
    global _client, _probed
    if _probed:
        return _client
    _probed = True
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        logger.info("state_store_local_only", reason="REDIS_URL not set")
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            url,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        client.ping()
        _client = client
        logger.info("state_store_redis_ready")
    except Exception as e:
        logger.warning("state_store_redis_unavailable", error=str(e)[:200])
        _client = None
    return _client


def reset_client_cache() -> None:
    """Force the next call to probe again (tests)."""
    global _client, _probed
    _client = None
    _probed = False


class StateStore:
    """Namespaced key -> dict with a TTL, shared across workers when possible."""

    def __init__(self, namespace: str, ttl_seconds: int):
        self.namespace = namespace
        self.ttl = ttl_seconds
        self._local: Dict[str, Dict[str, Any]] = {}

    def _key(self, key: str) -> str:
        return f"rafaela:{self.namespace}:{key}"

    # -- local fallback --------------------------------------------------

    def _prune_local(self, now: float) -> None:
        for k, rec in list(self._local.items()):
            if now - rec.get("_created", now) > self.ttl:
                self._local.pop(k, None)

    # -- public ----------------------------------------------------------

    def put(self, key: str, value: Dict[str, Any]) -> None:
        client = _redis()
        if client is not None:
            try:
                client.setex(self._key(key), self.ttl, json.dumps(value))
                return
            except Exception as e:
                logger.warning("state_store_put_failed", error=str(e)[:200])
        record = dict(value)
        record["_created"] = time.time()
        self._prune_local(record["_created"])
        self._local[key] = record

    def pop(self, key: str) -> Optional[Dict[str, Any]]:
        """Read and delete in one step — these records are single use."""
        if not key:
            return None
        client = _redis()
        if client is not None:
            try:
                raw = None
                if hasattr(client, "getdel"):
                    raw = client.getdel(self._key(key))
                else:  # Redis < 6.2
                    pipe = client.pipeline()
                    pipe.get(self._key(key))
                    pipe.delete(self._key(key))
                    raw = pipe.execute()[0]
                if raw is not None:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("state_store_pop_failed", error=str(e)[:200])
        record = self._local.pop(key, None)
        if record is None:
            return None
        if time.time() - record.get("_created", 0) > self.ttl:
            return None
        record.pop("_created", None)
        return record
