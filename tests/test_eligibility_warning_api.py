"""Phase 19.4.1 — eligibility_warning field in list + detail API responses.

A geo-restricted remote job (remote_restriction != null) that excludes the
user's home country must include eligibility_warning = restriction_text in both
GET /api/jobs and GET /api/jobs/{id}.

Jobs without a restriction (or where the user is eligible) must have
eligibility_warning absent or None.
"""

import json
import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session
from api.main import app

# Profile: home in Barcelona (Spain) — ineligible for US-only remote jobs
_PROFILE_BARCELONA = {
    "domains": {"saas": 10},
    "seniority": {
        "senior": 15,
        "principal": 10,
    },
    "skills": [],
    "home_locations": ["barcelona"],
    "home_regions": [],
    "languages": [],
    "location_preference": "a",
    "country_weights": {},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}

_RESTRICTION_TEXT = "Must be based in the United States"

_JOB_RESTRICTED = {
    "job_id": "ew-001",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Remote (US only)",
    "url": "https://example.com/ew001",
    "location_type": "remote",
    "domain": "saas",
    "parsed": json.dumps(
        {
            "domain": "saas",
            "seniority": "senior",
            "location_type": "remote",
            "remote_restriction": _RESTRICTION_TEXT,
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "red_flags": [],
        }
    ),
    "first_seen": "2026-02-01",
    "last_seen": "2026-02-01",
    "ingested_at": "2026-02-01T10:00:00",
}

_JOB_UNRESTRICTED = {
    "job_id": "ew-002",
    "title": "PM Europe",
    "company": "Beta",
    "location": "Remote",
    "url": "https://example.com/ew002",
    "location_type": "remote",
    "domain": "saas",
    "parsed": json.dumps(
        {
            "domain": "saas",
            "seniority": "senior",
            "location_type": "remote",
            "remote_restriction": None,
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "red_flags": [],
        }
    ),
    "first_seen": "2026-02-01",
    "last_seen": "2026-02-01",
    "ingested_at": "2026-02-01T10:00:00",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, _JOB_RESTRICTED)
    upsert_job(db_path, _JOB_UNRESTRICTED)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_ew",
            "email": "ew@test.com",
            "name": "EW",
            "avatar_url": None,
            "profile_id": "ew_user",
        },
    )
    monkeypatch.setattr("api.routes.jobs.load_profile_data", lambda uid: _PROFILE_BARCELONA)
    create_session(db_path, "tok-ew", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok-ew")
    return c


class TestEligibilityWarningList:
    """GET /api/jobs — eligibility_warning in list response."""

    def test_restricted_job_has_eligibility_warning(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        assert "ew-001" in jobs
        assert jobs["ew-001"]["eligibility_warning"] == _RESTRICTION_TEXT

    def test_unrestricted_job_has_no_eligibility_warning(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        assert "ew-002" in jobs
        assert jobs["ew-002"].get("eligibility_warning") is None


class TestEligibilityWarningDetail:
    """GET /api/jobs/{id} — eligibility_warning in detail response."""

    def test_restricted_job_detail_has_eligibility_warning(self, client):
        resp = client.get("/api/jobs/ew-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility_warning"] == _RESTRICTION_TEXT

    def test_unrestricted_job_detail_has_no_eligibility_warning(self, client):
        resp = client.get("/api/jobs/ew-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("eligibility_warning") is None
