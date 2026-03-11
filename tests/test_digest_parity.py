"""Parity tests: GET /api/digest/{user_id} must match list_jobs() scoring.

For each job returned by the digest endpoint, the score and tier must be
identical to what list_jobs() would compute via the same code path.
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, upsert_user_job_score, create_session
from api.main import app

INGEST_KEY = "parity-test-key"
TODAY = date.today().isoformat()

JOBS = [
    {
        "job_id": "p1",
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "url": "https://ex.com/p1",
        "location_type": "remote",
        "domain": "saas",
        "parsed": json.dumps(
            {
                "domain": "saas",
                "seniority": "senior",
                "location_type": "remote",
                "skills": ["product strategy"],
                "remote_restriction": None,
            }
        ),
        "first_seen": TODAY,
        "last_seen": TODAY,
        "ingested_at": f"{TODAY}T10:00:00",
    },
    {
        "job_id": "p2",
        "title": "Senior PM",
        "company": "Beta",
        "location": "Barcelona",
        "url": "https://ex.com/p2",
        "location_type": "onsite",
        "domain": "fintech",
        "parsed": json.dumps(
            {
                "domain": "fintech",
                "seniority": "senior",
                "location_type": "onsite",
                "skills": ["roadmap"],
                "remote_restriction": None,
            }
        ),
        "first_seen": TODAY,
        "last_seen": TODAY,
        "ingested_at": f"{TODAY}T09:00:00",
    },
    {
        "job_id": "p3",
        "title": "Growth Lead",
        "company": "Gamma",
        "location": "Remote",
        "url": "https://ex.com/p3",
        "location_type": "remote",
        "domain": "ecommerce",
        "parsed": json.dumps(
            {
                "domain": "ecommerce",
                "seniority": "lead",
                "location_type": "remote",
                "skills": [],
                "remote_restriction": None,
            }
        ),
        "first_seen": TODAY,
        "last_seen": TODAY,
        "ingested_at": f"{TODAY}T08:00:00",
    },
]

MINIMAL_PROFILE = {
    "domains": {"saas": 15, "fintech": 5},
    "seniority": {"senior": 10, "lead": 8},
    "skills": ["product strategy", "roadmap"],
    "home_locations": ["spain", "barcelona"],
    "home_regions": ["europe", "eu"],
    "languages": ["english", "spanish"],
    "location_preference": "r",
    "country_weights": {},
    "company_type_weights": {},
    "role_function": None,
}


@pytest.fixture
def parity_setup(tmp_path, monkeypatch):
    """Seed DB with jobs and two clients: web (session auth) + digest (ingest key)."""
    db_path = str(tmp_path / "parity.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_parity",
            "email": "parity@test.com",
            "name": "Parity User",
            "avatar_url": None,
            "profile_id": "paritypro",
        },
    )
    for job in JOBS:
        upsert_job(db_path, job)

    # Seed v2 score for p1
    upsert_user_job_score(
        db_path,
        user["id"],
        "p1",
        0,
        "A",
        json.dumps({"technical_depth": "A", "profile_evidence": "A"}),
        technical_grade="A",
        profile_grade="A",
        scored_v2=1,
    )

    monkeypatch.setattr("api.routes.digest.load_profile_data", lambda uid: MINIMAL_PROFILE)
    monkeypatch.setattr("api.routes.jobs.load_profile_data", lambda uid: MINIMAL_PROFILE)

    create_session(db_path, "parity_tok", user["id"], "2099-01-01T00:00:00")

    web_client = TestClient(app)
    web_client.cookies.set("jsk", "parity_tok")

    digest_client = TestClient(app)

    return {"web": web_client, "digest": digest_client, "user_id": user["id"]}


def test_digest_and_web_scores_are_identical(parity_setup):
    """For every job in the digest, score and tier match list_jobs(period='today')."""
    web_resp = parity_setup["web"].get("/api/jobs", params={"period": "today"})
    assert web_resp.status_code == 200
    web_jobs = {j["job_id"]: j for j in web_resp.json()["jobs"]}

    uid = parity_setup["user_id"]
    digest_resp = parity_setup["digest"].get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert digest_resp.status_code == 200
    digest_jobs = {j["job_id"]: j for j in digest_resp.json()["jobs"]}

    # All digest jobs should be in web jobs
    for job_id, digest_job in digest_jobs.items():
        assert job_id in web_jobs, f"Job {job_id} in digest but not in web"
        web_job = web_jobs[job_id]
        assert digest_job["score"] == web_job["score"], (
            f"Score mismatch for {job_id}: digest={digest_job['score']} web={web_job['score']}"
        )
        assert digest_job["tier"] == web_job["tier"], (
            f"Tier mismatch for {job_id}: digest={digest_job['tier']} web={web_job['tier']}"
        )


def test_digest_summary_counts_match_jobs(parity_setup):
    """summary.tier_a/b/c must equal actual job tier counts."""
    uid = parity_setup["user_id"]
    resp = parity_setup["digest"].get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    jobs = data["jobs"]
    summary = data["summary"]

    assert summary["tier_a"] == sum(1 for j in jobs if j["tier"] == "A")
    assert summary["tier_b"] == sum(1 for j in jobs if j["tier"] == "B")
    assert summary["tier_c"] == sum(1 for j in jobs if j["tier"] == "C")
    assert summary["total"] == len(jobs)
