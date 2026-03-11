"""Tests for Phase 2.2: admin endpoints accept user_id internally.

Verifies:
- POST /api/admin/reset-seen-ids accepts {user_id: N} (not profile_id)
- POST /api/admin/trigger-pipeline resolves profile_id string to integer user_id
- POST /api/admin/trigger-pipeline passes integer string when given integer string
"""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.main import app


@pytest.fixture()
def admin_client(tmp_path, monkeypatch):
    """TestClient authenticated as an admin user with seeded test data."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("GH_ACTIONS_TOKEN", "test-gh-token")
    monkeypatch.setenv("GH_REPO", "test/repo")
    monkeypatch.setenv("GH_REF", "main")

    init_db(db_path)

    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO users (google_id, email, name, profile_id, is_admin) VALUES (?, ?, ?, ?, 1)",
        ("g-admin", "admin@test.com", "Admin", "admin"),
    )
    con.commit()
    admin_uid = con.execute("SELECT id FROM users WHERE google_id='g-admin'").fetchone()[0]

    # Seed a regular user whose seen_ids we'll reset
    con.execute(
        "INSERT INTO users (google_id, email, name, profile_id) VALUES (?, ?, ?, ?)",
        ("g-juan", "juan@test.com", "Juan", "juanAza"),
    )
    con.commit()
    juan_uid = con.execute("SELECT id FROM users WHERE google_id='g-juan'").fetchone()[0]

    # Seed some seen_ids for juan
    con.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (juan_uid, "job-001"))
    con.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (juan_uid, "job-002"))
    con.commit()
    con.close()

    create_session(db_path, "admin-tok", admin_uid, "2099-01-01T00:00:00")

    client = TestClient(app)
    client.cookies.set("jsk", "admin-tok")
    return client, db_path, juan_uid


class TestResetSeenIdsAcceptsUserId:
    """POST /api/admin/reset-seen-ids must accept user_id (int), not profile_id."""

    def test_accepts_user_id_and_clears_db(self, admin_client):
        """Passing {user_id: N} clears seen_job_ids for that user."""
        client, db_path, juan_uid = admin_client

        # Mock GitHub API calls (GET file SHA + PUT empty)
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"sha": "abc123"}

        mock_put = MagicMock()
        mock_put.status_code = 200

        mock_aenter = AsyncMock()
        mock_aenter.get = AsyncMock(return_value=mock_get)
        mock_aenter.put = AsyncMock(return_value=mock_put)

        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_aenter)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.admin.httpx.AsyncClient", return_value=mock_client_cm):
            resp = client.post("/api/admin/reset-seen-ids", json={"user_id": juan_uid})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reset"
        assert data["db_deleted"] == 2

        # Verify DB is actually empty for juan
        con = sqlite3.connect(db_path)
        remaining = con.execute("SELECT COUNT(*) FROM seen_job_ids WHERE user_id = ?", (juan_uid,)).fetchone()[0]
        con.close()
        assert remaining == 0

    def test_rejects_profile_id_string(self, admin_client):
        """Passing {profile_id: '...'} is rejected with 422 (wrong schema)."""
        client, db_path, _uid = admin_client

        # No mock needed — validation fails before any GitHub call
        resp = client.post("/api/admin/reset-seen-ids", json={"profile_id": "juanAza"})

        assert resp.status_code == 422

    def test_uses_profile_id_for_github_path(self, admin_client):
        """GitHub file path is built from profile_id looked up by user_id."""
        client, _db_path, juan_uid = admin_client

        captured_url = {}

        mock_get = MagicMock()
        mock_get.status_code = 404  # File not found — simpler path

        mock_aenter = AsyncMock()

        async def _get(url, **kwargs):
            captured_url["get"] = url
            return mock_get

        mock_aenter.get = _get
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_aenter)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.admin.httpx.AsyncClient", return_value=mock_client_cm):
            resp = client.post("/api/admin/reset-seen-ids", json={"user_id": juan_uid})

        assert resp.status_code == 200
        # The GitHub GET URL should contain "juanAza" (the profile_id for this user)
        assert "juanAza" in captured_url.get("get", "")


class TestTriggerPipelineNormalizesProfileId:
    """POST /api/admin/trigger-pipeline resolves profile_id string to integer user_id."""

    def _mock_gh_dispatch(self, status_code=204):
        """Return a mock that captures the dispatched inputs."""
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = status_code

        mock_aenter = AsyncMock()

        async def _post(url, json=None, **kwargs):
            captured["inputs"] = (json or {}).get("inputs", {})
            return mock_resp

        mock_aenter.post = _post
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_aenter)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        return mock_client_cm, captured

    def test_integer_string_passed_through(self, admin_client):
        """Passing profile='7' sends '7' to GHA inputs (already an integer)."""
        client, db_path, juan_uid = admin_client
        mock_cm, captured = self._mock_gh_dispatch()

        with patch("api.routes.admin.httpx.AsyncClient", return_value=mock_cm):
            resp = client.post("/api/admin/trigger-pipeline", json={"profile": str(juan_uid)})

        assert resp.status_code == 200
        assert captured["inputs"]["profile"] == str(juan_uid)

    def test_profile_id_string_resolves_to_user_id(self, admin_client):
        """Passing profile='juanAza' resolves to integer user_id and sends that to GHA."""
        client, db_path, juan_uid = admin_client
        mock_cm, captured = self._mock_gh_dispatch()

        with patch("api.routes.admin.httpx.AsyncClient", return_value=mock_cm):
            resp = client.post("/api/admin/trigger-pipeline", json={"profile": "juanAza"})

        assert resp.status_code == 200
        # GHA should receive the integer user_id, not the string "juanAza"
        assert captured["inputs"]["profile"] == str(juan_uid)

    def test_no_profile_runs_all(self, admin_client):
        """Empty body dispatches with no profile input (all active profiles)."""
        client, _db, _uid = admin_client
        mock_cm, captured = self._mock_gh_dispatch()

        with patch("api.routes.admin.httpx.AsyncClient", return_value=mock_cm):
            resp = client.post("/api/admin/trigger-pipeline", json={})

        assert resp.status_code == 200
        assert "profile" not in captured["inputs"]
