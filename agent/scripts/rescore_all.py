"""
RAG-score all jobs that only have heuristic scores.

Use this after reparse_all.py to backfill full semantic scores for jobs
that were processed without going through the normal main.py RAG pipeline.

Usage:
    cd ~/Proyectos/jobsearch/agent && ../venv/bin/python3 scripts/rescore_all.py [--all]

Options:
    --all   Re-score even jobs that already have rag_score (refresh all)

What it does:
  1. Loads all unique jobs from output/jobs_*.json (including reparsed files)
  2. Filters to jobs with description + parsed but no rag_score (or all if --all)
  3. Builds the vectorstore from Juan's knowledge files
  4. Calls score_all() (gpt-4o) to produce full semantic scores
  5. Writes results to output/jobs_rescored_<timestamp>.json
  6. Prints ingest command to run

Cost estimate: ~$0.02/job (gpt-4o). For 109 jobs ≈ $2.
"""

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from user_config import load_profile, list_profiles  # noqa: E402
from vectorstore import build_vectorstore  # noqa: E402
from scorer import score_all  # noqa: E402


def load_all_unique_jobs():
    """Load all unique jobs, preferring reparsed > original files.
    Within each group, prefer entries with rag_score, then fit_score."""
    all_jobs: dict[str, dict] = {}
    # Load original files first, then reparsed (reparsed has latest parsed data)
    original_files = sorted(f for f in glob.glob("output/jobs_*.json") if "reparsed" not in f and "rescored" not in f)
    reparsed_files = sorted(f for f in glob.glob("output/jobs_*.json") if "reparsed" in f and "rescored" not in f)

    for path in original_files + reparsed_files:
        try:
            with open(path) as f:
                jobs = json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"  ⚠  Skipping: {path}")
            continue
        for j in jobs:
            jid = j.get("id")
            if not jid:
                continue
            existing = all_jobs.get(jid)
            if existing is None:
                all_jobs[jid] = j
            else:
                has_rag = bool(j.get("rag_score"))
                ex_rag = bool(existing.get("rag_score"))
                # Prefer rag_score; within rag prefer higher score; else prefer latest
                if has_rag and not ex_rag:
                    all_jobs[jid] = j
                elif has_rag and ex_rag:
                    if (j.get("rag_score") or {}).get("score", 0) > (existing.get("rag_score") or {}).get("score", 0):
                        all_jobs[jid] = j
                elif not ex_rag:
                    all_jobs[jid] = j  # take latest if neither has rag
    return list(all_jobs.values())


def main():
    force_all = "--all" in sys.argv

    print("=" * 70)
    print("RAG-score all jobs (backfill)")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if force_all:
        print("(--all: re-scoring everything, including jobs with existing RAG scores)")
    print("=" * 70)

    # Load profile
    profiles = list_profiles()
    if not profiles:
        print("ERROR: No profiles found. Create one first.")
        return
    profile = load_profile(profiles[0])
    print(f"\nProfile: {profiles[0]}")

    # Load jobs
    jobs = load_all_unique_jobs()
    print(f"\nLoaded {len(jobs)} unique jobs from output/ files")

    # Filter: need description + parsed, and either no rag_score or --all
    eligible = [
        j
        for j in jobs
        if j.get("description")
        and len(j.get("description", "")) >= 100
        and j.get("parsed")
        and (force_all or not j.get("rag_score"))
    ]
    already_scored = sum(1 for j in jobs if j.get("rag_score"))
    skipped_no_desc = sum(1 for j in jobs if not j.get("description") or len(j.get("description", "")) < 100)

    print(f"  Already RAG-scored:  {already_scored}")
    print(f"  Skipped (no desc):   {skipped_no_desc}")
    print(f"  To score now:        {len(eligible)}")

    if not eligible:
        print("\nNothing to score — all jobs already have RAG scores.")
        print("Use --all to re-score everything.")
        return

    # Build vectorstore
    print("\nBuilding vectorstore from profile knowledge files...")
    collection = build_vectorstore(profile=profile)

    # RAG score
    print(f"\nRAG-scoring {len(eligible)} jobs with gpt-4o...")
    scored_jobs = score_all(eligible, collection, profile=profile)
    n_scored = sum(1 for j in scored_jobs if j.get("rag_score"))
    n_failed = len(scored_jobs) - n_scored
    print(f"\nResults: {n_scored} scored, {n_failed} failed")

    # Merge scored results back into the full job set
    scored_by_id = {j["id"]: j for j in scored_jobs if j.get("id")}
    all_jobs_by_id = {j["id"]: j for j in jobs if j.get("id")}
    all_jobs_by_id.update(scored_by_id)
    final_jobs = list(all_jobs_by_id.values())

    # Save
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"output/jobs_rescored_{timestamp}.json"

    clean = [{k: v for k, v in j.items() if not k.startswith("_")} for j in final_jobs]
    with open(out_path, "w") as f:
        json.dump(clean, f, indent=2, default=str)

    total_rag = sum(1 for j in clean if j.get("rag_score"))
    print(f"\n>> Saved {len(clean)} jobs to {out_path}")
    print(f"   Total with RAG score: {total_rag}/{len(clean)}")
    print("\nNext step: ingest into jobsearch:")
    print("  cd ~/Proyectos/jobsearch && python3 -m api.ingest")


if __name__ == "__main__":
    main()
