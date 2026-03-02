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
    "parsed": json.dumps({"description": "We are looking for a Senior PM to drive data platform growth."}),
    "scored": json.dumps(
        {
            "rag_score": {
                "total": 75,
                "breakdown": {"domain_fit": 20},
                "strengths": ["Data background"],
                "gaps": [],
            }
        }
    ),
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

    # Create the 2 logic reference files (personal CV comes from DB)
    refs = tmp_path / "refs"
    refs.mkdir()
    for name in ["generate-cv.md", "ats-rules.md"]:
        (refs / name).write_text(f"# {name}\nReference content for {name}.")

    user = upsert_user(
        db_path,
        {
            "google_id": "g_cv",
            "email": "cv@test.com",
            "name": "CV Tester",
            "avatar_url": None,
            "profile_id": None,
        },
    )
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


def test_generate_cv_no_jd_succeeds_with_fallback(authed_client):
    """Job without JD text succeeds in plan-aware path using parsed fallback note."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_2/generate-cv")
    assert resp.status_code == 200
    assert "no_jd" not in resp.text


def test_generate_cv_llm_failure_returns_500(authed_client):
    """LLM exception returns 500 with error detail."""
    with patch("api.cv.llm.generate_cv", side_effect=RuntimeError("API quota exceeded")):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "llm_error"
    assert "API quota exceeded" in data["detail"]


# ── Plan-driven pipeline headers (Step 6.6) ──────────────────────────────


def test_generate_cv_returns_cv_validation_header(authed_client):
    """Response includes X-CV-Validation header with passed and warning_count."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert "x-cv-validation" in resp.headers, "Response must include X-CV-Validation header"
    validation = json.loads(resp.headers["x-cv-validation"])
    assert "passed" in validation
    assert "warning_count" in validation
    assert isinstance(validation["passed"], bool)
    assert isinstance(validation["warning_count"], int)


def test_generate_cv_returns_fix_applied_header_false_when_no_fix(authed_client):
    """X-CV-Fix-Applied header is 'false' when validation passes on first attempt."""
    with patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert "x-cv-fix-applied" in resp.headers
    # Minimal reference files → empty source_facts → validation passes without fix
    assert resp.headers["x-cv-fix-applied"] == "false"


def test_generate_cv_fix_applied_when_first_validation_fails(authed_client):
    """When first validation fails, a fix call is triggered and X-CV-Fix-Applied is 'true'."""
    from api.cv.validator import validate_cv as real_validate_cv

    # First validate call returns failed; second returns passed
    validate_results = [
        {"passed": False, "errors": [{"code": "slop_detected", "detail": "Found slop"}], "warnings": []},
        {"passed": True, "errors": [], "warnings": []},
    ]

    call_count = 0

    def mock_validate(markdown, plan):
        nonlocal call_count
        result = validate_results[min(call_count, len(validate_results) - 1)]
        call_count += 1
        return result

    with (
        patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN),
        patch("api.cv.validator.validate_cv", side_effect=mock_validate),
    ):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert resp.headers.get("x-cv-fix-applied") == "true", "X-CV-Fix-Applied must be 'true' when fix call was triggered"


def test_generate_cv_llm_called_twice_when_fix_needed(authed_client):
    """Two LLM calls are made when validation fails: initial + fix."""
    validate_results = [
        {"passed": False, "errors": [{"code": "title_downgraded", "detail": "Title wrong"}], "warnings": []},
        {"passed": True, "errors": [], "warnings": []},
    ]
    call_count = 0

    def mock_validate(markdown, plan):
        nonlocal call_count
        result = validate_results[min(call_count, 1)]
        call_count += 1
        return result

    with (
        patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN) as mock_llm,
        patch("api.cv.validator.validate_cv", side_effect=mock_validate),
    ):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert mock_llm.call_count == 2, f"Expected 2 LLM calls (initial + fix), got {mock_llm.call_count}"


def test_generate_cv_fix_not_applied_when_validation_passes(authed_client):
    """When validation passes immediately, only one LLM call is made."""
    with (
        patch("api.cv.llm.generate_cv", return_value=MOCK_CV_MARKDOWN) as mock_llm,
        patch("api.cv.validator.validate_cv", return_value={"passed": True, "errors": [], "warnings": []}),
    ):
        resp = authed_client.post("/api/jobs/cv_test_1/generate-cv")

    assert resp.status_code == 200
    assert mock_llm.call_count == 1, f"Expected 1 LLM call (no fix needed), got {mock_llm.call_count}"
    assert resp.headers.get("x-cv-fix-applied") == "false"
