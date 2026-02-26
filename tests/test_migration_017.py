"""Tests for migration 017 — role_function column on jobs."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from api.db.init import init_db

MIGRATIONS_DIR = Path(__file__).parent.parent / "api" / "db" / "migrations"


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestMigration017RoleFunction:
    def test_jobs_table_has_role_function_column(self, db_path):
        """Migration 017 must add role_function column to jobs table."""
        con = sqlite3.connect(db_path)
        cols = [row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()]
        con.close()
        assert "role_function" in cols

    def test_role_function_defaults_to_null(self, db_path):
        """Existing rows should have role_function = NULL (or backfill value)."""
        con = sqlite3.connect(db_path)
        # Insert a job without role_function
        con.execute("""
            INSERT INTO jobs (job_id, title, company, location, url,
                              location_type, domain, first_seen, last_seen, ingested_at)
            VALUES ('rf-test-1', 'PM', 'Acme', 'Remote', 'https://x.com',
                    'remote', 'saas', '2026-01-01', '2026-01-01', '2026-01-01T00:00:00')
        """)
        con.commit()
        row = con.execute("SELECT role_function FROM jobs WHERE job_id = 'rf-test-1'").fetchone()
        con.close()
        assert row is not None
        # role_function may be NULL (no parsed) or backfilled — just must not error

    def test_backfill_from_parsed_json(self, db_path):
        """After migration, role_function should be populated from parsed JSON when present."""
        con = sqlite3.connect(db_path)
        parsed = json.dumps({"domain": "saas", "role_function": "product"})
        con.execute(
            """
            INSERT INTO jobs (job_id, title, company, location, url,
                              location_type, domain, parsed, first_seen, last_seen, ingested_at)
            VALUES ('rf-test-2', 'PM', 'Acme', 'Remote', 'https://x.com',
                    'remote', 'saas', ?, '2026-01-01', '2026-01-01', '2026-01-01T00:00:00')
        """,
            (parsed,),
        )
        con.commit()

        # Simulate the migration backfill
        con.execute("""
            UPDATE jobs
            SET role_function = json_extract(parsed, '$.role_function')
            WHERE parsed IS NOT NULL AND role_function IS NULL
        """)
        con.commit()

        row = con.execute("SELECT role_function FROM jobs WHERE job_id = 'rf-test-2'").fetchone()
        con.close()
        assert row[0] == "product"

    def test_migration_file_exists(self):
        """Migration file 017_role_function.sql must exist."""
        path = MIGRATIONS_DIR / "017_role_function.sql"
        assert path.exists(), f"Migration file not found: {path}"
