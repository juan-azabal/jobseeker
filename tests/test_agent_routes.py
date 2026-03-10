"""Tests for api/routes/agent.py — profile and seen_ids endpoints.

Covers step 2.1 and 3.2 of the pipeline-scalability plan.
"""

import os
import pytest
from fastapi.testclient import TestClient


INGEST_KEY = "test-ingest-key"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    from api.main import app
    from api.db.init import init_db

    init_db(str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def client_with_user(tmp_path, monkeypatch):
    """Client with a seeded user that has profile_id and profile_yaml."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    from api.main import app
    from api.db.init import init_db
    import sqlite3

    init_db(db_path)

    # Seed a user with profile_id and profile_yaml
    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, profile_yaml, created_at, last_login)
           VALUES ('g1', 'noura@example.com', 'Noura', 'noura', 'user:\n  name: Noura\n', datetime('now'), datetime('now'))"""
    )
    # Seed a user without profile_yaml (should not appear in list)
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, created_at, last_login)
           VALUES ('g2', 'nobody@example.com', 'Nobody', 'nobody', datetime('now'), datetime('now'))"""
    )
    con.commit()
    con.close()

    return TestClient(app)


# ---------------------------------------------------------------------------
# Profile endpoints
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

    def test_returns_users_with_profile_yaml(self, client_with_user):
        r = client_with_user.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        profiles = r.json()
        assert len(profiles) == 1
        assert profiles[0]["profile_id"] == "noura"

    def test_excludes_users_without_profile_yaml(self, client_with_user):
        r = client_with_user.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
        ids = [p["profile_id"] for p in r.json()]
        assert "nobody" not in ids


class TestGetProfile:
    def test_requires_ingest_key(self, client):
        r = client.get("/api/agent/profile/noura")
        assert r.status_code == 422

    def test_rejects_wrong_key(self, client):
        r = client.get("/api/agent/profile/noura", headers={"X-Ingest-Key": "wrong"})
        assert r.status_code == 403

    def test_404_for_nonexistent_profile(self, client):
        r = client.get("/api/agent/profile/nonexistent", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 404

    def test_returns_profile_yaml(self, client_with_user):
        r = client_with_user.get("/api/agent/profile/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        data = r.json()
        assert data["profile_id"] == "noura"
        assert "Noura" in data["profile_yaml"]


# ---------------------------------------------------------------------------
# Seen IDs endpoints
# ---------------------------------------------------------------------------


class TestSeenIds:
    def test_get_empty_initially(self, client):
        r = client.get("/api/agent/seen-ids/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        assert r.json() == {"profile_id": "noura", "job_ids": []}

    def test_post_adds_ids(self, client):
        r = client.post(
            "/api/agent/seen-ids/noura",
            json={"job_ids": ["id1", "id2", "id3"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["added"] == 3

    def test_get_returns_posted_ids(self, client):
        client.post(
            "/api/agent/seen-ids/noura",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = client.get("/api/agent/seen-ids/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert set(r.json()["job_ids"]) == {"id1", "id2"}

    def test_post_duplicate_ids_no_error(self, client):
        client.post(
            "/api/agent/seen-ids/noura",
            json={"job_ids": ["id1"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = client.post(
            "/api/agent/seen-ids/noura",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        # id1 is a duplicate, only id2 is new
        assert r.json()["added"] == 1

    def test_delete_clears_ids(self, client):
        client.post(
            "/api/agent/seen-ids/noura",
            json={"job_ids": ["id1", "id2"]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        r = client.delete("/api/agent/seen-ids/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.status_code == 200
        assert r.json()["deleted"] == 2

        r = client.get("/api/agent/seen-ids/noura", headers={"X-Ingest-Key": INGEST_KEY})
        assert r.json()["job_ids"] == []

    def test_requires_ingest_key_on_all_methods(self, client):
        assert client.get("/api/agent/seen-ids/x").status_code == 422
        assert client.post("/api/agent/seen-ids/x", json={"job_ids": []}).status_code == 422
        assert client.delete("/api/agent/seen-ids/x").status_code == 422
