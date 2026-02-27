import json
import pytest
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session, upsert_user_job_score
from api.main import app

JOB = {
    "job_id": "a1",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Paris, FR",
    "url": "https://ex.com/1",
    "location_type": "hybrid",
    "domain": "data",
    "parsed": json.dumps({"domain": "data", "must_have_skills": ["SQL"]}),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}

SCORED_JSON = json.dumps(
    {
        "score": 72,
        "score_breakdown": {
            "domain_fit": 20,
            "seniority_fit": 15,
            "technical_depth": 18,
            "profile_evidence": 15,
            "strategic_impact": 4,
        },
        "strengths": [{"claim": "Strong data background", "evidence": "5 years"}],
        "gaps": [{"skill": "Rust", "severity": "low", "mitigation": "nice to have"}],
    }
)


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_t",
            "email": "t@t.com",
            "name": "T",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    upsert_user_job_score(db_path, user["id"], "a1", 72, "A", SCORED_JSON)
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
    # v1 UJS (scored_v2=0) no longer returns the stored scored JSON — it is
    # re-scored via heuristic and scored=None. Only v2 jobs return scored blob.
    resp = authed_client.get("/api/jobs/a1")
    data = resp.json()
    assert "scored" in data
    assert data["scored"] is None


def test_get_job_detail_404(authed_client):
    resp = authed_client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


def test_get_job_detail_has_skill_matches(tmp_path, monkeypatch):
    """Job detail includes skill_matches when user has a profile."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    job_with_skills = {
        **JOB,
        "parsed": json.dumps(
            {
                "domain": "data",
                "must_have_skills": ["SQL", "python"],
                "nice_to_have_skills": ["kafka"],
                "technical_stack": ["snowflake"],
            }
        ),
    }
    upsert_job(db_path, job_with_skills)
    monkeypatch.setenv("DB_PATH", db_path)

    # Create user with a profile_id so load_profile_data is attempted
    user = upsert_user(
        db_path,
        {
            "google_id": "g_skill",
            "email": "skill@test.com",
            "name": "Skill User",
            "avatar_url": None,
            "profile_id": "test_skill_user",
        },
    )
    create_session(db_path, "skill_tok", user["id"], "2099-01-01T00:00:00")

    # Mock load_profile_data to return a profile with skills
    from unittest.mock import patch

    mock_profile = {
        "domains": {"data": 15},
        "seniority": {"senior": 15},
        "skills": ["python", "sql"],
        "home_locations": [],
        "home_regions": [],
        "languages": [],
        "location_preference": "b",
        "country_weights": {},
        "company_type_weights": {},
    }
    with patch("api.routes.jobs.load_profile_data", return_value=mock_profile):
        c = TestClient(app)
        c.cookies.set("jsk", "skill_tok")
        resp = c.get("/api/jobs/a1")

    assert resp.status_code == 200
    data = resp.json()
    assert "skill_matches" in data
    assert "must_have" in data["skill_matches"]
    assert "nice_to_have" in data["skill_matches"]
    # Must-have should have 2 entries (SQL, python)
    assert len(data["skill_matches"]["must_have"]) == 2
    for sm in data["skill_matches"]["must_have"]:
        assert "skill" in sm
        assert "status" in sm


def test_get_job_detail_skill_matches_null_without_profile(authed_client):
    """skill_matches is null when user has no profile."""
    resp = authed_client.get("/api/jobs/a1")
    data = resp.json()
    assert data.get("skill_matches") is None
