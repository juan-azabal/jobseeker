"""Tests for POST /api/onboard/add-source — Phase 2.3."""

import io
import json
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_master_cv_json, get_master_cv_json
from api.main import app

_INITIAL_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice Martin", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "Acme",
            "position": "Senior PM",
            "start_date": "2020-01",
            "end_date": None,
            "summary": "Led product.",
            "highlights": ["Launched feature X"],
            "skills_used": ["python"],
        }
    ],
    "education": [],
    "skills": [{"name": "python"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}

_NEW_SOURCE_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice Martin", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "StartupCo",
            "position": "PM",
            "start_date": "2017-01",
            "end_date": "2019-12",
            "summary": "Built products.",
            "highlights": ["Grew user base by 3x"],
            "skills_used": ["sql"],
        }
    ],
    "education": [],
    "skills": [{"name": "sql"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}

_MOCK_DERIVED = {
    "name": "Alice Martin",
    "email": "alice@example.com",
    "skills": ["python", "sql"],
    "domains": {},
    "current_level": "senior",
    "target_level": "senior",
    "track": "ic",
    "home_locations": [],
    "languages": [],
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    os.makedirs(jobagent_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_t",
            "email": "t@t.com",
            "name": "T",
            "avatar_url": None,
            "profile_id": "test1234",
        },
    )
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    # Pre-load initial master CV
    save_master_cv_json(db_path, user["id"], json.dumps(_INITIAL_MASTER_CV))
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c, db_path, user["id"]


def test_add_source_file_upload_200(authed_client):
    """Upload a PDF → merge → return 202; merged master_cv persisted in DB."""
    client, db_path, user_id = authed_client
    with (
        patch("api.routes.onboard._make_openai_client", return_value=None),
        patch(
            "api.routes.onboard.extract_text_from_file",
            return_value="# StartupCo\n\nPM 2017–2019",
        ),
        patch(
            "api.routes.onboard.extract_master_cv_json",
            return_value=_NEW_SOURCE_MASTER_CV,
        ),
        patch("api.routes.onboard.index_master_cv"),
    ):
        resp = client.post(
            "/api/onboard/add-source",
            files={"file": ("linkedin.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
    assert resp.status_code == 202
    # TestClient runs BackgroundTasks synchronously — data is persisted now
    saved = json.loads(get_master_cv_json(db_path, user_id))
    companies = [e["company"] for e in saved["work"]]
    assert "Acme" in companies
    assert "StartupCo" in companies


def test_add_source_merges_skills(authed_client):
    """Skills from new source are merged with existing; persisted in DB after 202."""
    client, db_path, user_id = authed_client
    with (
        patch("api.routes.onboard._make_openai_client", return_value=None),
        patch(
            "api.routes.onboard.extract_text_from_file",
            return_value="StartupCo PM 2017",
        ),
        patch(
            "api.routes.onboard.extract_master_cv_json",
            return_value=_NEW_SOURCE_MASTER_CV,
        ),
        patch("api.routes.onboard.index_master_cv"),
    ):
        resp = client.post(
            "/api/onboard/add-source",
            files={
                "file": (
                    "cv.docx",
                    io.BytesIO(b"PK\x03\x04"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert resp.status_code == 202
    saved = json.loads(get_master_cv_json(db_path, user_id))
    names = {s["name"] for s in saved["skills"]}
    assert "python" in names
    assert "sql" in names


def test_add_source_no_existing_master_cv(authed_client):
    """If no existing master CV, incoming becomes master CV; returns 202."""
    client, db_path, user_id = authed_client
    # Clear existing master CV
    from api.db.queries import save_master_cv_json as _save  # noqa: PLC0415

    _save(db_path, user_id, "null")  # simulate no stored CV
    with (
        patch("api.routes.onboard._make_openai_client", return_value=None),
        patch(
            "api.routes.onboard.extract_text_from_file",
            return_value="StartupCo",
        ),
        patch(
            "api.routes.onboard.extract_master_cv_json",
            return_value=_NEW_SOURCE_MASTER_CV,
        ),
        patch("api.routes.onboard.index_master_cv"),
    ):
        resp = client.post(
            "/api/onboard/add-source",
            files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
    assert resp.status_code == 202


def test_add_source_unsupported_type(authed_client):
    client, db_path, user_id = authed_client
    resp = client.post(
        "/api/onboard/add-source",
        files={"file": ("cv.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert resp.status_code == 400


def test_add_source_401_unauthenticated():
    c = TestClient(app)
    resp = c.post(
        "/api/onboard/add-source",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert resp.status_code == 401
