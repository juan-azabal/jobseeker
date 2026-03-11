"""Tests for api/routes/agent.py — profile and seen_ids endpoints.

Phase 1.3: endpoints use integer user_id as primary identifier.
profile-by-name kept as backward-compat alias until Phase 2.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient


INGEST_KEY = "test-ingest-key"

_PROFILE_YAML = "user:\n  name: Noura\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    from api.main import app
    from api.db.init import init_db

    init_db(str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def client_and_uid(tmp_path, monkeypatch):
    """Client with a seeded user; returns (client, user_id, profile_id)."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    from api.main import app
    from api.db.init import init_db

    init_db(db_path)

    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, profile_yaml, created_at, last_login)
           VALUES ('g1', 'noura@example.com', 'Noura', 'noura', ?, datetime('now'), datetime('now'))""",
        (_PROFILE_YAML,),
    )
    # User without profile_yaml — should be excluded from active profiles
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, created_at, last_login)
           VALUES ('g2', 'nobody@example.com', 'Nobody', 'nobody', datetime('now'), datetime('now'))"""
    )
    con.commit()
    uid = con.execute("SELECT id FROM users WHERE google_id='g1'").fetchone()[0]
    con.close()

    return TestClient(app), uid, "noura"


# backward-compat alias for fixtures that only need client
@pytest.fixture
def client_with_user(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    from api.main import app
    from api.db.init import init_db

    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, profile_yaml, created_at, last_login)
           VALUES ('g1', 'noura@example.com', 'Noura', 'noura', ?, datetime('now'), datetime('now'))""",
        (_PROFILE_YAML,),
    )
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, created_at, last_login)
           VALUES ('g2', 'nobody@example.com', 'Nobody', 'nobody', datetime('now'), datetime('now'))"""
    )
    con.commit()
    con.close()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Profile list
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_requires_ingest_key(self, client):
        r = client.get("/api/agent/profiles")
        assert r.status_code == 422  # missing header

    def test_rejects_wrong_key(self, client):
        r = client.get("/api/agent/profiles", headers={"X-Ingest-Key": "wrong"})
        assert r.status_code == 403

    def test_empty_when_no_users(self, client):
        r = client.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_user_id_and_profile_id(self, client_and_uid):
        c, uid, pid = client_and_uid
        r = c.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        profiles = r.json()
        assert len(profiles) == 1
        assert profiles[0]["user_id"] == uid
        assert profiles[0]["profile_id"] == pid

    def test_excludes_users_without_profile_yaml(self, client_and_uid):
        c, uid, _ = client_and_uid
        r = c.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
        profile_ids = [p["profile_id"] for p in r.json()]
        assert "nobody" not in profile_ids


# ---------------------------------------------------------------------------
# Profile by user_id (new primary endpoint)
# ---------------------------------------------------------------------------


class TestGetProfileByUserId:
    def test_requires_ingest_key(self, client):
        r = client.get("/api/agent/profile/1")
        assert r.status_code == 422

    def test_rejects_wrong_key(self, client):
        r = client.get("/api/agent/profile/1", headers={"X-Ingest-Key": "wrong"})
        assert r.status_code == 403

    def test_404_for_nonexistent_user_id(self, client):
        r = client.get("/api/agent/profile/9999", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 404

    def test_returns_profile_yaml_with_user_id(self, client_and_uid):
        c, uid, pid = client_and_uid
        r = c.get(f"/api/agent/profile/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == uid
        assert data["profile_id"] == pid
        assert "Noura" in data["profile_yaml"]


# ---------------------------------------------------------------------------
# Profile by name (backward compat — removed in Phase 2)
# ---------------------------------------------------------------------------


class TestGetProfileByName:
    def test_returns_profile_yaml(self, client_with_user):
        r = client_with_user.get("/api/agent/profile-by-name/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        data = r.json()
        assert data["profile_id"] == "noura"
        assert "Noura" in data["profile_yaml"]

    def test_404_for_nonexistent_name(self, client):
        r = client.get("/api/agent/profile-by-name/ghost", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Seen IDs (use integer user_id)
# ---------------------------------------------------------------------------


class TestSeenIds:
    def test_get_empty_initially(self, client_and_uid):
        c, uid, _ = client_and_uid
        r = c.get(f"/api/agent/seen-ids/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        assert r.json() == {"user_id": uid, "job_ids": []}

    def test_post_adds_ids(self, client_and_uid):
        c, uid, _ = client_and_uid
        r = c.post(
            f"/api/agent/seen-ids/{uid}",
            json={"job_ids": ["id1", "id2", "id3"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["added"] == 3

    def test_get_returns_posted_ids(self, client_and_uid):
        c, uid, _ = client_and_uid
        c.post(
            f"/api/agent/seen-ids/{uid}",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = c.get(f"/api/agent/seen-ids/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
        assert set(r.json()["job_ids"]) == {"id1", "id2"}

    def test_post_duplicate_ids_no_error(self, client_and_uid):
        c, uid, _ = client_and_uid
        c.post(
            f"/api/agent/seen-ids/{uid}",
            json={"job_ids": ["id1"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = c.post(
            f"/api/agent/seen-ids/{uid}",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["added"] == 1

    def test_delete_clears_ids(self, client_and_uid):
        c, uid, _ = client_and_uid
        c.post(
            f"/api/agent/seen-ids/{uid}",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = c.delete(f"/api/agent/seen-ids/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        assert r.json()["deleted"] == 2

        r = c.get(f"/api/agent/seen-ids/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.json()["job_ids"] == []

    def test_requires_ingest_key_on_all_methods(self, client):
        assert client.get("/api/agent/seen-ids/1").status_code == 422
        assert client.post("/api/agent/seen-ids/1", json={"job_ids": []}).status_code == 422
        assert client.delete("/api/agent/seen-ids/1").status_code == 422
