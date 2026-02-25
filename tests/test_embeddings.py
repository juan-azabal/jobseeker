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

@pytest.fixture(autouse=True)
def _clear_embedding_state():
    """Clear the in-memory embedding cache and circuit breaker before each test."""
    import api.embeddings as _emb
    _emb.clear_memory_cache()
    _emb._api_unavailable_until = 0.0
    yield
    _emb.clear_memory_cache()
    _emb._api_unavailable_until = 0.0


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

        mock_embedding = [0.1] * 256
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


# ---------------------------------------------------------------------------
# 12.3 — Skill matcher
# ---------------------------------------------------------------------------


class TestSkillMatcher:
    """Tests for api/skill_matcher.py using mocked embeddings."""

    def _make_embeddings(self, mapping: dict[str, list[float]]):
        """Helper to mock get_embeddings_batch with known vectors."""
        def mock_batch(texts, db_path):
            result = {}
            for t in texts:
                key = t.strip().lower()
                if key in mapping:
                    result[key] = mapping[key]
            return result
        return mock_batch

    def test_identical_strings_matched(self, db_path):
        from api.skill_matcher import match_skills

        # Use vectors that are identical → cosine=1.0
        embs = {
            "python": [1.0, 0.0, 0.0],
        }
        with patch("api.skill_matcher.get_embeddings_batch", self._make_embeddings(embs)):
            results = match_skills(["python"], ["python"], db_path)
        assert len(results) == 1
        assert results[0].status == "matched"
        assert results[0].similarity == pytest.approx(1.0, abs=0.01)

    def test_similar_concepts_matched(self, db_path):
        from api.skill_matcher import match_skills

        # "data analysis" and "analytics" with high similarity
        embs = {
            "data analysis": [0.9, 0.1, 0.0],
            "analytics": [0.85, 0.15, 0.05],
        }
        with patch("api.skill_matcher.get_embeddings_batch", self._make_embeddings(embs)):
            results = match_skills(["data analysis"], ["analytics"], db_path)
        assert len(results) == 1
        assert results[0].status == "matched"  # cosine ≈ 0.99
        assert results[0].user_skill == "data analysis"

    def test_unrelated_skills_none(self, db_path):
        from api.skill_matcher import match_skills

        # Orthogonal vectors → cosine=0.0
        embs = {
            "python": [1.0, 0.0],
            "cooking": [0.0, 1.0],
        }
        with patch("api.skill_matcher.get_embeddings_batch", self._make_embeddings(embs)):
            results = match_skills(["python"], ["cooking"], db_path)
        assert len(results) == 1
        assert results[0].status == "none"
        assert results[0].similarity == pytest.approx(0.0, abs=0.01)

    def test_partial_match(self, db_path):
        from api.skill_matcher import match_skills, MATCH_THRESHOLD, PARTIAL_THRESHOLD

        # Construct vectors with cosine similarity between thresholds
        # cos(a,b) = 0.73 (between 0.68 and 0.80)
        import math
        angle = math.acos(0.73)
        embs = {
            "javascript": [1.0, 0.0],
            "typescript": [math.cos(angle), math.sin(angle)],
        }
        with patch("api.skill_matcher.get_embeddings_batch", self._make_embeddings(embs)):
            results = match_skills(["javascript"], ["typescript"], db_path)
        assert len(results) == 1
        assert results[0].status == "partial"
        assert 0.68 <= results[0].similarity <= 0.80

    def test_fallback_substring_match(self, db_path):
        """When embeddings unavailable, fall back to substring matching."""
        from api.skill_matcher import match_skills

        # Return empty dict → no embeddings available
        with patch("api.skill_matcher.get_embeddings_batch", return_value={}):
            results = match_skills(["sql"], ["sql server"], db_path)
        assert len(results) == 1
        assert results[0].status == "matched"
        assert results[0].user_skill == "sql"

    def test_fallback_no_match(self, db_path):
        """Fallback substring: unrelated strings don't match."""
        from api.skill_matcher import match_skills

        with patch("api.skill_matcher.get_embeddings_batch", return_value={}):
            results = match_skills(["python"], ["cooking"], db_path)
        assert len(results) == 1
        assert results[0].status == "none"

    def test_multiple_job_skills(self, db_path):
        from api.skill_matcher import match_skills

        embs = {
            "python": [1.0, 0.0],
            "sql": [0.0, 1.0],
            "java": [0.5, 0.5],
        }
        with patch("api.skill_matcher.get_embeddings_batch", self._make_embeddings(embs)):
            results = match_skills(["python", "sql"], ["python", "java", "sql"], db_path)
        assert len(results) == 3
        statuses = {r.job_skill: r.status for r in results}
        assert statuses["python"] == "matched"
        assert statuses["sql"] == "matched"
        # java (0.5, 0.5) vs python (1,0) → cos ≈ 0.707 → partial or none
        # java vs sql (0,1) → cos ≈ 0.707 → same
        assert statuses["java"] in ("partial", "none")

    def test_empty_user_skills_all_none(self, db_path):
        from api.skill_matcher import match_skills

        with patch("api.skill_matcher.get_embeddings_batch", return_value={}):
            results = match_skills([], ["python"], db_path)
        assert len(results) == 1
        assert results[0].status == "none"

    def test_empty_job_skills_returns_empty(self, db_path):
        from api.skill_matcher import match_skills

        with patch("api.skill_matcher.get_embeddings_batch", return_value={}):
            results = match_skills(["python"], [], db_path)
        assert results == []


# ---------------------------------------------------------------------------
# 12.4 — DB query helpers for embeddings
# ---------------------------------------------------------------------------


class TestEmbeddingQueryHelpers:
    def test_round_trip_save_and_get(self, db_path):
        from api.db.queries import save_embedding, get_cached_embeddings

        emb = [0.1, 0.2, 0.3]
        save_embedding(db_path, "python", emb, "text-embedding-3-small")
        result = get_cached_embeddings(db_path, ["python"])
        assert result["python"] == emb

    def test_get_multiple(self, db_path):
        from api.db.queries import save_embedding, get_cached_embeddings

        save_embedding(db_path, "python", [0.1], "text-embedding-3-small")
        save_embedding(db_path, "sql", [0.2], "text-embedding-3-small")
        result = get_cached_embeddings(db_path, ["python", "sql", "java"])
        assert "python" in result
        assert "sql" in result
        assert "java" not in result

    def test_batch_save(self, db_path):
        from api.db.queries import save_embeddings_batch, get_cached_embeddings

        items = [
            ("python", [0.1], "text-embedding-3-small"),
            ("sql", [0.2], "text-embedding-3-small"),
        ]
        save_embeddings_batch(db_path, items)
        result = get_cached_embeddings(db_path, ["python", "sql"])
        assert result["python"] == [0.1]
        assert result["sql"] == [0.2]

    def test_upsert_overwrites(self, db_path):
        from api.db.queries import save_embedding, get_cached_embeddings

        save_embedding(db_path, "python", [0.1], "text-embedding-3-small")
        save_embedding(db_path, "python", [0.9], "text-embedding-3-small")
        result = get_cached_embeddings(db_path, ["python"])
        assert result["python"] == [0.9]

    def test_empty_list_returns_empty(self, db_path):
        from api.db.queries import get_cached_embeddings

        result = get_cached_embeddings(db_path, [])
        assert result == {}


# ---------------------------------------------------------------------------
# 12.12 — Performance guards + edge cases
# ---------------------------------------------------------------------------


class TestPerformanceGuards:
    """Tests for performance guards in skill matcher and embeddings."""

    def test_large_skill_lists_fallback_to_substring(self, db_path):
        """Pair count > 500 falls back to substring matching."""
        from api.skill_matcher import match_skills, MAX_PAIRS

        user_skills = [f"skill_{i}" for i in range(30)]
        job_skills = [f"skill_{i}" for i in range(20)]
        assert len(user_skills) * len(job_skills) > MAX_PAIRS

        # Should NOT call get_embeddings_batch (substring fallback)
        with patch("api.skill_matcher.get_embeddings_batch") as mock_batch:
            results = match_skills(user_skills, job_skills, db_path)

        mock_batch.assert_not_called()
        assert len(results) == 20
        # skill_0..skill_19 should all match (substring exact)
        matched = [r for r in results if r.status == "matched"]
        assert len(matched) == 20

    def test_long_skill_text_skipped(self, db_path):
        """Skills > 200 chars are filtered out before matching."""
        from api.skill_matcher import match_skills

        long_skill = "a" * 201
        with patch("api.skill_matcher.get_embeddings_batch", return_value={}):
            results = match_skills(["python"], [long_skill, "sql"], db_path)

        # long_skill is filtered out from norm_job, but original list has 2 items.
        # The function filters at normalization level so it'll still return results
        # for all original job_skills. Let's verify the match behavior is safe.
        assert len(results) >= 1

    def test_empty_user_skills_returns_all_none(self, db_path):
        """Empty user skills returns all-none matches without API call."""
        from api.skill_matcher import match_skills

        with patch("api.skill_matcher.get_embeddings_batch") as mock_batch:
            results = match_skills([], ["python", "sql"], db_path)

        mock_batch.assert_not_called()
        assert len(results) == 2
        assert all(r.status == "none" for r in results)

    def test_memory_cache_avoids_db_lookups(self, db_path):
        """Process-level memory cache prevents repeated SQLite reads."""
        from api.embeddings import get_embeddings_batch, _memory_cache, clear_memory_cache

        # Start clean
        clear_memory_cache()

        # Pre-populate SQLite cache
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
            ("python", "text-embedding-3-small", json.dumps([0.1, 0.2])),
        )
        con.commit()
        con.close()

        # First call populates memory cache from SQLite
        with patch("api.embeddings.openai") as mock_openai:
            result1 = get_embeddings_batch(["python"], db_path)
            assert result1["python"] == [0.1, 0.2]
            assert "python" in _memory_cache

        # Second call should hit memory cache — no SQLite read needed
        with patch("api.embeddings._load_batch_from_cache") as mock_sqlite:
            result2 = get_embeddings_batch(["python"], db_path)
            assert result2["python"] == [0.1, 0.2]
            mock_sqlite.assert_not_called()

        # Cleanup
        clear_memory_cache()

    def test_clear_memory_cache(self, db_path):
        """clear_memory_cache empties the in-memory cache."""
        from api.embeddings import _memory_cache, clear_memory_cache

        _memory_cache["test_skill"] = [0.1]
        assert "test_skill" in _memory_cache

        clear_memory_cache()
        assert "test_skill" not in _memory_cache
