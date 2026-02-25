"""Embedding service with SQLite cache for semantic skill matching.

Computes text embeddings via OpenAI text-embedding-3-small. Caches results
in the skill_embeddings table (migration 011) to avoid redundant API calls.

Falls back gracefully if OPENAI_API_KEY is missing or the API errors.
"""

import json
import logging
import math
import os
import sqlite3

logger = logging.getLogger(__name__)

MODEL = "text-embedding-3-small"

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Pure Python, no numpy."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Cache helpers (direct SQLite — will be refactored to db/queries in 12.4)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return text.strip().lower()


def _load_from_cache(db_path: str, skill_text: str) -> list[float] | None:
    """Read embedding from SQLite cache. Returns None on miss."""
    try:
        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT embedding FROM skill_embeddings WHERE skill_text = ? AND model = ?",
            (_normalize(skill_text), MODEL),
        ).fetchone()
        con.close()
        if row:
            return json.loads(row[0])
    except Exception as exc:
        logger.warning("Cache read failed for %r: %s", skill_text, exc)
    return None


def _load_batch_from_cache(db_path: str, skills: list[str]) -> dict[str, list[float]]:
    """Bulk-read embeddings from cache. Returns dict of normalized_text → embedding."""
    result: dict[str, list[float]] = {}
    if not skills:
        return result
    try:
        normalized = [_normalize(s) for s in skills]
        con = sqlite3.connect(db_path)
        placeholders = ",".join("?" for _ in normalized)
        rows = con.execute(
            f"SELECT skill_text, embedding FROM skill_embeddings "
            f"WHERE skill_text IN ({placeholders}) AND model = ?",
            normalized + [MODEL],
        ).fetchall()
        con.close()
        for row in rows:
            result[row[0]] = json.loads(row[1])
    except Exception as exc:
        logger.warning("Batch cache read failed: %s", exc)
    return result


def _save_to_cache(db_path: str, skill_text: str, embedding: list[float]) -> None:
    """Store embedding in SQLite cache."""
    try:
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT OR REPLACE INTO skill_embeddings (skill_text, model, embedding) "
            "VALUES (?, ?, ?)",
            (_normalize(skill_text), MODEL, json.dumps(embedding)),
        )
        con.commit()
        con.close()
    except Exception as exc:
        logger.warning("Cache write failed for %r: %s", skill_text, exc)


def _save_batch_to_cache(
    db_path: str, items: list[tuple[str, list[float]]]
) -> None:
    """Bulk-store embeddings in SQLite cache."""
    if not items:
        return
    try:
        con = sqlite3.connect(db_path)
        con.executemany(
            "INSERT OR REPLACE INTO skill_embeddings (skill_text, model, embedding) "
            "VALUES (?, ?, ?)",
            [(_normalize(text), MODEL, json.dumps(emb)) for text, emb in items],
        )
        con.commit()
        con.close()
    except Exception as exc:
        logger.warning("Batch cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# OpenAI API calls
# ---------------------------------------------------------------------------


def _call_openai(texts: list[str]) -> list[list[float]] | None:
    """Call OpenAI embeddings API. Returns None on any failure."""
    if openai is None:
        logger.info("openai package not installed — skipping embedding")
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not set — skipping embedding")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.embeddings.create(model=MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as exc:
        logger.warning("OpenAI embeddings API call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_embedding(text: str, db_path: str) -> list[float] | None:
    """Get embedding for a single text. Cache-first, API on miss.

    Returns None if no API key or API error and not in cache.
    """
    normalized = _normalize(text)

    # Check cache
    cached = _load_from_cache(db_path, normalized)
    if cached is not None:
        return cached

    # Call API
    try:
        client = openai.OpenAI()
        response = client.embeddings.create(model=MODEL, input=[normalized])
        embedding = response.data[0].embedding
        _save_to_cache(db_path, normalized, embedding)
        return embedding
    except Exception as exc:
        logger.warning("get_embedding failed for %r: %s", text, exc)
        return None


def get_embeddings_batch(
    texts: list[str], db_path: str
) -> dict[str, list[float]]:
    """Get embeddings for multiple texts. Cache-first, API only for misses.

    Returns dict of normalized_text → embedding. Missing texts (API failure)
    are omitted from the result.
    """
    if not texts:
        return {}

    # Normalize and deduplicate
    norm_map: dict[str, str] = {}  # normalized → original (first seen)
    for t in texts:
        n = _normalize(t)
        if n not in norm_map:
            norm_map[n] = t

    normalized_keys = list(norm_map.keys())

    # Bulk cache lookup
    cached = _load_batch_from_cache(db_path, normalized_keys)
    result = dict(cached)

    # Determine misses
    misses = [k for k in normalized_keys if k not in cached]
    if not misses:
        return result

    # Call API for misses
    try:
        client = openai.OpenAI()
        response = client.embeddings.create(model=MODEL, input=misses)
        new_embeddings = [item.embedding for item in response.data]
        to_cache = []
        for text, emb in zip(misses, new_embeddings):
            result[text] = emb
            to_cache.append((text, emb))
        _save_batch_to_cache(db_path, to_cache)
    except Exception as exc:
        logger.warning("Batch embedding API call failed: %s", exc)

    return result
