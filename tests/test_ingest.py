import os
import sqlite3
from pathlib import Path
from api.db.init import init_db
from api.db.queries import get_jobs, get_job_by_id, get_user_job_score
from api.ingest import ingest, ingest_from_list

FIXTURES = Path(__file__).parent / "fixtures"


def _create_test_user(db_path, user_id=1, profile_id="test-user"):
    import sqlite3

    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO users (id, google_id, email, name, profile_id) VALUES (?, 'g1', 'a@b.com', 'Test', ?)",
        (user_id, profile_id),
    )
    con.commit()
    con.close()


def test_ingest_two_files_deduped(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    result = ingest(db_path, str(FIXTURES))
    jobs = get_jobs(db_path)
    # run1 has job001+job002, run2 has job001(dup)+job003 → 3 unique
    assert len(jobs) == 3
    assert result["inserted"] + result["updated"] == 4  # 4 records processed total
    assert result["updated"] >= 1  # job001 appears twice


def test_ingest_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    ingest(db_path, str(FIXTURES))
    result2 = ingest(db_path, str(FIXTURES))
    jobs = get_jobs(db_path)
    assert len(jobs) == 3
    assert result2["inserted"] == 0


def test_ingest_per_user_scores(tmp_path):
    """When profile_id is provided, per-user scores are stored in user_job_scores."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    _create_test_user(db_path, user_id=1, profile_id="test-user")
    result = ingest(db_path, str(FIXTURES), profile_id="test-user")
    # job001 has rag_score 72, job002 has 35 — both stored as per-user scores
    assert result["scored"] >= 2
    ujs1 = get_user_job_score(db_path, 1, "job001")
    ujs2 = get_user_job_score(db_path, 1, "job002")
    assert ujs1 is not None and ujs1["score"] == 72
    assert ujs2 is not None and ujs2["score"] == 35


def test_ingest_no_profile_no_scores(tmp_path):
    """Without profile_id, job data is stored but no per-user scores."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    _create_test_user(db_path)
    ingest(db_path, str(FIXTURES))
    # Jobs exist but no per-user scores
    j1 = get_job_by_id(db_path, "job001")
    assert j1 is not None
    ujs = get_user_job_score(db_path, 1, "job001")
    assert ujs is None


def test_ingest_no_rag_score(tmp_path):
    """Jobs without rag_score are stored but have no per-user score even with profile_id."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    _create_test_user(db_path)
    ingest(db_path, str(FIXTURES), profile_id="test-user")
    j3 = get_job_by_id(db_path, "job003")
    assert j3 is not None
    ujs = get_user_job_score(db_path, 1, "job003")
    assert ujs is None  # job003 has no rag_score


def test_ingest_v15_columns_persisted(tmp_path):
    """Parser v1.5 fields are extracted from parsed JSON and written to real columns."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    raw = [
        {
            "id": "jv15-001",
            "title": "Head of Product",
            "company": "Acme",
            "location": "Remote",
            "parsed": {
                "location_type": "remote",
                "domain": "saas",
                "role_in_plain_english": "You will own the product roadmap end-to-end.",
                "company_context": {
                    "stage": "growth",
                    "what_they_value": ["speed", "data"],
                    "tone": "startup_scrappy",
                },
            },
        }
    ]
    ingest_from_list(db_path, raw)
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT role_in_plain_english, company_stage, company_tone FROM jobs WHERE job_id = 'jv15-001'"
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == "You will own the product roadmap end-to-end."
    assert row[1] == "growth"
    assert row[2] == "startup_scrappy"


def test_ingest_v15_columns_null_when_missing(tmp_path):
    """v1.5 columns default to NULL when parsed blob has no company_context."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    raw = [
        {
            "id": "jv15-002",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "parsed": {"location_type": "remote", "domain": "saas"},
        }
    ]
    ingest_from_list(db_path, raw)
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT role_in_plain_english, company_stage, company_tone FROM jobs WHERE job_id = 'jv15-002'"
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] is None
    assert row[1] is None
    assert row[2] is None


def test_ingest_v15_coalesce_on_update(tmp_path):
    """Re-ingesting a job without v1.5 fields preserves existing column values."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    # First ingest: has v1.5 fields
    raw_v1 = [
        {
            "id": "jv15-003",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "parsed": {
                "location_type": "remote",
                "role_in_plain_english": "Lead the roadmap.",
                "company_context": {"stage": "mature", "tone": "corporate_polished"},
            },
        }
    ]
    ingest_from_list(db_path, raw_v1)
    # Second ingest: same job without v1.5 fields (simulates old cached job)
    raw_v2 = [
        {
            "id": "jv15-003",
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "parsed": {"location_type": "remote"},
        }
    ]
    ingest_from_list(db_path, raw_v2)
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT role_in_plain_english, company_stage, company_tone FROM jobs WHERE job_id = 'jv15-003'"
    ).fetchone()
    con.close()
    # COALESCE preserves existing values when new values are NULL
    assert row[0] == "Lead the roadmap."
    assert row[1] == "mature"
    assert row[2] == "corporate_polished"
