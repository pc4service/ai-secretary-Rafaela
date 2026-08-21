"""Tools to recall prior Rafaela chat turns (not email/calendar)."""

from haystack.tools import tool

from app.services.agent_context import current_agent_user


def _run(coro):
    """Bridge async DB helpers from sync Haystack tools (worker thread)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=30)
    return asyncio.run(coro)


@tool
def search_conversation_memory(
    query: str = "",
    days: int = 7,
    limit: int = 20,
) -> str:
    """
    Search THIS USER's past Rafaela chat messages (conversation memory in the app DB).

    Use when the user asks about:
    - what we discussed yesterday / earlier / last week
    - a previous chat thread, promise, draft, or decision inside Rafaela
    - "θυμάσαι", "στην προηγούμενη συνομιλία", "χθες μου είπες"

    Do NOT use this for Outlook/Gmail/calendar — those need ms_* / google_* tools.
    Do NOT invent past chats if this returns nothing.

    Args:
        query: Keywords to find (Greek or English). Empty = recent messages in the window.
        days: How many days back to search (1–90, default 7).
        limit: Max messages to return (default 20).
    """
    from app.services.conversation import (
        format_memory_for_agent,
        search_user_conversation_memory,
    )

    uid = current_agent_user()
    try:
        hits = _run(
            search_user_conversation_memory(
                uid,
                query=query or "",
                days=days,
                limit=limit,
            )
        )
        return format_memory_for_agent(hits, query=query or "")
    except Exception as e:
        return f"Error searching conversation memory: {e}"
