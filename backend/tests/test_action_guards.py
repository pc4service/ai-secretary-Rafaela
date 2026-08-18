"""Executor guards: mail stays read-only, executor runs as the action's owner."""

import pytest

from app.main import BLOCKED_ACTION_TYPES, execute_action


@pytest.mark.parametrize("action_type", sorted(BLOCKED_ACTION_TYPES))
@pytest.mark.asyncio
async def test_mail_send_is_refused(action_type):
    payload = {"to": "someone@example.com", "subject": "x", "body": "y"}
    with pytest.raises(ValueError, match="read-only"):
        await execute_action(action_type, payload, "demo-user")


@pytest.mark.asyncio
async def test_unknown_action_type_is_refused():
    with pytest.raises(ValueError, match="Unknown action type"):
        await execute_action("definitely_not_real", {}, "demo-user")


@pytest.mark.asyncio
async def test_executor_ignores_user_id_smuggled_in_payload(monkeypatch):
    """The owner argument wins over any user_id left inside the payload."""
    seen = {}

    def fake_save(filename, content):
        from pathlib import Path

        seen["filename"] = filename
        return Path(filename)

    async def fake_audit(user_id, action, meta):
        seen["audit_user"] = user_id

    monkeypatch.setattr("app.services.knowledge.save_knowledge_markdown", fake_save)
    monkeypatch.setattr(
        "app.services.knowledge.index_knowledge_to_qdrant",
        lambda recreate=False: {"status": "skipped", "chunks": 0},
    )
    monkeypatch.setattr("app.main.log_audit", fake_audit)

    await execute_action(
        "knowledge_save_page",
        {"filename": "x.md", "content": "hello", "user_id": "attacker"},
        "real-owner",
    )
    assert seen["audit_user"] == "real-owner"
