"""
Reparse all existing jobs with the current parser-prompt.md version.

Use this after a parser prompt update to backfill parsed data for jobs that
were already processed with an older version.

Usage:
    cd ~/Proyectos/jobsearch/agent && ../venv/bin/python3 scripts/reparse_all.py

What it does:
  1. Loads all unique jobs from output/jobs_*.json (dedup by id, newest run wins)
  2. Strips the existing 'parsed' field so parse_all() re-processes each job
  3. Calls parse_all() with the current parser-prompt.md (gpt-4o-mini)
  4. Writes reparsed jobs to output/jobs_reparsed_<timestamp>.json
  5. Prints a before/after sample to verify improvement

Cost estimate: ~$0.001/job. For 116 jobs ≈ $0.12.
"""

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Run from jobagent root
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from parser import parse_all  # noqa: E402 — must run after chdir


def load_all_unique_jobs():
    """Load all unique jobs from output/jobs_*.json.

    Dedup strategy: for each job_id, keep the entry with the best score data
    (prefer rag_score, then fit_score). If no scored version exists, use the
    most recent file's entry. This prevents newer scraper-only runs (no scores)
    from overwriting scored entries produced by earlier full runs.
    """
    all_jobs: dict[str, dict] = {}  # job_id -> best entry seen so far
    files = sorted(glob.glob("output/jobs_*.json"))  # sorted = chronological
    for path in files:
        if "reparsed" in path:
            continue  # skip previously reparsed files
        with open(path) as f:
            try:
                jobs = json.load(f)
            except json.JSONDecodeError:
                print(f"  ⚠  Skipping malformed file: {path}")
                continue
        for j in jobs:
            jid = j.get("id")
            if not jid:
                continue
            existing = all_jobs.get(jid)
            if existing is None:
                all_jobs[jid] = j
            else:
                # Prefer entries that have a score; within scored entries, keep highest
                has_rag = bool(j.get("rag_score"))
                has_fit = bool(j.get("fit_score"))
                ex_rag = bool(existing.get("rag_score"))
                ex_fit = bool(existing.get("fit_score"))
                if has_rag and not ex_rag:
                    all_jobs[jid] = j  # new has rag, old doesn't → upgrade
                elif has_rag and ex_rag:
                    if (j.get("rag_score") or {}).get("score", 0) > (existing.get("rag_score") or {}).get("score", 0):
                        all_jobs[jid] = j  # new has higher rag score
                elif not ex_rag and has_fit and not ex_fit:
                    all_jobs[jid] = j  # new has fit_score, old has nothing
                elif not ex_rag and not has_rag:
                    all_jobs[jid] = j  # neither has rag, use latest (chronological order)
    return list(all_jobs.values())


def main():
    print("=" * 70)
    print("Reparse all jobs with current parser-prompt.md")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    jobs = load_all_unique_jobs()
    print(f"\nLoaded {len(jobs)} unique jobs from output/ files")

    with_desc = [j for j in jobs if j.get("description") and len(j["description"]) >= 100]
    skipped = len(jobs) - len(with_desc)
    if skipped:
        print(f"  Skipping {skipped} jobs with missing/short description")

    # Snapshot before: count soft-skill contamination
    def has_soft_skills(j):
        p = j.get("parsed") or {}
        if not isinstance(p, dict):
            return False
        mh = p.get("truly_required") or p.get("must_have_skills") or []
        return any(
            any(w in s.lower() for w in ["year", "degree", "bachelor", "experience", "fluent", "communication"])
            for s in mh
        )

    before_soft = sum(1 for j in with_desc if has_soft_skills(j))
    before_parsed = sum(1 for j in with_desc if j.get("parsed"))
    print("\nBefore reparse:")
    print(f"  Jobs with parsed data:                {before_parsed}/{len(with_desc)}")
    print(f"  Jobs with soft skills in must_have:   {before_soft}/{before_parsed}")

    # Strip 'parsed' and 'parse_error' to force re-parse
    for j in with_desc:
        j.pop("parsed", None)
        j.pop("parse_error", None)

    # Re-parse with current parser-prompt.md (v1.1)
    print(f"\nRe-parsing {len(with_desc)} jobs with gpt-4o-mini...")
    reparsed = parse_all(with_desc, model="gpt-4o-mini")

    # After snapshot
    after_soft = sum(1 for j in reparsed if has_soft_skills(j))
    after_parsed = sum(1 for j in reparsed if j.get("parsed"))
    new_field = sum(1 for j in reparsed if (j.get("parsed") or {}).get("experience_requirements"))
    with_restriction = sum(1 for j in reparsed if (j.get("parsed") or {}).get("remote_restriction"))

    print("\nAfter reparse:")
    print(f"  Jobs with parsed data:                {after_parsed}/{len(reparsed)}")
    print(f"  Jobs with soft skills in must_have:   {after_soft}/{after_parsed}  (was {before_soft})")
    print(f"  Jobs with experience_requirements:    {new_field}/{after_parsed}")
    print(f"  Jobs with remote_restriction set:     {with_restriction}/{after_parsed}")

    # Save
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"output/jobs_reparsed_{timestamp}.json"

    clean = []
    for j in reparsed:
        clean.append({k: v for k, v in j.items() if not k.startswith("_")})

    with open(out_path, "w") as f:
        json.dump(clean, f, indent=2, default=str)

    print(f"\n>> Saved to {out_path}  ({len(clean)} jobs)")
    print("\nNext step: ingest into jobsearch:")
    print("  cd ~/Proyectos/jobsearch && python3 -m api.ingest")


if __name__ == "__main__":
    main()
