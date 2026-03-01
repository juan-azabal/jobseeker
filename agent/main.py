"""
JobAgent - Phase 2: Scrape -> Pre-filter -> Parse -> RAG Score -> Rank

Usage:
  python main.py              # normal run (uses cache for already-processed jobs)
  python main.py --no-score   # skip RAG scoring, heuristic only (fast)
  python main.py --refresh    # clear cache, reprocess everything from scratch
  python main.py --rescore    # keep parsed data, redo all RAG scores (e.g. after rubric change)
"""

import sys

import structlog

from logging_setup import configure_logging
from user_config import load_profile, list_profiles, is_profile_active, resolve_profile_paths
from scoring import load_heuristic_config as _load_heuristic_config

# Re-exported for test-suite backward compatibility (test_ranked_jobs_v2, test_ranked_jobs_v1_elimination)
from display import ranked_jobs, print_summary  # noqa: F401

from pipeline import run_pipeline, PipelineOptions

configure_logging()
logger = structlog.get_logger("agent.main")


def main():
    args = sys.argv[1:]
    skip_scoring = "--no-score" in args
    full_refresh = "--refresh" in args
    rescore_only = "--rescore" in args
    send_email = "--notify" in args

    profile_id = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile_id = args[idx + 1]
    if not profile_id:
        available = list_profiles()
        if not available:
            print("ERROR: No profiles found in config/profiles/. Create one first.")
            return
        profile_id = available[0]

    profile = load_profile(profile_id)
    if not is_profile_active(profile):
        print(f"Profile '{profile_id}' is inactive (user.active: false) — skipping.")
        return

    _load_heuristic_config(profile)
    paths = resolve_profile_paths(profile_id, profile)

    if full_refresh:
        mode = "refresh"
    elif rescore_only:
        mode = "rescore"
    elif skip_scoring:
        mode = "no_score"
    else:
        mode = "full"

    opts = PipelineOptions(
        mode=mode,
        skip_scoring=skip_scoring,
        full_refresh=full_refresh,
        rescore_only=rescore_only,
        send_email=send_email,
    )
    run_pipeline(profile_id, profile, paths, opts)


if __name__ == "__main__":
    main()
