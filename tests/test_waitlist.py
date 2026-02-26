"""Tests for Phase 15.1 — Waitlist backend (migration + API endpoints).

Written BEFORE implementation (test-first). Must FAIL initially.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import api.routes.waitlist as waitlist_module
from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.main import app


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    """Reset in-memory rate limiter between tests."""
    waitlist_module._rate_limiter.clear()
    yield
    waitlist_module._rate_limiter.clear()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh DB + monkeypatched DB_PATH."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    return db_path


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def admin_client(db):
    """Authenticated admin client."""
    user = upsert_user(
        db,
        {
            "google_id": "g_admin",
            "email": "admin@test.com",
            "name": "Admin",
            "avatar_url": None,
            "profile_id": "admin",
        },
    )
    conn = sqlite3.connect(db)
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()
    create_session(db, "admin_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "admin_tok")
    return c, db


class TestWaitlistPost:
    def test_valid_email_returns_201(self, client, db):
        resp = client.post("/api/waitlist", json={"email": "user@example.com"})
        assert resp.status_code == 201
        assert resp.json() == {"status": "ok"}

    def test_valid_email_stored_in_db(self, client, db):
        client.post("/api/waitlist", json={"email": "stored@example.com"})
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT email FROM waitlist WHERE email = ?", ("stored@example.com",)).fetchone()
        conn.close()
        assert row is not None

    def test_duplicate_email_returns_409(self, client, db):
        client.post("/api/waitlist", json={"email": "dup@example.com"})
        resp = client.post("/api/waitlist", json={"email": "dup@example.com"})
        assert resp.status_code == 409
        assert resp.json()["detail"] == "already_registered"

    def test_invalid_email_no_at_returns_422(self, client):
        resp = client.post("/api/waitlist", json={"email": "notanemail"})
        assert resp.status_code == 422
        assert resp.json()["detail"] == "invalid_email"

    def test_invalid_email_no_domain_returns_422(self, client):
        resp = client.post("/api/waitlist", json={"email": "missing@"})
        assert resp.status_code == 422
        assert resp.json()["detail"] == "invalid_email"

    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/waitlist", json={})
        assert resp.status_code == 422


class TestWaitlistAdminGet:
    def test_get_without_auth_returns_401(self, client):
        resp = client.get("/api/admin/waitlist")
        assert resp.status_code == 401

    def test_get_with_admin_returns_200_with_list_and_count(self, admin_client, client):
        ac, db = admin_client
        # Add an entry first
        client.post("/api/waitlist", json={"email": "w@example.com"})
        resp = ac.get("/api/admin/waitlist")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        assert data["total"] >= 1
        assert any(e["email"] == "w@example.com" for e in data["entries"])


class TestRateLimit:
    def test_6th_request_from_same_ip_returns_429(self, client, db):
        for i in range(5):
            resp = client.post("/api/waitlist", json={"email": f"rl{i}@example.com"})
            assert resp.status_code == 201
        resp = client.post("/api/waitlist", json={"email": "rl5@example.com"})
        assert resp.status_code == 429
        assert resp.json()["detail"] == "rate_limited"
