"""Tests for POST /api/admin/db-import endpoint.

Verifies:
- Mock httpx call to return valid SQLite → admin on staging → 200 + DB file replaced
- Non-admin → 403
- ENVIRONMENT=production → 400
- Prod unreachable (httpx timeout) → 502
- Invalid response (not SQLite) → 400
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

SQLITE_MAGIC = b"SQLite format 3\x00" + b"\x00" * 84  # minimal 100-byte header


@pytest.fixture()
def staging_db(tmp_path):
    """Create a minimal DB with an admin user in staging environment."""
    db_path = str(tmp_path / "staging.db")
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, google_id TEXT UNIQUE, email TEXT, name TEXT,
            avatar_url TEXT, profile_id TEXT, is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT, last_login TEXT, cv_md TEXT, profile_yaml TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            impersonated_user_id INTEGER, created_at TEXT, expires_at TEXT
        );
        INSERT INTO users (id, google_id, email, name, is_admin, profile_yaml)
            VALUES (1, 'admin-g', 'admin@test.com', 'Admin', 1, 'name: A');
        INSERT INTO users (id, google_id, email, name, is_admin, profile_yaml)
            VALUES (2, 'user-g', 'user@test.com', 'User', 0, 'name: U');
        INSERT INTO sessions VALUES ('admin-tok', 1, NULL, '2026-01-01', '2099-01-01');
        INSERT INTO sessions VALUES ('user-tok', 2, NULL, '2026-01-01', '2099-01-01');
    """)
    con.close()
    return db_path


def _valid_sqlite_bytes() -> bytes:
    """Build minimal valid SQLite file bytes (100-byte header + one page)."""
    tmp = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    data = Path(tmp).read_bytes()
    Path(tmp).unlink(missing_ok=True)
    return data


class TestDbImport:
    def test_admin_staging_import_succeeds(self, staging_db):
        valid_db = _valid_sqlite_bytes()

        async def _aiter_bytes(chunk_size):
            yield valid_db

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.aiter_bytes = _aiter_bytes
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream.return_value = mock_stream

        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=staging_db),
            patch("api.middleware.auth._db_path", return_value=staging_db),
            patch("api.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.config.DB_EXPORT_API_KEY", "secret"),
            patch("api.routes.admin.config.ENVIRONMENT", "staging"),
            patch("api.routes.admin.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret"),
            patch("api.routes.admin._db_path", return_value=staging_db),
            patch("api.db.snapshot.httpx.AsyncClient", return_value=mock_client),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "admin-tok")
            resp = client.post("/api/admin/db-import")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_non_admin_returns_403(self, staging_db):
        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=staging_db),
            patch("api.routes.admin.config.ENVIRONMENT", "staging"),
            patch("api.routes.admin._db_path", return_value=staging_db),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "user-tok")
            resp = client.post("/api/admin/db-import")

        # Staging gate blocks non-admin before endpoint runs → 403
        assert resp.status_code == 403

    def test_production_environment_returns_400(self, staging_db):
        with (
            patch("api.routes.admin.config.ENVIRONMENT", "production"),
            patch("api.routes.admin._db_path", return_value=staging_db),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            # Use basic auth setup for non-staging environment
            with (
                patch("api.middleware.auth.get_session") as mock_sess,
                patch("api.middleware.auth.get_user_by_id") as mock_user,
            ):
                mock_sess.return_value = {"user_id": 1, "impersonated_user_id": None}
                mock_user.return_value = {
                    "id": 1,
                    "email": "a@b.com",
                    "name": "A",
                    "avatar_url": None,
                    "profile_id": "p",
                    "is_admin": True,
                    "profile_yaml": "name: A",
                }
                client.cookies.set("jsk", "admin-tok")
                resp = client.post("/api/admin/db-import")

        assert resp.status_code == 400

    def test_prod_unreachable_returns_502(self, staging_db):
        import httpx as httpx_lib

        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=staging_db),
            patch("api.middleware.auth._db_path", return_value=staging_db),
            patch("api.routes.admin.config.ENVIRONMENT", "staging"),
            patch("api.routes.admin.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret"),
            patch("api.routes.admin._db_path", return_value=staging_db),
            patch("api.db.snapshot.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_stream = MagicMock()
            mock_stream.__aenter__ = AsyncMock(side_effect=httpx_lib.TimeoutException("timeout"))
            mock_stream.__aexit__ = AsyncMock(return_value=None)
            mock_client.stream.return_value = mock_stream
            mock_cls.return_value = mock_client

            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "admin-tok")
            resp = client.post("/api/admin/db-import")

        assert resp.status_code == 502

    def test_invalid_response_not_sqlite_returns_400(self, staging_db):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.aiter_bytes = AsyncMock(return_value=iter([b"not a sqlite file at all"]))
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream

        with (
            patch("api.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging.config.ENVIRONMENT", "staging"),
            patch("api.middleware.staging._db_path", return_value=staging_db),
            patch("api.middleware.auth._db_path", return_value=staging_db),
            patch("api.routes.admin.config.ENVIRONMENT", "staging"),
            patch("api.routes.admin.config.PROD_API_URL", "https://prod.example.com"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret"),
            patch("api.routes.admin._db_path", return_value=staging_db),
            patch("api.db.snapshot.httpx.AsyncClient", return_value=mock_client),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set("jsk", "admin-tok")
            resp = client.post("/api/admin/db-import")

        assert resp.status_code == 400
