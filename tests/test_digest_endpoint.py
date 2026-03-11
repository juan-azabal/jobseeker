"""Tests for GET /api/digest/{user_id} endpoint (Phase 1.4: integer user_id)."""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, upsert_user_job_score
from api.main import app

INGEST_KEY = "test-ingest-key"

JOBS_TODAY = [
    {
        "job_id": "d1",
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "url": "https://ex.com/d1",
        "location_type": "remote",
        "domain": "saas",
        "parsed": "{}",
        "first_seen": date.today().isoformat(),
        "last_seen": date.today().isoformat(),
        "ingested_at": f"{date.today().isoformat()}T10:00:00",
    },
    {
        "job_id": "d2",
        "title": "Senior PM",
        "company": "Beta",
        "location": "Barcelona",
        "url": "https://ex.com/d2",
        "location_type": "onsite",
        "domain": "fintech",
        "parsed": "{}",
        "first_seen": date.today().isoformat(),
        "last_seen": date.today().isoformat(),
        "ingested_at": f"{date.today().isoformat()}T09:00:00",
    },
    {
        "job_id": "d3",
        "title": "Growth Lead",
        "company": "Gamma",
        "location": "Remote",
        "url": "https://ex.com/d3",
        "location_type": "remote",
        "domain": "ecommerce",
        "parsed": "{}",
        "first_seen": date.today().isoformat(),
        "last_seen": date.today().isoformat(),
        "ingested_at": f"{date.today().isoformat()}T08:00:00",
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
def client_with_profile(tmp_path, monkeypatch):
    """TestClient with DB seeded: user with profile_id, jobs from today.
    Returns (client, user_id).
    """
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_digest",
            "email": "digest@test.com",
            "name": "Digest User",
            "avatar_url": None,
            "profile_id": "testprofile",
        },
    )

    for job in JOBS_TODAY:
        upsert_job(db_path, job)

    # Seed v2 scores for two jobs
    upsert_user_job_score(
        db_path,
        user["id"],
        "d1",
        0,
        "A",
        json.dumps({"technical_depth": "A", "profile_evidence": "A"}),
        technical_grade="A",
        profile_grade="A",
        scored_v2=1,
    )
    upsert_user_job_score(
        db_path,
        user["id"],
        "d2",
        0,
        "B",
        json.dumps({"technical_depth": "B", "profile_evidence": "C"}),
        technical_grade="B",
        profile_grade="C",
        scored_v2=1,
    )
    # d3 is unscored (heuristic path)

    monkeypatch.setattr("api.routes.digest.load_profile_data", lambda uid: MINIMAL_PROFILE)

    return TestClient(app), user["id"]


def test_valid_request_returns_200(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert "summary" in data


def test_invalid_ingest_key_returns_403(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": "wrong-key"},
    )
    assert resp.status_code == 403


def test_unknown_user_id_returns_404(client_with_profile):
    client, _ = client_with_profile
    resp = client.get(
        "/api/digest/99999",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 404


def test_response_jobs_have_required_fields(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    assert len(jobs) > 0
    for job in jobs:
        assert "job_id" in job
        assert "score" in job
        assert "tier" in job
        assert "url" in job


def test_summary_tier_a_count_matches_jobs(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    jobs = data["jobs"]
    summary = data["summary"]
    tier_a_actual = sum(1 for j in jobs if j["tier"] == "A")
    assert summary["tier_a"] == tier_a_actual


def test_jobs_sorted_by_score_descending(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    scores = [j["score"] for j in jobs]
    assert scores == sorted(scores, reverse=True)


def test_response_has_profile_id_and_date(client_with_profile):
    client, uid = client_with_profile
    resp = client.get(
        f"/api/digest/{uid}",
        headers={"X-Ingest-Key": INGEST_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile_id"] == "testprofile"
    assert data["date"] == date.today().isoformat()
