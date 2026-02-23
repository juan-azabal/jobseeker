import json
import pytest
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session
from api.main import app

JOB = {
    "job_id": "a1",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Paris, FR",
    "url": "https://ex.com/1",
    "location_type": "hybrid",
    "domain": "data",
    "score": 72,
    "tier": "A",
    "parsed": json.dumps({"domain": "data", "must_have_skills": ["SQL"]}),
    "scored": json.dumps({
        "score": 72,
        "score_breakdown": {
            "domain_fit": 20, "seniority_fit": 15,
            "technical_depth": 18, "profile_evidence": 15, "strategic_impact": 4
        },
        "strengths": [{"claim": "Strong data background", "evidence": "5 years"}],
        "gaps": [{"skill": "Rust", "severity": "low", "mitigation": "nice to have"}],
    }),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(db_path, {
        "google_id": "g_t", "email": "t@t.com",
        "name": "T", "avatar_url": None, "profile_id": None,
    })
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c


def test_get_job_detail_200(authed_client):
    resp = authed_client.get("/api/jobs/a1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "a1"
    assert data["title"] == "Senior PM"


def test_get_job_detail_has_parsed(authed_client):
    resp = authed_client.get("/api/jobs/a1")
    data = resp.json()
    assert "parsed" in data
    assert data["parsed"]["domain"] == "data"


def test_get_job_detail_has_scored(authed_client):
    resp = authed_client.get("/api/jobs/a1")
    data = resp.json()
    assert "scored" in data
    assert data["scored"]["score"] == 72
    assert "score_breakdown" in data["scored"]


def test_get_job_detail_404(authed_client):
    resp = authed_client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404
