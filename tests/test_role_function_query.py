"""Tests for 17.5.2 — role_function propagated through get_jobs() query."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from api.db.init import init_db as run_migrations
from api.db.queries import get_jobs


@pytest.fixture()
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    run_migrations(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    # Insert user
    con.execute(
        "INSERT INTO users (google_id, email, profile_id) VALUES (?, ?, ?)",
        ("gid-test", "test@example.com", "test"),
    )
    con.commit()
    row = con.execute("SELECT id FROM users WHERE google_id = 'gid-test'").fetchone()
    uid = row["id"]
    con.close()
    yield db_path, uid


def _insert_job(db_path: str, job_id: str, role_function: str | None):
    parsed = {"domain": "saas", "seniority": "senior", "role_function": role_function} if role_function else {"domain": "saas", "seniority": "senior"}
    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO jobs (job_id, title, company, location, location_type,
           parsed, role_function, first_seen, last_seen, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'))""",
        (job_id, "PM Role", "Acme", "Remote", "remote", json.dumps(parsed), role_function),
    )
    con.commit()
    con.close()


class TestRoleFunctionQuery:
    def test_role_function_returned_in_job_list(self, db):
        """get_jobs() returns role_function from jobs table."""
        db_path, uid = db
        _insert_job(db_path, "job-001", "product")
        jobs = get_jobs(db_path, user_id=uid)
        assert len(jobs) == 1
        assert jobs[0]["role_function"] == "product"

    def test_role_function_null_when_absent(self, db):
        """get_jobs() returns role_function=None when not set."""
        db_path, uid = db
        _insert_job(db_path, "job-002", None)
        jobs = get_jobs(db_path, user_id=uid)
        assert len(jobs) == 1
        assert jobs[0]["role_function"] is None

    def test_multiple_role_functions(self, db):
        """Each job has its own role_function (distinct titles to avoid dedup)."""
        db_path, uid = db
        parsed_pm = {"domain": "saas", "seniority": "senior", "role_function": "product"}
        parsed_eng = {"domain": "saas", "seniority": "senior", "role_function": "engineering"}
        con = sqlite3.connect(db_path)
        con.execute(
            """INSERT INTO jobs (job_id, title, company, location, location_type,
               parsed, role_function, first_seen, last_seen, ingested_at)
               VALUES (?, 'PM Role', 'Acme', 'Remote', 'remote', ?, ?, datetime('now'), datetime('now'), datetime('now'))""",
            ("job-003", json.dumps(parsed_pm), "product"),
        )
        con.execute(
            """INSERT INTO jobs (job_id, title, company, location, location_type,
               parsed, role_function, first_seen, last_seen, ingested_at)
               VALUES (?, 'Eng Role', 'Acme', 'Remote', 'remote', ?, ?, datetime('now'), datetime('now'), datetime('now'))""",
            ("job-004", json.dumps(parsed_eng), "engineering"),
        )
        con.commit()
        con.close()
        jobs = get_jobs(db_path, user_id=uid)
        rfs = {j["job_id"]: j["role_function"] for j in jobs}
        assert rfs["job-003"] == "product"
        assert rfs["job-004"] == "engineering"
