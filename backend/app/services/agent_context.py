"""
Acting user for the current agent run.

Tools must never let the model choose whose tokens or data they touch, so they
resolve the acting user from here instead of from a model-supplied argument.
Bound once per run in run_agent(); each request task gets its own copy.
"""

from contextvars import ContextVar
from typing import Optional

import structlog

logger = structlog.get_logger()

DEFAULT_USER_ID = "demo-user"

# Aliases models commonly invent instead of omitting the argument.
_SELF_ALIASES = {"me", "current", "user", "current_user", "self", "demo-user"}

_agent_user_id: ContextVar[str] = ContextVar("agent_user_id", default=DEFAULT_USER_ID)


def set_agent_user(user_id: Optional[str]) -> None:
    """Bind the acting user for this agent run."""
    _agent_user_id.set((user_id or "").strip() or DEFAULT_USER_ID)


def current_agent_user(model_supplied: Optional[str] = None) -> str:
    """
    Return the user a tool must act as.

    Any user_id the model passed is ignored — it is not allowed to target
    another account. We only log when it tried to.

    Call this in the tool function body, not inside a coroutine handed to
    _run(): that runs in a worker thread which does not inherit this context.
    """
    uid = _agent_user_id.get() or DEFAULT_USER_ID
    supplied = (model_supplied or "").strip()
    if supplied and supplied.lower() not in _SELF_ALIASES and supplied != uid:
        logger.warning(
            "tool_user_id_override_ignored", supplied=supplied[:64], acting=uid
        )
    return uid
