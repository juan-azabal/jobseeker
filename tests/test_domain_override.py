"""Tests for Phase 13.4a — domain override feature.

Tests are written test-first and must FAIL before implementation.

Coverage:
  A. PATCH /api/jobs/{job_id}/domain — set/clear domain override
  B. GET /api/jobs/{job_id} — returns domain_override in response
  C. heuristic_score() with domain_override parameter
  D. _score_and_tier_jobs() batch loading of domain overrides
"""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session, upsert_user_job_score
from api.main import app

JOB = {
    "job_id": "j1",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Paris, FR",
    "url": "https://ex.com/1",
    "location_type": "hybrid",
    "domain": "data",
    "parsed": json.dumps({"domain": "data", "must_have_skills": ["SQL"], "seniority": "senior"}),
    "first_seen": "2026-02-23",
    "last_seen": "2026-02-23",
    "ingested_at": "2026-02-23T10:00:00",
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    """Authenticated client with a single test job and no prior status rows."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
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
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    c._user_id = user["id"]
    c._db_path = db_path
    return c


@pytest.fixture
def authed_client_with_status(tmp_path, monkeypatch):
    """Authenticated client where the job already has an applied_at status row."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_job(db_path, JOB)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_test2",
            "email": "t2@t.com",
            "name": "T2",
            "avatar_url": None,
            "profile_id": None,
        },
    )
    # Insert a pre-existing applied status
    import sqlite3

    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO user_job_status (user_id, job_id, applied_at) VALUES (?, ?, ?)",
        (user["id"], "j1", "2026-02-24T10:00:00"),
    )
    con.commit()
    con.close()
    create_session(db_path, "tok2", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok2")
    c._user_id = user["id"]
    c._db_path = db_path
    return c


# ── A. PATCH /api/jobs/{job_id}/domain ────────────────────────────────────


class TestPatchDomainEndpoint:
    def test_valid_domain_returns_200(self, authed_client):
        resp = authed_client.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"ok": True, "domain": "gaming"}

    def test_valid_domain_stores_override(self, authed_client):
        authed_client.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        # Verify it persisted by fetching the detail
        resp = authed_client.get("/api/jobs/j1")
        assert resp.status_code == 200
        assert resp.json()["domain_override"] == "gaming"

    def test_null_domain_clears_override(self, authed_client):
        # Set then clear
        authed_client.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        resp = authed_client.patch("/api/jobs/j1/domain", json={"domain": None})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "domain": None}

    def test_null_domain_clears_stored_override(self, authed_client):
        authed_client.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        authed_client.patch("/api/jobs/j1/domain", json={"domain": None})
        resp = authed_client.get("/api/jobs/j1")
        assert resp.json().get("domain_override") is None

    def test_invalid_domain_returns_422(self, authed_client):
        resp = authed_client.patch("/api/jobs/j1/domain", json={"domain": "not_a_real_domain_xyz"})
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        upsert_job(db_path, JOB)
        monkeypatch.setenv("DB_PATH", db_path)
        c = TestClient(app)
        resp = c.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        assert resp.status_code == 401

    def test_patch_preserves_applied_at(self, authed_client_with_status):
        """Setting domain override must not overwrite applied_at."""
        authed_client_with_status.patch("/api/jobs/j1/domain", json={"domain": "gaming"})
        resp = authed_client_with_status.get("/api/jobs/j1")
        data = resp.json()
        assert data["applied_at"] is not None
        assert data["domain_override"] == "gaming"

    def test_unknown_job_returns_404(self, authed_client):
        resp = authed_client.patch("/api/jobs/nonexistent_job/domain", json={"domain": "gaming"})
        assert resp.status_code == 404

    def test_all_valid_domains_accepted(self, authed_client):
        """Every value in VALID_DOMAINS must be accepted."""
        from api.scoring import VALID_DOMAINS

        for domain in sorted(VALID_DOMAINS):
            resp = authed_client.patch("/api/jobs/j1/domain", json={"domain": domain})
            assert resp.status_code == 200, f"Expected 200 for domain={domain!r}"


# ── B. GET /api/jobs/{job_id} includes domain_override ───────────────────


class TestGetJobDetailDomainOverride:
    def test_no_override_returns_none(self, authed_client):
        resp = authed_client.get("/api/jobs/j1")
        assert resp.status_code == 200
        # domain_override key should be present but None (or absent — acceptable)
        data = resp.json()
        assert data.get("domain_override") is None

    def test_set_override_appears_in_detail(self, authed_client):
        authed_client.patch("/api/jobs/j1/domain", json={"domain": "fintech"})
        resp = authed_client.get("/api/jobs/j1")
        assert resp.json()["domain_override"] == "fintech"

    def test_cleared_override_is_none_in_detail(self, authed_client):
        authed_client.patch("/api/jobs/j1/domain", json={"domain": "fintech"})
        authed_client.patch("/api/jobs/j1/domain", json={"domain": None})
        resp = authed_client.get("/api/jobs/j1")
        assert resp.json().get("domain_override") is None


# ── C. heuristic_score() with domain_override ─────────────────────────────


class TestHeuristicScoreWithOverride:
    """Unit tests for heuristic_score() domain_override parameter."""

    @pytest.fixture
    def profile(self):
        return {
            "domains": {"gaming": 15, "data": 5},
            "seniority": {"senior": 15, "mid": 10},
            "skills": [],
            "home_locations": [],
            "home_regions": [],
            "languages": [],
            "location_preference": "b",
            "country_weights": {},
            "company_type_weights": {},
        }

    @pytest.fixture
    def parsed_data(self):
        return {"domain": "other", "seniority": "senior"}

    @pytest.fixture
    def job_row(self):
        return {"location": "Paris", "title": "PM"}

    def test_override_uses_override_domain(self, profile, parsed_data, job_row):
        """When domain_override='gaming', score uses gaming weight (15) not 'other' (0)."""
        from api.scoring import heuristic_score

        score_with_override = heuristic_score(profile, parsed_data, job_row, False, domain_override="gaming")
        score_without = heuristic_score(profile, parsed_data, job_row, False)
        # Gaming gives 15 domain pts, other gives 0
        assert score_with_override > score_without

    def test_override_none_uses_cascade(self, profile, parsed_data, job_row):
        """domain_override=None falls back to normal cascade."""
        from api.scoring import heuristic_score

        score_none_override = heuristic_score(profile, parsed_data, job_row, False, domain_override=None)
        score_default = heuristic_score(profile, parsed_data, job_row, False)
        assert score_none_override == score_default

    def test_override_skips_inferred_domain(self, profile, job_row):
        """Override ignores keyword-inferred domain."""
        from api.scoring import heuristic_score

        # Parsed has keywords that would infer 'data', but override says 'gaming'
        parsed_with_data_keywords = {
            "domain": "other",
            "seniority": "senior",
            "must_have_skills": ["data platform", "data pipeline"],
        }
        score_override = heuristic_score(profile, parsed_with_data_keywords, job_row, False, domain_override="gaming")
        score_inferred = heuristic_score(profile, parsed_with_data_keywords, job_row, False)
        # Override forces gaming (15); inference would find 'data' (5)
        assert score_override > score_inferred

    def test_override_backward_compatible(self, profile, parsed_data, job_row):
        """Calling heuristic_score() without domain_override still works."""
        from api.scoring import heuristic_score

        # Must not raise
        score = heuristic_score(profile, parsed_data, job_row, False)
        assert isinstance(score, int)
        assert 0 <= score <= 100


# ── D. _score_and_tier_jobs() batch loading ──────────────────────────────


class TestScoreAndTierJobsBatchLoad:
    """Integration tests: domain overrides are loaded and applied in batch scoring."""

    def test_domain_override_affects_job_list_score(self, tmp_path, monkeypatch):
        """A domain override for a job changes its score in GET /api/jobs."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        # Job whose parser domain is 'other'
        job_other = {
            "job_id": "x1",
            "title": "PM Role",
            "company": "OtherCo",
            "location": "Remote",
            "url": "https://ex.com/x1",
            "location_type": "remote",
            "domain": "other",
            "parsed": json.dumps({"domain": "other", "seniority": "senior"}),
            "first_seen": "2026-02-23",
            "last_seen": "2026-02-23",
            "ingested_at": "2026-02-23T10:00:00",
        }
        upsert_job(db_path, job_other)
        monkeypatch.setenv("DB_PATH", db_path)

        user = upsert_user(
            db_path,
            {
                "google_id": "g_batch",
                "email": "batch@t.com",
                "name": "B",
                "avatar_url": None,
                "profile_id": "batch_profile",
            },
        )
        create_session(db_path, "batch_tok", user["id"], "2099-01-01T00:00:00")

        mock_profile = {
            "domains": {"gaming": 15, "other": 0},
            "seniority": {"senior": 15},
            "skills": [],
            "home_locations": [],
            "home_regions": [],
            "languages": [],
            "location_preference": "b",
            "country_weights": {},
            "company_type_weights": {},
        }

        c = TestClient(app)
        c.cookies.set("jsk", "batch_tok")

        with patch("api.routes.jobs.load_profile_data", return_value=mock_profile):
            resp_before = c.get("/api/jobs")
        score_before = next(j["score"] for j in resp_before.json()["jobs"] if j["job_id"] == "x1")

        # Set domain override to gaming
        with patch("api.routes.jobs.load_profile_data", return_value=mock_profile):
            c.patch("/api/jobs/x1/domain", json={"domain": "gaming"})
            resp_after = c.get("/api/jobs")
        score_after = next(j["score"] for j in resp_after.json()["jobs"] if j["job_id"] == "x1")

        # After override to gaming (weight 15), score should be higher than 'other' (weight 0)
        assert score_after > score_before
