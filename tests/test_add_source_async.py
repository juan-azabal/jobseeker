"""Phase 2.3 — Tests: POST /add-source returns 202 and runs async."""

import json
import os
from unittest.mock import patch, MagicMock

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
  name: Async Source User
  email: async_src@example.com
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

SAMPLE_MASTER_CV = {
    "work": [{"id": "w1", "company": "Src Corp", "position": "Engineer"}],
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

    user = upsert_user(
        db_path,
        {
            "google_id": "g_src_async",
            "email": "async_src@example.com",
            "name": "Async Source User",
            "avatar_url": None,
            "profile_id": "async_src_user",
        },
    )
    save_user_profile_yaml(db_path, user["id"], MINIMAL_YAML)
    create_session(db_path, "tok_src_async", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "tok_src_async")
    return c, db_path, user["id"]


def _patch_extract():
    return patch(
        "api.routes.onboard.extract_master_cv_json",
        return_value=SAMPLE_MASTER_CV,
    )


def _patch_index():
    return patch("api.routes.onboard.index_master_cv", return_value=None)


class TestAddSourceAsync:
    def test_returns_202_immediately(self, tmp_path, monkeypatch):
        """POST /add-source returns 202 without waiting for LLM."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            _patch_extract(),
            _patch_index(),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "LinkedIn experience: Senior PM at Src Corp"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "processing"

    def test_status_set_to_processing(self, tmp_path, monkeypatch):
        """After 202, cv_processing_status is 'processing' or 'done' in DB."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        start_event = __import__("threading").Event()

        def slow_process(*args, **kwargs):
            start_event.wait(timeout=1)

        with (
            _patch_index(),
            patch("api.routes.onboard._run_add_source_background", side_effect=slow_process),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "My career"},
            )

        assert resp.status_code == 202
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] in ("processing", "done")

    def test_background_task_sets_done(self, tmp_path, monkeypatch):
        """Background task completes and sets status='done' with master_cv."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            _patch_extract(),
            _patch_index(),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "Senior PM at Src Corp 2020-2024"},
            )

        # TestClient runs BackgroundTasks synchronously after response
        assert resp.status_code == 202
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "done"
        assert status["result"] is not None

    def test_background_task_handles_exception(self, tmp_path, monkeypatch):
        """If background task raises, status='failed' with error message."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with patch(
            "api.routes.onboard._run_add_source_background",
            side_effect=RuntimeError("src boom"),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "My career"},
            )

        assert resp.status_code == 202
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "failed"
        assert "src boom" in status["result"]["error"]

    def test_file_upload_returns_202(self, tmp_path, monkeypatch):
        """Multipart file upload also returns 202."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        docx_bytes = b"PK\x03\x04" + b"\x00" * 100  # minimal fake docx header

        with (
            patch("api.routes.onboard.extract_text_from_file", return_value="CV text"),
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            _patch_extract(),
            _patch_index(),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                files={"file": ("cv.docx", docx_bytes, "application/octet-stream")},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "processing"
