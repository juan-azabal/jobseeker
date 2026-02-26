"""Reparse + rescore existing jobs for v1→v2 migration.

Re-parses cached jobs with parser v1.4 (adds role_function field), then
re-scores with rubric v2 (technical_depth + profile_evidence grades), and
ingests results back to the Railway DB.

Skips jobs that are already applied or dismissed (present in applied.yaml).

Usage:
    cd agent && ../venv/bin/python scripts/reparse_rescore.py --profile juan
    cd agent && ../venv/bin/python scripts/reparse_rescore.py --profile juan --dry-run

Options:
    --profile PROFILE_ID   Profile to process (required)
    --dry-run              Print job count and cost estimate only, no API calls
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from user_config import load_profile, resolve_profile_paths  # noqa: E402
from jobcache import load_cache, update_cache, save_cache  # noqa: E402
from parser import parse_jd  # noqa: E402

# Cost constants (from main.py comments)
_COST_PARSE = 0.001  # gpt-4o-mini per job
_COST_SCORE = 0.040  # gpt-4o per job


def _load_applied_ids(applied_path: str) -> set:
    """Return set of job IDs that are applied or dismissed."""
    if not os.path.exists(applied_path):
        return set()
    try:
        import yaml  # noqa: PLC0415

        with open(applied_path) as f:
            data = yaml.safe_load(f) or {}
        return set(data.get("applied", {}).get("ids", []))
    except Exception as e:
        print(f"⚠  Could not load applied IDs from {applied_path}: {e}")
        return set()


def _post_to_railway(jobs: list, profile_id: str) -> bool:
    """POST reparsed/rescored jobs to Railway ingest endpoint.

    Returns True on success, False if credentials missing or request fails.
    """
    url = os.environ.get("RAILWAY_URL", "").rstrip("/")
    key = os.environ.get("INGEST_API_KEY", "")

    if not url or not key:
        print("⚠  RAILWAY_URL or INGEST_API_KEY not set — skipping Railway sync.")
        return False

    if not url.startswith("http"):
        url = f"https://{url}"

    payload = json.dumps({"jobs": jobs, "profile_id": profile_id}).encode()
    req = urllib.request.Request(
        f"{url}/api/ingest",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Ingest-Key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        inserted = body.get("inserted", "?")
        updated = body.get("updated", "?")
        print(f"   ✓ Railway sync: inserted={inserted}, updated={updated}")
        return True
    except urllib.error.HTTPError as e:
        print(f"   ✗ Railway ingest HTTP {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as e:
        print(f"   ✗ Railway ingest error: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Reparse + rescore existing cached jobs for v1→v2 migration.")
    ap.add_argument("--profile", required=True, help="Profile ID (e.g. juan)")
    ap.add_argument("--dry-run", action="store_true", help="Print job count and cost estimate only; no API calls")
    args = ap.parse_args()

    profile_id = args.profile
    dry_run = args.dry_run

    print("=" * 70)
    print(f"Reparse + Rescore — {profile_id}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if dry_run:
        print("(--dry-run: no API calls)")
    print("=" * 70)

    # Load profile
    try:
        profile = load_profile(profile_id)
    except FileNotFoundError:
        print(f"ERROR: Profile '{profile_id}' not found in config/profiles/")
        sys.exit(1)

    paths = resolve_profile_paths(profile_id, profile)
    applied_ids = _load_applied_ids(paths["applied"])

    # Load jobs from local cache
    cache = load_cache()
    if not cache:
        print("ERROR: No jobs in local cache. Run main.py first.")
        sys.exit(1)

    all_jobs = list(cache.values())
    print(f"\nCache: {len(all_jobs)} total jobs")

    # Filter to eligible: not applied/dismissed, has description + parsed
    eligible = [
        j
        for j in all_jobs
        if j.get("id") not in applied_ids
        and j.get("description")
        and len(j.get("description", "")) >= 100
        and j.get("parsed")
    ]
    n_applied = sum(1 for j in all_jobs if j.get("id") in applied_ids)
    n_no_desc = sum(
        1
        for j in all_jobs
        if j.get("id") not in applied_ids and (not j.get("description") or len(j.get("description", "")) < 100)
    )
    n_already_v2 = sum(1 for j in eligible if (j.get("rag_score") or {}).get("technical_depth") is not None)

    print(f"  Applied/dismissed:      {n_applied}")
    print(f"  Skipped (no desc):      {n_no_desc}")
    print(f"  Eligible for migration: {len(eligible)}")
    print(f"    of which already v2:  {n_already_v2}")

    if not eligible:
        print("\nNothing to process.")
        sys.exit(0)

    cost_est = round(len(eligible) * (_COST_PARSE + _COST_SCORE), 2)
    print(f"\nCost estimate: ~${cost_est} ({len(eligible)} jobs × ${_COST_PARSE + _COST_SCORE:.3f}/job)")

    if dry_run:
        print("\n--dry-run: stopping here. Remove flag to execute.")
        sys.exit(0)

    # ── Step 1: Re-parse with parser v1.4 (adds role_function) ──────────────
    print(f"\n── Step 1: Re-parsing {len(eligible)} jobs with parser v1.4...")
    reparsed = []
    n_parse_fail = 0
    for i, job in enumerate(eligible, 1):
        result = parse_jd(job)
        if result.get("parsed"):
            reparsed.append(result)
        else:
            n_parse_fail += 1
            print(f"   [{i:3}/{len(eligible)}] ⚠  Parse failed: {job.get('title')} — {result.get('parse_error')}")
        if i % 10 == 0:
            print(f"   [{i:3}/{len(eligible)}] parsed so far...")

    n_with_rf = sum(1 for j in reparsed if (j.get("parsed") or {}).get("role_function"))
    print(f"   Parsed: {len(reparsed)}, with role_function: {n_with_rf}, failed: {n_parse_fail}")

    if not reparsed:
        print("All parses failed — aborting.")
        sys.exit(1)

    # ── Step 2: Re-score with rubric v2 (technical_depth + profile_evidence) ─
    print(f"\n── Step 2: Re-scoring {len(reparsed)} jobs with rubric v2...")
    try:
        from vectorstore import build_vectorstore  # noqa: PLC0415
        from scorer import score_all  # noqa: PLC0415

        collection = build_vectorstore(profile=profile)
        scored = score_all(reparsed, collection, profile=profile)
    except Exception as e:
        print(f"   ✗ Scoring error: {e}")
        print("   Ingesting parse results only (no v2 grades).")
        scored = reparsed

    n_scored_v2 = sum(1 for j in scored if (j.get("rag_score") or {}).get("technical_depth") is not None)
    print(f"   Scored v2: {n_scored_v2}/{len(scored)}")

    # ── Step 3: Ingest to Railway DB ─────────────────────────────────────────
    print(f"\n── Step 3: Ingesting {len(scored)} jobs to Railway DB...")
    railway_ok = _post_to_railway(scored, profile_id)

    # ── Step 4: Refresh local cache ───────────────────────────────────────────
    added = update_cache(cache, scored)
    save_cache(cache)
    print(f"   Local cache refreshed: {added} entries updated")

    # Summary
    print("\n" + "=" * 70)
    print("Done.")
    print(f"  Reparsed:     {len(reparsed)}/{len(eligible)}")
    print(f"  Scored v2:    {n_scored_v2}/{len(scored)}")
    print(f"  Railway sync: {'✓ ok' if railway_ok else '⚠  skipped (set RAILWAY_URL + INGEST_API_KEY)'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
