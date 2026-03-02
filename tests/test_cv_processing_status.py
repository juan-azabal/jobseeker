"""Phase 2.1 — Tests: cv_processing columns + query helpers."""

import sqlite3
import pytest

from api.db.init import init_db
from api.db.queries import (
    set_cv_processing_status,
    get_cv_processing_status,
    upsert_user,
)


def _make_db(tmp_path) -> tuple[str, int]:
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_proc",
            "email": "proc@example.com",
            "name": "Proc User",
            "avatar_url": None,
            "profile_id": "proc_user",
        },
    )
    return db_path, user["id"]


class TestCvProcessingColumns:
    def test_columns_exist_after_migration(self, tmp_path):
        """Migration 022 adds cv_processing_status, cv_processing_started_at, cv_pending_result."""
        db_path, _ = _make_db(tmp_path)
        with sqlite3.connect(db_path) as con:
            row = con.execute("PRAGMA table_info(users)").fetchall()
            col_names = [r[1] for r in row]
        assert "cv_processing_status" in col_names
        assert "cv_processing_started_at" in col_names
        assert "cv_pending_result" in col_names

    def test_default_status_is_null(self, tmp_path):
        db_path, user_id = _make_db(tmp_path)
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] is None
        assert status["started_at"] is None
        assert status["result"] is None

    def test_set_processing(self, tmp_path):
        db_path, user_id = _make_db(tmp_path)
        set_cv_processing_status(db_path, user_id, "processing")
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "processing"
        assert status["started_at"] is not None  # auto-set when transitioning to "processing"

    def test_set_done_with_result(self, tmp_path):
        db_path, user_id = _make_db(tmp_path)
        result = {"type": "replace", "diff": {"skills_added": ["go"]}}
        set_cv_processing_status(db_path, user_id, "done", result=result)
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "done"
        assert status["result"]["diff"]["skills_added"] == ["go"]

    def test_set_failed_with_error(self, tmp_path):
        db_path, user_id = _make_db(tmp_path)
        set_cv_processing_status(db_path, user_id, "failed", error="LLM timeout")
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] == "failed"
        assert status["result"]["error"] == "LLM timeout"

    def test_clear_status(self, tmp_path):
        db_path, user_id = _make_db(tmp_path)
        set_cv_processing_status(db_path, user_id, "processing")
        set_cv_processing_status(db_path, user_id, None)
        status = get_cv_processing_status(db_path, user_id)
        assert status["status"] is None
        assert status["started_at"] is None
        assert status["result"] is None
