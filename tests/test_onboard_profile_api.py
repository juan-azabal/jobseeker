import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.main import app

MOCK_PROFILE = {
    "name": "Alice Martin",
    "email": "alice@example.com",
    "languages": ["en", "fr"],
    "home_locations": ["paris", "france"],
    "current_level": "senior",
    "track": "ic",
    "target_level": "principal",
    "domains": {"data": 15, "ml": 10},
    "skills": ["python", "sql", "stakeholder-management"],
    "exclude_companies": ["OldCorp"],
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(db_path, {
        "google_id": "g_t", "email": "t@t.com",
        "name": "T", "avatar_url": None, "profile_id": None,
    })
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("session", "tok")
    return c


def test_generate_profile_200(authed_client):
    with patch("api.routes.onboard._extract_profile_from_cv", return_value=MOCK_PROFILE):
        resp = authed_client.post(
            "/api/onboard/generate-profile",
            json={"cv_markdown": "# Alice Martin\n\nSenior PM with data experience"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice Martin"
    assert "domains" in data
    assert "skills" in data


def test_generate_profile_missing_body_422(authed_client):
    resp = authed_client.post("/api/onboard/generate-profile", json={})
    assert resp.status_code == 422


def test_generate_profile_unauthenticated():
    c = TestClient(app)
    resp = c.post(
        "/api/onboard/generate-profile",
        json={"cv_markdown": "# Alice"},
    )
    assert resp.status_code == 401
