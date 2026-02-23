import os
from pathlib import Path
from api.db.init import init_db
from api.db.queries import get_jobs, get_job_by_id
from api.ingest import ingest

FIXTURES = Path(__file__).parent / "fixtures"


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


def test_ingest_tier_assignment(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    ingest(db_path, str(FIXTURES))
    j1 = get_job_by_id(db_path, "job001")
    j2 = get_job_by_id(db_path, "job002")
    j3 = get_job_by_id(db_path, "job003")
    assert j1["tier"] == "A"   # score 72
    assert j2["tier"] == "B"   # score 35
    assert j3["tier"] == "C"   # no rag_score → score 0


def test_ingest_no_rag_score(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    ingest(db_path, str(FIXTURES))
    j3 = get_job_by_id(db_path, "job003")
    assert j3 is not None
    assert j3["score"] == 0
