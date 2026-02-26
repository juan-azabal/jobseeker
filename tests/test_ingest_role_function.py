"""Tests for 17.1.3 — ingest persists role_function from parsed data."""

import json

import pytest

from api.db.init import init_db
from api.db.queries import get_job_by_id
from api.ingest import ingest_from_list


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _make_job(job_id, role_function):
    return {
        "id": job_id,
        "title": "Product Manager",
        "company": "Acme",
        "location": "Remote",
        "job_url": "https://example.com/job/1",
        "is_remote": True,
        "date_posted": "2026-01-15",
        "parsed": {
            "domain": "saas",
            "role_function": role_function,
            "seniority": "senior",
            "location_type": "remote",
        },
    }


class TestIngestRoleFunction:
    def test_ingest_stores_role_function_product(self, db_path):
        """Ingest must persist role_function=product to jobs.role_function."""
        job = _make_job("rf-ingest-001", "product")
        ingest_from_list(db_path, [job])
        row = get_job_by_id(db_path, "rf-ingest-001")
        assert row is not None
        assert row["role_function"] == "product"

    def test_ingest_stores_role_function_engineering(self, db_path):
        """Ingest must persist role_function=engineering."""
        job = _make_job("rf-ingest-002", "engineering")
        ingest_from_list(db_path, [job])
        row = get_job_by_id(db_path, "rf-ingest-002")
        assert row["role_function"] == "engineering"

    def test_ingest_handles_missing_role_function(self, db_path):
        """Ingest must not crash when parsed data has no role_function."""
        job = {
            "id": "rf-ingest-003",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "job_url": "https://example.com/job/3",
            "is_remote": True,
            "date_posted": "2026-01-15",
            "parsed": {"domain": "saas", "seniority": "senior", "location_type": "remote"},
        }
        ingest_from_list(db_path, [job])
        row = get_job_by_id(db_path, "rf-ingest-003")
        assert row is not None
        # role_function should be None/NULL — not raise
        assert row.get("role_function") is None

    def test_ingest_upsert_updates_role_function(self, db_path):
        """Upsert of existing job must update role_function when re-ingested."""
        job = _make_job("rf-ingest-004", "product")
        ingest_from_list(db_path, [job])

        # Re-ingest with a different role_function (e.g., parser v1.4 re-run)
        updated = _make_job("rf-ingest-004", "marketing")
        ingest_from_list(db_path, [updated])

        row = get_job_by_id(db_path, "rf-ingest-004")
        assert row["role_function"] == "marketing"
