"""
Conversation memory service – persist chat history per user.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.models.database import Conversation, Message, AsyncSessionLocal, AuditLog
from app.services.token_store import ensure_user
import structlog

logger = structlog.get_logger()


async def get_or_create_conversation(user_id: str, conversation_id: Optional[str] = None) -> Conversation:
    async with AsyncSessionLocal() as session:
        await ensure_user(session, user_id)

        if conversation_id:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .options(selectinload(Conversation.messages))
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conv = Conversation(id=str(uuid.uuid4()), user_id=user_id, title="Νέα συνομιλία")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return conv


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    pending_action_id: Optional[str] = None,
) -> Message:
    async with AsyncSessionLocal() as session:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            pending_action_id=pending_action_id,
        )
        session.add(msg)
        # touch conversation updated_at
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            if conv.title == "Νέα συνομιλία" and role == "user":
                conv.title = content[:60] + ("…" if len(content) > 60 else "")
        await session.commit()
        await session.refresh(msg)
        return msg


async def get_conversation_messages(
    conversation_id: str,
    limit: int = 50,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Messages of a conversation (most recent ``limit``, chronological order).

    Pass user_id whenever the caller is a request: without it this returns any
    conversation's messages to anyone holding the id. It stays optional so
    internal callers that already loaded the conversation for a known owner do
    not have to repeat the check.
    """
    async with AsyncSessionLocal() as session:
        query = select(Message).where(Message.conversation_id == conversation_id)
        if user_id is not None:
            query = query.join(Conversation).where(Conversation.user_id == user_id)
        # Newest first for the window, then reverse → chronological for the LLM.
        result = await session.execute(
            query.order_by(Message.created_at.desc()).limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "pending_action_id": m.pending_action_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]


async def search_user_conversation_memory(
    user_id: str,
    *,
    query: str = "",
    days: int = 7,
    limit: int = 25,
    conversation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search this user's stored chat messages (across conversations by default).

    Used when the user asks what was discussed yesterday / earlier — that data
    lives in Postgres, not in Outlook. Scoped strictly by user_id.
    """
    from datetime import timedelta
    from sqlalchemy import and_, or_

    days = max(1, min(int(days or 7), 90))
    limit = max(1, min(int(limit or 25), 50))
    q = (query or "").strip()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Message, Conversation)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.created_at >= since,
            )
        )
        if conversation_id:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        if q:
            # Simple ILIKE tokens (AND). Avoids raw SQL injection via bound params.
            tokens = [t for t in q.replace(",", " ").split() if len(t) >= 2][:8]
            if tokens:
                stmt = stmt.where(
                    and_(*[Message.content.ilike(f"%{t}%") for t in tokens])
                )
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).all()

        out: List[Dict[str, Any]] = []
        for msg, conv in rows:
            out.append(
                {
                    "conversation_id": conv.id,
                    "conversation_title": conv.title,
                    "role": msg.role,
                    "content": (msg.content or "")[:1500],
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
            )
        return out


def format_memory_for_agent(hits: List[Dict[str, Any]], *, query: str = "") -> str:
    """Human-readable block for the LLM (not untrusted third-party content)."""
    if not hits:
        return (
            "No matching messages found in Rafaela conversation history "
            f"for query={query!r}. "
            "Tell the user you only searched *chat memory* (not email/calendar) "
            "and ask for a keyword, date, or to open the old thread in the sidebar."
        )
    lines = [
        f"Found {len(hits)} message(s) in conversation history"
        + (f" matching {query!r}" if query else "")
        + ":",
        "Use these as prior chat context. Do NOT claim they are emails or calendar events.",
        "",
    ]
    for i, h in enumerate(hits, 1):
        when = h.get("created_at") or "?"
        title = h.get("conversation_title") or "(no title)"
        role = h.get("role") or "?"
        body = (h.get("content") or "").replace("\n", " ").strip()
        if len(body) > 400:
            body = body[:400] + "…"
        lines.append(
            f"{i}. [{when}] conv={title!r} ({role}): {body}"
        )
    return "\n".join(lines)


async def list_conversations(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        convs = result.scalars().all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in convs
        ]


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return False
        await session.delete(conv)
        await session.commit()
        return True


async def log_audit(user_id: str, action: str, details: Optional[dict] = None) -> None:
    async with AsyncSessionLocal() as session:
        entry = AuditLog(user_id=user_id, action=action, details=details or {})
        session.add(entry)
        await session.commit()
