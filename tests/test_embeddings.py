"""Tests for embedding infrastructure: migration, service, skill matcher."""

import json
import math
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# 12.2 — Embedding service: get_embedding, cosine_similarity, cache
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        from api.embeddings import cosine_similarity
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-9)

    def test_orthogonal_vectors(self):
        from api.embeddings import cosine_similarity
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-9)

    def test_opposite_vectors(self):
        from api.embeddings import cosine_similarity
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-9)

    def test_known_angle(self):
        from api.embeddings import cosine_similarity
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        # cos(45°) ≈ 0.7071
        assert cosine_similarity(a, b) == pytest.approx(math.cos(math.pi / 4), abs=1e-6)

    def test_zero_vector_returns_zero(self):
        from api.embeddings import cosine_similarity
        a = [0.0, 0.0]
        b = [1.0, 1.0]
        assert cosine_similarity(a, b) == 0.0


class TestGetEmbedding:
    def test_cache_miss_calls_api_then_caches(self, db_path):
        from api.embeddings import get_embedding

        mock_embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]

        with patch("api.embeddings.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.embeddings.create.return_value = mock_response

            result = get_embedding("python", db_path)
            assert result == mock_embedding
            mock_client.embeddings.create.assert_called_once()

            # Verify cached in DB
            con = sqlite3.connect(db_path)
            row = con.execute(
                "SELECT embedding FROM skill_embeddings WHERE skill_text = ?",
                ("python",),
            ).fetchone()
            con.close()
            assert row is not None
            cached = json.loads(row[0])
            assert cached == mock_embedding

    def test_cache_hit_skips_api(self, db_path):
        from api.embeddings import get_embedding

        # Pre-populate cache
        embedding = [0.5, 0.5, 0.5]
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "text-embedding-3-small", json.dumps(embedding)),
        )
        con.commit()
        con.close()

        with patch("api.embeddings.openai") as mock_openai:
            result = get_embedding("python", db_path)
            assert result == embedding
            # API should NOT be called
            mock_openai.OpenAI.assert_not_called()

    def test_normalizes_text(self, db_path):
        from api.embeddings import get_embedding

        # Pre-populate with normalized key
        embedding = [0.1, 0.2]
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "text-embedding-3-small", json.dumps(embedding)),
        )
        con.commit()
        con.close()

        with patch("api.embeddings.openai"):
            # Should find cache even with different casing/whitespace
            assert get_embedding("  Python  ", db_path) == embedding

    def test_no_api_key_returns_none(self, db_path):
        from api.embeddings import get_embedding

        with patch("api.embeddings.openai") as mock_openai:
            mock_openai.OpenAI.side_effect = Exception("No API key")
            result = get_embedding("python", db_path)
            assert result is None

    def test_api_error_returns_none(self, db_path):
        from api.embeddings import get_embedding

        with patch("api.embeddings.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.embeddings.create.side_effect = Exception("API error")
            result = get_embedding("python", db_path)
            assert result is None


class TestGetEmbeddingsBatch:
    def test_batch_calls_api_for_misses_only(self, db_path):
        from api.embeddings import get_embeddings_batch

        # Pre-populate "python" in cache
        cached_emb = [0.1, 0.2]
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "text-embedding-3-small", json.dumps(cached_emb)),
        )
        con.commit()
        con.close()

        api_emb = [0.3, 0.4]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=api_emb)]

        with patch("api.embeddings.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.embeddings.create.return_value = mock_response

            result = get_embeddings_batch(["python", "sql"], db_path)
            assert result["python"] == cached_emb
            assert result["sql"] == api_emb
            # Only "sql" should be sent to API
            call_args = mock_client.embeddings.create.call_args
            assert call_args.kwargs["input"] == ["sql"]

    def test_empty_list_returns_empty(self, db_path):
        from api.embeddings import get_embeddings_batch

        result = get_embeddings_batch([], db_path)
        assert result == {}

    def test_all_cached_skips_api(self, db_path):
        from api.embeddings import get_embeddings_batch

        for skill, emb in [("python", [0.1]), ("sql", [0.2])]:
            con = sqlite3.connect(db_path)
            con.execute(
                "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
                (skill, "text-embedding-3-small", json.dumps(emb)),
            )
            con.commit()
            con.close()

        with patch("api.embeddings.openai") as mock_openai:
            result = get_embeddings_batch(["python", "sql"], db_path)
            assert result["python"] == [0.1]
            assert result["sql"] == [0.2]
            mock_openai.OpenAI.assert_not_called()

    def test_no_api_key_returns_cached_only(self, db_path):
        from api.embeddings import get_embeddings_batch

        cached_emb = [0.1]
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "text-embedding-3-small", json.dumps(cached_emb)),
        )
        con.commit()
        con.close()

        with patch("api.embeddings.openai") as mock_openai:
            mock_openai.OpenAI.side_effect = Exception("No key")
            result = get_embeddings_batch(["python", "sql"], db_path)
            # python from cache, sql missing
            assert result["python"] == cached_emb
            assert "sql" not in result
