import os
import tempfile
import pytest
from api.db.init import init_db
from api.db.queries import (
    upsert_job,
    get_jobs,
    get_job_by_id,
    upsert_user_job_score,
    get_user_job_score,
    get_total_job_count,
)

JOB = {
    "job_id": "abc123",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Paris, FR",
    "url": "https://example.com/job/1",
    "location_type": "hybrid",
    "domain": "data",
    "parsed": '{"domain": "data"}',
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


def test_user_job_scores(db_path):
    """Per-user scores are stored separately from shared job data."""
    upsert_job(db_path, JOB)
    # Create a test user
    import sqlite3

    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO users (id, google_id, email, name) VALUES (1, 'g1', 'a@b.com', 'Test')")
    con.commit()
    con.close()
    # Upsert a score
    upsert_user_job_score(db_path, 1, "abc123", 72, "A", '{"score": 72}')
    ujs = get_user_job_score(db_path, 1, "abc123")
    assert ujs is not None
    assert ujs["score"] == 72
    assert ujs["tier"] == "A"
    # Jobs query with user_id returns the score
    jobs = get_jobs(db_path, user_id=1)
    assert len(jobs) == 1
    assert jobs[0]["ujs_score"] == 72


def test_get_total_job_count(db_path):
    assert get_total_job_count(db_path) == 0
    upsert_job(db_path, JOB)
    assert get_total_job_count(db_path) == 1


def test_get_jobs_filter_date(db_path):
    upsert_job(db_path, JOB)
    upsert_job(db_path, {**JOB, "job_id": "old", "first_seen": "2026-01-01"})
    jobs = get_jobs(db_path, date_from="2026-02-01")
    assert all(j["first_seen"] >= "2026-02-01" for j in jobs)


def test_get_job_by_id_not_found(db_path):
    result = get_job_by_id(db_path, "nonexistent")
    assert result is None
