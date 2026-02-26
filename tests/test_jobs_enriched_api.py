"""Tests for Phase 4.3 — enriched fields exposed in list and detail job API."""

import json

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.ingest import ingest_from_list
from api.main import app


def _make_enriched_job(job_id="enr-api-001"):
    return {
        "id": job_id,
        "title": "Product Manager",
        "company": "Acme",
        "location": "Barcelona, Spain",
        "job_url": f"https://example.com/job/{job_id}",
        "is_remote": False,
        "date_posted": "2026-01-15",
        "company_url": "https://acme.com",
        "company_logo": "https://acme.com/logo.png",
        "company_industry": "Financial Services",
        "company_employees_label": "201-500",
        "job_level": "Mid-Senior Level",
        "min_amount": 80000.0,
        "max_amount": 100000.0,
        "currency": "EUR",
        "interval": "yearly",
        "salary_source": "direct_data",
        "country": "ES",
        "city": "Barcelona",
        "remote_type": "no",
        "sources": ["linkedin", "indeed"],
        "parsed": {"domain": "fintech", "seniority": "senior", "location_type": "onsite"},
    }


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    ingest_from_list(db_path, [_make_enriched_job()])
    # Add a job without enriched fields too
    ingest_from_list(db_path, [{
        "id": "plain-001",
        "title": "Senior PM",
        "company": "Beta",
        "location": "Remote",
        "job_url": "https://example.com/job/plain-001",
        "is_remote": True,
        "date_posted": "2026-01-15",
        "parsed": {"domain": "saas"},
    }])
    user = upsert_user(db_path, {
        "google_id": "g_test", "email": "t@t.com",
        "name": "T", "avatar_url": None, "profile_id": None,
    })
    create_session(db_path, "test_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "test_tok")
    return c


class TestListEnrichedFields:
    def test_company_industry_in_list(self, authed_client):
        resp = authed_client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        job = jobs["enr-api-001"]
        assert job["company_industry"] == "Financial Services"

    def test_job_level_in_list(self, authed_client):
        resp = authed_client.get("/api/jobs")
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        assert jobs["enr-api-001"]["job_level"] == "Mid-Senior Level"

    def test_salary_fields_in_list(self, authed_client):
        resp = authed_client.get("/api/jobs")
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        job = jobs["enr-api-001"]
        assert job["salary_min"] == 80000.0
        assert job["salary_max"] == 100000.0
        assert job["salary_currency"] == "EUR"
        assert job["salary_interval"] == "yearly"

    def test_location_fields_in_list(self, authed_client):
        resp = authed_client.get("/api/jobs")
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        job = jobs["enr-api-001"]
        assert job["city"] == "Barcelona"
        assert job["country"] == "ES"
        assert job["remote_type"] == "no"

    def test_sources_parsed_as_list(self, authed_client):
        resp = authed_client.get("/api/jobs")
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        sources = jobs["enr-api-001"]["sources"]
        assert isinstance(sources, list)
        assert "linkedin" in sources

    def test_null_enriched_fields_absent_from_list(self, authed_client):
        """Jobs without enriched fields must not expose null keys for those fields."""
        resp = authed_client.get("/api/jobs")
        jobs = {j["job_id"]: j for j in resp.json()["jobs"]}
        plain = jobs["plain-001"]
        # Null enriched fields must be absent, not None
        assert "company_industry" not in plain
        assert "salary_min" not in plain
        assert "job_level" not in plain


class TestDetailEnrichedFields:
    def test_company_industry_in_detail(self, authed_client):
        resp = authed_client.get("/api/jobs/enr-api-001")
        assert resp.status_code == 200
        job = resp.json()
        assert job["company_industry"] == "Financial Services"

    def test_company_url_in_detail(self, authed_client):
        resp = authed_client.get("/api/jobs/enr-api-001")
        assert resp.json()["company_url"] == "https://acme.com"

    def test_sources_parsed_in_detail(self, authed_client):
        resp = authed_client.get("/api/jobs/enr-api-001")
        sources = resp.json()["sources"]
        assert isinstance(sources, list)
        assert "linkedin" in sources

    def test_null_enriched_fields_absent_from_detail(self, authed_client):
        resp = authed_client.get("/api/jobs/plain-001")
        assert resp.status_code == 200
        job = resp.json()
        assert "company_industry" not in job
        assert "salary_min" not in job
