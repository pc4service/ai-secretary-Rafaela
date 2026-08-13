"""
Google Workspace integration (Gmail + Calendar) via google-api-python-client.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import json
import structlog
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from app.core.config import settings

logger = structlog.get_logger()


class GoogleWorkspaceService:
    def __init__(self, token_data: Optional[Dict] = None):
        """
        token_data should contain the fields returned by the OAuth flow
        (token, refresh_token, token_uri, client_id, client_secret, scopes).
        """
        self.creds: Optional[Credentials] = None
        if token_data:
            self.creds = Credentials.from_authorized_user_info(token_data, settings.GOOGLE_SCOPES)

    def _ensure_valid_creds(self):
        if not self.creds:
            raise ValueError("No Google credentials. User must connect Google Workspace first.")
        if self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())
        if not self.creds.valid:
            raise ValueError("Google credentials are invalid or expired.")

    def get_auth_url(self, state: str = "google") -> str:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=settings.GOOGLE_SCOPES,
            state=state,
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url

    def exchange_code(self, code: str) -> Dict[str, Any]:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=settings.GOOGLE_SCOPES,
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }

    # ---------- Gmail ----------
    def list_messages(self, max_results: int = 10, query: str = "in:inbox") -> List[Dict]:
        self._ensure_valid_creds()
        service = build("gmail", "v1", credentials=self.creds)
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])
        detailed = []
        for m in messages:
            msg = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            detailed.append({
                "id": msg["id"],
                "snippet": msg.get("snippet"),
                "from": headers.get("From"),
                "subject": headers.get("Subject"),
                "date": headers.get("Date"),
            })
        return detailed

    def get_message(self, message_id: str) -> Dict:
        self._ensure_valid_creds()
        service = build("gmail", "v1", credentials=self.creds)
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        return msg

    def send_email(self, to: str, subject: str, body: str) -> Dict:
        if settings.DRY_RUN:
            return {"status": "dry-run", "message": f"Would send Gmail to {to} with subject '{subject}'"}
        self._ensure_valid_creds()
        import base64
        from email.mime.text import MIMEText
        service = build("gmail", "v1", credentials=self.creds)
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"status": "sent", "id": sent.get("id"), "to": to, "subject": subject}

    # ---------- Calendar ----------
    def list_events(self, days_ahead: int = 7) -> List[Dict]:
        self._ensure_valid_creds()
        service = build("calendar", "v3", credentials=self.creds)
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict:
        if settings.DRY_RUN:
            return {
                "status": "dry-run",
                "message": f"Would create Google event '{summary}' from {start} to {end}",
            }
        self._ensure_valid_creds()
        service = build("calendar", "v3", credentials=self.creds)
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {"status": "created", "id": created.get("id"), "htmlLink": created.get("htmlLink")}

    def get_profile(self) -> Dict:
        self._ensure_valid_creds()
        service = build("oauth2", "v2", credentials=self.creds)
        return service.userinfo().get().execute()
