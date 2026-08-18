"""
Server-side OAuth state for the integration (mail/calendar) connect flows.

The callback must never take the account to bind from the URL. Previously
`state` was used directly as the user_id, so an unauthenticated caller could
hand us their own authorization code with `state=<someone else>` and attach
their mailbox to that account. State is now an opaque single-use token that we
issue and look up, mirroring how openai_oauth handles its pending records.

Records live in Redis when it is reachable, so the callback resolves even when
it lands on a different worker than the one that issued the state.
"""

from __future__ import annotations

import secrets

import structlog

from app.services.state_store import StateStore

logger = structlog.get_logger()

STATE_TTL_SECONDS = 600  # 10 minutes: an OAuth round trip is far shorter

_store = StateStore("oauth_connect", STATE_TTL_SECONDS)


def issue(user_id: str, provider: str) -> str:
    """Start a connect flow and return the state to send to the provider."""
    state = secrets.token_urlsafe(24)
    _store.put(state, {"user_id": user_id, "provider": provider})
    return state


def consume(state: str, provider: str) -> str:
    """
    Return the user_id that started this flow, and invalidate the state.

    Raises ValueError if the state is unknown, expired, already used, or was
    issued for a different provider.
    """
    record = _store.pop(state or "")
    if not record:
        logger.warning("oauth_state_rejected", provider=provider)
        raise ValueError("Invalid or expired OAuth state")
    if record.get("provider") != provider:
        logger.warning(
            "oauth_state_provider_mismatch",
            expected=provider,
            got=record.get("provider"),
        )
        raise ValueError("OAuth state provider mismatch")
    return record["user_id"]
