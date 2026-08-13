"""
Rafaela – AI Secretary – FastAPI entrypoint
Includes: chat + memory, OAuth, HITL, rate limiting, audit.
"""

from contextlib import asynccontextmanager
from collections import defaultdict
from time import time
from msal import SerializableTokenCache
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from haystack.dataclasses import ChatMessage
import structlog
import re

from app.core.config import settings
from app.agent.secretary_agent import create_secretary_agent, run_agent, SECRETARY_SYSTEM_PROMPT
from app.models.database import init_db
from app.services.token_store import save_oauth_token, delete_oauth_token, is_connected, get_token_info
from app.services.pending_actions import resolve_action, list_pending_for_user, get_pending_action
from app.services.microsoft import Microsoft365Service
from app.services.google import GoogleWorkspaceService
from app.services.conversation import (
    get_or_create_conversation,
    add_message,
    get_conversation_messages,
    list_conversations,
    delete_conversation,
    log_audit,
)

logger = structlog.get_logger()

# Simple in-memory rate limiter (per IP)
_rate_buckets: Dict[str, list] = defaultdict(list)
RATE_LIMIT = 60  # requests
RATE_WINDOW = 60  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("database_initialized")
    yield


app = FastAPI(
    title="Rafaela – AI Secretary",
    version=settings.APP_VERSION,
    description="GDPR-compliant AI Secretary Agent powered by Haystack",
    lifespan=lifespan,
)

from app.api_auth import router as login_router, get_current_user, require_user

app.include_router(login_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/health"):
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    now = time()
    bucket = _rate_buckets[client]
    _rate_buckets[client] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(_rate_buckets[client]) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
    _rate_buckets[client].append(now)
    return await call_next(request)


# ---------- Schemas ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    history: Optional[List[dict]] = Field(default_factory=list)
    user_id: str = "demo-user"
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    pending_action_id: Optional[str] = None
    conversation_id: Optional[str] = None
    dry_run: bool = settings.DRY_RUN
    environment: str = settings.ENVIRONMENT


class ActionResolveRequest(BaseModel):
    approve: bool
    user_id: str = "demo-user"


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    dry_run: bool
    llm_provider: str


# ---------- Action executor ----------

async def execute_action(action_type: str, payload: dict) -> str:
    user_id = payload.get("user_id", "demo-user")
    from app.services.token_store import get_oauth_token, get_fresh_microsoft_tokens, ReconnectRequired

    if action_type == "ms_send_email":
        try:
            token = await get_fresh_microsoft_tokens(user_id)
        except ReconnectRequired as e:
            raise ValueError(str(e))
        service = Microsoft365Service(token.get("access_token"), token.get("refresh_token"))
        result = await service.send_mail(payload["to"], payload["subject"], payload["body"])
        await log_audit(user_id, "ms_send_email", {"to": payload["to"], "subject": payload["subject"]})
        return str(result)

    elif action_type == "ms_create_event":
        try:
            token = await get_fresh_microsoft_tokens(user_id)
        except ReconnectRequired as e:
            raise ValueError(str(e))
        service = Microsoft365Service(token.get("access_token"), token.get("refresh_token"))
        att = [a.strip() for a in payload.get("attendees", "").split(",") if a.strip()] or None
        result = await service.create_event(
            subject=payload["subject"], start=payload["start"], end=payload["end"],
            body=payload.get("body", ""), location=payload.get("location", ""), attendees=att,
        )
        await log_audit(user_id, "ms_create_event", {"subject": payload["subject"]})
        return str(result)

    elif action_type == "google_send_email":
        token = await get_oauth_token(user_id, "google")
        if not token:
            raise ValueError("Google not connected")
        service = GoogleWorkspaceService(token_data=token)
        result = service.send_email(payload["to"], payload["subject"], payload["body"])
        await log_audit(user_id, "google_send_email", {"to": payload["to"]})
        return str(result)

    elif action_type == "google_create_event":
        token = await get_oauth_token(user_id, "google")
        if not token:
            raise ValueError("Google not connected")
        service = GoogleWorkspaceService(token_data=token)
        att = [a.strip() for a in payload.get("attendees", "").split(",") if a.strip()] or None
        result = service.create_event(
            summary=payload["summary"], start=payload["start"], end=payload["end"],
            description=payload.get("description", ""), location=payload.get("location", ""), attendees=att,
        )
        await log_audit(user_id, "google_create_event", {"summary": payload["summary"]})
        return str(result)

    raise ValueError(f"Unknown action type: {action_type}")


# ---------- Core routes ----------

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        dry_run=settings.DRY_RUN,
        llm_provider=settings.LLM_PROVIDER,
    )


@app.get("/")
async def root():
    return {"name": "Rafaela – AI Secretary", "version": settings.APP_VERSION, "docs": "/docs"}


@app.post(f"{settings.API_PREFIX}/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, raw: Request, user: dict | None = Depends(get_current_user)):
    try:
        # Prefer authenticated session user over client-supplied user_id
        effective_user = (user or {}).get("user_id") or request.user_id or "demo-user"
        conv = await get_or_create_conversation(effective_user, request.conversation_id)
        conversation_id = conv.id

        # Load history from DB if no client history provided
        messages: List[ChatMessage] = []
        if request.history:
            for h in request.history:
                role, content = h.get("role", "user"), h.get("content", "")
                if role == "user":
                    messages.append(ChatMessage.from_user(content))
                elif role == "assistant":
                    messages.append(ChatMessage.from_assistant(content))
        else:
            db_msgs = await get_conversation_messages(conversation_id, limit=30)
            for m in db_msgs:
                if m["role"] == "user":
                    messages.append(ChatMessage.from_user(m["content"]))
                elif m["role"] == "assistant":
                    messages.append(ChatMessage.from_assistant(m["content"]))

        messages.append(ChatMessage.from_user(request.message))
        await add_message(conversation_id, "user", request.message)

        agent = create_secretary_agent()
        result = await run_agent(messages, agent=agent)

        last_message = result.get("last_message")
        reply_text = last_message.text if last_message else "Sorry, I could not generate a reply."

        pending_id = None
        match = re.search(r"\[PENDING_ACTION:([a-f0-9\-]+)\]", reply_text)
        if match:
            pending_id = match.group(1)

        await add_message(conversation_id, "assistant", reply_text, pending_action_id=pending_id)
        await log_audit(effective_user, "chat", {"conversation_id": conversation_id})

        return ChatResponse(
            reply=reply_text,
            pending_action_id=pending_id,
            conversation_id=conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get(f"{settings.API_PREFIX}/system-prompt")
async def get_system_prompt():
    return {"system_prompt": SECRETARY_SYSTEM_PROMPT}


# ---------- Conversations ----------

@app.get(f"{settings.API_PREFIX}/conversations")
async def api_list_conversations(user_id: str = "demo-user"):
    return await list_conversations(user_id)


@app.get(f"{settings.API_PREFIX}/conversations/{{conversation_id}}/messages")
async def api_get_messages(conversation_id: str, user_id: str = "demo-user"):
    return await get_conversation_messages(conversation_id)


@app.delete(f"{settings.API_PREFIX}/conversations/{{conversation_id}}")
async def api_delete_conversation(conversation_id: str, user_id: str = "demo-user"):
    ok = await delete_conversation(user_id, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await log_audit(user_id, "delete_conversation", {"conversation_id": conversation_id})
    return {"status": "deleted"}


# ---------- Settings & OAuth ----------


def _key_present(value) -> bool:
    """True if a credential looks configured (non-empty and not an .env.example placeholder)."""
    if not value:
        return False
    return value not in ("sk-...", "sk-ant-...", "fc-...")

@app.get(f"{settings.API_PREFIX}/settings")
async def get_settings_info(user: dict | None = Depends(get_current_user), user_id: str = "demo-user"):
    uid = (user or {}).get("user_id") or user_id
    ms_connected = await is_connected(uid, "microsoft")
    ms_info = await get_token_info(uid, "microsoft") if ms_connected else None
    granted = set((ms_info or {}).get("scopes") or [])
    return {
        "microsoft_connected": ms_connected,
        "google_connected": await is_connected(uid, "google"),
        "dry_run": settings.DRY_RUN,
        "retention_days": settings.DEFAULT_RETENTION_DAYS,
        "environment": settings.ENVIRONMENT,
        "user_id": uid,
        "authenticated": bool(user),
        # Feature flags: which credentials are configured server-side.
        # Booleans only — secret values are never exposed to the frontend.
        "config": {
            "llm": _key_present(settings.OPENAI_API_KEY) if settings.LLM_PROVIDER == "openai" else _key_present(settings.ANTHROPIC_API_KEY),
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
            "microsoft_oauth": bool(settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET),
            # Granted vs required scopes (least-privilege drift detection)
            "microsoft_scopes": sorted(granted) if granted else None,
            "microsoft_scopes_missing": sorted(set(settings.MS_SCOPES) - granted) if granted else None,
            "microsoft_scopes_extra": sorted(granted - set(settings.MS_SCOPES) - {"openid", "profile", "offline_access"}) if granted else None,
            "microsoft_token_expires_at": (ms_info or {}).get("expires_at"),
            "google_oauth": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            "firecrawl": _key_present(settings.FIRECRAWL_API_KEY),
        },
    }


@app.get(f"{settings.API_PREFIX}/auth/microsoft/login")
async def ms_login(user_id: str = "demo-user"):
    try:
        service = Microsoft365Service()
        return {"auth_url": service.get_auth_url(state=user_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(f"{settings.API_PREFIX}/auth/microsoft/callback")
async def ms_callback(code: str, state: str = "demo-user"):
    try:
        # Fresh MSAL cache — the auth-code exchange populates it (AT + RT +
        # account metadata); persisting it enables the enterprise silent path.
        msal_cache = SerializableTokenCache()
        service = Microsoft365Service(token_cache=msal_cache)
        tokens = service.exchange_code(code)
        await save_oauth_token(
            user_id=state, provider="microsoft",
            token_data={
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "msal_cache": msal_cache.serialize(),
            },
            expires_in=tokens.get("expires_in"),
            scopes=tokens.get("scope"),
        )
        await log_audit(state, "oauth_connect", {"provider": "microsoft"})
        return RedirectResponse(url="http://localhost:3000/?tab=settings&ms=connected")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(f"{settings.API_PREFIX}/auth/google/login")
async def google_login(user_id: str = "demo-user"):
    try:
        service = GoogleWorkspaceService()
        return {"auth_url": service.get_auth_url(state=user_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(f"{settings.API_PREFIX}/auth/google/callback")
async def google_callback(code: str, state: str = "demo-user"):
    try:
        service = GoogleWorkspaceService()
        token_data = service.exchange_code(code)
        await save_oauth_token(user_id=state, provider="google", token_data=token_data)
        await log_audit(state, "oauth_connect", {"provider": "google"})
        return RedirectResponse(url="http://localhost:3000/?tab=settings&google=connected")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post(f"{settings.API_PREFIX}/auth/microsoft/disconnect")
async def ms_disconnect(user_id: str = "demo-user"):
    await delete_oauth_token(user_id, "microsoft")
    await log_audit(user_id, "oauth_disconnect", {"provider": "microsoft"})
    return {"status": "disconnected", "provider": "microsoft"}


@app.post(f"{settings.API_PREFIX}/auth/google/disconnect")
async def google_disconnect(user_id: str = "demo-user"):
    await delete_oauth_token(user_id, "google")
    await log_audit(user_id, "oauth_disconnect", {"provider": "google"})
    return {"status": "disconnected", "provider": "google"}


# ---------- HITL ----------

@app.get(f"{settings.API_PREFIX}/actions/pending")
async def get_pending_actions(user_id: str = "demo-user", status: str = "pending"):
    actions = await list_pending_for_user(user_id, status=status)
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description,
            "status": a.status,
            "result": a.result,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        }
        for a in actions
    ]


@app.get(f"{settings.API_PREFIX}/actions/history")
async def get_action_history(user_id: str = "demo-user"):
    """Return recent non-pending actions for the history view."""
    from app.models.database import PendingAction, AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PendingAction)
            .where(PendingAction.user_id == user_id, PendingAction.status != "pending")
            .order_by(PendingAction.created_at.desc())
            .limit(30)
        )
        actions = result.scalars().all()
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description,
            "status": a.status,
            "result": a.result,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        }
        for a in actions
    ]


@app.post(f"{settings.API_PREFIX}/actions/{{action_id}}/resolve")
async def resolve_pending_action(action_id: str, body: ActionResolveRequest):
    action = await get_pending_action(action_id)
    if action and action.payload is not None:
        action.payload["user_id"] = body.user_id

    result = await resolve_action(
        action_id=action_id,
        approve=body.approve,
        executor=execute_action if body.approve else None,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await log_audit(body.user_id, "action_resolve", {"action_id": action_id, "approve": body.approve, "status": result.get("status")})
    return result
