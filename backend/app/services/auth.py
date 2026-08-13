"""
User authentication via OAuth (Google / Microsoft) + JWT session cookies.
Separate from integration OAuth (mail/calendar scopes).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import secrets
import httpx
from jose import jwt, JWTError
from pydantic import BaseModel

from app.core.config import settings
import structlog

logger = structlog.get_logger()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days


class TokenPayload(BaseModel):
    sub: str  # user_id
    email: Optional[str] = None
    name: Optional[str] = None
    provider: Optional[str] = None  # google | microsoft | local
    exp: Optional[int] = None


def create_access_token(
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    provider: str = "local",
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "provider": provider,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(
            sub=data["sub"],
            email=data.get("email"),
            name=data.get("name"),
            provider=data.get("provider"),
            exp=data.get("exp"),
        )
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        return None


# ---------- Google Sign-In (OpenID) ----------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Login scopes only (identity) – not full Gmail
GOOGLE_LOGIN_SCOPES = "openid email profile"


def get_google_login_url(state: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_LOGIN_SCOPES,
        "access_type": "online",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_login_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        access = tokens.get("access_token")
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        user_resp.raise_for_status()
        info = user_resp.json()
    user_id = f"google:{info.get('sub')}"
    return {
        "user_id": user_id,
        "email": info.get("email"),
        "name": info.get("name") or info.get("email"),
        "provider": "google",
        "picture": info.get("picture"),
    }


# ---------- Microsoft Sign-In (OpenID) ----------

def get_microsoft_login_url(state: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode
    authority = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}"
    params = {
        "client_id": settings.MS_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email User.Read",
        "state": state,
    }
    return f"{authority}/oauth2/v2.0/authorize?{urlencode(params)}"


async def exchange_microsoft_login_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    if not settings.MS_CLIENT_ID or not settings.MS_CLIENT_SECRET:
        raise ValueError("Microsoft OAuth not configured")
    token_url = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            token_url,
            data={
                "client_id": settings.MS_CLIENT_ID,
                "client_secret": settings.MS_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "scope": "openid profile email User.Read",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        access = tokens.get("access_token")
        # Graph /me
        me = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access}"},
            params={"$select": "id,displayName,mail,userPrincipalName"},
        )
        me.raise_for_status()
        info = me.json()
    oid = info.get("id")
    email = info.get("mail") or info.get("userPrincipalName")
    user_id = f"microsoft:{oid}"
    return {
        "user_id": user_id,
        "email": email,
        "name": info.get("displayName") or email,
        "provider": "microsoft",
        "picture": None,
    }


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)
