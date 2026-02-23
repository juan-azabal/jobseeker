import pytest
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.main import app


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    yield db_path


def test_jobs_no_session_returns_401():
    c = TestClient(app)
    resp = c.get("/api/jobs")
    assert resp.status_code == 401


def test_jobs_valid_session_returns_200(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    user = upsert_user(db_path, {
        "google_id": "g1", "email": "a@b.com",
        "name": "A", "avatar_url": None, "profile_id": None,
    })
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("session", "tok")
    resp = c.get("/api/jobs")
    assert resp.status_code == 200


def test_health_public():
    c = TestClient(app)
    resp = c.get("/api/health")
    assert resp.status_code == 200


def test_auth_login_public():
    from unittest.mock import AsyncMock, patch, MagicMock
    from fastapi.responses import RedirectResponse
    c = TestClient(app)
    with patch("api.routes.auth.oauth") as mock_oauth:
        mock_oauth.google.authorize_redirect = AsyncMock(
            return_value=RedirectResponse(url="https://accounts.google.com")
        )
        resp = c.get("/api/auth/login", follow_redirects=False)
    assert resp.status_code != 401
