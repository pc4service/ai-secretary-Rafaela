"""
Haystack tools for Google Workspace (Gmail + Calendar).
Uses encrypted DB token store + human-in-the-loop for write actions.
"""

from haystack.tools import tool
from app.services.google import GoogleWorkspaceService
from app.services.token_store import get_oauth_token
from app.services.pending_actions import create_pending_action
import structlog
import asyncio

logger = structlog.get_logger()


async def _get_google_service(user_id: str = "demo-user") -> GoogleWorkspaceService:
    token_data = await get_oauth_token(user_id, "google")
    if not token_data:
        raise ValueError("Google Workspace is not connected. Please connect it in Settings.")
    return GoogleWorkspaceService(token_data=token_data)


def _run(coro):
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
def google_list_emails(max_results: int = 5, query: str = "in:inbox", user_id: str = "demo-user") -> str:
    """List recent emails from the user's Gmail inbox."""
    try:
        async def _inner():
            service = await _get_google_service(user_id)
            messages = service.list_messages(max_results=max_results, query=query)
            if not messages:
                return "No emails found."
            lines = []
            for m in messages:
                lines.append(
                    f"- [{m.get('date', '')[:25]}] {m.get('subject', '(no subject)')} "
                    f"from {m.get('from', 'unknown')} | {m.get('snippet', '')[:80]}"
                )
            return "Recent Gmail messages:\n" + "\n".join(lines)
        return _run(_inner())
    except Exception as e:
        return f"Error listing Gmail: {str(e)}"


@tool
def google_list_calendar(days_ahead: int = 7, user_id: str = "demo-user") -> str:
    """List upcoming events from Google Calendar."""
    try:
        async def _inner():
            service = await _get_google_service(user_id)
            events = service.list_events(days_ahead=days_ahead)
            if not events:
                return "No upcoming Google Calendar events."
            lines = []
            for e in events:
                start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
                end = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", "")
                lines.append(f"- {start[:16]} → {end[:16]} | {e.get('summary', '(no title)')}")
            return f"Upcoming Google Calendar events (next {days_ahead} days):\n" + "\n".join(lines)
        return _run(_inner())
    except Exception as e:
        return f"Error listing Google Calendar: {str(e)}"


@tool
def google_propose_send_email(to: str, subject: str, body: str, user_id: str = "demo-user") -> str:
    """
    Propose sending an email via Gmail.
    Creates a pending action that requires user approval (human-in-the-loop).
    """
    try:
        async def _inner():
            await _get_google_service(user_id)
            desc = f"Αποστολή Gmail σε {to}\nΘέμα: {subject}\n\n{body[:300]}"
            action = await create_pending_action(
                user_id=user_id,
                action_type="google_send_email",
                payload={"to": to, "subject": subject, "body": body},
                description=desc,
            )
            return (
                f"[PENDING_ACTION:{action.id}]\n"
                f"Πρότεινα την αποστολή του παρακάτω email. "
                f"Παρακαλώ ενέκρινε ή απέρριψε.\n\n{desc}"
            )
        return _run(_inner())
    except Exception as e:
        return f"Error proposing Gmail: {str(e)}"


@tool
def google_propose_create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: str = "",
    user_id: str = "demo-user",
) -> str:
    """
    Propose creating an event in Google Calendar.
    Creates a pending action that requires user approval.
    """
    try:
        async def _inner():
            await _get_google_service(user_id)
            desc = (
                f"Δημιουργία Google event: {summary}\n"
                f"Από: {start}  Έως: {end}\n"
                f"Τοποθεσία: {location or '—'}\n"
                f"Συμμετέχοντες: {attendees or '—'}\n"
                f"{description[:200]}"
            )
            payload = {
                "summary": summary,
                "start": start,
                "end": end,
                "description": description,
                "location": location,
                "attendees": attendees,
            }
            action = await create_pending_action(
                user_id=user_id,
                action_type="google_create_event",
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
        return f"Error proposing Google event: {str(e)}"
