"""Tests for migration 024: seen_job_ids profile_id → user_id."""

import sqlite3
import textwrap
import pytest


def _apply_migrations_up_to_023(con: sqlite3.Connection) -> None:
    """Bootstrap a test DB with users + seen_job_ids (023 schema)."""
    con.executescript(
        textwrap.dedent("""\
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id  TEXT UNIQUE NOT NULL,
            email      TEXT,
            name       TEXT,
            profile_id TEXT
        );

        CREATE TABLE IF NOT EXISTS seen_job_ids (
            profile_id   TEXT NOT NULL,
            job_id       TEXT NOT NULL,
            first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (profile_id, job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_seen_job_ids_profile
            ON seen_job_ids(profile_id);
    """)
    )


def _apply_migration_024(con: sqlite3.Connection) -> None:
    with open("api/db/migrations/024-seen-job-ids-user-id.sql") as f:
        con.executescript(f.read())


@pytest.fixture()
def db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    _apply_migrations_up_to_023(con)
    return con


def test_user_id_populated_from_users(db):
    """Rows whose profile_id maps to a user get the correct user_id."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juanAza')")
    uid = db.execute("SELECT id FROM users WHERE profile_id='juanAza'").fetchone()["id"]

    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('juanAza', 'job-001')")
    _apply_migration_024(db)

    row = db.execute("SELECT * FROM seen_job_ids WHERE job_id='job-001'").fetchone()
    assert row is not None
    assert row["user_id"] == uid
    assert "profile_id" not in row.keys()


def test_orphaned_rows_deleted(db):
    """Rows with no matching user are deleted (not migrated)."""
    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('ghost-profile', 'job-999')")
    _apply_migration_024(db)

    row = db.execute("SELECT * FROM seen_job_ids WHERE job_id='job-999'").fetchone()
    assert row is None


def test_multiple_users_mapped_correctly(db):
    """Each user's seen IDs are mapped to their own user_id."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juanAza')")
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g2', 'noura')")

    uid_juan = db.execute("SELECT id FROM users WHERE profile_id='juanAza'").fetchone()["id"]
    uid_noura = db.execute("SELECT id FROM users WHERE profile_id='noura'").fetchone()["id"]

    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('juanAza', 'j1')")
    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('juanAza', 'j2')")
    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('noura', 'j3')")

    _apply_migration_024(db)

    rows = {r["job_id"]: r["user_id"] for r in db.execute("SELECT * FROM seen_job_ids").fetchall()}
    assert rows == {"j1": uid_juan, "j2": uid_juan, "j3": uid_noura}


def test_pk_constraint_rejects_duplicates(db):
    """(user_id, job_id) PK rejects duplicate inserts after migration."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juanAza')")
    db.execute("INSERT INTO seen_job_ids (profile_id, job_id) VALUES ('juanAza', 'j1')")
    _apply_migration_024(db)

    uid = db.execute("SELECT id FROM users WHERE profile_id='juanAza'").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (uid, "j1"))
        db.commit()


def test_first_seen_at_preserved(db):
    """first_seen_at timestamp is carried through the migration."""
    db.execute("INSERT INTO users (google_id, profile_id) VALUES ('g1', 'juanAza')")
    db.execute(
        "INSERT INTO seen_job_ids (profile_id, job_id, first_seen_at) VALUES ('juanAza', 'j1', '2025-01-15 10:00:00')"
    )
    _apply_migration_024(db)

    row = db.execute("SELECT * FROM seen_job_ids WHERE job_id='j1'").fetchone()
    assert row["first_seen_at"] == "2025-01-15 10:00:00"


def test_empty_table_migrates_cleanly(db):
    """Migration on empty seen_job_ids succeeds with no rows."""
    _apply_migration_024(db)
    count = db.execute("SELECT COUNT(*) FROM seen_job_ids").fetchone()[0]
    assert count == 0
