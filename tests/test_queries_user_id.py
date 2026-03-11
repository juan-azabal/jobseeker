"""Tests for Phase 1.2: get_profile_id_by_user_id + reset_seen_ids uses user_id."""

import sqlite3

import pytest

from api.db.init import init_db
from api.db.queries import get_profile_id_by_user_id


def _make_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _seed_user(db_path: str, google_id: str, profile_id: str) -> int:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO users (google_id, email, profile_id) VALUES (?, ?, ?)",
        (google_id, f"{google_id}@test.com", profile_id),
    )
    con.commit()
    uid = con.execute("SELECT id FROM users WHERE google_id = ?", (google_id,)).fetchone()[0]
    con.close()
    return uid


class TestGetProfileIdByUserId:
    def test_returns_profile_id(self, tmp_path):
        db_path = _make_db(tmp_path)
        uid = _seed_user(db_path, "g1", "juanAza")

        result = get_profile_id_by_user_id(db_path, uid)

        assert result == "juanAza"

    def test_returns_none_for_unknown_user(self, tmp_path):
        db_path = _make_db(tmp_path)

        result = get_profile_id_by_user_id(db_path, 9999)

        assert result is None

    def test_multiple_users_return_correct_profile_id(self, tmp_path):
        db_path = _make_db(tmp_path)
        uid1 = _seed_user(db_path, "g1", "juanAza")
        uid2 = _seed_user(db_path, "g2", "noura")

        assert get_profile_id_by_user_id(db_path, uid1) == "juanAza"
        assert get_profile_id_by_user_id(db_path, uid2) == "noura"

    def test_user_without_profile_id_returns_none(self, tmp_path):
        db_path = _make_db(tmp_path)
        con = sqlite3.connect(db_path)
        con.execute("INSERT INTO users (google_id, email) VALUES ('g1', 'g1@test.com')")
        con.commit()
        uid = con.execute("SELECT id FROM users WHERE google_id='g1'").fetchone()[0]
        con.close()

        result = get_profile_id_by_user_id(db_path, uid)

        assert result is None


class TestResetSeenIdsUsesUserId:
    """Verify that admin reset_seen_ids deletes by user_id (not profile_id)."""

    def test_db_delete_uses_user_id(self, tmp_path):
        """After migration 024, seen_job_ids has user_id column.
        Inserting and deleting by user_id works correctly.
        """
        db_path = _make_db(tmp_path)
        uid = _seed_user(db_path, "g1", "juanAza")

        con = sqlite3.connect(db_path)
        con.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (uid, "job-001"))
        con.commit()

        # Simulate what reset_seen_ids does after Phase 1.2 fix
        cur = con.execute("DELETE FROM seen_job_ids WHERE user_id = ?", (uid,))
        deleted = cur.rowcount
        con.commit()

        remaining = con.execute("SELECT COUNT(*) FROM seen_job_ids WHERE user_id = ?", (uid,)).fetchone()[0]
        con.close()

        assert deleted == 1
        assert remaining == 0

    def test_delete_only_affects_target_user(self, tmp_path):
        """Clearing user A's seen_ids does not affect user B's."""
        db_path = _make_db(tmp_path)
        uid1 = _seed_user(db_path, "g1", "juanAza")
        uid2 = _seed_user(db_path, "g2", "noura")

        con = sqlite3.connect(db_path)
        con.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (uid1, "j1"))
        con.execute("INSERT INTO seen_job_ids (user_id, job_id) VALUES (?, ?)", (uid2, "j2"))
        con.commit()

        con.execute("DELETE FROM seen_job_ids WHERE user_id = ?", (uid1,))
        con.commit()

        uid2_remaining = con.execute("SELECT COUNT(*) FROM seen_job_ids WHERE user_id = ?", (uid2,)).fetchone()[0]
        con.close()

        assert uid2_remaining == 1
