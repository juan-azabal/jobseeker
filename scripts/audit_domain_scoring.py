#!/usr/bin/env python3
"""Audit domain scoring paths for jobs in the database.

Loads sample jobs from the DB and shows how each one scores through all
three domain scoring paths (enum, keyword, semantic) with a given profile.
Also shows the jobs.domain column vs parsed.domain to spot reparse drift.

Usage:
    python scripts/audit_domain_scoring.py [profile_id] [--limit N] [--db path]

Example:
    python scripts/audit_domain_scoring.py juan --limit 30
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_sample_jobs(db_path: str, limit: int = 30) -> list[dict]:
    """Load sample jobs with parsed data from the DB."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT j.job_id, j.title, j.company, j.location, j.domain, j.parsed
            FROM jobs j
            WHERE j.parsed IS NOT NULL
            ORDER BY j.last_seen DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        jobs = []
        for row in rows:
            parsed = json.loads(row["parsed"] or "{}")
            jobs.append({
                "id": row["job_id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "domain_col": row["domain"],  # jobs.domain column (updated by reparse)
                "description": "",
                "parsed": parsed,
            })
        return jobs
    finally:
        conn.close()


def run_audit(profile_id: str, db_path: str, limit: int) -> None:
    from api.scoring import (
        load_profile_data, _infer_domain, _semantic_domain_score, heuristic_score,
        _DOMAIN_KEYWORDS,
    )

    profile = load_profile_data(profile_id)
    if not profile:
        print(f"ERROR: Could not load profile for '{profile_id}'")
        sys.exit(1)

    jobs = load_sample_jobs(db_path, limit=limit)
    if not jobs:
        print("No jobs found in DB (with parsed data)")
        return

    print(f"\nDomain Scoring Audit — profile: {profile_id}")
    print(f"DB: {db_path}  |  Jobs: {len(jobs)}")
    print(f"\nDomain weights: {profile['domains']}\n")

    header = (
        f"{'Title':<35} {'Company':<18} "
        f"{'Parsed':>9} {'DB.col':>9} {'Inferred':>9} {'Path':>8} {'Score':>6}"
    )
    print(header)
    print("-" * len(header))

    for job in jobs:
        parsed = job.get("parsed") or {}
        raw_domain = parsed.get("domain", "?")
        db_domain = job.get("domain_col") or "—"

        # Scoring cascade: enum match → keyword override → semantic fallback
        inferred = _infer_domain(parsed)

        # Determine which path was used
        if raw_domain != "other":
            path = "enum"
        elif inferred != "other":
            path = "keyword"
        else:
            path = "semantic"

        # Domain contribution
        if inferred != "other":
            domain_score = profile["domains"].get(inferred, 0)
        else:
            domain_score = _semantic_domain_score(profile, parsed, job, db_path)

        # Flag drift: jobs.domain differs from parsed.domain (reparse updated it)
        drift = " *" if db_domain not in ("—", raw_domain) else ""

        title = (job["title"] or "?")[:34]
        company = (job["company"] or "?")[:17]
        print(
            f"{title:<35} {company:<18} "
            f"{raw_domain:>9} {db_domain:>9} {inferred:>9} "
            f"{path:>8} {domain_score:>+6}{drift}"
        )

    print("\n" + "-" * len(header))
    print("Path legend: enum=parser domain used, keyword=_DOMAIN_KEYWORDS override, semantic=embedding fallback")
    print("Score: domain contribution to heuristic_score. * = jobs.domain differs from parsed.domain (reparsed).")


def main():
    parser = argparse.ArgumentParser(description="Audit domain scoring for jobs in DB")
    parser.add_argument("profile_id", nargs="?", default="juan", help="Profile ID to use")
    parser.add_argument("--limit", type=int, default=30, help="Number of jobs to audit")
    parser.add_argument(
        "--db",
        default=os.environ.get("DB_PATH", "data/jobseeker.db"),
        help="SQLite DB path",
    )
    args = parser.parse_args()
    run_audit(args.profile_id, args.db, args.limit)


if __name__ == "__main__":
    main()
