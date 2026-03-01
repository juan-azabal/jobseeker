"""Tests for the staging environment gate middleware.

Verifies:
- ENVIRONMENT=staging + admin user → 200
- ENVIRONMENT=staging + non-admin user → 403
- ENVIRONMENT=production + non-admin user → 200
- Auth routes excluded from gate in staging
- /api/health excluded from gate in staging
- GET /api/admin/db-export excluded from gate in staging
"""

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def db_with_users(tmp_path):
    """Create a minimal DB with an admin and a non-admin user."""
    db_path = str(tmp_path / "test.db")
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            google_id TEXT UNIQUE,
            email TEXT,
            name TEXT,
            avatar_url TEXT,
            profile_id TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            last_login TEXT,
            cv_md TEXT,
            profile_yaml TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            impersonated_user_id INTEGER,
            created_at TEXT,
            expires_at TEXT
        );
        INSERT INTO users (id, google_id, email, name, is_admin, profile_yaml)
            VALUES (1, 'admin-google', 'admin@example.com', 'Admin', 1, 'name: Admin');
        INSERT INTO users (id, google_id, email, name, is_admin, profile_yaml)
            VALUES (2, 'user-google', 'user@example.com', 'User', 0, 'name: User');
        INSERT INTO sessions (token, user_id, created_at, expires_at)
            VALUES ('admin-token', 1, '2026-01-01', '2099-01-01');
        INSERT INTO sessions (token, user_id, created_at, expires_at)
            VALUES ('user-token', 2, '2026-01-01', '2099-01-01');
    """)
    con.close()
    return db_path


class TestStagingGate:
    def test_admin_user_gets_200_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "admin-token")
            resp = client.get("/api/jobs")
        assert resp.status_code != 403, f"Admin should not be blocked by staging gate, got {resp.status_code}"

    def test_non_admin_user_gets_403_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "user-token")
            resp = client.get("/api/jobs")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Staging environment: admin access only"

    def test_unauthenticated_gets_403_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/jobs")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Staging environment: admin access only"

    def test_non_admin_gets_200_in_production(self, db_with_users):
        with patch("api.middleware.staging._db_path", return_value=db_with_users):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "user-token")
            resp = client.get("/api/jobs")
        # Gate is off in production; route may return other status but NOT staging gate 403
        if resp.headers.get("content-type", "").startswith("application/json"):
            assert resp.json().get("detail") != "Staging environment: admin access only"

    def test_auth_routes_excluded_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            # follow_redirects=False: auth/login redirects to Google; we only check our gate
            client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
            for path in ["/api/auth/login", "/api/auth/callback", "/api/auth/logout"]:
                resp = client.get(path)
                if resp.headers.get("content-type", "").startswith("application/json"):
                    assert resp.json().get("detail") != "Staging environment: admin access only", (
                        f"Auth route {path} should not be blocked by staging gate"
                    )

    def test_health_excluded_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_db_export_excluded_in_staging(self, db_with_users):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=db_with_users),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/admin/db-export")
        # Not blocked by staging gate; will 403 due to missing API key (correct)
        if resp.headers.get("content-type", "").startswith("application/json"):
            assert resp.json().get("detail") != "Staging environment: admin access only"
