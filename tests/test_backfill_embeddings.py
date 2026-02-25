"""Tests for the backfill_embeddings script and ingest embedding wiring."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from api.db.init import init_db


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestBackfillScript:
    def test_backfill_empty_db(self, db):
        """Backfill on empty DB does nothing."""
        from scripts.backfill_embeddings import backfill

        with patch("api.embeddings.get_embeddings_batch") as mock_batch:
            result = backfill(db)

        assert result["total"] == 0
        assert result["cached"] == 0
        mock_batch.assert_not_called()

    def test_backfill_collects_job_skills(self, db):
        """Backfill extracts skills from parsed job data."""
        from scripts.backfill_embeddings import backfill

        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO jobs (job_id, title, company, location, url, parsed, first_seen, last_seen, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("j1", "PM", "Co", "NYC", "http://x", json.dumps({
                "must_have_skills": ["Python", "SQL"],
                "nice_to_have_skills": ["Docker"],
            }), "2024-01-01", "2024-01-01", "2024-01-01"),
        )
        conn.commit()
        conn.close()

        with patch("scripts.backfill_embeddings.get_embeddings_batch", return_value={"python": [0.1], "sql": [0.2], "docker": [0.3]}) as mock_batch:
            result = backfill(db)

        assert result["total"] == 3
        assert result["cached"] == 3
        mock_batch.assert_called_once()
        # All skills should be lowercase
        called_skills = set(mock_batch.call_args[0][0])
        assert called_skills == {"python", "sql", "docker"}

    def test_backfill_collects_profile_skills(self, db):
        """Backfill extracts skills from user profile YAMLs."""
        from scripts.backfill_embeddings import backfill

        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO users (google_id, email, name, profile_id, profile_yaml) VALUES (?, ?, ?, ?, ?)",
            ("g1", "u@test.com", "Test", "test", "skills:\n  - analytics\n  - python\n"),
        )
        conn.commit()
        conn.close()

        with patch("scripts.backfill_embeddings.get_embeddings_batch", return_value={"analytics": [0.1], "python": [0.2]}) as mock_batch:
            result = backfill(db)

        assert result["total"] == 2
        assert result["cached"] == 2

    def test_backfill_deduplicates(self, db):
        """Skills appearing in both profiles and jobs are counted once."""
        from scripts.backfill_embeddings import backfill

        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO users (google_id, email, name, profile_id, profile_yaml) VALUES (?, ?, ?, ?, ?)",
            ("g1", "u@test.com", "Test", "test", "skills:\n  - python\n"),
        )
        conn.execute(
            "INSERT INTO jobs (job_id, title, company, location, url, parsed, first_seen, last_seen, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("j1", "PM", "Co", "NYC", "http://x", json.dumps({
                "must_have_skills": ["Python"],
            }), "2024-01-01", "2024-01-01", "2024-01-01"),
        )
        conn.commit()
        conn.close()

        with patch("scripts.backfill_embeddings.get_embeddings_batch", return_value={"python": [0.1]}) as mock_batch:
            result = backfill(db)

        assert result["total"] == 1  # deduplicated


class TestIngestEmbeddingPrecompute:
    def test_ingest_precomputes_embeddings(self, db):
        """Ingest calls get_embeddings_batch for new job skills."""
        from api.ingest import ingest_from_list

        raw_jobs = [{
            "id": "j1",
            "title": "PM",
            "company": "Co",
            "location": "NYC",
            "job_url": "http://x",
            "date_posted": "2024-01-01",
            "parsed": {
                "must_have_skills": ["Python", "SQL"],
                "nice_to_have_skills": ["Docker"],
            },
        }]

        with patch("api.embeddings.get_embeddings_batch") as mock_batch:
            ingest_from_list(db, raw_jobs)

        mock_batch.assert_called_once()
        called_skills = set(mock_batch.call_args[0][0])
        assert called_skills == {"python", "sql", "docker"}

    def test_ingest_precompute_failure_nonfatal(self, db):
        """Embedding precompute failure doesn't break ingest."""
        from api.ingest import ingest_from_list

        raw_jobs = [{
            "id": "j1",
            "title": "PM",
            "company": "Co",
            "location": "NYC",
            "job_url": "http://x",
            "date_posted": "2024-01-01",
            "parsed": {"must_have_skills": ["Python"]},
        }]

        with patch("api.ingest._precompute_skill_embeddings", side_effect=Exception("boom")):
            # Should not raise
            result = ingest_from_list(db, raw_jobs)

        assert result["inserted"] == 1
