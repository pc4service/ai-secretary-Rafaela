"""
Endpoint guards added in P0/P1.

These assert the auth boundary only, so they need no database: an
unauthenticated request is rejected by the dependency before any handler runs.
"""

import pytest
from fastapi.testclient import TestClient

from app.api_auth import require_user
from app.core.config import settings
from app.main import app

API = settings.API_PREFIX

# No context manager: skip lifespan (DB init / Qdrant indexing) on purpose.
client = TestClient(app)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{API}/actions/pending"),
        ("GET", f"{API}/actions/history"),
        ("POST", f"{API}/actions/00000000-0000-0000-0000-000000000000/resolve"),
        ("GET", f"{API}/knowledge/search?q=follow-up"),
        ("POST", f"{API}/knowledge/index"),
    ],
)
def test_protected_endpoints_reject_anonymous(method, path):
    res = client.request(method, path, json={"approve": True})
    assert res.status_code == 401, res.text


def test_status_stays_open_as_health_probe():
    """Documented smoke check — counts and filenames only, never content."""
    res = client.get(f"{API}/knowledge/status")
    assert res.status_code == 200
    body = res.json()
    assert "chunk_count" in body
    # Must not leak document text.
    assert "results" not in body


def test_resolve_ignores_client_supplied_user_id():
    """user_id was removed from the schema; sending it must not be honoured."""
    app.dependency_overrides[require_user] = lambda: {"user_id": "real-user"}
    try:
        res = client.post(
            f"{API}/actions/00000000-0000-0000-0000-000000000000/resolve",
            json={"approve": True, "user_id": "attacker"},
        )
        # Unknown action for this user -> 404, never a 200 acting as "attacker".
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_knowledge_search_requires_a_query():
    app.dependency_overrides[require_user] = lambda: {"user_id": "real-user"}
    try:
        assert client.get(f"{API}/knowledge/search?q=").status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_knowledge_search_returns_results_when_authenticated():
    app.dependency_overrides[require_user] = lambda: {"user_id": "real-user"}
    try:
        res = client.get(f"{API}/knowledge/search?q=follow-up")
        assert res.status_code == 200
        body = res.json()
        assert body["mode"] in ("keyword", "semantic", "hybrid")
        assert isinstance(body["results"], list)
    finally:
        app.dependency_overrides.clear()
