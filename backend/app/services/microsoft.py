"""
Microsoft 365 integration via Microsoft Graph API (MSAL + requests).
Handles OAuth and basic Mail / Calendar operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import httpx
import structlog
from msal import ConfidentialClientApplication, SerializableTokenCache

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token

logger = structlog.get_logger()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def build_msal_app(token_cache: Optional[SerializableTokenCache] = None) -> ConfidentialClientApplication:
    """Create a ConfidentialClientApplication for the configured app registration.

    Pass a SerializableTokenCache (persisted encrypted in the DB) so MSAL manages
    the full token lifecycle itself: cached access tokens, silent refreshes and
    refresh-token rotation.
    """
    if not settings.MS_CLIENT_ID or not settings.MS_CLIENT_SECRET:
        raise ValueError("MS_CLIENT_ID and MS_CLIENT_SECRET must be set")
    return ConfidentialClientApplication(
        client_id=settings.MS_CLIENT_ID,
        client_credential=settings.MS_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}",
        token_cache=token_cache,
    )


def silent_acquire_from_cache(
    cache_json: str, scopes: Optional[List[str]] = None
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Acquire a token silently using a persisted MSAL cache.

    MSAL returns a valid cached access token when possible, otherwise redeems
    the cached refresh token (handling rotation internally).

    Returns (result, updated_cache_json). result is None when no silent token
    is available (e.g. refresh token revoked/expired). updated_cache_json is
    None when the cache did not change (nothing to persist).
    """
    cache = SerializableTokenCache()
    cache.deserialize(cache_json)
    app = build_msal_app(token_cache=cache)
    accounts = app.get_accounts()
    if not accounts:
        return None, None
    result = app.acquire_token_silent(list(scopes or settings.MS_SCOPES), account=accounts[0])
    new_cache = cache.serialize() if cache.has_state_changed else None
    if not result or "access_token" not in result:
        return None, new_cache
    return result, new_cache


def refresh_microsoft_access_token(refresh_token: str) -> Dict[str, Any]:
    """Silently redeem a refresh token for a fresh token set (no user interaction).

    Returns the raw MSAL result dict (check for the 'error' key).
    NOTE: Microsoft refresh tokens are rolling — each successful redemption
    returns a NEW refresh token that must be persisted by the caller.
    """
    return build_msal_app().acquire_token_by_refresh_token(
        refresh_token, scopes=settings.MS_SCOPES
    )


class Microsoft365Service:
    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_cache: Optional[SerializableTokenCache] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._token_cache = token_cache
        self._app = None

    def _get_msal_app(self) -> ConfidentialClientApplication:
        if self._app is None:
            self._app = build_msal_app(token_cache=self._token_cache)
        return self._app

    def get_auth_url(self, state: str = "ms365") -> str:
        app = self._get_msal_app()
        return app.get_authorization_request_url(
            scopes=settings.MS_SCOPES,
            redirect_uri=settings.MS_REDIRECT_URI,
            state=state,
        )

    def exchange_code(self, code: str) -> Dict[str, Any]:
        app = self._get_msal_app()
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=settings.MS_SCOPES,
            redirect_uri=settings.MS_REDIRECT_URI,
        )
        if "error" in result:
            raise ValueError(result.get("error_description", result["error"]))
        return {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_in": result.get("expires_in"),
            "token_type": result.get("token_type"),
            "scope": result.get("scope"),
        }

    def refresh_access_token(self) -> str:
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        app = self._get_msal_app()
        result = app.acquire_token_by_refresh_token(
            self.refresh_token,
            scopes=settings.MS_SCOPES,
        )
        if "error" in result:
            raise ValueError(result.get("error_description", result["error"]))
        self.access_token = result["access_token"]
        if "refresh_token" in result:
            self.refresh_token = result["refresh_token"]
        return self.access_token

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self.access_token:
            raise ValueError("No access token. User must connect Microsoft 365 first.")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers.setdefault("Content-Type", "application/json")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, f"{GRAPH_BASE}{path}", headers=headers, **kwargs)
            if resp.status_code == 401:
                # try refresh once
                self.refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                resp = await client.request(method, f"{GRAPH_BASE}{path}", headers=headers, **kwargs)
            resp.raise_for_status()
            if resp.status_code == 204:
                return {}
            return resp.json()

    # ---------- Mail ----------
    async def list_messages(self, top: int = 10, folder: str = "inbox") -> List[Dict]:
        data = await self._request(
            "GET",
            f"/me/mailFolders/{folder}/messages",
            params={"$top": top, "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead", "$orderby": "receivedDateTime desc"},
        )
        return data.get("value", [])

    async def get_message(self, message_id: str) -> Dict:
        return await self._request(
            "GET",
            f"/me/messages/{message_id}",
            params={"$select": "id,subject,from,toRecipients,receivedDateTime,body,bodyPreview,isRead"},
        )

    async def send_mail(self, to: str, subject: str, body: str, content_type: str = "Text") -> Dict:
        if settings.DRY_RUN:
            return {"status": "dry-run", "message": f"Would send email to {to} with subject '{subject}'"}
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": content_type, "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        await self._request("POST", "/me/sendMail", json=payload)
        return {"status": "sent", "to": to, "subject": subject}

    # ---------- Calendar ----------
    async def list_events(self, days_ahead: int = 7) -> List[Dict]:
        start = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()
        data = await self._request(
            "GET",
            "/me/calendarView",
            params={
                "startDateTime": start,
                "endDateTime": end,
                "$select": "id,subject,start,end,location,organizer,isAllDay",
                "$orderby": "start/dateTime",
                "$top": 50,
            },
        )
        return data.get("value", [])

    async def create_event(
        self,
        subject: str,
        start: str,
        end: str,
        body: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict:
        if settings.DRY_RUN:
            return {
                "status": "dry-run",
                "message": f"Would create event '{subject}' from {start} to {end}",
            }
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if location:
            payload["location"] = {"displayName": location}
        if attendees:
            payload["attendees"] = [
                {"emailAddress": {"address": a}, "type": "required"} for a in attendees
            ]
        return await self._request("POST", "/me/events", json=payload)

    async def get_me(self) -> Dict:
        return await self._request("GET", "/me", params={"$select": "displayName,mail,userPrincipalName"})
