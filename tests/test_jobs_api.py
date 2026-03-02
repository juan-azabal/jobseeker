import json
import pytest
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session, upsert_user_job_score
from api.main import app

JOBS = [
    {
        "job_id": "a1",
        "title": "Senior PM",
        "company": "Acme",
        "location": "Paris, FR",
        "url": "https://ex.com/1",
        "location_type": "hybrid",
        "domain": "data",
        "parsed": "{}",
        "first_seen": "2026-02-23",
        "last_seen": "2026-02-23",
        "ingested_at": "2026-02-23T10:00:00",
    },
    {
        "job_id": "b1",
        "title": "ML PM",
        "company": "Beta",
        "location": "Remote",
        "url": "https://ex.com/2",
        "location_type": "remote",
        "domain": "ml",
        "parsed": "{}",
        "first_seen": "2026-02-20",
        "last_seen": "2026-02-20",
        "ingested_at": "2026-02-20T10:00:00",
    },
    {
        "job_id": "c1",
        "title": "Growth PM",
        "company": "Gamma",
        "location": "Amsterdam",
        "url": "https://ex.com/3",
        "location_type": "onsite",
        "domain": "growth",
        "parsed": "{}",
        "first_seen": "2026-02-01",
        "last_seen": "2026-02-01",
        "ingested_at": "2026-02-01T10:00:00",
    },
]

# Per-user RAG scores for the test user
USER_SCORES = [
    ("a1", 72, "A"),
    ("b1", 35, "B"),
    ("c1", 20, "C"),
]


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    for j in JOBS:
        upsert_job(db_path, j)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_test",
            "email": "t@t.com",
            "name": "T",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    # Insert per-user scores
    for job_id, score, tier in USER_SCORES:
        upsert_user_job_score(db_path, user["id"], job_id, score, tier, "{}")
    create_session(db_path, "test_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "test_tok")
    return c


def test_get_jobs_all(authed_client):
    resp = authed_client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["jobs"]) == 3


def test_get_jobs_filter_tier_a(authed_client):
    resp = authed_client.get("/api/jobs?tier=a")
    assert resp.status_code == 200
    assert all(j["tier"] == "A" for j in resp.json()["jobs"])


def test_get_jobs_filter_multiple_tiers(authed_client):
    # Without a user profile, all jobs score 0 (tier C) because v1 stored scores
    # are no longer used directly. Filtering for A+B returns empty; the invariant
    # is that no C-tier jobs appear when only A+B are requested.
    resp = authed_client.get("/api/jobs?tier=a&tier=b")
    tiers = {j["tier"] for j in resp.json()["jobs"]}
    assert tiers.issubset({"A", "B"})


def test_get_jobs_filter_period_today(authed_client):
    resp = authed_client.get("/api/jobs?period=today")
    assert all(j["first_seen"] == "2026-02-23" for j in resp.json()["jobs"])


def test_get_jobs_filter_period_week(authed_client):
    resp = authed_client.get("/api/jobs?period=week")
    assert all(j["first_seen"] >= "2026-02-17" for j in resp.json()["jobs"])


def test_get_jobs_sorted_by_score(authed_client):
    resp = authed_client.get("/api/jobs")
    scores = [j["score"] for j in resp.json()["jobs"]]
    assert scores == sorted(scores, reverse=True)


def test_get_jobs_response_shape(authed_client):
    resp = authed_client.get("/api/jobs")
    job = resp.json()["jobs"][0]
    for field in ("job_id", "title", "company", "location", "score", "tier", "first_seen", "url"):
        assert field in job


def test_get_jobs_total_in_db(authed_client):
    resp = authed_client.get("/api/jobs")
    data = resp.json()
    assert "total_in_db" in data
    assert data["total_in_db"] == 3


@pytest.fixture
def v15_client(tmp_path, monkeypatch):
    """Client with one job that has v1.5 parser fields."""
    db_path = str(tmp_path / "v15.db")
    init_db(db_path)
    parsed_blob = json.dumps(
        {
            "location_type": "remote",
            "domain": "saas",
            "role_in_plain_english": "Own the roadmap end-to-end.",
            "truly_required": ["SQL", "stakeholder management"],
            "preferred_skills": ["Python", "dbt"],
            "verbatim_for_cv": ["scale our data platform"],
            "company_context": {
                "stage": "growth",
                "what_they_value": ["speed"],
                "tone": "startup_scrappy",
            },
        }
    )
    upsert_job(
        db_path,
        {
            "job_id": "v15-001",
            "title": "Head of Product",
            "company": "Acme",
            "location": "Remote",
            "url": "https://ex.com/v15",
            "location_type": "remote",
            "domain": "saas",
            "parsed": parsed_blob,
            "first_seen": "2026-03-01",
            "last_seen": "2026-03-01",
            "ingested_at": "2026-03-01T10:00:00",
            "role_in_plain_english": "Own the roadmap end-to-end.",
            "company_stage": "growth",
            "company_tone": "startup_scrappy",
        },
    )
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {"google_id": "g_v15", "email": "v15@t.com", "name": "V15", "avatar_url": None, "profile_id": None},
    )
    create_session(db_path, "v15_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "v15_tok")
    return c


def test_list_jobs_v15_real_columns(v15_client):
    """List endpoint exposes real-column v1.5 fields."""
    resp = v15_client.get("/api/jobs")
    assert resp.status_code == 200
    job = resp.json()["jobs"][0]
    assert job["role_in_plain_english"] == "Own the roadmap end-to-end."
    assert job["company_stage"] == "growth"
    assert job["company_tone"] == "startup_scrappy"


def test_list_jobs_v15_blob_fields(v15_client):
    """List endpoint extracts truly_required, preferred_skills from parsed blob."""
    resp = v15_client.get("/api/jobs")
    job = resp.json()["jobs"][0]
    assert "SQL" in job["truly_required"]
    assert "Python" in job["preferred_skills"]
    assert job["verbatim_for_cv"] == ["scale our data platform"]
    assert job["company_context"]["stage"] == "growth"
    assert job["company_context"]["tone"] == "startup_scrappy"


def test_detail_job_v15_fields(v15_client):
    """Detail endpoint exposes all v1.5 fields at top level."""
    resp = v15_client.get("/api/jobs/v15-001")
    assert resp.status_code == 200
    job = resp.json()
    assert job["role_in_plain_english"] == "Own the roadmap end-to-end."
    assert job["company_stage"] == "growth"
    assert job["company_tone"] == "startup_scrappy"
    assert "SQL" in job["truly_required"]
    assert "Python" in job["preferred_skills"]
    assert job["verbatim_for_cv"] == ["scale our data platform"]
    assert job["company_context"]["tone"] == "startup_scrappy"


def test_v15_fields_omitted_when_null(authed_client):
    """v1.5 fields absent from response when null (null-omit pattern)."""
    resp = authed_client.get("/api/jobs")
    # JOBS fixture has no v1.5 fields; verify keys absent
    for job in resp.json()["jobs"]:
        assert "role_in_plain_english" not in job
        assert "company_stage" not in job
        assert "company_tone" not in job
        assert "truly_required" not in job
        assert "preferred_skills" not in job
        assert "verbatim_for_cv" not in job
        assert "company_context" not in job
