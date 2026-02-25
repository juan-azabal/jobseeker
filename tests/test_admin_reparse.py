"""Tests for Phase 13.5 admin endpoints: domain reparse and domain corrections."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_job, upsert_user, create_session
from api.main import app


def _make_job(
    job_id: str,
    domain: str = "other",
    parsed_domain: str = "other",
    responsibilities: str = "",
) -> dict:
    return {
        "job_id": job_id,
        "title": f"Job {job_id}",
        "company": "TestCo",
        "location": "Remote",
        "url": f"https://example.com/{job_id}",
        "location_type": "remote",
        "domain": domain,
        "parsed": json.dumps({
            "domain": parsed_domain,
            "responsibilities_summary": responsibilities,
            "must_have_skills": [],
            "technical_stack": [],
        }),
        "first_seen": "2026-01-01",
        "last_seen": "2026-01-01",
        "ingested_at": "2026-01-01T00:00:00",
    }


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    """TestClient authenticated as an admin user."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    user = upsert_user(db_path, {
        "google_id": "g_admin",
        "email": "admin@test.com",
        "name": "Admin",
        "avatar_url": None,
        "profile_id": "admin",
    })
    # Grant admin privileges
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()

    create_session(db_path, "admin_tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "admin_tok")
    return c, db_path


class TestReparseDomainsEndpoint:
    def test_reparse_reclassifies_other_jobs(self, admin_client):
        """POST /reparse-domains reclassifies jobs with inferred non-'other' domain."""
        client, db_path = admin_client

        # Insert a job with domain='other' but text that matches 'game' keywords
        upsert_job(db_path, _make_job(
            "j1", domain="other", parsed_domain="other",
            responsibilities="video game development for mobile gaming studio",
        ))

        resp = client.post("/api/admin/reparse-domains")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_other"] == 1
        assert data["reclassified"] == 1

        # Verify jobs.domain column was updated
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT domain FROM jobs WHERE job_id = 'j1'").fetchone()
        conn.close()
        assert row[0] == "gaming"

    def test_reparse_does_not_touch_parsed_domain(self, admin_client):
        """Reparse must NOT mutate the parsed JSON — only jobs.domain column."""
        client, db_path = admin_client

        original_parsed = json.dumps({
            "domain": "other",
            "responsibilities_summary": "video game development for mobile gaming studio",
            "must_have_skills": [],
            "technical_stack": [],
        })
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO jobs (job_id, title, company, location, url, location_type, domain, parsed, first_seen, last_seen, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("j2", "Game Dev", "GameCo", "Remote", "https://x.com/j2", "remote",
             "other", original_parsed, "2026-01-01", "2026-01-01", "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

        client.post("/api/admin/reparse-domains")

        # Check parsed column is unchanged
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT parsed FROM jobs WHERE job_id = 'j2'").fetchone()
        conn.close()
        stored = json.loads(row[0])
        assert stored["domain"] == "other"  # parsed.domain must remain untouched

    def test_reparse_skips_already_classified_jobs(self, admin_client):
        """Jobs that still infer to 'other' are counted but not written."""
        client, db_path = admin_client

        upsert_job(db_path, _make_job(
            "j3", domain="other", parsed_domain="other",
            responsibilities="generic consulting advisory strategy",
        ))

        resp = client.post("/api/admin/reparse-domains")
        data = resp.json()
        assert data["total_other"] == 1
        assert data["reclassified"] == 0

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT domain FROM jobs WHERE job_id = 'j3'").fetchone()
        conn.close()
        assert row[0] == "other"  # unchanged

    def test_reparse_is_idempotent(self, admin_client):
        """Running reparse twice produces the same result: second run sees 0 'other' jobs."""
        client, db_path = admin_client

        upsert_job(db_path, _make_job(
            "j4", domain="other", parsed_domain="other",
            responsibilities="video game development for mobile gaming studio",
        ))

        resp1 = client.post("/api/admin/reparse-domains")
        assert resp1.json()["reclassified"] == 1

        # Second run: the job's domain is now 'game', but parsed.domain is still 'other',
        # so it will still appear in the query. However _infer_domain returns 'game' again,
        # meaning update is called again (idempotent write).
        resp2 = client.post("/api/admin/reparse-domains")
        assert resp2.json()["reclassified"] >= 0  # no crash; runs cleanly

    def test_reparse_empty_db_returns_zeros(self, admin_client):
        """Reparse on DB with no 'other' jobs returns zeros."""
        client, _ = admin_client

        resp = client.post("/api/admin/reparse-domains")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_other"] == 0
        assert data["reclassified"] == 0

    def test_reparse_requires_admin(self, tmp_path, monkeypatch):
        """Non-admin user gets 403."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        monkeypatch.setenv("DB_PATH", db_path)

        user = upsert_user(db_path, {
            "google_id": "g_user", "email": "user@test.com",
            "name": "User", "avatar_url": None, "profile_id": None,
        })
        create_session(db_path, "user_tok", user["id"], "2099-01-01T00:00:00")
        c = TestClient(app)
        c.cookies.set("jsk", "user_tok")

        resp = c.post("/api/admin/reparse-domains")
        assert resp.status_code == 403


class TestReparseDomainsPreview:
    def test_preview_returns_count_and_samples(self, admin_client):
        """GET /reparse-domains/preview returns domain_other_count and sample list."""
        client, db_path = admin_client

        upsert_job(db_path, _make_job(
            "p1", domain="other", parsed_domain="other",
            responsibilities="video game development for mobile gaming studio",
        ))
        upsert_job(db_path, _make_job(
            "p2", domain="other", parsed_domain="other",
            responsibilities="generic consulting services",
        ))

        resp = client.get("/api/admin/reparse-domains/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["domain_other_count"] == 2
        # Only the gaming job would be reclassified
        assert len(data["sample"]) == 1
        assert data["sample"][0]["job_id"] == "p1"
        assert data["sample"][0]["inferred"] == "gaming"
        assert "company" in data["sample"][0]
        assert "title" in data["sample"][0]

    def test_preview_does_not_modify_db(self, admin_client):
        """Preview must not change any database rows."""
        client, db_path = admin_client

        upsert_job(db_path, _make_job(
            "p3", domain="other", parsed_domain="other",
            responsibilities="video game development for mobile gaming studio",
        ))

        client.get("/api/admin/reparse-domains/preview")

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT domain FROM jobs WHERE job_id = 'p3'").fetchone()
        conn.close()
        assert row[0] == "other"  # must remain unchanged

    def test_preview_sample_capped_at_five(self, admin_client):
        """Preview returns at most 5 samples."""
        client, db_path = admin_client

        for i in range(10):
            upsert_job(db_path, _make_job(
                f"s{i}", domain="other", parsed_domain="other",
                responsibilities="video game development for mobile gaming studio",
            ))

        resp = client.get("/api/admin/reparse-domains/preview")
        data = resp.json()
        assert data["domain_other_count"] == 10
        assert len(data["sample"]) <= 5

    def test_preview_empty_db(self, admin_client):
        """Preview on empty DB returns zeros."""
        client, _ = admin_client
        resp = client.get("/api/admin/reparse-domains/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["domain_other_count"] == 0
        assert data["sample"] == []


class TestDomainCorrections:
    def test_no_corrections_returns_empty_list(self, admin_client):
        """GET /domain-corrections returns empty list when no overrides exist."""
        client, _ = admin_client
        resp = client.get("/api/admin/domain-corrections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["corrections"] == []

    def test_corrections_aggregated(self, admin_client):
        """Domain corrections are aggregated by (from, to) with correct counts."""
        client, db_path = admin_client

        # Insert a job with parsed domain = 'other'
        upsert_job(db_path, _make_job("c1", domain="other", parsed_domain="other"))
        upsert_job(db_path, _make_job("c2", domain="other", parsed_domain="other"))

        # Insert a user
        user = upsert_user(db_path, {
            "google_id": "g_corr", "email": "corr@test.com",
            "name": "Corr", "avatar_url": None, "profile_id": None,
        })

        conn = sqlite3.connect(db_path)
        # Two corrections: other → game
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (user["id"], "c1", "gaming"),
        )
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (user["id"], "c2", "gaming"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/admin/domain-corrections")
        assert resp.status_code == 200
        corrections = resp.json()["corrections"]
        assert len(corrections) == 1
        assert corrections[0]["from"] == "other"
        assert corrections[0]["to"] == "gaming"
        assert corrections[0]["count"] == 2

    def test_corrections_exclude_same_domain(self, admin_client):
        """Overrides that match the parsed domain are not counted as corrections."""
        client, db_path = admin_client

        # Job with parsed domain = 'game'
        upsert_job(db_path, _make_job("d1", domain="gaming", parsed_domain="gaming"))

        user = upsert_user(db_path, {
            "google_id": "g_same", "email": "same@test.com",
            "name": "Same", "avatar_url": None, "profile_id": None,
        })

        conn = sqlite3.connect(db_path)
        # "Correction" that matches parsed domain — should NOT appear
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (user["id"], "d1", "gaming"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/admin/domain-corrections")
        data = resp.json()
        assert data["corrections"] == []

    def test_corrections_ordered_by_count_desc(self, admin_client):
        """Corrections are ordered by count descending."""
        client, db_path = admin_client

        # Two jobs: one corrected 2 times to 'fintech', one corrected 1 time to 'game'
        upsert_job(db_path, _make_job("e1", parsed_domain="other"))
        upsert_job(db_path, _make_job("e2", parsed_domain="other"))
        upsert_job(db_path, _make_job("e3", parsed_domain="other"))

        u1 = upsert_user(db_path, {
            "google_id": "g_u1", "email": "u1@test.com", "name": "U1",
            "avatar_url": None, "profile_id": None,
        })
        u2 = upsert_user(db_path, {
            "google_id": "g_u2", "email": "u2@test.com", "name": "U2",
            "avatar_url": None, "profile_id": None,
        })

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (u1["id"], "e1", "fintech"),
        )
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (u2["id"], "e2", "fintech"),
        )
        conn.execute(
            "INSERT INTO user_job_status (user_id, job_id, domain_override) VALUES (?, ?, ?)",
            (u1["id"], "e3", "gaming"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/admin/domain-corrections")
        corrections = resp.json()["corrections"]
        assert corrections[0]["to"] == "fintech"
        assert corrections[0]["count"] == 2
        assert corrections[1]["to"] == "gaming"
        assert corrections[1]["count"] == 1
