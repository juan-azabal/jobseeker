"""Embedding service with SQLite cache for semantic skill matching.

Computes text embeddings via OpenAI text-embedding-3-small. Caches results
in the skill_embeddings table (migration 011) to avoid redundant API calls.

Falls back gracefully if OPENAI_API_KEY is missing or the API errors.
"""

import time

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

MODEL = "text-embedding-3-small"
DIMENSIONS = 256

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors using numpy."""
    va, vb = np.asarray(a), np.asarray(b)
    norm = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / norm) if norm > 0 else 0.0


# ---------------------------------------------------------------------------
# Cache helpers (delegated to db/queries.py)
# ---------------------------------------------------------------------------


_MAX_MEMORY_CACHE = 2000  # max entries in process-level cache

# Process-level in-memory cache: avoids repeated SQLite reads within the same
# process lifecycle (e.g. scoring 100 jobs in one request).
_memory_cache: dict[str, list[float]] = {}

# Circuit breaker: after any API failure, skip retries for this many seconds.
# Prevents cascading slow requests when the API is down or quota is exhausted.
_API_BACKOFF_S = 60.0
_api_unavailable_until: float = 0.0


def _api_is_available() -> bool:
    return time.monotonic() >= _api_unavailable_until


def _mark_api_unavailable() -> None:
    global _api_unavailable_until
    _api_unavailable_until = time.monotonic() + _API_BACKOFF_S


def clear_memory_cache() -> None:
    """Clear the in-memory embedding cache (call after profile skill updates)."""
    _memory_cache.clear()


def _normalize(text: str) -> str:
    return text.strip().lower()


def _load_from_cache(db_path: str, skill_text: str) -> list[float] | None:
    """Read embedding from SQLite cache. Returns None on miss."""
    try:
        from api.db.queries import get_cached_embeddings

        result = get_cached_embeddings(db_path, [_normalize(skill_text)])
        return result.get(_normalize(skill_text))
    except Exception as exc:
        logger.warning("Cache read failed for %r: %s", skill_text, exc)
    return None


def _load_batch_from_cache(db_path: str, skills: list[str]) -> dict[str, list[float]]:
    """Bulk-read embeddings from cache."""
    if not skills:
        return {}
    try:
        from api.db.queries import get_cached_embeddings

        return get_cached_embeddings(db_path, [_normalize(s) for s in skills])
    except Exception as exc:
        logger.warning("Batch cache read failed: %s", exc)
    return {}


def _save_to_cache(db_path: str, skill_text: str, embedding: list[float]) -> None:
    """Store embedding in SQLite cache."""
    try:
        from api.db.queries import save_embedding

        save_embedding(db_path, _normalize(skill_text), embedding, MODEL)
    except Exception as exc:
        logger.warning("Cache write failed for %r: %s", skill_text, exc)


def _save_batch_to_cache(db_path: str, items: list[tuple[str, list[float]]]) -> None:
    """Bulk-store embeddings in SQLite cache."""
    if not items:
        return
    try:
        from api.db.queries import save_embeddings_batch

        save_embeddings_batch(
            db_path,
            [(_normalize(text), emb, MODEL) for text, emb in items],
        )
    except Exception as exc:
        logger.warning("Batch cache write failed: %s", exc)


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

    # Call API (skip if circuit breaker is open)
    if not _api_is_available():
        return None
    try:
        client = openai.OpenAI()
        response = client.embeddings.create(
            model=MODEL,
            input=[normalized],
            dimensions=DIMENSIONS,
        )
        embedding = response.data[0].embedding
        _save_to_cache(db_path, normalized, embedding)
        return embedding
    except Exception as exc:
        _mark_api_unavailable()
        logger.warning("get_embedding failed for %r: %s — pausing API calls for %.0fs", text, exc, _API_BACKOFF_S)
        return None


def get_embeddings_batch(texts: list[str], db_path: str) -> dict[str, list[float]]:
    """Get embeddings for multiple texts. Memory cache → SQLite → API.

    Returns dict of normalized_text → embedding. Missing texts (API failure)
    are omitted from the result.
    """
    if not texts:
        return {}

    t_start = time.perf_counter()

    # Normalize and deduplicate
    norm_map: dict[str, str] = {}  # normalized → original (first seen)
    for t in texts:
        n = _normalize(t)
        if n not in norm_map:
            norm_map[n] = t

    normalized_keys = list(norm_map.keys())

    # 1. Check process-level memory cache first
    result: dict[str, list[float]] = {}
    mem_hit_count = 0
    mem_misses = []
    for k in normalized_keys:
        if k in _memory_cache:
            result[k] = _memory_cache[k]
            mem_hit_count += 1
        else:
            mem_misses.append(k)

    sqlite_hit_count = 0
    api_call_count = 0

    if mem_misses:
        # 2. Bulk SQLite cache lookup for memory misses
        cached = _load_batch_from_cache(db_path, mem_misses)
        sqlite_hit_count = len(cached)
        for k, emb in cached.items():
            result[k] = emb
            if len(_memory_cache) < _MAX_MEMORY_CACHE:
                _memory_cache[k] = emb

        # 3. Determine remaining misses (not in memory or SQLite)
        misses = [k for k in mem_misses if k not in cached]

        # 4. Call API for remaining misses (skip if circuit breaker is open)
        if misses and _api_is_available():
            api_call_count = len(misses)
            try:
                client = openai.OpenAI()
                response = client.embeddings.create(
                    model=MODEL,
                    input=misses,
                    dimensions=DIMENSIONS,
                )
                new_embeddings = [item.embedding for item in response.data]
                to_cache = []
                for text, emb in zip(misses, new_embeddings):
                    result[text] = emb
                    to_cache.append((text, emb))
                    if len(_memory_cache) < _MAX_MEMORY_CACHE:
                        _memory_cache[text] = emb
                _save_batch_to_cache(db_path, to_cache)
            except Exception as exc:
                _mark_api_unavailable()
                logger.warning(
                    "Batch embedding API call failed — pausing API calls",
                    error=str(exc),
                    pause_s=_API_BACKOFF_S,
                )

    logger.info(
        "Batch embedding call",
        total_requested=len(texts),
        cache_hits=mem_hit_count + sqlite_hit_count,
        api_calls=api_call_count,
        duration_ms=round((time.perf_counter() - t_start) * 1000, 1),
    )
    return result
