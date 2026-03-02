"""Tests for migration 020 — role_in_plain_english, company_stage, company_tone
columns on jobs table."""

import sqlite3
from pathlib import Path

from api.db.init import init_db

MIGRATIONS_DIR = Path(__file__).parent.parent / "api" / "db" / "migrations"


def _db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestMigration020ParserV15Columns:
    def test_jobs_has_role_in_plain_english(self, tmp_path):
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()]
        con.close()
        assert "role_in_plain_english" in cols

    def test_jobs_has_company_stage(self, tmp_path):
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()]
        con.close()
        assert "company_stage" in cols

    def test_jobs_has_company_tone(self, tmp_path):
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()]
        con.close()
        assert "company_tone" in cols

    def test_new_columns_default_to_null(self, tmp_path):
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        con.execute(
            "INSERT INTO jobs (job_id, title, company, location, first_seen) VALUES (?, ?, ?, ?, datetime('now'))",
            ("jtest-020", "PM", "Acme", "Remote"),
        )
        con.commit()
        row = con.execute(
            "SELECT role_in_plain_english, company_stage, company_tone FROM jobs WHERE job_id = 'jtest-020'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None

    def test_new_columns_accept_text_values(self, tmp_path):
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        con.execute(
            """INSERT INTO jobs (job_id, title, company, location, first_seen,
               role_in_plain_english, company_stage, company_tone)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)""",
            ("jtest-020b", "DE", "Acme", "Remote", "Own the data platform.", "growth", "technical_serious"),
        )
        con.commit()
        row = con.execute(
            "SELECT role_in_plain_english, company_stage, company_tone FROM jobs WHERE job_id = 'jtest-020b'"
        ).fetchone()
        con.close()
        assert row[0] == "Own the data platform."
        assert row[1] == "growth"
        assert row[2] == "technical_serious"

    def test_migration_file_exists(self):
        path = MIGRATIONS_DIR / "020_parser_v15_columns.sql"
        assert path.exists(), f"Migration file not found: {path}"
