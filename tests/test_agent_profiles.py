"""Tests for get_active_profile_ids() query and GET /api/agent/profiles endpoint."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import get_active_profile_ids
from api.main import app

INGEST_KEY = "test-key"

ACTIVE_YAML = (
    "user:\n  name: Test\n  email: test@example.com\n  active: true\n"
    "target:\n  level: senior\n  track: ic\nskills:\n- python\n"
)
INACTIVE_YAML = (
    "user:\n  name: Inactive\n  email: inactive@example.com\n  active: false\n"
    "target:\n  level: senior\n  track: ic\nskills:\n- python\n"
)
NO_ACTIVE_YAML = (
    "user:\n  name: NoFlag\n  email: noflag@example.com\ntarget:\n  level: senior\n  track: ic\nskills:\n- python\n"
)


# ── Query-level tests (get_active_profile_ids) ────────────────────────────


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _insert_user(db_path, google_id, email, profile_id=None, profile_yaml=None):
    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO users (google_id, email, name, profile_id, profile_yaml, created_at, last_login)
           VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (google_id, email, email.split("@")[0], profile_id, profile_yaml),
    )
    con.commit()
    con.close()


def test_returns_onboarded_users(db_path):
    _insert_user(db_path, "g1", "a@example.com", "profile_a", ACTIVE_YAML)
    _insert_user(db_path, "g2", "b@example.com", "profile_b", NO_ACTIVE_YAML)

    result = get_active_profile_ids(db_path)

    assert "profile_a" in result
    assert "profile_b" in result
    assert len(result) == 2


def test_excludes_users_without_profile_id(db_path):
    _insert_user(db_path, "g1", "a@example.com", profile_id=None, profile_yaml=ACTIVE_YAML)

    result = get_active_profile_ids(db_path)

    assert result == []


def test_excludes_users_without_yaml(db_path):
    _insert_user(db_path, "g1", "a@example.com", profile_id="profile_a", profile_yaml=None)

    result = get_active_profile_ids(db_path)

    assert result == []


def test_excludes_inactive_profiles(db_path):
    _insert_user(db_path, "g1", "a@example.com", "profile_a", INACTIVE_YAML)

    result = get_active_profile_ids(db_path)

    assert result == []


def test_includes_profiles_without_active_field(db_path):
    _insert_user(db_path, "g1", "a@example.com", "profile_a", NO_ACTIVE_YAML)

    result = get_active_profile_ids(db_path)

    assert "profile_a" in result


# ── Endpoint tests (GET /api/agent/profiles) ──────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    init_db(db)
    return TestClient(app), db


def test_endpoint_returns_json_list(client):
    tc, db = client
    _insert_user(db, "g1", "a@example.com", "profile_a", ACTIVE_YAML)

    r = tc.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "profile_id" in data[0]
    assert data[0]["profile_id"] == "profile_a"


def test_endpoint_rejects_bad_key(client):
    tc, _ = client

    r = tc.get("/api/agent/profiles", headers={"X-Ingest-Key": "wrong"})

    assert r.status_code == 403


def test_endpoint_empty_when_no_users(client):
    tc, _ = client

    r = tc.get("/api/agent/profiles", headers={"X-Ingest-Key": INGEST_KEY})

    assert r.status_code == 200
    assert r.json() == []
