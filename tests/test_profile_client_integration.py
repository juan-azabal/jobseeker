"""Integration test: profile_client response format matches the API contract.

Verifies that the JSON shapes returned by /api/agent/* endpoints
are exactly what profile_client.py expects to parse.  Uses the same
TestClient fixtures as test_agent_routes.py so the DB is isolated.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

INGEST_KEY = "test-ingest-key"
PROFILE_YAML = "user:\n  name: Noura\n  active: true\nskills:\n  - Python\n"


@pytest.fixture
def client_and_uid(tmp_path, monkeypatch):
    """Seeded TestClient — same pattern as test_agent_routes.py.

    Returns (TestClient, user_id) tuple.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    from api.main import app
    from api.db.init import init_db

    init_db(db_path)

    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO users
               (google_id, email, name, profile_id, profile_yaml, created_at, last_login)
           VALUES ('g1', 'noura@example.com', 'Noura', 'noura', ?, datetime('now'), datetime('now'))""",
        (PROFILE_YAML,),
    )
    con.commit()
    uid = con.execute("SELECT id FROM users WHERE profile_id = 'noura'").fetchone()[0]
    con.close()

    return TestClient(app), uid


# ---------------------------------------------------------------------------
# Verify API response shapes match what profile_client expects to parse
# ---------------------------------------------------------------------------


def test_list_profiles_shape(client_and_uid):
    """GET /api/agent/profiles returns list of {user_id, profile_id} dicts."""
    client, uid = client_and_uid
    r = client.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    # profile_client.fetch_profiles reads data[i]["user_id"] and data[i]["profile_id"]
    assert data[0]["user_id"] == uid
    assert data[0]["profile_id"] == "noura"


def test_get_profile_shape(client_and_uid):
    """GET /api/agent/profile/{user_id} returns {user_id, profile_id, profile_yaml}."""
    client, uid = client_and_uid
    r = client.get(f"/api/agent/profile/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
    assert r.status_code == 200
    data = r.json()
    # profile_client.fetch_profile reads data["user_id"], data["profile_id"], data["profile_yaml"]
    assert data["user_id"] == uid
    assert data["profile_id"] == "noura"
    assert "profile_yaml" in data
    import yaml

    parsed = yaml.safe_load(data["profile_yaml"])
    assert parsed["user"]["name"] == "Noura"
    assert "Python" in parsed["skills"]


def test_seen_ids_post_shape(client_and_uid):
    """POST /api/agent/seen-ids/{user_id} returns {added: N}."""
    client, uid = client_and_uid
    r = client.post(
        f"/api/agent/seen-ids/{uid}",
        json={"job_ids": ["a", "b", "c"]},
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert r.status_code == 200
    data = r.json()
    # profile_client.post_seen_ids reads data["added"]
    assert data["added"] == 3


def test_seen_ids_get_shape(client_and_uid):
    """GET /api/agent/seen-ids/{user_id} returns {user_id, job_ids: [...]}."""
    client, uid = client_and_uid
    # Seed some IDs first
    client.post(
        f"/api/agent/seen-ids/{uid}",
        json={"job_ids": ["x", "y"]},
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    r = client.get(f"/api/agent/seen-ids/{uid}", headers={"X-Ingest-Key": INGEST_KEY})
    assert r.status_code == 200
    data = r.json()
    # profile_client.fetch_seen_ids reads data["job_ids"]
    assert "job_ids" in data
    assert set(data["job_ids"]) == {"x", "y"}


def test_duplicate_seen_ids_returns_zero_added(client_and_uid):
    """Second POST with same IDs returns added=0 (INSERT OR IGNORE)."""
    client, uid = client_and_uid
    headers = {"X-Ingest-Key": INGEST_KEY}
    client.post(f"/api/agent/seen-ids/{uid}", json={"job_ids": ["dup"]}, headers=headers)
    r = client.post(f"/api/agent/seen-ids/{uid}", json={"job_ids": ["dup"]}, headers=headers)
    assert r.json()["added"] == 0
