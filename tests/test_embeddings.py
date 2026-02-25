"""Tests for embedding infrastructure: migration, service, skill matcher."""

import sqlite3
import tempfile
import pytest

from api.db.init import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


# ---------------------------------------------------------------------------
# 12.1 — Migration: skill_embeddings table exists
# ---------------------------------------------------------------------------

class TestSkillEmbeddingsMigration:
    def test_table_exists_after_init(self, db_path):
        con = sqlite3.connect(db_path)
        tables = [
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        con.close()
        assert "skill_embeddings" in tables

    def test_table_columns(self, db_path):
        con = sqlite3.connect(db_path)
        cols = con.execute("PRAGMA table_info(skill_embeddings)").fetchall()
        col_names = [c[1] for c in cols]
        con.close()
        assert "skill_text" in col_names
        assert "model" in col_names
        assert "embedding" in col_names
        assert "created_at" in col_names

    def test_primary_key_is_composite(self, db_path):
        """Primary key should be (skill_text, model)."""
        con = sqlite3.connect(db_path)
        # Insert with same skill_text but different model → OK
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "model-a", b"[1,2,3]"),
        )
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "model-b", b"[4,5,6]"),
        )
        con.commit()
        # Duplicate (skill_text, model) → should fail
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
                ("python", "model-a", b"[7,8,9]"),
            )
        con.close()

    def test_default_model_value(self, db_path):
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, embedding) VALUES (?, ?)",
            ("sql", b"[1,0]"),
        )
        con.commit()
        row = con.execute(
            "SELECT model FROM skill_embeddings WHERE skill_text = ?", ("sql",)
        ).fetchone()
        con.close()
        assert row[0] == "text-embedding-3-small"
