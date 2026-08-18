"""OAuth state must decide the account to bind — never the callback URL."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.oauth_state import consume, issue

API = settings.API_PREFIX
client = TestClient(app)

# States are random tokens, so tests cannot collide and need no cleanup.
# TTL and backend behaviour are covered in test_state_store.py.


def test_issued_state_resolves_to_the_issuing_user():
    state = issue("google-123", "microsoft")
    assert consume(state, "microsoft") == "google-123"


def test_state_is_opaque_not_the_user_id():
    state = issue("google-123", "microsoft")
    assert "google-123" not in state


def test_state_is_single_use():
    state = issue("google-123", "microsoft")
    consume(state, "microsoft")
    with pytest.raises(ValueError):
        consume(state, "microsoft")


def test_unknown_state_is_rejected():
    """The old hole: attacker sends state=<victim> and binds their own account."""
    with pytest.raises(ValueError):
        consume("victim-user", "microsoft")


def test_blank_state_is_rejected():
    for bad in ("", None):
        with pytest.raises(ValueError):
            consume(bad, "microsoft")


def test_state_cannot_cross_providers():
    state = issue("google-123", "microsoft")
    with pytest.raises(ValueError):
        consume(state, "google")


# --- endpoint behaviour ---

@pytest.mark.parametrize(
    "path,provider",
    [(f"{API}/auth/microsoft/callback", "ms"), (f"{API}/auth/google/callback", "google")],
)
def test_callback_with_forged_state_does_not_store_tokens(path, provider, monkeypatch):
    called = {}

    async def fake_save(**kwargs):
        called["hit"] = True

    monkeypatch.setattr("app.main.save_oauth_token", fake_save)

    res = client.get(
        f"{path}?code=attacker-code&state=victim-user", follow_redirects=False
    )
    # Redirected to the error page, and no token was written for anyone.
    assert res.status_code in (302, 307)
    assert f"{provider}=error" in res.headers["location"]
    assert "hit" not in called


def test_callback_error_redirect_uses_configured_frontend():
    res = client.get(
        f"{API}/auth/microsoft/callback?code=x&state=bogus", follow_redirects=False
    )
    assert res.headers["location"].startswith(settings.FRONTEND_URL)
