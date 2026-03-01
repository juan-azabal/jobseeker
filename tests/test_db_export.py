"""Tests for GET /api/admin/db-export endpoint.

Verifies:
- Valid API key → 200 + response starts with SQLite magic bytes
- Invalid API key → 403
- Missing API key header → 403
- Empty DB_EXPORT_API_KEY in config → 403 (fail closed)
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

SQLITE_MAGIC = b"SQLite format 3\x00"


@pytest.fixture()
def test_db(tmp_path):
    """Create a minimal SQLite DB for export testing."""
    db_path = str(tmp_path / "export_test.db")
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    return db_path


class TestDbExport:
    def test_valid_api_key_returns_sqlite(self, test_db):
        with (
            patch("api.config.DB_EXPORT_API_KEY", "secret-key"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret-key"),
            patch("api.routes.admin._db_path", return_value=test_db),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/admin/db-export", headers={"X-API-Key": "secret-key"})
        assert resp.status_code == 200
        assert resp.content[:16] == SQLITE_MAGIC

    def test_invalid_api_key_returns_403(self, test_db):
        with (
            patch("api.config.DB_EXPORT_API_KEY", "secret-key"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret-key"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/admin/db-export", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_missing_api_key_header_returns_403(self, test_db):
        with (
            patch("api.config.DB_EXPORT_API_KEY", "secret-key"),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", "secret-key"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/admin/db-export")
        assert resp.status_code == 403

    def test_empty_export_api_key_returns_403_fail_closed(self, test_db):
        with (
            patch("api.config.DB_EXPORT_API_KEY", ""),
            patch("api.routes.admin.config.DB_EXPORT_API_KEY", ""),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/admin/db-export", headers={"X-API-Key": ""})
        assert resp.status_code == 403
