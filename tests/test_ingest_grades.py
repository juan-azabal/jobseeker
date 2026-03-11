"""Tests for 17.3.2 — ingest stores LLM grades from v2 rag_score."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from api.db.init import init_db
from api.ingest import ingest_from_list


def _make_db(tmp_path, with_user: bool = False):
    path = str(tmp_path / "test.db")
    init_db(path)
    if with_user:
        con = sqlite3.connect(path)
        con.execute(
            "INSERT INTO users (google_id, email, profile_id) VALUES (?, ?, ?)",
            ("gid-test-juan", "juan@test.com", "juan"),
        )
        con.commit()
        con.close()
    return path


def _get_uid(db_path: str, profile_id: str = "juan") -> int:
    con = sqlite3.connect(db_path)
    row = con.execute("SELECT id FROM users WHERE profile_id=?", (profile_id,)).fetchone()
    con.close()
    return row[0]


def _base_job(job_id="test-g-001"):
    return {
        "id": job_id,
        "title": "Senior PM",
        "company": "Acme",
        "location": "Remote",
        "url": "https://x.com",
        "location_type": "remote",
        "source": "test",
        "description": "A job description",
        "first_seen": "2026-01-01",
        "last_seen": "2026-01-01",
    }


class TestIngestV2GradeStorage:
    """v2 rag_score (has technical_depth + profile_evidence, no top-level score)
    → grades stored, scored_v2=1."""

    def test_v2_rag_stores_technical_grade(self, tmp_path):
        db = _make_db(tmp_path, with_user=True)
        job = _base_job("v2-001")
        job["rag_score"] = {
            "technical_depth": "A",
            "profile_evidence": "B",
            "strengths": [],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": [],
            "one_line_verdict": "Good fit.",
        }
        ingest_from_list(db, [job], user_id=_get_uid(db))
        con = sqlite3.connect(db)
        row = con.execute("SELECT technical_grade FROM user_job_scores WHERE job_id LIKE 'v2-001%'").fetchone()
        con.close()
        assert row is not None
        assert row[0] == "A"

    def test_v2_rag_stores_profile_grade(self, tmp_path):
        db = _make_db(tmp_path, with_user=True)
        job = _base_job("v2-002")
        job["rag_score"] = {
            "technical_depth": "B",
            "profile_evidence": "C",
            "strengths": [],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": [],
            "one_line_verdict": "Weak fit.",
        }
        ingest_from_list(db, [job], user_id=_get_uid(db))
        con = sqlite3.connect(db)
        row = con.execute("SELECT profile_grade FROM user_job_scores WHERE job_id LIKE 'v2-002%'").fetchone()
        con.close()
        assert row is not None
        assert row[0] == "C"

    def test_v2_rag_sets_scored_v2_flag(self, tmp_path):
        db = _make_db(tmp_path, with_user=True)
        job = _base_job("v2-003")
        job["rag_score"] = {
            "technical_depth": "A",
            "profile_evidence": "A",
            "strengths": [],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": [],
            "one_line_verdict": "Strong fit.",
        }
        ingest_from_list(db, [job], user_id=_get_uid(db))
        con = sqlite3.connect(db)
        row = con.execute("SELECT scored_v2 FROM user_job_scores WHERE job_id LIKE 'v2-003%'").fetchone()
        con.close()
        assert row is not None
        assert row[0] == 1


class TestIngestV1BackwardCompat:
    """v1 rag_score (has top-level score, no grades) → unchanged path, scored_v2=0."""

    def test_v1_rag_score_stored(self, tmp_path):
        db = _make_db(tmp_path, with_user=True)
        job = _base_job("v1-001")
        job["rag_score"] = {
            "score": 75,
            "score_breakdown": {"domain_fit": 20},
            "strengths": [],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": [],
            "one_line_verdict": "Good.",
        }
        ingest_from_list(db, [job], user_id=_get_uid(db))
        con = sqlite3.connect(db)
        row = con.execute(
            "SELECT score, scored_v2, technical_grade FROM user_job_scores WHERE job_id LIKE 'v1-001%'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] == 75
        assert row[1] == 0  # scored_v2 unchanged
        assert row[2] is None  # no grades

    def test_no_rag_score_no_user_row(self, tmp_path):
        """Jobs without rag_score → no row in user_job_scores."""
        db = _make_db(tmp_path, with_user=True)
        job = _base_job("norag-001")
        ingest_from_list(db, [job], user_id=_get_uid(db))
        con = sqlite3.connect(db)
        row = con.execute("SELECT 1 FROM user_job_scores WHERE job_id LIKE 'norag-001%'").fetchone()
        con.close()
        assert row is None
