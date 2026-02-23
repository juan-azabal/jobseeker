"""
Job cache: persist parsed + scored jobs across runs to avoid reprocessing.

Cache file: output/cache.json
Key: job ID (deterministic title|company hash from scraper.py)
Value: full job dict including 'parsed' and 'rag_score' fields

Strategy:
  - Prefilter always runs on all scraped jobs (fast, no API calls).
    This ensures changes to applied.yaml / preferences.yaml take effect immediately.
  - Parse + RAG score only run on jobs NOT already in cache.
  - Cache is updated at the end of each run with newly processed jobs.
  - Rejected jobs are never cached (they'll be rejected again cheaply next run).
"""

import json
import os

CACHE_PATH = "output/cache.json"


def load_cache(path=CACHE_PATH):
    """Load job cache from disk. Returns dict of {job_id: job_dict}."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        # Validate: must be a dict
        if not isinstance(data, dict):
            print(f"⚠️  Cache at {path} is malformed, starting fresh.")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Could not load cache ({e}), starting fresh.")
        return {}


def save_cache(cache, path=CACHE_PATH):
    """Persist cache dict to disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=2, default=str)


def split_by_cache(jobs, cache):
    """
    Partition jobs that passed prefilter into cached vs new.

    Returns:
        cached_jobs: list of jobs already in cache (with parsed + rag_score restored)
        new_jobs:    list of jobs not in cache (need parse + score)
    """
    cached_jobs = []
    new_jobs = []

    for job in jobs:
        job_id = job.get("id")
        if job_id and job_id in cache:
            # Restore parsed + rag_score from cache, keep fresh metadata
            # (title/company/location/url may have been updated by scraper)
            cached = dict(cache[job_id])
            # Overwrite scrape-time fields with latest values in case they changed
            for field in ("title", "company", "location", "job_url", "date_posted",
                          "is_remote", "min_amount", "max_amount", "currency", "interval"):
                if field in job:
                    cached[field] = job[field]
            cached_jobs.append(cached)
        else:
            new_jobs.append(job)

    return cached_jobs, new_jobs


def update_cache(cache, jobs):
    """
    Add/update processed jobs in the cache.
    Only caches jobs that have been parsed (to avoid storing empty shells).
    """
    added = 0
    for job in jobs:
        job_id = job.get("id")
        if job_id and job.get("parsed"):
            cache[job_id] = job
            added += 1
    return added


def cache_stats(cache):
    """Return a short stats string for logging."""
    total = len(cache)
    scored = sum(1 for j in cache.values() if j.get("rag_score"))
    return f"{total} cached ({scored} RAG scored)"
