"""HTTP client for Railway API profile and seen_ids access.

Replaces file-based access patterns:
  - config/profiles/{id}.yaml  → fetch_profile()
  - config/seen_ids/{id}.txt   → fetch_seen_ids() / post_seen_ids()

On failure: raises with a clear error message. No silent file fallback.
All callers must provide RAILWAY_URL and INGEST_API_KEY.

Phase 1.6: all endpoints use integer user_id as the primary key.
  fetch_profiles() returns [(user_id, profile_id), ...]
"""

import yaml
import httpx
import structlog

logger = structlog.get_logger(__name__)

_TIMEOUT = 10.0


def fetch_profiles(railway_url: str, ingest_key: str) -> list[tuple[int, str]]:
    """Return list of (user_id, profile_id) pairs from the Railway DB.

    Replaces: reading YAML filenames from config/profiles/
    Raises: RuntimeError on HTTP error or network failure.
    """
    url = f"{railway_url.rstrip('/')}/api/agent/profiles"
    try:
        r = httpx.get(url, headers={"X-Ingest-Key": ingest_key}, timeout=_TIMEOUT)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"fetch_profiles: HTTP {e.response.status_code} from {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"fetch_profiles: network error reaching {url}: {e}") from e

    profiles = r.json()
    result = [(p["user_id"], p["profile_id"]) for p in profiles]
    logger.info("profile_client.fetch_profiles", count=len(result))
    return result


def fetch_profile(railway_url: str, ingest_key: str, user_id: int) -> dict:
    """Return parsed profile dict for the given integer user_id.

    Replaces: yaml.safe_load(open(f"config/profiles/{profile_id}.yaml"))
    Raises: RuntimeError on HTTP error, network failure, or missing profile.
    """
    url = f"{railway_url.rstrip('/')}/api/agent/profile/{user_id}"
    try:
        r = httpx.get(url, headers={"X-Ingest-Key": ingest_key}, timeout=_TIMEOUT)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"fetch_profile(user_id={user_id}): HTTP {e.response.status_code} from {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"fetch_profile(user_id={user_id}): network error reaching {url}: {e}") from e

    data = r.json()
    profile = yaml.safe_load(data["profile_yaml"])
    logger.info("profile_client.fetch_profile", user_id=user_id, profile_id=data.get("profile_id"))
    return profile


def fetch_seen_ids(railway_url: str, ingest_key: str, user_id: int) -> set[str]:
    """Return seen job IDs for a user from the Railway DB.

    Replaces: reading config/seen_ids/{profile_id}.txt
    Raises: RuntimeError on HTTP error or network failure.
    """
    url = f"{railway_url.rstrip('/')}/api/agent/seen-ids/{user_id}"
    try:
        r = httpx.get(url, headers={"X-Ingest-Key": ingest_key}, timeout=_TIMEOUT)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"fetch_seen_ids(user_id={user_id}): HTTP {e.response.status_code} from {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"fetch_seen_ids(user_id={user_id}): network error reaching {url}: {e}") from e

    ids = set(r.json()["job_ids"])
    logger.info("profile_client.fetch_seen_ids", user_id=user_id, count=len(ids))
    return ids


def post_seen_ids(railway_url: str, ingest_key: str, user_id: int, job_ids: list[str]) -> int:
    """Upsert seen job IDs for a user to the Railway DB.

    Replaces: appending to config/seen_ids/{profile_id}.txt
    Returns: number of newly added IDs.
    Raises: RuntimeError on HTTP error or network failure.
    """
    if not job_ids:
        return 0

    url = f"{railway_url.rstrip('/')}/api/agent/seen-ids/{user_id}"
    try:
        r = httpx.post(
            url,
            json={"job_ids": job_ids},
            headers={"X-Ingest-Key": ingest_key},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"post_seen_ids(user_id={user_id}): HTTP {e.response.status_code} from {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"post_seen_ids(user_id={user_id}): network error reaching {url}: {e}") from e

    added = r.json()["added"]
    logger.info("profile_client.post_seen_ids", user_id=user_id, added=added)
    return added
