"""Tests for migration 025: seed seen_job_ids from active users × all jobs.

Root cause: Phase UID migration (024) transferred only the ~50/84 DB entries.
File-based seen_ids history was lost → old jobs pass prefilter every day →
first_seen dates old in Railway → digest returns 0 → empty emails.

This migration seeds seen_job_ids with ALL current jobs for every active user
(defined as: has at least one existing seen_job_id OR at least one user_job_score).
"""

import sqlite3
import textwrap
import pytest


def _bootstrap(con: sqlite3.Connection) -> None:
    """Create minimal schema needed by migration 025."""
    con.executescript(
        textwrap.dedent("""\
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id  TEXT UNIQUE NOT NULL,
            profile_id TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title  TEXT
        );

        CREATE TABLE IF NOT EXISTS user_job_scores (
            user_id INTEGER NOT NULL,
            job_id  TEXT NOT NULL,
            PRIMARY KEY (user_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS seen_job_ids (
            user_id       INTEGER NOT NULL,
            job_id        TEXT NOT NULL,
            first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, job_id)
        );
    """)
    )


def _apply_migration_025(con: sqlite3.Connection) -> None:
    with open("api/db/migrations/025-seed-seen-ids.sql") as f:
        con.executescript(f.read())


@pytest.fixture()
def db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    _bootstrap(con)
    return con


def test_user_with_seen_ids_gets_all_jobs(db):
    """User who already has seen_ids gets seeded with all jobs in DB."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juan')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='juan'").fetchone()["id"]
    db.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, 'old-job')", (uid,))
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-A')")
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-B')")
    db.commit()

    _apply_migration_025(db)

    job_ids = {r["job_id"] for r in db.execute("SELECT job_id FROM seen_job_ids WHERE user_id=?", (uid,)).fetchall()}
    assert "old-job" in job_ids
    assert "job-A" in job_ids
    assert "job-B" in job_ids


def test_user_with_scores_but_no_seen_ids_gets_seeded(db):
    """User who has user_job_scores but 0 seen_ids gets seeded with all jobs."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g2', 'noura')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='noura'").fetchone()["id"]
    db.execute("INSERT INTO user_job_scores (user_id, job_id) VALUES (?, 'scored-job')", (uid,))
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-X')")
    db.commit()

    _apply_migration_025(db)

    job_ids = {r["job_id"] for r in db.execute("SELECT job_id FROM seen_job_ids WHERE user_id=?", (uid,)).fetchall()}
    assert "job-X" in job_ids


def test_inactive_user_not_seeded(db):
    """User with no seen_ids and no scores is not seeded (inactive)."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g3', 'newuser')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='newuser'").fetchone()["id"]
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-Y')")
    db.commit()

    _apply_migration_025(db)

    count = db.execute("SELECT COUNT(*) FROM seen_job_ids WHERE user_id=?", (uid,)).fetchone()[0]
    assert count == 0


def test_existing_entries_preserved(db):
    """INSERT OR IGNORE keeps existing (user_id, job_id) rows untouched."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juan')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='juan'").fetchone()["id"]
    db.execute(
        "INSERT INTO seen_job_ids (user_id, job_id, first_seen_at) VALUES (?, 'job-A', '2025-01-01 00:00:00')",
        (uid,),
    )
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-A')")
    db.commit()

    _apply_migration_025(db)

    row = db.execute("SELECT first_seen_at FROM seen_job_ids WHERE user_id=? AND job_id='job-A'", (uid,)).fetchone()
    assert row["first_seen_at"] == "2025-01-01 00:00:00"


def test_multiple_active_users_seeded_independently(db):
    """Each active user gets all jobs seeded independently."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juan')")
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g2', 'noura')")
    uid1 = db.execute("SELECT id FROM users WHERE profile_id='juan'").fetchone()["id"]
    uid2 = db.execute("SELECT id FROM users WHERE profile_id='noura'").fetchone()["id"]

    # juan has seen_ids; noura has scores
    db.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, 'j1')", (uid1,))
    db.execute("INSERT INTO user_job_scores (user_id, job_id) VALUES (?, 'j2')", (uid2,))
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-001')")
    db.execute("INSERT INTO jobs (job_id) VALUES ('job-002')")
    db.commit()

    _apply_migration_025(db)

    juan_ids = {r["job_id"] for r in db.execute("SELECT job_id FROM seen_job_ids WHERE user_id=?", (uid1,)).fetchall()}
    noura_ids = {r["job_id"] for r in db.execute("SELECT job_id FROM seen_job_ids WHERE user_id=?", (uid2,)).fetchall()}
    assert {"j1", "job-001", "job-002"} == juan_ids
    assert {"job-001", "job-002"} == noura_ids


def test_empty_jobs_table_no_rows_added(db):
    """If jobs table is empty, migration adds no seen_job_ids rows."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juan')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='juan'").fetchone()["id"]
    db.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, 'old-job')", (uid,))
    db.commit()

    _apply_migration_025(db)

    # Only the original 'old-job' entry should exist (no jobs table rows to seed)
    count = db.execute("SELECT COUNT(*) FROM seen_job_ids WHERE user_id=?", (uid,)).fetchone()[0]
    assert count == 1
