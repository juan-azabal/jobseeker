"""Tests for Phase 14.4 — 8 server-side user action events.

Each test verifies that analytics.capture() is called with the correct
event name and key properties when the corresponding endpoint succeeds.
Tests are written BEFORE implementation (test-first).
"""

import json
import os
import pytest
import yaml
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session

from api.main import app

JOB = {
    "job_id": "j1",
    "title": "Senior PM",
    "company": "Acme Corp",
    "location": "Barcelona, Spain",
    "url": "https://ex.com/1",
    "location_type": "hybrid",
    "domain": "saas",
    "description": "We need a seasoned Product Manager to drive the roadmap for our SaaS platform.",
    "parsed": json.dumps(
        {
            "domain": "saas",
            "must_have_skills": ["SQL"],
            "seniority": "senior",
            "description": "We need a seasoned Product Manager to drive the roadmap for our SaaS platform.",
        }
    ),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}

# Minimal valid CV markdown the mocked LLM returns
MOCK_CV = (
    "# Alice Martin\n"
    "Senior PM | Barcelona\n\n"
    "## Summary\n\nExperienced PM.\n\n"
    "## Work Experience\n\n"
    "### Acme Corp, Barcelona\n"
    "**Senior PM | 01/2022 - Present**\n\n"
    "- Led roadmap for SaaS platform\n\n"
    "## Education\n\n"
    "- MBA - IESE 2017\n\n"
    "## Languages\n\n"
    "- English - Native\n"
)


@pytest.fixture
def db_client(tmp_path, monkeypatch):
    """Authenticated client with a user + single test job; no profile."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g1",
            "email": "u@t.com",
            "name": "User",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c, user, db_path


@pytest.fixture
def profile_client(tmp_path, monkeypatch):
    """Authenticated client with a user who has a profile YAML on disk."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)

    jobagent_dir = str(tmp_path / "jobagent")
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    user = upsert_user(
        db_path,
        {
            "google_id": "g2",
            "email": "p@t.com",
            "name": "Profile User",
            "avatar_url": None,
            "profile_id": "profXYZ",
        },
    )
    create_session(db_path, "ptok", user["id"], "2099-01-01T00:00:00")

    # Create profile YAML on disk
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    profile_data = {
        "user": {"name": "Profile User", "email": "p@t.com", "home_locations": ["barcelona"]},
        "target": {"domains": {"saas": 15}, "level": "senior", "track": "ic"},
        "skills": ["python", "sql"],
    }
    with open(os.path.join(profiles_dir, "profXYZ.yaml"), "w") as f:
        yaml.dump(profile_data, f)

    c = TestClient(app)
    c.cookies.set("jsk", "ptok")
    return c, user, db_path


# ─── Event tests ──────────────────────────────────────────────────────────────


def test_job_viewed_event(db_client):
    """GET /api/jobs/{id} fires job_viewed with job_id and company."""
    client, user, _ = db_client
    with (
        patch("api.analytics.capture") as mock_capture,
        patch("api.routes.jobs.load_profile_data", return_value=None),
        patch("api.routes.jobs.match_skills", return_value=[]),
    ):
        resp = client.get("/api/jobs/j1")
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    event_name = mock_capture.call_args[0][1]
    props = mock_capture.call_args[0][2]
    assert event_name == "job_viewed"
    assert props["job_id"] == "j1"
    assert props["company"] == "Acme Corp"
    assert props["tier"] in ("A", "B", "C")


def test_job_applied_event(db_client):
    """POST /api/jobs/{id}/apply fires job_applied with job_id and company."""
    client, user, _ = db_client
    with patch("api.analytics.capture") as mock_capture:
        resp = client.post("/api/jobs/j1/apply", json={"applied": True})
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "job_applied"
    props = mock_capture.call_args[0][2]
    assert props["job_id"] == "j1"
    assert props["company"] == "Acme Corp"


def test_job_dismissed_event(db_client):
    """POST /api/jobs/{id}/dismiss fires job_dismissed with job_id and company."""
    client, user, _ = db_client
    with patch("api.analytics.capture") as mock_capture:
        resp = client.post("/api/jobs/j1/dismiss")
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "job_dismissed"
    props = mock_capture.call_args[0][2]
    assert props["job_id"] == "j1"
    assert props["company"] == "Acme Corp"


def test_cv_generated_event(tmp_path, monkeypatch):
    """POST /api/jobs/{id}/generate-cv fires cv_generated via background_tasks."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("CV_REFERENCES_DIR", str(tmp_path / "refs"))

    user = upsert_user(
        db_path,
        {
            "google_id": "g3",
            "email": "cv@t.com",
            "name": "CV User",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    create_session(db_path, "cvtok", user["id"], "2099-01-01T00:00:00")
    client = TestClient(app)
    client.cookies.set("jsk", "cvtok")

    with (
        patch("api.cv.llm.generate_cv", return_value=MOCK_CV),
        patch("api.cv.prompt.build_cv_prompts", return_value=("sys", "usr")),
        patch("api.analytics.capture") as mock_capture,
    ):
        resp = client.post("/api/jobs/j1/generate-cv")

    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "cv_generated"
    props = mock_capture.call_args[0][2]
    assert props["job_id"] == "j1"
    assert props["company"] == "Acme Corp"
    assert "validation_passed" in props
    assert "ats_passed" in props
    assert "fix_applied" in props
    assert "ats_violation_count" in props


def test_skill_added_event(profile_client):
    """POST /api/onboard/profile/skills fires skill_added with the skill name."""
    client, user, _ = profile_client
    with (
        patch("api.analytics.capture") as mock_capture,
        patch("api.embeddings.get_embedding"),
        patch("api.embeddings.clear_memory_cache"),
    ):
        resp = client.post("/api/onboard/profile/skills", json={"skill": "go"})
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "skill_added"
    props = mock_capture.call_args[0][2]
    assert props["skill_name"] == "go"


def test_domain_overridden_event(db_client):
    """PATCH /api/jobs/{id}/domain fires domain_overridden with old and new domains."""
    client, user, _ = db_client
    with patch("api.analytics.capture") as mock_capture:
        resp = client.patch("/api/jobs/j1/domain", json={"domain": "fintech"})
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "domain_overridden"
    props = mock_capture.call_args[0][2]
    assert props["job_id"] == "j1"
    assert props["new_domain"] == "fintech"
    assert "old_domain" in props


def test_profile_saved_event(profile_client):
    """PATCH /api/onboard/profile fires profile_saved."""
    client, user, _ = profile_client
    payload = {
        "name": "Updated Name",
        "home_locations": ["barcelona"],
        "domains": {"saas": 15},
        "skills": ["python", "sql"],
        "seniority_weights": {"senior": 10},
        "country_weights": {},
        "company_type_weights": {},
        "salary_min": 80000,
        "location_preference": "b",
    }
    with (
        patch("api.analytics.capture") as mock_capture,
        patch("api.routes.onboard._push_file_to_github", new_callable=AsyncMock),
    ):
        resp = client.patch("/api/onboard/profile", json=payload)
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "profile_saved"


def test_onboard_completed_event(tmp_path, monkeypatch):
    """POST /api/onboard/save-profile fires onboard_completed on first-time save."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    os.makedirs(jobagent_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    # User with profile_id but NO profile_yaml → onboarded=False → first-time path
    user = upsert_user(
        db_path,
        {
            "google_id": "g5",
            "email": "ob@t.com",
            "name": "Onboard",
            "avatar_url": None,
            "profile_id": "obXYZ",
        },
    )
    create_session(db_path, "obtok", user["id"], "2099-01-01T00:00:00")
    client = TestClient(app)
    client.cookies.set("jsk", "obtok")

    with (
        patch("api.analytics.capture") as mock_capture,
        patch("api.routes.onboard._sync_and_trigger_pipeline", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/onboard/save-profile",
            json={
                "cv_markdown": "# Onboard\nSenior PM",
                "profile": {
                    "name": "Onboard",
                    "email": "ob@t.com",
                    "home_locations": ["barcelona"],
                    "current_level": "senior",
                    "target_level": "senior",
                    "track": "ic",
                    "domains": {"saas": 15, "data": 10},
                    "skills": ["python", "sql"],
                },
                "salary_min": 80000,
                "location_preference": "b",
            },
        )
    assert resp.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args[0][1] == "onboard_completed"
    props = mock_capture.call_args[0][2]
    assert props["profile_id"] == "obXYZ"
    assert props["domains_count"] == 2
    assert props["skills_count"] == 2
