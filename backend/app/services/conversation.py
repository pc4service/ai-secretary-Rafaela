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
    Messages of a conversation.

    Pass user_id whenever the caller is a request: without it this returns any
    conversation's messages to anyone holding the id. It stays optional so
    internal callers that already loaded the conversation for a known owner do
    not have to repeat the check.
    """
    async with AsyncSessionLocal() as session:
        query = select(Message).where(Message.conversation_id == conversation_id)
        if user_id is not None:
            query = query.join(Conversation).where(Conversation.user_id == user_id)
        result = await session.execute(
            query.order_by(Message.created_at.asc()).limit(limit)
        )
        messages = result.scalars().all()
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
