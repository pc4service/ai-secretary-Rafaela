"""The model must never be able to choose which user a tool acts as."""

from app.services.agent_context import (
    DEFAULT_USER_ID,
    current_agent_user,
    set_agent_user,
)


def test_defaults_to_demo_user():
    set_agent_user(None)
    assert current_agent_user() == DEFAULT_USER_ID


def test_uses_bound_session_user():
    set_agent_user("google-123")
    assert current_agent_user() == "google-123"


def test_model_supplied_id_is_ignored():
    set_agent_user("google-123")
    # A model trying to act as somebody else gets the session user anyway.
    assert current_agent_user("ms-victim-456") == "google-123"
    assert current_agent_user("demo-user") == "google-123"


def test_self_aliases_resolve_to_session_user():
    set_agent_user("google-123")
    for alias in ("me", "current", "self", "", None):
        assert current_agent_user(alias) == "google-123"


def test_blank_binding_falls_back():
    set_agent_user("   ")
    assert current_agent_user() == DEFAULT_USER_ID
