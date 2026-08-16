"""
Haystack tools for Microsoft 365.
Uses encrypted DB token store + human-in-the-loop for write actions.
"""

from haystack.tools import tool
from typing import Optional
from app.core.config import settings
from app.services.microsoft import Microsoft365Service
from app.services.token_store import get_fresh_microsoft_tokens, ReconnectRequired
from app.services.pending_actions import create_pending_action
import structlog
import asyncio

logger = structlog.get_logger()


def _normalize_user_id(user_id: Optional[str] = None) -> str:
    """Models often pass 'me'/'current'; map those to the app user."""
    uid = (user_id or "").strip()
    if uid.lower() in ("", "me", "current", "user", "current_user", "self"):
        return "demo-user"
    return uid


async def _get_ms_service(user_id: str = "demo-user") -> Microsoft365Service:
    # Silent refresh: returns a valid access token without an OAuth login;
    # raises ReconnectRequired only if the refresh token is gone/revoked.
    user_id = _normalize_user_id(user_id)
    try:
        token_data = await get_fresh_microsoft_tokens(user_id)
    except ReconnectRequired as e:
        raise ValueError(str(e))
    return Microsoft365Service(
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
    )


def _run(coro):
    """Run async coroutine from sync tool context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def ms_list_emails(top: int = 5, user_id: str = "demo-user") -> str:
    """List the most recent emails from the user's Microsoft 365 (Outlook) inbox."""
    try:
        async def _inner():
            service = await _get_ms_service(user_id)
            messages = await service.list_messages(top=top)
            if not messages:
                return "No emails found."
            lines = []
            for m in messages:
                sender = m.get("from", {}).get("emailAddress", {}).get("address", "unknown")
                lines.append(
                    f"- [{m.get('receivedDateTime', '')[:16]}] {m.get('subject', '(no subject)')} "
                    f"from {sender} | preview: {m.get('bodyPreview', '')[:80]}"
                )
            return "Recent Outlook emails:\n" + "\n".join(lines)
        return _run(_inner())
    except Exception as e:
        return f"Error listing Microsoft emails: {str(e)}"


@tool
def ms_list_calendar(days_ahead: int = 7, user_id: str = "demo-user") -> str:
    """List upcoming calendar events from Microsoft 365 Outlook Calendar."""
    try:
        async def _inner():
            service = await _get_ms_service(user_id)
            events = await service.list_events(days_ahead=days_ahead)
            if not events:
                return "No upcoming events found."
            lines = []
            for e in events:
                start = e.get("start", {}).get("dateTime", "")[:16]
                end = e.get("end", {}).get("dateTime", "")[:16]
                loc = e.get("location", {}).get("displayName", "")
                lines.append(
                    f"- {start} → {end} | {e.get('subject', '(no title)')} "
                    f"{(' @ ' + loc) if loc else ''}"
                )
            return f"Upcoming Outlook events (next {days_ahead} days):\n" + "\n".join(lines)
        return _run(_inner())
    except Exception as e:
        return f"Error listing Microsoft calendar: {str(e)}"


@tool
def ms_propose_send_email(
    to: str,
    subject: str,
    body: str,
    user_id: str = "demo-user",
) -> str:
    """
    Propose sending an email via Microsoft 365 Outlook.
    Creates a pending action that requires user approval (human-in-the-loop).
    Do NOT use this for reading emails.
    """
    try:
        async def _inner():
            await _get_ms_service(user_id)
            desc = f"Αποστολή email σε {to}\nΘέμα: {subject}\n\n{body[:300]}"
            action = await create_pending_action(
                user_id=user_id,
                action_type="ms_send_email",
                payload={"to": to, "subject": subject, "body": body},
                description=desc,
            )
            return (
                f"[PENDING_ACTION:{action.id}]\n"
                f"Πρότεινα την αποστολή του παρακάτω email. "
                f"Παρακαλώ ενέκρινε ή απέρριψε την ενέργεια.\n\n{desc}"
            )
        return _run(_inner())
    except Exception as e:
        return f"Error proposing Microsoft email: {str(e)}"


@tool
def ms_propose_create_event(
    subject: str,
    start: str,
    end: str,
    body: str = "",
    location: str = "",
    attendees: str = "",
    user_id: str = "demo-user",
) -> str:
    """
    Propose creating a calendar event in Microsoft 365.
    Creates a pending action that requires user approval.
    start/end must be ISO-8601 (e.g. 2026-08-12T10:00:00).
    attendees is a comma-separated list of emails.
    """
    try:
        async def _inner():
            await _get_ms_service(user_id)
            desc = (
                f"Δημιουργία ραντεβού: {subject}\n"
                f"Από: {start}  Έως: {end}\n"
                f"Τοποθεσία: {location or '—'}\n"
                f"Συμμετέχοντες: {attendees or '—'}\n"
                f"{body[:200]}"
            )
            payload = {
                "subject": subject,
                "start": start,
                "end": end,
                "body": body,
                "location": location,
                "attendees": attendees,
            }
            action = await create_pending_action(
                user_id=user_id,
                action_type="ms_create_event",
                payload=payload,
                description=desc,
            )
            return (
                f"[PENDING_ACTION:{action.id}]\n"
                f"Πρότεινα τη δημιουργία του παρακάτω ραντεβού. "
                f"Παρακαλώ ενέκρινε ή απέρριψε.\n\n{desc}"
            )
        return _run(_inner())
    except Exception as e:
        return f"Error proposing Microsoft event: {str(e)}"
