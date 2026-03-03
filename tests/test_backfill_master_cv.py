"""Phase 1.4 — Tests: admin backfill-master-cv endpoint."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import (
    upsert_user,
    create_session,
    save_user_cv_md,
    get_master_cv_json,
)
from api.main import app

FAKE_MASTER_CV = {
    "work": [{"id": "w1", "company": "Backfill Corp"}],
    "projects": [],
    "skills": [{"name": "python"}],
}


def _make_admin_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("JOBAGENT_DIR", str(tmp_path / "jobagent"))

    admin = upsert_user(
        db_path,
        {
            "google_id": "g_admin",
            "email": "admin@example.com",
            "name": "Admin",
            "avatar_url": None,
            "profile_id": "admin_user",
        },
    )
    # Promote to admin
    import sqlite3

    with sqlite3.connect(db_path) as con:
        con.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))

    create_session(db_path, "tok_admin", admin["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "tok_admin")
    return c, db_path, admin["id"]


def _add_user_with_cv(db_path, google_id, email, profile_id, cv_text):
    user = upsert_user(
        db_path,
        {
            "google_id": google_id,
            "email": email,
            "name": "User",
            "avatar_url": None,
            "profile_id": profile_id,
        },
    )
    save_user_cv_md(db_path, user["id"], cv_text)
    return user


class TestBackfillMasterCv:
    def test_dry_run_returns_count(self, tmp_path, monkeypatch):
        """dry_run=true returns {users_needing_backfill: N} without writing."""
        client, db_path, admin_id = _make_admin_client(tmp_path, monkeypatch)
        _add_user_with_cv(db_path, "g_u1", "u1@e.com", "u1", "CV text 1")
        _add_user_with_cv(db_path, "g_u2", "u2@e.com", "u2", "CV text 2")

        resp = client.post("/api/admin/backfill-master-cv?dry_run=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "users_needing_backfill" in data
        assert data["users_needing_backfill"] == 2

    def test_dry_run_does_not_write(self, tmp_path, monkeypatch):
        """dry_run=true does not call extract_master_cv_json."""
        client, db_path, admin_id = _make_admin_client(tmp_path, monkeypatch)
        user = _add_user_with_cv(db_path, "g_u3", "u3@e.com", "u3", "CV text 3")

        extract_calls = []

        def capture_extract(text, source, client_arg):
            extract_calls.append(text)
            return FAKE_MASTER_CV

        with (
            patch("api.routes.admin._make_openai_client", return_value=object()),
            patch("api.routes.admin.extract_master_cv_json", side_effect=capture_extract),
        ):
            client.post("/api/admin/backfill-master-cv?dry_run=true")

        assert len(extract_calls) == 0
        assert get_master_cv_json(db_path, user["id"]) is None

    def test_backfill_runs_extraction(self, tmp_path, monkeypatch):
        """Without dry_run → extracts and saves master_cv_json for eligible users."""
        client, db_path, admin_id = _make_admin_client(tmp_path, monkeypatch)
        user = _add_user_with_cv(db_path, "g_u4", "u4@e.com", "u4", "CV text 4")

        with (
            patch("api.routes.admin._make_openai_client", return_value=object()),
            patch("api.routes.admin.extract_master_cv_json", return_value=FAKE_MASTER_CV),
            patch("api.routes.admin.save_master_cv_json"),
        ):
            resp = client.post("/api/admin/backfill-master-cv")

        assert resp.status_code == 200
        data = resp.json()
        assert data["backfilled"] >= 1

    def test_skips_users_already_having_master_cv(self, tmp_path, monkeypatch):
        """Users who already have master_cv_json are not re-processed."""
        from api.db.queries import save_master_cv_json

        client, db_path, admin_id = _make_admin_client(tmp_path, monkeypatch)
        user = _add_user_with_cv(db_path, "g_u5", "u5@e.com", "u5", "CV text 5")
        save_master_cv_json(db_path, user["id"], json.dumps(FAKE_MASTER_CV))

        extract_calls = []

        def capture_extract(text, source, client_arg):
            extract_calls.append(text)
            return FAKE_MASTER_CV

        with (
            patch("api.routes.admin._make_openai_client", return_value=object()),
            patch("api.routes.admin.extract_master_cv_json", side_effect=capture_extract),
        ):
            resp = client.post("/api/admin/backfill-master-cv?dry_run=true")

        assert resp.status_code == 200
        assert resp.json()["users_needing_backfill"] == 0
        assert len(extract_calls) == 0

    def test_requires_admin(self, tmp_path, monkeypatch):
        """Non-admin gets 403."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        monkeypatch.setenv("DB_PATH", db_path)

        user = upsert_user(
            db_path,
            {"google_id": "g_plain", "email": "plain@e.com", "name": "Plain", "avatar_url": None, "profile_id": None},
        )
        create_session(db_path, "tok_plain", user["id"], "2099-01-01T00:00:00")
        c = TestClient(app)
        c.cookies.set("jsk", "tok_plain")

        resp = c.post("/api/admin/backfill-master-cv")
        assert resp.status_code == 403
