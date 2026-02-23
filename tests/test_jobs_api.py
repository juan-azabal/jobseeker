import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from api.db.init import init_db
from api.db.queries import upsert_job
from api.main import app

FIXTURES = Path(__file__).parent / "fixtures"

JOBS = [
    {
        "job_id": "a1", "title": "Senior PM", "company": "Acme",
        "location": "Paris, FR", "url": "https://ex.com/1",
        "location_type": "hybrid", "domain": "data", "score": 72, "tier": "A",
        "parsed": '{}', "scored": '{}',
        "first_seen": "2026-02-23", "last_seen": "2026-02-23",
        "ingested_at": "2026-02-23T10:00:00",
    },
    {
        "job_id": "b1", "title": "ML PM", "company": "Beta",
        "location": "Remote", "url": "https://ex.com/2",
        "location_type": "remote", "domain": "ml", "score": 35, "tier": "B",
        "parsed": '{}', "scored": '{}',
        "first_seen": "2026-02-20", "last_seen": "2026-02-20",
        "ingested_at": "2026-02-20T10:00:00",
    },
    {
        "job_id": "c1", "title": "Growth PM", "company": "Gamma",
        "location": "Amsterdam", "url": "https://ex.com/3",
        "location_type": "onsite", "domain": "growth", "score": 20, "tier": "C",
        "parsed": '{}', "scored": None,
        "first_seen": "2026-02-01", "last_seen": "2026-02-01",
        "ingested_at": "2026-02-01T10:00:00",
    },
]


@pytest.fixture(autouse=True)
def seed_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    for j in JOBS:
        upsert_job(db_path, j)
    monkeypatch.setenv("DB_PATH", db_path)
    yield db_path


client = TestClient(app)


def test_get_jobs_all():
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["jobs"]) == 3


def test_get_jobs_filter_tier_a():
    resp = client.get("/api/jobs?tier=a")
    assert resp.status_code == 200
    data = resp.json()
    assert all(j["tier"] == "A" for j in data["jobs"])


def test_get_jobs_filter_multiple_tiers():
    resp = client.get("/api/jobs?tier=a&tier=b")
    data = resp.json()
    tiers = {j["tier"] for j in data["jobs"]}
    assert tiers == {"A", "B"}


def test_get_jobs_filter_period_today():
    resp = client.get("/api/jobs?period=today")
    data = resp.json()
    assert all(j["first_seen"] == "2026-02-23" for j in data["jobs"])


def test_get_jobs_filter_period_week():
    resp = client.get("/api/jobs?period=week")
    data = resp.json()
    # week includes 2026-02-20 and 2026-02-23 but not 2026-02-01
    assert all(j["first_seen"] >= "2026-02-17" for j in data["jobs"])


def test_get_jobs_sorted_by_score():
    resp = client.get("/api/jobs")
    scores = [j["score"] for j in resp.json()["jobs"]]
    assert scores == sorted(scores, reverse=True)


def test_get_jobs_response_shape():
    resp = client.get("/api/jobs")
    job = resp.json()["jobs"][0]
    for field in ("job_id", "title", "company", "location", "score", "tier", "first_seen", "url"):
        assert field in job
