import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.main import app

MOCK_USERINFO = {
    "sub": "google_999",
    "email": "user@example.com",
    "name": "Test User",
    "picture": "https://example.com/pic.png",
}


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("SESSION_SECRET", "test_session_secret")
    yield db_path


client = TestClient(app, raise_server_exceptions=True)


def test_me_no_cookie_returns_401():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_login_redirects():
    from fastapi.responses import RedirectResponse

    with patch("api.routes.auth.oauth") as mock_oauth:
        mock_client = MagicMock()
        mock_client.authorize_redirect = AsyncMock(
            return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
        )
        mock_oauth.google = mock_client
        resp = client.get("/api/auth/login", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)


def test_logout_clears_cookie():
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    # Cookie should be cleared
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session" in set_cookie or resp.json().get("status") == "ok"


def test_me_with_valid_session(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    from api.db.queries import upsert_user, create_session

    user = upsert_user(
        db_path,
        {
            "google_id": "g_test",
            "email": "u@e.com",
            "name": "U",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    create_session(db_path, "valid_token", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "valid_token")
    resp = c.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "u@e.com"
