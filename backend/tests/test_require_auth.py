"""REQUIRE_AUTH and the removal of the anonymous demo-user fallback."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api_auth import DEFAULT_USER_ID, resolve_user_id
from app.core.config import settings
from app.main import app

API = settings.API_PREFIX
client = TestClient(app)

# Endpoints that acted as demo-user for anonymous callers before this change.
USER_SCOPED = [
    ("GET", f"{API}/conversations"),
    ("GET", f"{API}/conversations/some-id/messages"),
    ("DELETE", f"{API}/conversations/some-id"),
    ("GET", f"{API}/settings"),
]


# --- auth_required policy ---

def test_trial_allows_demo_fallback(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "trial")
    assert settings.auth_required is False


def test_require_auth_flag_turns_it_on(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "trial")
    assert settings.auth_required is True


def test_production_always_requires_auth(monkeypatch):
    """Even with the flag off — an anonymous caller would act as demo-user."""
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.auth_required is True


# --- resolver ---

@pytest.mark.asyncio
async def test_resolver_prefers_the_session_user():
    assert await resolve_user_id(user={"user_id": "google-123"}) == "google-123"


@pytest.mark.asyncio
async def test_resolver_falls_back_when_auth_not_required(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "trial")
    assert await resolve_user_id(user=None) == DEFAULT_USER_ID


@pytest.mark.asyncio
async def test_resolver_rejects_anonymous_when_required(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    with pytest.raises(HTTPException) as exc:
        await resolve_user_id(user=None)
    assert exc.value.status_code == 401


# --- endpoints ---

@pytest.mark.parametrize("method,path", USER_SCOPED)
def test_user_scoped_endpoints_401_when_auth_required(monkeypatch, method, path):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    assert client.request(method, path).status_code == 401


def test_chat_no_longer_accepts_a_client_user_id():
    """user_id was removed from ChatRequest, so a sent one is ignored."""
    from app.main import ChatRequest

    assert "user_id" not in ChatRequest.model_fields
    parsed = ChatRequest(message="hi", user_id="victim")
    assert not hasattr(parsed, "user_id")


def test_oauth_login_state_is_not_caller_controlled(monkeypatch):
    """state decides whose account tokens are stored under."""
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    for path in (f"{API}/auth/microsoft/login", f"{API}/auth/google/login"):
        assert client.get(f"{path}?user_id=victim").status_code == 401
