"""Tests for POST /api/jobs/{id}/generate-cv endpoint."""
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session
from api.main import app

# Sample structured markdown the mocked LLM returns
MOCK_CV_MARKDOWN = """# Juan Azabal
Senior Product Manager | Data
Barcelona, Spain | j.azabal@gmail.com

## Summary

Experienced PM with focus on data products.

## Selected Impact

- Grew revenue 40% YoY

## Core Skills

**Data Platform**
Strong background in data warehousing.

## Work Experience

### Acme Corp, Barcelona, Spain
**Senior PM | 01/2021 - Present**

- Led data platform roadmap

## Education and Certifications

- MBA - IESE, 2017

## Languages

- Spanish - Native
"""

JOB_WITH_JD = {
    "job_id": "cv_test_1",
    "title": "Senior Product Manager",
    "company": "Acme Corp",
    "location": "Barcelona",
    "url": "https://ex.com/1",
    "location_type": "hybrid",
    "domain": "data",
    "score": 75,
    "tier": "A",
    "parsed": json.dumps({
        "description": "We are looking for a Senior PM to drive data platform growth."
    }),
    "scored": json.dumps({
        "rag_score": {
            "total": 75,
            "breakdown": {"domain_fit": 20},
            "strengths": ["Data background"],
            "gaps": [],
        }
    }),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}

JOB_WITHOUT_JD = {
    "job_id": "cv_test_2",
    "title": "PM Role No JD",
    "company": "Mystery Corp",
    "location": "Remote",
    "url": "https://ex.com/2",
    "location_type": "remote",
    "domain": "data",
    "score": 60,
    "tier": "B",
    "parsed": json.dumps({"other_field": "no description"}),
    "scored": json.dumps({}),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB_WITH_JD)
    upsert_job(db_path, JOB_WITHOUT_JD)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("CV_REFERENCES_DIR", str(tmp_path / "refs"))

    # Create minimal reference files so prompt builder doesn't fail
    refs = tmp_path / "refs"
    refs.mkdir()
    for name in ["generate-cv.md", "ats-rules.md", "master-cv-profile.md", "master-cv-experience.md"]:
        (refs / name).write_text(f"# {name}\nReference content for {name}.")

    user = upsert_user(db_path, {
        "google_id": "g_cv", "email": "cv@test.com",
        "name": "CV Tester", "avatar_url": None, "profile_id": None,
    })
    create_session(db_path, "cv_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "cv_tok")
    return c


@pytest.fixture
def unauthed_client():
    return TestClient(app)


def test_generate_cv_returns_docx(authed_client):
    """Successful call returns 200 with .docx content-type."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in resp.headers["content-type"]


def test_generate_cv_returns_ats_audit_header(authed_client):
    """Response includes X-ATS-Audit header."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert "x-ats-audit" in resp.headers


def test_generate_cv_filename_contains_company(authed_client):
    """Content-Disposition filename contains slugified company name."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    content_disp = resp.headers.get("content-disposition", "")
    assert "acme" in content_disp.lower()
    assert ".docx" in content_disp


def test_generate_cv_no_auth_returns_401(unauthed_client):
    """Without auth cookie, returns 401."""
    resp = unauthed_client.post("/api/jobs/cv_test_1/generate-cv")
    assert resp.status_code == 401


def test_generate_cv_invalid_job_returns_404(authed_client):
    """Unknown job_id returns 404."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/nonexistent_job/generate-cv")
    assert resp.status_code == 404


def test_generate_cv_no_jd_returns_422(authed_client):
    """Job without extractable JD returns 422 with error code no_jd."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_2/generate-cv")
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "no_jd"


def test_generate_cv_llm_failure_returns_500(authed_client):
    """LLM exception returns 500 with error detail."""
    with patch("api.cv.llm.generate_cv", side_effect=RuntimeError("API quota exceeded")):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "llm_error"
    assert "API quota exceeded" in data["detail"]
