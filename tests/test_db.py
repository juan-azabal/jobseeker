import os
import tempfile
import pytest
from api.db.init import init_db
from api.db.queries import upsert_job, get_jobs, get_job_by_id

JOB = {
    "job_id": "abc123",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Paris, FR",
    "url": "https://example.com/job/1",
    "location_type": "hybrid",
    "domain": "data",
    "score": 72,
    "tier": "A",
    "parsed": '{"domain": "data"}',
    "scored": '{"score": 72}',
    "first_seen": "2026-02-20",
    "last_seen": "2026-02-20",
    "ingested_at": "2026-02-20T10:00:00",
}


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_init_creates_table(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    import sqlite3
    con = sqlite3.connect(path)
    tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert ("jobs",) in tables


def test_upsert_inserts_job(db_path):
    upsert_job(db_path, JOB)
    row = get_job_by_id(db_path, "abc123")
    assert row is not None
    assert row["title"] == "Senior PM"


def test_upsert_updates_last_seen(db_path):
    upsert_job(db_path, JOB)
    updated = {**JOB, "last_seen": "2026-02-23"}
    upsert_job(db_path, updated)
    row = get_job_by_id(db_path, "abc123")
    assert row["last_seen"] == "2026-02-23"


def test_upsert_no_duplicate(db_path):
    upsert_job(db_path, JOB)
    upsert_job(db_path, JOB)
    jobs = get_jobs(db_path)
    assert len(jobs) == 1


def test_get_jobs_returns_list(db_path):
    upsert_job(db_path, JOB)
    jobs = get_jobs(db_path)
    assert isinstance(jobs, list)
    assert len(jobs) == 1


def test_get_jobs_filter_tier(db_path):
    upsert_job(db_path, JOB)
    upsert_job(db_path, {**JOB, "job_id": "xyz", "tier": "C", "score": 20})
    a_jobs = get_jobs(db_path, tiers=["A"])
    assert all(j["tier"] == "A" for j in a_jobs)


def test_get_jobs_filter_date(db_path):
    upsert_job(db_path, JOB)
    upsert_job(db_path, {**JOB, "job_id": "old", "first_seen": "2026-01-01"})
    jobs = get_jobs(db_path, date_from="2026-02-01")
    assert all(j["first_seen"] >= "2026-02-01" for j in jobs)


def test_get_job_by_id_not_found(db_path):
    result = get_job_by_id(db_path, "nonexistent")
    assert result is None
