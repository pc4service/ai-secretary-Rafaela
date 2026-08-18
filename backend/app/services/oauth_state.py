"""
Server-side OAuth state for the integration (mail/calendar) connect flows.

The callback must never take the account to bind from the URL. Previously
`state` was used directly as the user_id, so an unauthenticated caller could
hand us their own authorization code with `state=<someone else>` and attach
their mailbox to that account. State is now an opaque single-use token that we
issue and look up, mirroring how openai_oauth handles its pending records.

Note: in-memory, like the login flow's store. With more than one worker the
callback can land on a process that never issued the state — see P2-7 in
docs/AUDIT.md (move to Redis).
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict

import structlog

logger = structlog.get_logger()

STATE_TTL_SECONDS = 600  # 10 minutes: an OAuth round trip is far shorter

# state -> {user_id, provider, created}
_pending: Dict[str, Dict[str, Any]] = {}


def _prune(now: float) -> None:
    for state, rec in list(_pending.items()):
        if now - rec["created"] > STATE_TTL_SECONDS:
            _pending.pop(state, None)


def issue(user_id: str, provider: str) -> str:
    """Start a connect flow and return the state to send to the provider."""
    now = time.time()
    _prune(now)
    state = secrets.token_urlsafe(24)
    _pending[state] = {"user_id": user_id, "provider": provider, "created": now}
    return state


def consume(state: str, provider: str) -> str:
    """
    Return the user_id that started this flow, and invalidate the state.

    Raises ValueError if the state is unknown, expired, already used, or was
    issued for a different provider.
    """
    now = time.time()
    _prune(now)
    record = _pending.pop(state or "", None)
    if not record:
        logger.warning("oauth_state_rejected", provider=provider)
        raise ValueError("Invalid or expired OAuth state")
    if record["provider"] != provider:
        logger.warning(
            "oauth_state_provider_mismatch",
            expected=provider,
            got=record["provider"],
        )
        raise ValueError("OAuth state provider mismatch")
    return record["user_id"]
