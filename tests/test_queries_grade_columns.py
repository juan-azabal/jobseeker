"""Tests for 17.3.3 — queries return technical_grade, profile_grade, scored_v2."""

import json
import sqlite3

import pytest

from api.db.init import init_db
from api.db.queries import get_jobs, get_user_job_score, upsert_user_job_score


def _make_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    # Insert one test user
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO users (google_id, email, profile_id) VALUES (?, ?, ?)",
        ("gid-test", "test@test.com", "testuser"),
    )
    con.commit()
    uid = con.execute("SELECT id FROM users WHERE email = 'test@test.com'").fetchone()[0]
    con.close()
    return path, uid


def _insert_job(db_path, job_id="job-g-001"):
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT INTO jobs (job_id, title, company, location, url, location_type, domain,
                          first_seen, last_seen, ingested_at)
        VALUES (?, 'PM', 'Acme', 'Remote', 'https://x.com', 'remote', 'saas',
                '2026-01-01', '2026-01-01', '2026-01-01T00:00:00')
    """, (job_id,))
    con.commit()
    con.close()


class TestGetUserJobScoreReturnsGrades:
    """get_user_job_score returns grade columns after migration 018."""

    def test_returns_technical_grade(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "qg-001")
        upsert_user_job_score(
            db, uid, "qg-001", score=0, tier="C", scored_json=None,
            technical_grade="A", profile_grade="B", scored_v2=1,
        )
        row = get_user_job_score(db, uid, "qg-001")
        assert row is not None
        assert row["technical_grade"] == "A"

    def test_returns_profile_grade(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "qg-002")
        upsert_user_job_score(
            db, uid, "qg-002", score=0, tier="C", scored_json=None,
            technical_grade="B", profile_grade="C", scored_v2=1,
        )
        row = get_user_job_score(db, uid, "qg-002")
        assert row["profile_grade"] == "C"

    def test_returns_scored_v2(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "qg-003")
        upsert_user_job_score(
            db, uid, "qg-003", score=0, tier="C", scored_json=None,
            technical_grade="A", profile_grade="A", scored_v2=1,
        )
        row = get_user_job_score(db, uid, "qg-003")
        assert row["scored_v2"] == 1

    def test_grades_null_for_v1(self, tmp_path):
        """v1 rows (no grades) return None for grade columns."""
        db, uid = _make_db(tmp_path)
        _insert_job(db, "qg-004")
        upsert_user_job_score(db, uid, "qg-004", score=75, tier="A", scored_json=None)
        row = get_user_job_score(db, uid, "qg-004")
        assert row["technical_grade"] is None
        assert row["profile_grade"] is None
        assert row["scored_v2"] == 0


class TestGetJobsReturnsGrades:
    """get_jobs list query returns grade columns in each row."""

    def test_job_list_includes_technical_grade(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "jlg-001")
        upsert_user_job_score(
            db, uid, "jlg-001", score=0, tier="C", scored_json=None,
            technical_grade="A", profile_grade="B", scored_v2=1,
        )
        jobs = get_jobs(db, user_id=uid)
        assert len(jobs) == 1
        assert jobs[0]["ujs_technical_grade"] == "A"

    def test_job_list_includes_profile_grade(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "jlg-002")
        upsert_user_job_score(
            db, uid, "jlg-002", score=0, tier="C", scored_json=None,
            technical_grade="B", profile_grade="C", scored_v2=1,
        )
        jobs = get_jobs(db, user_id=uid)
        assert jobs[0]["ujs_profile_grade"] == "C"

    def test_job_list_includes_scored_v2(self, tmp_path):
        db, uid = _make_db(tmp_path)
        _insert_job(db, "jlg-003")
        upsert_user_job_score(
            db, uid, "jlg-003", score=0, tier="C", scored_json=None,
            technical_grade="A", profile_grade="A", scored_v2=1,
        )
        jobs = get_jobs(db, user_id=uid)
        assert jobs[0]["ujs_scored_v2"] == 1

    def test_job_list_grade_null_when_no_score(self, tmp_path):
        """Jobs with no score row → grade columns are None."""
        db, uid = _make_db(tmp_path)
        _insert_job(db, "jlg-004")
        jobs = get_jobs(db, user_id=uid)
        assert len(jobs) == 1
        assert jobs[0]["ujs_technical_grade"] is None
        assert jobs[0]["ujs_profile_grade"] is None
        assert jobs[0].get("ujs_scored_v2") in (None, 0)
