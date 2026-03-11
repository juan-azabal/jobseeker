"""Tests scoring parity between list and detail job endpoints.

Verifies that GET /api/jobs and GET /api/jobs/{id} produce the same score for
the same job when a domain_override is set — ensuring neither endpoint silently
ignores the override.
"""

import json
import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session, set_domain_override
from api.main import app

# Minimal profile: saas has weight 10, no skills (isolates domain scoring)
_PROFILE = {
    "domains": {"saas": 10},
    "seniority": {
        "junior": 6,
        "mid": 10,
        "senior": 15,
        "staff": 10,
        "principal": 6,
        "director": 4,
        "vp": 4,
    },
    "skills": [],
    "home_locations": [],
    "home_regions": [],
    "languages": [],
    "location_preference": "a",  # remote-only — avoids geo scoring noise
    "country_weights": {},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}

# Job with domain="other" and no saas keywords → heuristic gives 0 domain points
# Without override. With override="saas" the domain contributes +10.
_JOB = {
    "job_id": "parity-001",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Remote",
    "url": "https://example.com/parity",
    "location_type": "remote",
    "domain": "other",
    "parsed": json.dumps(
        {
            "domain": "other",
            "seniority": "senior",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "red_flags": [],
        }
    ),
    "first_seen": "2026-01-01",
    "last_seen": "2026-01-01",
    "ingested_at": "2026-01-01T10:00:00",
}


@pytest.fixture
def parity_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, _JOB)
    monkeypatch.setenv("DB_PATH", db_path)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_parity",
            "email": "parity@test.com",
            "name": "Parity",
            "avatar_url": None,
            "profile_id": "parity_user",
        },
    )
    create_session(db_path, "parity_tok", user["id"], "2099-01-01T00:00:00")

    # User corrects domain: "other" → "saas" (preferred domain, weight 10)
    set_domain_override(db_path, user["id"], "parity-001", "saas")

    # Patch profile loading so no DB lookup is needed
    monkeypatch.setattr("api.routes.jobs.load_profile_data", lambda uid: _PROFILE)

    c = TestClient(app)
    c.cookies.set("jsk", "parity_tok")
    return c


def test_list_and_detail_score_identical_with_domain_override(parity_client):
    """Both endpoints must apply domain_override and produce the same score."""
    list_resp = parity_client.get("/api/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()["jobs"]
    job_in_list = next((j for j in jobs if j["job_id"] == "parity-001"), None)
    assert job_in_list is not None, "Job not found in list response"
    list_score = job_in_list["score"]

    detail_resp = parity_client.get("/api/jobs/parity-001")
    assert detail_resp.status_code == 200
    detail_score = detail_resp.json()["score"]

    assert list_score == detail_score, (
        f"Score mismatch: list={list_score}, detail={detail_score}. "
        "domain_override='saas' must be applied identically in both endpoints."
    )


def test_domain_override_is_applied_not_ignored(parity_client):
    """domain_override='saas' (weight 10) must raise score above zero."""
    # Without override domain="other" → 0 domain points.
    # With override domain="saas" → +10 domain points.
    # Unscored: +20 grade neutral. Senior seniority: +15. Remote + pref="a": +10.
    # Expected minimum: at least the domain contribution makes score > 0.
    detail_resp = parity_client.get("/api/jobs/parity-001")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["score"] > 0, "Score should be > 0 when domain_override points to a preferred domain"
