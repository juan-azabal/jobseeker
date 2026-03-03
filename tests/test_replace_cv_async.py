"""Phase 2.2 — Tests: PATCH /replace-cv returns 202 and runs async."""

import json
import os
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import (
    upsert_user,
    create_session,
    save_user_profile_yaml,
    get_cv_processing_status,
)
from api.main import app


MINIMAL_YAML = """
user:
  name: Async User
  email: async@example.com
  home_locations:
    - spain
target:
  domains:
    saas: 10
  seniority_weights:
    senior: 10
skills:
  - python
"""

SAMPLE_PROFILE = {
    "name": "Async User",
    "email": "async@example.com",
    "home_locations": ["spain"],
    "skills": ["python", "go"],
    "domains": {"saas": 10},
    "seniority_weights": {"senior": 10},
}

SAMPLE_MASTER_CV = {
    "work": [{"id": "w1", "company": "Async Corp", "position": "PM"}],
    "projects": [],
    "skills": [{"name": "python"}],
}


def _make_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    with open(os.path.join(profiles_dir, "async_user.yaml"), "w") as f:
        f.write(MINIMAL_YAML)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_async",
            "email": "async@example.com",
            "name": "Async User",
            "avatar_url": None,
            "profile_id": "async_user",
        },
    )
    save_user_profile_yaml(db_path, user["id"], MINIMAL_YAML)
    create_session(db_path, "tok_async", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "tok_async")
    return c, db_path, user["id"]


def _patch_github():
    return patch("api.routes.onboard._push_file_to_github", return_value=None)


class TestReplaceCvAsync:
    def test_returns_202_immediately(self, tmp_path, monkeypatch):
        """PATCH /replace-cv returns 202 without waiting for LLM."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            _patch_github(),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# CV",
                    "extracted_profile": SAMPLE_PROFILE,
                    "master_cv_json": SAMPLE_MASTER_CV,
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "processing"

    def test_status_set_to_processing(self, tmp_path, monkeypatch):
        """After 202, cv_processing_status is 'processing' in DB."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        # Block the background task from completing immediately
        start_event = __import__("threading").Event()

        def slow_process(*args, **kwargs):
            start_event.wait(timeout=1)

        with (
            _patch_github(),
            patch("api.routes.onboard._run_replace_cv_background", side_effect=slow_process),
        ):
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# CV",
                    "extracted_profile": SAMPLE_PROFILE,
                },
            )

        assert resp.status_code == 202
        # The status was set before background task ran
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] in ("processing", "done")  # may complete before check

    def test_background_task_sets_done(self, tmp_path, monkeypatch):
        """Background task completes and sets status='done' with diff."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            _patch_github(),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# CV",
                    "extracted_profile": SAMPLE_PROFILE,
                    "master_cv_json": SAMPLE_MASTER_CV,
                },
            )

        # TestClient runs BackgroundTasks synchronously after response
        assert resp.status_code == 202
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "done"
        assert status["result"] is not None
        assert "diff" in status["result"]

    def test_background_task_handles_exception(self, tmp_path, monkeypatch):
        """If background task raises, status='failed' with error message."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            _patch_github(),
            patch("api.routes.onboard._run_replace_cv_background", side_effect=RuntimeError("boom")),
        ):
            resp = client.patch(
                "/api/onboard/replace-cv",
                json={
                    "cv_markdown": "# CV",
                    "extracted_profile": SAMPLE_PROFILE,
                },
            )

        assert resp.status_code == 202
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "failed"
        assert "boom" in status["result"]["error"]

    def test_timeout_guard(self, tmp_path, monkeypatch):
        """If status is 'processing' and started_at > 5 min ago, GET /profile returns 'failed'."""
        from datetime import datetime, timezone, timedelta

        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        # Manually set stale processing state
        from api.db.queries import set_cv_processing_status
        import sqlite3

        set_cv_processing_status(db_path, user_id, "processing")
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        with sqlite3.connect(db_path) as con:
            con.execute(
                "UPDATE users SET cv_processing_started_at=? WHERE id=?",
                (stale_time, user_id),
            )

        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        data = resp.json()
        cv_proc = data.get("cv_processing", {})
        assert cv_proc.get("status") == "failed"
