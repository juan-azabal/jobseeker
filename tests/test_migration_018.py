"""Tests for migration 018 — technical_grade + profile_grade columns on user_job_scores."""

import sqlite3
from pathlib import Path

from api.db.init import init_db

MIGRATIONS_DIR = Path(__file__).parent.parent / "api" / "db" / "migrations"


def _db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestMigration018GradeColumns:
    def test_user_job_scores_has_technical_grade(self, tmp_path):
        """Migration 018 must add technical_grade column to user_job_scores."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(user_job_scores)").fetchall()]
        con.close()
        assert "technical_grade" in cols

    def test_user_job_scores_has_profile_grade(self, tmp_path):
        """Migration 018 must add profile_grade column to user_job_scores."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(user_job_scores)").fetchall()]
        con.close()
        assert "profile_grade" in cols

    def test_user_job_scores_has_scored_v2(self, tmp_path):
        """Migration 018 must add scored_v2 column (0/1 flag) to user_job_scores."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        cols = [row[1] for row in con.execute("PRAGMA table_info(user_job_scores)").fetchall()]
        con.close()
        assert "scored_v2" in cols

    def test_scored_v2_defaults_to_zero(self, tmp_path):
        """New rows in user_job_scores get scored_v2 = 0 by default."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        # Insert a row without scored_v2
        con.execute("""
            INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, scored_at)
            VALUES (1, 'uj-test-1', 75, 'A', 1, datetime('now'))
        """)
        con.commit()
        row = con.execute(
            "SELECT scored_v2 FROM user_job_scores WHERE job_id = 'uj-test-1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] == 0

    def test_grade_columns_accept_abc_values(self, tmp_path):
        """technical_grade and profile_grade columns can store A/B/C strings."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        con.execute("""
            INSERT INTO user_job_scores
              (user_id, job_id, score, tier, scored, scored_at, technical_grade, profile_grade, scored_v2)
            VALUES (1, 'uj-test-2', 80, 'A', 1, datetime('now'), 'A', 'B', 1)
        """)
        con.commit()
        row = con.execute(
            "SELECT technical_grade, profile_grade, scored_v2 FROM user_job_scores WHERE job_id = 'uj-test-2'"
        ).fetchone()
        con.close()
        assert row[0] == "A"
        assert row[1] == "B"
        assert row[2] == 1

    def test_grade_columns_accept_null(self, tmp_path):
        """Grade columns default to NULL when not provided."""
        db = _db(tmp_path)
        con = sqlite3.connect(db)
        con.execute("""
            INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, scored_at)
            VALUES (1, 'uj-test-3', 60, 'B', 1, datetime('now'))
        """)
        con.commit()
        row = con.execute(
            "SELECT technical_grade, profile_grade FROM user_job_scores WHERE job_id = 'uj-test-3'"
        ).fetchone()
        con.close()
        assert row[0] is None
        assert row[1] is None

    def test_migration_file_exists(self):
        """Migration file 018_scoring_grades.sql must exist."""
        path = MIGRATIONS_DIR / "018_scoring_grades.sql"
        assert path.exists(), f"Migration file not found: {path}"
