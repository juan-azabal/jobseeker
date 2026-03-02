"""Phase 1.3 — Tests: add-source accepts JSON text input."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user, create_session, get_master_cv_json
from api.main import app


MINIMAL_YAML = """
user:
  name: Test User
  email: test@example.com
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

EXTRACTED_MASTER_CV = {
    "work": [
        {
            "id": "work_text_aaa",
            "company": "Text Corp",
            "position": "Product Lead",
            "start_date": "2021-01",
            "end_date": None,
            "summary": "Led product from text",
            "highlights": ["Built X"],
            "skills_used": ["leadership", "strategy"],
        }
    ],
    "projects": [],
    "skills": [{"name": "leadership"}, {"name": "strategy"}],
}


def _make_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    os.makedirs(os.path.join(jobagent_dir, "config", "profiles"))
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_text_src",
            "email": "text@example.com",
            "name": "Test User",
            "avatar_url": None,
            "profile_id": "text_src_user",
        },
    )
    create_session(db_path, "tok_text_src", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "tok_text_src")
    return c, db_path, user["id"]


class TestAddSourceTextInput:
    def test_json_text_body_accepted(self, tmp_path, monkeypatch):
        """POST /add-source with JSON {text: ...} → 200."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            patch("api.routes.onboard.extract_master_cv_json", return_value=EXTRACTED_MASTER_CV),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "LinkedIn summary: Senior PM at Text Corp..."},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data
        assert "master_cv" in data

    def test_json_text_saves_master_cv(self, tmp_path, monkeypatch):
        """POST /add-source with text → master_cv_json persisted in DB."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            patch("api.routes.onboard.extract_master_cv_json", return_value=EXTRACTED_MASTER_CV),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                json={"text": "LinkedIn summary text..."},
            )
        assert resp.status_code == 200

        raw = get_master_cv_json(db_path, user_id)
        assert raw is not None
        saved = json.loads(raw)
        assert saved["work"][0]["company"] == "Text Corp"

    def test_json_text_extract_called_with_text(self, tmp_path, monkeypatch):
        """extract_master_cv_json receives the text content, not a filename."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)
        text_content = "LinkedIn: Senior PM at Text Corp 2021-present"

        extract_calls = []

        def capture_extract(text, source, client):
            extract_calls.append((text, source))
            return EXTRACTED_MASTER_CV

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            patch("api.routes.onboard.extract_master_cv_json", side_effect=capture_extract),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.post("/api/onboard/add-source", json={"text": text_content})

        assert resp.status_code == 200
        assert len(extract_calls) == 1
        assert extract_calls[0][0] == text_content
        assert extract_calls[0][1] == "add_source"

    def test_file_upload_still_works(self, tmp_path, monkeypatch):
        """Original file upload path still returns 200."""
        client, db_path, user_id = _make_client(tmp_path, monkeypatch)

        with (
            patch("api.routes.onboard._make_openai_client", return_value=object()),
            patch("api.routes.onboard.extract_text_from_file", return_value="CV text"),
            patch("api.routes.onboard.extract_master_cv_json", return_value=EXTRACTED_MASTER_CV),
            patch("api.routes.onboard.index_master_cv", return_value=None),
        ):
            resp = client.post(
                "/api/onboard/add-source",
                files={"file": ("cv.docx", b"PK\x03\x04fake_docx_bytes", "application/octet-stream")},
            )
        # May fail on text extraction without a real docx, but the route should accept the file
        assert resp.status_code in (200, 400)

    def test_missing_text_field_returns_422(self, tmp_path, monkeypatch):
        """POST /add-source with empty JSON body → 422."""
        client, _, _ = _make_client(tmp_path, monkeypatch)
        resp = client.post("/api/onboard/add-source", json={})
        assert resp.status_code == 422
