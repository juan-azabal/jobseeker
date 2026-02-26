"""
Step 0.4 — Smoke tests against real scraper output files.

Skipped in CI (requires output/jobs_*.json files).
Run manually: pytest agent/tests/test_smoke_output.py -v -m smoke

These tests verify data quality invariants on actual pipeline output:
- No 'nan' string locations
- Job IDs are deterministic (recomputed ID matches stored ID)
- No near-dupes (same normalised title+company but different IDs)
- All site values are from the known set
"""

import glob
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Path to output directory (relative to agent/ or absolute via env override)
_OUTPUT_DIR = os.environ.get(
    "AGENT_OUTPUT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "output"),
)

KNOWN_SITES = {"indeed", "linkedin", "google", "glassdoor", "greenhouse", "lever", "ashby", "wttj"}


def _load_output_files():
    """Return list of (filepath, list[dict]) for all jobs_*.json output files."""
    pattern = os.path.join(_OUTPUT_DIR, "jobs_*.json")
    files = sorted(glob.glob(pattern))
    result = []
    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                result.append((path, data))
        except Exception:
            pass
    return result


def _skip_if_no_output():
    files = _load_output_files()
    if not files:
        pytest.skip(f"No jobs_*.json output files found in {_OUTPUT_DIR}")
    return files


@pytest.mark.smoke
def test_no_nan_locations():
    """All location values must be '' or a non-'nan' string."""
    files = _skip_if_no_output()
    violations = []
    for path, jobs in files:
        for job in jobs:
            loc = job.get("location", "")
            if isinstance(loc, str) and loc.lower() == "nan":
                violations.append(f"{os.path.basename(path)}: job '{job.get('title')}' has location='nan'")
    assert not violations, "Found 'nan' location values:\n" + "\n".join(violations[:10])


@pytest.mark.smoke
def test_job_ids_are_deterministic():
    """Recomputed make_job_id(title, company) must match stored id for every job."""
    from scraper import make_job_id

    files = _skip_if_no_output()
    mismatches = []
    for path, jobs in files:
        for job in jobs:
            title = job.get("title", "")
            company = job.get("company", "")
            stored_id = job.get("id", "")
            recomputed = make_job_id(title, company)
            if recomputed != stored_id:
                mismatches.append(
                    f"{os.path.basename(path)}: '{title}' @ '{company}' "
                    f"stored={stored_id!r} recomputed={recomputed!r}"
                )
    assert not mismatches, (
        f"Found {len(mismatches)} ID mismatches (first 10):\n" + "\n".join(mismatches[:10])
    )


@pytest.mark.smoke
def test_no_duplicate_ids_within_file():
    """No two jobs in the same file should have the same id."""
    files = _skip_if_no_output()
    for path, jobs in files:
        ids = [j.get("id") for j in jobs]
        unique_ids = set(ids)
        assert len(ids) == len(unique_ids), (
            f"{os.path.basename(path)}: {len(ids) - len(unique_ids)} duplicate job IDs"
        )


@pytest.mark.smoke
def test_no_near_dupes_different_ids():
    """No two jobs with same normalised title+company but different IDs in same file."""
    from scraper import _normalize_for_id

    files = _skip_if_no_output()
    for path, jobs in files:
        seen: dict[str, str] = {}  # normalised_key → stored_id
        dupes = []
        for job in jobs:
            key = f"{_normalize_for_id(job.get('title', ''))}|{_normalize_for_id(job.get('company', ''))}"
            stored_id = job.get("id", "")
            if key in seen and seen[key] != stored_id:
                dupes.append(f"  '{job.get('title')}' @ '{job.get('company')}' (ids: {seen[key]} vs {stored_id})")
            seen[key] = stored_id
        assert not dupes, f"{os.path.basename(path)}: near-dupes with different IDs:\n" + "\n".join(dupes[:5])


@pytest.mark.smoke
def test_all_site_values_known():
    """All 'site' field values must be in the known set."""
    files = _skip_if_no_output()
    unknown = []
    for path, jobs in files:
        for job in jobs:
            site = job.get("site", "")
            if site and site not in KNOWN_SITES:
                unknown.append(f"{os.path.basename(path)}: site={site!r} in '{job.get('title')}'")
    assert not unknown, "Unknown site values:\n" + "\n".join(unknown[:10])
