"""Tests for Phase 1.5: ingest accepts user_id (int) with profile_id backward compat."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user
from api.ingest import ingest_from_list
from api.main import app

INGEST_KEY = "test-ingest-key"

_BASE_JOB = {
    "id": "uid-job-001",
    "title": "Senior PM",
    "company": "Acme",
    "location": "Remote",
    "url": "https://ex.com/1",
    "location_type": "remote",
    "source": "test",
    "description": "A job",
    "first_seen": "2026-01-01",
    "last_seen": "2026-01-01",
    "rag_score": {
        "technical_depth": "A",
        "profile_evidence": "B",
        "strengths": [],
        "gaps": [],
        "deal_breakers": [],
        "talking_points": [],
        "one_line_verdict": "Good fit.",
    },
}


@pytest.fixture
def db_with_user(tmp_path):
    """Seeded DB with one user; returns (db_path, user_id)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    user = upsert_user(
        db_path,
        {"google_id": "g1", "email": "a@b.com", "name": "Test", "avatar_url": None, "profile_id": "testuid"},
    )
    return db_path, user["id"]


class TestIngestFromListUserId:
    def test_ingest_with_user_id_stores_score(self, db_with_user):
        """ingest_from_list(user_id=N) stores per-user score correctly."""
        db_path, uid = db_with_user
        job = {**_BASE_JOB, "id": "uid-001"}

        ingest_from_list(db_path, [job], user_id=uid)

        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT technical_grade FROM user_job_scores WHERE user_id=? AND job_id LIKE 'uid-001%'",
            (uid,),
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] == "A"

    def test_ingest_without_user_id_skips_score(self, db_with_user):
        """ingest_from_list(user_id=None) stores job but no per-user score."""
        db_path, _ = db_with_user
        job = {**_BASE_JOB, "id": "uid-002"}

        ingest_from_list(db_path, [job])

        con = sqlite3.connect(db_path)
        row = con.execute("SELECT * FROM user_job_scores WHERE job_id LIKE 'uid-002%'").fetchone()
        con.close()
        assert row is None


@pytest.fixture
def ingest_client(tmp_path, monkeypatch):
    """HTTP client + seeded user; returns (client, user_id, profile_id)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("INGEST_API_KEY", INGEST_KEY)
    user = upsert_user(
        db_path,
        {"google_id": "g1", "email": "a@b.com", "name": "Test", "avatar_url": None, "profile_id": "testuid"},
    )
    return TestClient(app), user["id"], "testuid"


class TestIngestRouteBackwardCompat:
    def test_ingest_with_user_id_works(self, ingest_client):
        """Payload with user_id (int) stores per-user score."""
        client, uid, _ = ingest_client
        job = {**_BASE_JOB, "id": "route-uid-001"}
        r = client.post(
            "/api/ingest",
            json={"jobs": [job], "user_id": uid},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["scored"] == 1

    def test_ingest_with_profile_id_backward_compat(self, ingest_client):
        """Payload with profile_id (str) still works and stores per-user score."""
        client, uid, pid = ingest_client
        job = {**_BASE_JOB, "id": "route-pid-001"}
        r = client.post(
            "/api/ingest",
            json={"jobs": [job], "profile_id": pid},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["scored"] == 1

    def test_user_id_takes_priority_over_profile_id(self, ingest_client):
        """When both user_id and profile_id provided, user_id is used."""
        client, uid, _ = ingest_client
        job = {**_BASE_JOB, "id": "route-both-001"}
        r = client.post(
            "/api/ingest",
            json={"jobs": [job], "user_id": uid, "profile_id": "ghost-profile"},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["scored"] == 1

    def test_ingest_without_either_skips_score(self, ingest_client):
        """Payload with no user_id or profile_id still stores job, skips score."""
        client, _, _ = ingest_client
        job = {**_BASE_JOB, "id": "route-none-001"}
        r = client.post(
            "/api/ingest",
            json={"jobs": [job]},
            headers={"X-Ingest-Key": INGEST_KEY},
        )
        assert r.status_code == 200
        assert r.json()["scored"] == 0
