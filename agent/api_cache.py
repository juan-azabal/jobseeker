"""Cross-user parsed-job cache via Railway DB.

When multiple users' pipelines scrape the same job, only the first one needs
to call OpenAI for parsing.  Subsequent pipelines fetch the already-parsed
data from the shared Railway DB, skipping the LLM call.

Graceful fallback: if RAILWAY_URL / INGEST_API_KEY are not set, or the API
is unreachable, returns an empty dict so the pipeline proceeds as before.
"""

import json
import os
import urllib.request
import urllib.error


def fetch_existing_parsed(
    job_ids: list[str],
    railway_url: str | None = None,
    ingest_key: str | None = None,
    timeout: int = 10,
) -> dict[str, dict]:
    """Check Railway DB for already-parsed jobs.

    Args:
        job_ids: List of job IDs to look up.
        railway_url: Railway API base URL (reads RAILWAY_URL env if None).
        ingest_key: Ingest API key (reads INGEST_API_KEY env if None).
        timeout: HTTP timeout in seconds.

    Returns:
        Dict mapping job_id -> parsed dict for jobs found in the DB.
        Empty dict on any failure (never raises).
    """
    if not job_ids:
        return {}

    url = railway_url or os.environ.get("RAILWAY_URL", "")
    key = ingest_key or os.environ.get("INGEST_API_KEY", "")

    if not url or not key:
        return {}

    # Normalise URL
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"

    endpoint = f"{url}/api/ingest/batch-lookup"
    payload = json.dumps({"job_ids": job_ids}).encode()

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Ingest-Key": key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        return body.get("jobs", {})
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError) as exc:
        print(f"⚠  DB cache lookup failed (continuing without): {exc}")
        return {}
    except Exception as exc:
        print(f"⚠  DB cache lookup unexpected error: {exc}")
        return {}
