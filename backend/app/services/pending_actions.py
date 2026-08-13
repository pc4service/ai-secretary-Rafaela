"""
Human-in-the-loop pending actions service.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import PendingAction, AsyncSessionLocal, User
from app.services.token_store import ensure_user
import structlog

logger = structlog.get_logger()


async def create_pending_action(
    user_id: str,
    action_type: str,
    payload: Dict[str, Any],
    description: str,
) -> PendingAction:
    async with AsyncSessionLocal() as session:
        await ensure_user(session, user_id)
        action = PendingAction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action_type=action_type,
            payload=payload,
            description=description,
            status="pending",
        )
        session.add(action)
        await session.commit()
        await session.refresh(action)
        logger.info("pending_action_created", action_id=action.id, type=action_type)
        return action


async def get_pending_action(action_id: str) -> Optional[PendingAction]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PendingAction).where(PendingAction.id == action_id)
        )
        return result.scalar_one_or_none()


async def list_pending_for_user(user_id: str, status: str = "pending") -> List[PendingAction]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PendingAction)
            .where(PendingAction.user_id == user_id, PendingAction.status == status)
            .order_by(PendingAction.created_at.desc())
        )
        return list(result.scalars().all())


async def resolve_action(
    action_id: str,
    approve: bool,
    executor=None,
) -> Dict[str, Any]:
    """
    Approve or reject a pending action.
    If approve=True and executor is provided, execute the real action.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PendingAction).where(PendingAction.id == action_id)
        )
        action = result.scalar_one_or_none()
        if not action:
            return {"error": "Action not found"}
        if action.status != "pending":
            return {"error": f"Action already {action.status}"}

        if not approve:
            action.status = "rejected"
            action.resolved_at = datetime.now(timezone.utc)
            action.result = "Rejected by user"
            await session.commit()
            return {"status": "rejected", "action_id": action_id}

        # Approve
        action.status = "approved"
        action.resolved_at = datetime.now(timezone.utc)

        result_text = "Approved"
        if executor:
            try:
                result_text = await executor(action.action_type, action.payload)
                action.status = "executed"
                action.result = str(result_text)
            except Exception as e:
                action.status = "failed"
                action.result = str(e)
                result_text = f"Execution failed: {e}"

        await session.commit()
        return {
            "status": action.status,
            "action_id": action_id,
            "result": result_text,
        }
