#!/usr/bin/env python3
"""Audit domain scoring paths for jobs in the database.

Loads sample jobs from the DB and shows how each one scores through all
three domain scoring paths (enum, keyword, semantic) with a given profile.

Usage:
    python scripts/audit_domain_scoring.py [profile_id] [--limit N] [--db path]

Example:
    python scripts/audit_domain_scoring.py juan --limit 20
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_sample_jobs(db_path: str, limit: int = 20) -> list[dict]:
    """Load sample jobs with parsed data from the DB."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT j.id, j.title, j.company, j.location, j.parsed_json
            FROM jobs j
            WHERE j.parsed_json IS NOT NULL
            ORDER BY j.date_posted DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        jobs = []
        for row in rows:
            parsed = json.loads(row["parsed_json"] or "{}")
            jobs.append({
                "id": row["id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
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

    header = f"{'Title':<35} {'Company':<20} {'Raw':>5} {'Inferred':>12} {'Path':>10} {'Score':>6}"
    print(header)
    print("-" * len(header))

    for job in jobs:
        parsed = job.get("parsed") or {}
        raw_domain = parsed.get("domain", "?")

        # Path 1: enum match
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

        title = (job["title"] or "?")[:34]
        company = (job["company"] or "?")[:19]
        print(
            f"{title:<35} {company:<20} {raw_domain:>5} {inferred:>12} "
            f"{path:>10} {domain_score:>+6}"
        )

    print("\n" + "-" * len(header))
    print("\nPath legend: enum=parser domain matched, keyword=_DOMAIN_KEYWORDS reclassified, semantic=embedding fallback")
    print("Score: domain contribution to heuristic_score (before other dimensions)")


def main():
    parser = argparse.ArgumentParser(description="Audit domain scoring for jobs in DB")
    parser.add_argument("profile_id", nargs="?", default="juan", help="Profile ID to use")
    parser.add_argument("--limit", type=int, default=20, help="Number of jobs to audit")
    parser.add_argument(
        "--db",
        default=os.environ.get("DB_PATH", "data/jobseeker.db"),
        help="SQLite DB path",
    )
    args = parser.parse_args()
    run_audit(args.profile_id, args.db, args.limit)


if __name__ == "__main__":
    main()
