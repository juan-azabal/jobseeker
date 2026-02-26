"""Tests for Phase 4.1–4.2 — migration 019 + ingest persists enriched scraper fields."""

import json
import sqlite3

import pytest

from api.db.init import init_db
from api.db.queries import get_job_by_id
from api.ingest import ingest_from_list


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _make_enriched_job(job_id="enr-001", **overrides):
    base = {
        "id": job_id,
        "title": "Product Manager",
        "company": "Acme",
        "location": "Barcelona, Spain",
        "job_url": "https://example.com/job/1",
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
    base.update(overrides)
    return base


class TestMigration019:
    def test_new_columns_exist(self, db_path):
        """Migration 019 must add all enriched columns to the jobs table."""
        con = sqlite3.connect(db_path)
        info = {row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()}
        con.close()
        required = {
            "company_url",
            "company_logo",
            "company_industry",
            "company_size",
            "job_level",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_interval",
            "salary_source",
            "country",
            "city",
            "remote_type",
            "sources",
        }
        for col in required:
            assert col in info, f"Column {col!r} missing from jobs table"


class TestIngestEnrichedFields:
    def test_ingest_stores_company_industry(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["company_industry"] == "Financial Services"

    def test_ingest_stores_company_size(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["company_size"] == "201-500"

    def test_ingest_stores_job_level(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["job_level"] == "Mid-Senior Level"

    def test_ingest_stores_salary_fields(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["salary_min"] == 80000.0
        assert row["salary_max"] == 100000.0
        assert row["salary_currency"] == "EUR"
        assert row["salary_interval"] == "yearly"
        assert row["salary_source"] == "direct_data"

    def test_ingest_stores_location_fields(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["country"] == "ES"
        assert row["city"] == "Barcelona"
        assert row["remote_type"] == "no"

    def test_ingest_stores_sources_as_json(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        sources = json.loads(row["sources"])
        assert "linkedin" in sources
        assert "indeed" in sources

    def test_ingest_stores_company_url_and_logo(self, db_path):
        ingest_from_list(db_path, [_make_enriched_job()])
        row = get_job_by_id(db_path, "enr-001")
        assert row["company_url"] == "https://acme.com"
        assert row["company_logo"] == "https://acme.com/logo.png"

    def test_ingest_handles_missing_enriched_fields(self, db_path):
        """Job with no enriched fields must not crash — all nulls."""
        job = {
            "id": "enr-002",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "job_url": "https://example.com/job/2",
            "is_remote": True,
            "date_posted": "2026-01-15",
            "parsed": {"domain": "saas"},
        }
        ingest_from_list(db_path, [job])
        row = get_job_by_id(db_path, "enr-002")
        assert row is not None
        assert row.get("company_industry") is None
        assert row.get("salary_min") is None
        assert row.get("job_level") is None

    def test_upsert_coalesce_preserves_richer_data(self, db_path):
        """Re-ingesting with null company_industry must NOT overwrite existing value."""
        ingest_from_list(db_path, [_make_enriched_job("enr-003")])

        # Re-ingest from a source that lacks company_industry
        poor_job = {
            "id": "enr-003",
            "title": "Product Manager",
            "company": "Acme",
            "location": "Barcelona, Spain",
            "job_url": "https://example.com/job/3",
            "is_remote": False,
            "date_posted": "2026-01-20",
            "parsed": {"domain": "fintech"},
        }
        ingest_from_list(db_path, [poor_job])
        row = get_job_by_id(db_path, "enr-003")
        assert row["company_industry"] == "Financial Services"
        assert row["salary_min"] == 80000.0

    def test_upsert_coalesce_allows_update_when_previously_null(self, db_path):
        """If company_industry was null, re-ingest with a value must store it."""
        poor_job = {
            "id": "enr-004",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "job_url": "https://example.com/job/4",
            "is_remote": True,
            "date_posted": "2026-01-15",
            "parsed": {"domain": "saas"},
        }
        ingest_from_list(db_path, [poor_job])

        rich_job = _make_enriched_job("enr-004")
        rich_job["date_posted"] = "2026-01-20"
        ingest_from_list(db_path, [rich_job])

        row = get_job_by_id(db_path, "enr-004")
        assert row["company_industry"] == "Financial Services"
