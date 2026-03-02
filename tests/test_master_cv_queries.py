"""Tests for master_cv_json DB query helpers."""

import tempfile

from api.db.init import init_db
from api.db.queries import get_master_cv_json, save_master_cv_json


def _make_db() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    init_db(db)
    return db


class TestSaveAndGetMasterCvJson:
    def test_save_and_retrieve(self):
        db = _make_db()
        import sqlite3

        with sqlite3.connect(db) as con:
            con.execute("INSERT INTO users (id, google_id, email, name) VALUES (1, 'g1', 'a@b.com', 'Test')")

        payload = '{"version": "1.0", "work": []}'
        save_master_cv_json(db, user_id=1, json_str=payload)
        result = get_master_cv_json(db, user_id=1)
        assert result == payload

    def test_get_nonexistent_user_returns_none(self):
        db = _make_db()
        result = get_master_cv_json(db, user_id=999)
        assert result is None

    def test_overwrite_updates_value(self):
        db = _make_db()
        import sqlite3

        with sqlite3.connect(db) as con:
            con.execute("INSERT INTO users (id, google_id, email, name) VALUES (1, 'g1', 'a@b.com', 'Test')")

        save_master_cv_json(db, user_id=1, json_str='{"version":"1.0"}')
        save_master_cv_json(db, user_id=1, json_str='{"version":"1.0","updated":true}')
        result = get_master_cv_json(db, user_id=1)
        assert '"updated":true' in result
