"""
User login routes (OAuth Sign-In) + session helpers.
Integration OAuth (mail/calendar) stays in main.py under /auth/...
"""

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
import structlog

from app.core.config import settings
from app.services.auth import (
    create_access_token,
    decode_access_token,
    get_google_login_url,
    exchange_google_login_code,
    get_microsoft_login_url,
    exchange_microsoft_login_code,
    new_oauth_state,
)
from app.services.token_store import ensure_user
from app.models.database import AsyncSessionLocal
from app.services.conversation import log_audit

logger = structlog.get_logger()
router = APIRouter(prefix=f"{settings.API_PREFIX}/login", tags=["login"])

# Simple in-memory state store for OAuth CSRF (use Redis in production)
_oauth_states: dict = {}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")


async def get_current_user(
    request: Request,
    rafaela_session: Optional[str] = Cookie(None, alias="rafaela_session"),
) -> Optional[dict]:
    """Optional auth: returns user dict or None."""
    token = rafaela_session
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    return {
        "user_id": payload.sub,
        "email": payload.email,
        "name": payload.name,
        "provider": payload.provider,
    }


async def require_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    return user


DEFAULT_USER_ID = "demo-user"


async def resolve_user_id(user: Optional[dict] = Depends(get_current_user)) -> str:
    """
    The user a request acts as, taken from the session only.

    A client-supplied user_id is never consulted — that was how callers used to
    read other people's conversations. Without a session this falls back to the
    demo user for local development, unless REQUIRE_AUTH is set or we are in
    production, where it is a 401.

    Use this for user-scoped reads. Endpoints that change external state should
    depend on require_user instead, so they always need a real session.
    """
    if user:
        return user["user_id"]
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    return DEFAULT_USER_ID


@router.get("/providers")
async def list_login_providers():
    """Which identity providers are configured."""
    return {
        "google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "microsoft": bool(settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET),
        "demo": settings.ENVIRONMENT in ("development", "trial"),
    }


@router.get("/google")
async def login_google_start():
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(400, "Google login not configured")
    state = new_oauth_state()
    _oauth_states[state] = "google"
    url = get_google_login_url(state, settings.GOOGLE_LOGIN_REDIRECT_URI)
    return {"auth_url": url}


@router.get("/google/callback")
async def login_google_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error={error}")
    if not code or state not in _oauth_states:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=invalid_state")
    _oauth_states.pop(state, None)
    try:
        info = await exchange_google_login_code(code, settings.GOOGLE_LOGIN_REDIRECT_URI)
        async with AsyncSessionLocal() as session:
            await ensure_user(session, info["user_id"])
        token = create_access_token(
            info["user_id"], info.get("email"), info.get("name"), "google"
        )
        await log_audit(info["user_id"], "login", {"provider": "google"})
        resp = RedirectResponse(f"{settings.FRONTEND_URL}/?login=ok")
        _set_session_cookie(resp, token)
        return resp
    except Exception as e:
        logger.exception("google_login_failed")
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=login_failed")


@router.get("/microsoft")
async def login_microsoft_start():
    if not settings.MS_CLIENT_ID:
        raise HTTPException(400, "Microsoft login not configured")
    state = new_oauth_state()
    _oauth_states[state] = "microsoft"
    url = get_microsoft_login_url(state, settings.MS_LOGIN_REDIRECT_URI)
    return {"auth_url": url}


@router.get("/microsoft/callback")
async def login_microsoft_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error={error}")
    if not code or state not in _oauth_states:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=invalid_state")
    _oauth_states.pop(state, None)
    try:
        info = await exchange_microsoft_login_code(code, settings.MS_LOGIN_REDIRECT_URI)
        async with AsyncSessionLocal() as session:
            await ensure_user(session, info["user_id"])
        token = create_access_token(
            info["user_id"], info.get("email"), info.get("name"), "microsoft"
        )
        await log_audit(info["user_id"], "login", {"provider": "microsoft"})
        resp = RedirectResponse(f"{settings.FRONTEND_URL}/?login=ok")
        _set_session_cookie(resp, token)
        return resp
    except Exception as e:
        logger.exception("microsoft_login_failed")
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=login_failed")


@router.post("/demo")
async def login_demo():
    """Trial-only: sign in as demo user without OAuth."""
    if settings.ENVIRONMENT not in ("development", "trial"):
        raise HTTPException(403, "Demo login disabled in production")
    user_id = "demo-user"
    async with AsyncSessionLocal() as session:
        await ensure_user(session, user_id)
    token = create_access_token(user_id, "demo@local", "Demo User", "demo")
    resp = JSONResponse({"status": "ok", "user_id": user_id, "name": "Demo User"})
    _set_session_cookie(resp, token)
    return resp


@router.get("/me")
async def login_me(user: Optional[dict] = Depends(get_current_user)):
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, **user}


@router.post("/logout")
async def logout(user: Optional[dict] = Depends(get_current_user)):
    if user:
        await log_audit(user["user_id"], "logout", {})
    resp = JSONResponse({"status": "logged_out"})
    _clear_session_cookie(resp)
    return resp
