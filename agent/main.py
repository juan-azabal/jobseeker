"""
JobAgent - Phase 2: Scrape -> Pre-filter -> Parse -> RAG Score -> Rank

Usage:
  python main.py              # normal run: scrape all profiles, score all
  python main.py --no-score   # skip RAG scoring, heuristic only (fast)
  python main.py --refresh    # clear cache, reprocess everything from scratch
  python main.py --rescore    # keep parsed data, redo all RAG scores (e.g. after rubric change)
  python main.py --profile ID # only score profile ID (scraping still uses all active profiles)
"""

import os
import sys

import structlog

from logging_setup import configure_logging
from user_config import is_profile_active, resolve_profile_paths
from profile_client import fetch_profiles, fetch_profile
from scoring import load_heuristic_config as _load_heuristic_config

from pipeline import run_pipeline, PipelineOptions, _to_dicts, _log_merge_stats

configure_logging()
logger = structlog.get_logger("agent.main")


def _get_api_config() -> tuple[str, str]:
    """Return (railway_url, ingest_key) from env. Raises if missing."""
    railway_url = os.environ.get("RAILWAY_URL", "").strip()
    ingest_key = os.environ.get("INGEST_API_KEY", "").strip()
    if not railway_url:
        raise RuntimeError("RAILWAY_URL env var is required")
    if not ingest_key:
        raise RuntimeError("INGEST_API_KEY env var is required")
    return railway_url, ingest_key


def _union_target_countries(profiles: list[tuple[str, dict]]) -> list[str]:
    """Collect the union of target countries across all profiles."""
    from geo import derive_target_countries  # noqa: PLC0415

    seen: set[str] = set()
    result: list[str] = []
    for _pid, profile in profiles:
        home_locs = profile.get("user", {}).get("home_locations", [])
        countries = derive_target_countries(home_locs) or profile.get("target", {}).get("wttj_countries") or []
        for c in countries:
            if c not in seen:
                seen.add(c)
                result.append(c)
    return result


def _unified_scrape(
    profiles: list[tuple[str, dict]], watchlist_path: str = "config/watchlist.yaml"
) -> tuple[list[dict], int]:
    """Scrape jobs once across all profiles. Returns (jobs_as_dicts, geo_rejected_count)."""
    from search_generator import generate_unified_queries  # noqa: PLC0415
    from scraper import run_scraper_from_queries  # noqa: PLC0415
    from ats_scraper import run_watchlist_scraper  # noqa: PLC0415
    from wttj_scraper import run_wttj_scraper  # noqa: PLC0415
    from merger import merge_jobs  # noqa: PLC0415

    target_countries = _union_target_countries(profiles)
    queries = generate_unified_queries(profiles)
    print(f"\nUnified scraping: {len(queries)} queries across {len(profiles)} profile(s)")

    all_raw = run_scraper_from_queries(queries)
    geo_rejected = 0
    try:
        ats_jobs, ats_geo = run_watchlist_scraper(config_path=watchlist_path, target_countries=target_countries or None)
        all_raw.extend(ats_jobs)
        geo_rejected += ats_geo
    except Exception as e:
        print(f"\nWatchlist error (continuing without): {e}")
    try:
        wttj_countries = target_countries or ["ES"]
        all_raw.extend(run_wttj_scraper(target_countries=wttj_countries))
    except Exception as e:
        print(f"\nWTTJ error (continuing without): {e}")

    raw_jobs = merge_jobs(all_raw)
    _log_merge_stats(raw_jobs)
    jobs = _to_dicts(raw_jobs)
    logger.info("unified_scrape_complete", total_jobs=len(jobs), n_queries=len(queries))
    print(f"\nCombined: {len(jobs)} total jobs")
    return jobs, geo_rejected


def main():
    args = sys.argv[1:]
    skip_scoring = "--no-score" in args
    full_refresh = "--refresh" in args
    rescore_only = "--rescore" in args
    send_email = "--notify" in args

    requested_profile = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            requested_profile = args[idx + 1]

    # Load all active profiles from Railway DB via API
    railway_url, ingest_key = _get_api_config()
    all_profile_ids = fetch_profiles(railway_url, ingest_key)
    if not all_profile_ids:
        print("ERROR: No profiles found in Railway DB (GET /api/agent/profiles returned empty).")
        return

    all_profiles: list[tuple[str, dict]] = []
    for pid in all_profile_ids:
        try:
            p = fetch_profile(railway_url, ingest_key, pid)
            if is_profile_active(p):
                all_profiles.append((pid, p))
        except Exception as e:
            print(f"Warning: could not load profile '{pid}': {e}")

    if not all_profiles:
        print("ERROR: No active profiles could be loaded.")
        return

    # Determine which profiles to score
    if requested_profile:
        profiles_to_score = [(pid, p) for pid, p in all_profiles if pid == requested_profile]
        if not profiles_to_score:
            print(f"ERROR: Profile '{requested_profile}' not found or inactive.")
            return
    else:
        profiles_to_score = all_profiles

    # Run unified scraping ONCE across all active profiles
    pre_scraped_jobs, _geo_rejected = _unified_scrape(all_profiles)

    if full_refresh:
        mode = "refresh"
    elif rescore_only:
        mode = "rescore"
    elif skip_scoring:
        mode = "no_score"
    else:
        mode = "full"

    # Run per-profile pipeline on shared job pool
    for profile_id, profile in profiles_to_score:
        _load_heuristic_config(profile)
        paths = resolve_profile_paths(profile_id, profile)
        opts = PipelineOptions(
            mode=mode,
            skip_scoring=skip_scoring,
            full_refresh=full_refresh,
            rescore_only=rescore_only,
            send_email=send_email,
        )
        run_pipeline(profile_id, profile, paths, opts, pre_scraped_jobs=pre_scraped_jobs)


if __name__ == "__main__":
    main()
