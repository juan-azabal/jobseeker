"""Tests for GET /api/health/ready — deep readiness check.

Test-first per Phase 14 plan: these must FAIL before implementation.
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from api.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Liveness (existing endpoint — must still pass)
# ---------------------------------------------------------------------------


def test_liveness_always_200(client):
    """GET /api/health always returns 200 regardless of DB/env state."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Readiness — happy path
# ---------------------------------------------------------------------------


def test_readiness_200_with_valid_db_and_env(tmp_path, client):
    """GET /api/health/ready returns 200 when DB is readable and critical vars set."""
    db = tmp_path / "test.db"
    # Create a minimal valid SQLite file
    import sqlite3
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE _ping (id INTEGER)")
    conn.close()

    env = {
        "DB_PATH": str(db),
        "GOOGLE_CLIENT_ID": "fake-client-id",
        "GOOGLE_CLIENT_SECRET": "fake-secret",
        "INGEST_API_KEY": "fake-ingest-key",
    }
    with patch.dict(os.environ, env):
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "checks" in body


def test_readiness_response_has_per_check_results(tmp_path, client):
    """Response includes individual pass/fail for db and critical env vars."""
    db = tmp_path / "test.db"
    import sqlite3
    sqlite3.connect(str(db)).close()

    env = {
        "DB_PATH": str(db),
        "GOOGLE_CLIENT_ID": "x",
        "GOOGLE_CLIENT_SECRET": "x",
        "INGEST_API_KEY": "x",
    }
    with patch.dict(os.environ, env):
        response = client.get("/api/health/ready")

    checks = response.json()["checks"]
    assert "db" in checks
    assert "critical_env" in checks


# ---------------------------------------------------------------------------
# Readiness — failure cases
# ---------------------------------------------------------------------------


def test_readiness_503_when_db_missing(client):
    """Returns 503 when DB_PATH points to a non-existent file."""
    env = {
        "DB_PATH": "/nonexistent/path/to/db.sqlite",
        "GOOGLE_CLIENT_ID": "x",
        "GOOGLE_CLIENT_SECRET": "x",
        "INGEST_API_KEY": "x",
    }
    with patch.dict(os.environ, env):
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["checks"]["db"]["ok"] is False


def test_readiness_503_when_critical_env_missing(tmp_path, client):
    """Returns 503 when a critical env var is absent."""
    db = tmp_path / "test.db"
    import sqlite3
    sqlite3.connect(str(db)).close()

    # Remove INGEST_API_KEY
    env = {
        "DB_PATH": str(db),
        "GOOGLE_CLIENT_ID": "x",
        "GOOGLE_CLIENT_SECRET": "x",
    }
    # Explicitly unset INGEST_API_KEY
    with patch.dict(os.environ, env):
        os.environ.pop("INGEST_API_KEY", None)
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["checks"]["critical_env"]["ok"] is False


# ---------------------------------------------------------------------------
# Readiness — optional warnings (must not cause 503)
# ---------------------------------------------------------------------------


def test_readiness_200_without_optional_vars(tmp_path, client):
    """Missing OPENAI_API_KEY / POSTHOG_API_KEY must NOT cause 503."""
    db = tmp_path / "test.db"
    import sqlite3
    sqlite3.connect(str(db)).close()

    env = {
        "DB_PATH": str(db),
        "GOOGLE_CLIENT_ID": "x",
        "GOOGLE_CLIENT_SECRET": "x",
        "INGEST_API_KEY": "x",
    }
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("POSTHOG_API_KEY", None)
        response = client.get("/api/health/ready")

    assert response.status_code == 200


def test_readiness_warns_about_optional_vars(tmp_path, client):
    """Response includes warnings for missing optional vars."""
    db = tmp_path / "test.db"
    import sqlite3
    sqlite3.connect(str(db)).close()

    env = {
        "DB_PATH": str(db),
        "GOOGLE_CLIENT_ID": "x",
        "GOOGLE_CLIENT_SECRET": "x",
        "INGEST_API_KEY": "x",
    }
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("POSTHOG_API_KEY", None)
        response = client.get("/api/health/ready")

    body = response.json()
    assert "warnings" in body
    warnings = body["warnings"]
    assert isinstance(warnings, list)
    # At least one warning about the missing optional vars
    assert len(warnings) > 0
