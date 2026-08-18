"""What an unauthenticated caller may reach, and what production hides."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import _cors_origins, app, docs_urls

API = settings.API_PREFIX
client = TestClient(app)


# --- P1-5: the agent policy is not public ---

def test_system_prompt_requires_a_session():
    assert client.get(f"{API}/system-prompt").status_code == 401


def test_system_prompt_served_to_a_session():
    from app.api_auth import require_user

    app.dependency_overrides[require_user] = lambda: {"user_id": "u1"}
    try:
        res = client.get(f"{API}/system-prompt")
        assert res.status_code == 200
        assert "system_prompt" in res.json()
    finally:
        app.dependency_overrides.clear()


# --- P2-9: CORS may not trust loopback in production ---

def test_dev_keeps_localhost_for_convenience(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "trial")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    assert "http://localhost:3000" in _cors_origins()


def test_production_drops_loopback_origins(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings, "CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:8000"]
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://rafaela.example.com")
    origins = _cors_origins()
    assert origins == ["https://rafaela.example.com"]


def test_production_keeps_real_hosts(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://a.example.com"])
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://b.example.com")
    assert _cors_origins() == ["https://a.example.com", "https://b.example.com"]


def test_frontend_url_is_not_duplicated(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://a.example.com"])
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://a.example.com")
    assert _cors_origins() == ["https://a.example.com"]


def test_production_without_usable_origins_denies_everything(monkeypatch):
    """Fail closed rather than falling back to a permissive default."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "FRONTEND_URL", "")
    assert _cors_origins() == []


# --- P2-8: docs are off in production ---

def test_production_switches_docs_off():
    assert docs_urls("production") == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


@pytest.mark.parametrize("env", ["development", "trial"])
def test_non_production_keeps_docs(env):
    assert all(v is not None for v in docs_urls(env).values())


def test_docs_are_reachable_in_this_environment():
    """This env is not production, so the wiring should really serve them."""
    assert settings.ENVIRONMENT != "production"
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
