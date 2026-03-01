"""Phase 19.0.1 — v1 RAG scoring path elimination tests.

Verifies that:
- Jobs with ujs_score (v1) are re-scored via heuristic, NOT via stored score
- Jobs with scored_v2=1 still use hybrid_score with grades (v2 unchanged)
- Jobs with no ujs still use _score_single_job (unscored unchanged)
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db() -> str:
    """Create a minimal in-memory-like SQLite DB with required tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            location_type TEXT,
            parsed TEXT,
            domain TEXT,
            role_function TEXT,
            scored_v2 INTEGER DEFAULT 0,
            -- enriched columns (may be absent in older DBs)
            company_url TEXT, company_logo TEXT, company_industry TEXT,
            company_size TEXT, job_level TEXT,
            salary_min REAL, salary_max REAL, salary_currency TEXT,
            salary_interval TEXT, salary_source TEXT,
            country TEXT, city TEXT, remote_type TEXT, sources TEXT
        );
        CREATE TABLE IF NOT EXISTS user_job_scores (
            user_id INTEGER,
            job_id TEXT,
            score REAL,
            tier TEXT,
            scored INTEGER DEFAULT 0,
            technical_grade TEXT,
            profile_grade TEXT,
            scored_v2 INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_job_status (
            user_id INTEGER,
            job_id TEXT,
            domain_override TEXT,
            applied_at TEXT,
            dismissed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS skill_embeddings (skill TEXT PRIMARY KEY, embedding BLOB);
    """)
    con.commit()
    con.close()
    return db_path


_PARSED_DATA = {
    "domain": "data",
    "seniority": "principal",
    "location_type": "remote",
    "must_have_skills": ["python", "sql"],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "locations_mentioned": ["netherlands"],
    "remote_restriction": "Netherlands only",
}


_PROFILE_DATA = {
    "domains": {"data": 15},
    "seniority": {"principal": 15, "senior": 10},
    "skills": ["python", "sql"],
    "home_locations": ["barcelona"],
    "home_regions": ["EU"],
    "languages": [],
    "location_preference": "b",
    "country_weights": {"netherlands": -10, "remote": 10},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}


def _insert_job(db_path: str, job_id: str, parsed: dict) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO jobs (job_id, title, company, location, location_type, parsed, domain, role_function)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            job_id,
            "Staff Data Engineer",
            "ClickHouse",
            "Netherlands",
            "remote",
            json.dumps(parsed),
            parsed.get("domain", "other"),
            None,
        ),
    )
    con.commit()
    con.close()


def _insert_ujs_v1(db_path: str, user_id: int, job_id: str, score: float) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, scored_v2) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, job_id, score, "A", 1, 0),
    )
    con.commit()
    con.close()


def _insert_ujs_v2(db_path: str, user_id: int, job_id: str, tech_grade: str, prof_grade: str) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, technical_grade, profile_grade, scored_v2)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, job_id, 0, "A", 1, tech_grade, prof_grade, 1),
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestV1Elimination:
    """v1 stored scores must not be returned directly — all jobs re-scored."""

    def test_v1_job_score_differs_from_stored_when_profile_changes(self):
        """Job with ujs_score=85, scored_v2=0 + modified profile → score ≠ 85."""
        db_path = _make_db()
        _insert_job(db_path, "job-v1", _PARSED_DATA)
        _insert_ujs_v1(db_path, 1, "job-v1", 85)

        from api.routes.jobs import _score_and_tier_jobs

        # Simulate the job row as get_jobs() would return it
        job = {
            "job_id": "job-v1",
            "title": "Staff Data Engineer",
            "company": "ClickHouse",
            "location": "Netherlands",
            "location_type": "remote",
            "parsed": json.dumps(_PARSED_DATA),
            "domain": "data",
            "role_function": None,
            "ujs_score": 85,  # v1: stored score
            "ujs_tier": "A",
            "ujs_scored": 1,
            "ujs_technical_grade": None,
            "ujs_profile_grade": None,
            "ujs_scored_v2": 0,  # NOT v2
            "remote_restriction": "Netherlands only",
        }

        with patch("api.routes.jobs._db_path", return_value=db_path):
            with patch("api.routes.jobs.get_all_domain_overrides", return_value={}):
                results = _score_and_tier_jobs([job], _PROFILE_DATA, ["barcelona"], ["EU"], user_id=1)

        # Score must NOT be 85 (the stored v1 value)
        assert results[0]["score"] != 85, f"v1 stored score 85 should not be used directly; got {results[0]['score']}"

    def test_v2_job_uses_hybrid_score(self):
        """v2 job (scored_v2=1) uses hybrid_score with grades (v2 unchanged)."""
        db_path = _make_db()
        parsed_no_restriction = {**_PARSED_DATA, "remote_restriction": None, "locations_mentioned": []}
        _insert_job(db_path, "job-v2", parsed_no_restriction)
        _insert_ujs_v2(db_path, 1, "job-v2", "A", "B")

        from api.routes.jobs import _score_and_tier_jobs
        from api.scoring import hybrid_score

        job = {
            "job_id": "job-v2",
            "title": "Staff Data Engineer",
            "company": "ClickHouse",
            "location": "Netherlands",
            "location_type": "remote",
            "parsed": json.dumps(parsed_no_restriction),
            "domain": "data",
            "role_function": None,
            "ujs_score": 0,
            "ujs_tier": "A",
            "ujs_scored": 1,
            "ujs_technical_grade": "A",
            "ujs_profile_grade": "B",
            "ujs_scored_v2": 1,  # v2!
            "remote_restriction": None,
        }

        with patch("api.routes.jobs._db_path", return_value=db_path):
            with patch("api.routes.jobs.get_all_domain_overrides", return_value={}):
                results = _score_and_tier_jobs([job], _PROFILE_DATA, ["barcelona"], ["EU"], user_id=1)

        expected = hybrid_score(
            _PROFILE_DATA,
            parsed_no_restriction,
            job,
            False,
            technical_grade="A",
            profile_grade="B",
            db_path=db_path,
        )
        assert results[0]["score"] == expected, f"v2 job should use hybrid_score({expected}), got {results[0]['score']}"

    def test_unscored_job_uses_heuristic(self):
        """Job with no ujs at all uses _score_single_job (heuristic path)."""
        db_path = _make_db()
        _insert_job(db_path, "job-unscored", _PARSED_DATA)
        # No UJS inserted

        from api.routes.jobs import _score_and_tier_jobs

        job = {
            "job_id": "job-unscored",
            "title": "Staff Data Engineer",
            "company": "ClickHouse",
            "location": "Netherlands",
            "location_type": "remote",
            "parsed": json.dumps(_PARSED_DATA),
            "domain": "data",
            "role_function": None,
            "ujs_score": None,
            "ujs_tier": None,
            "ujs_scored": None,
            "ujs_technical_grade": None,
            "ujs_profile_grade": None,
            "ujs_scored_v2": None,
            "remote_restriction": "Netherlands only",
        }

        with patch("api.routes.jobs._db_path", return_value=db_path):
            with patch("api.routes.jobs.get_all_domain_overrides", return_value={}):
                results = _score_and_tier_jobs([job], _PROFILE_DATA, ["barcelona"], ["EU"], user_id=1)

        score = results[0]["score"]
        assert isinstance(score, int)
        assert 0 <= score <= 100
        # Score should be computed, not 0 (profile has domain+skills match)
        assert score > 0, f"Unscored job with matching profile should score > 0, got {score}"
