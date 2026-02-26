"""
Migration script: recompute job IDs after make_job_id normalization change (Step 0.2).

The new _normalize_for_id() strips gender suffixes, legal entity suffixes, and
normalizes punctuation. This changes the hash for many jobs.

Usage:
    python migrate_job_ids.py [--db PATH]

Default DB path: ../data/jobseeker.db (relative to agent/ directory).

On collision (two old IDs map to the same new ID), keeps the record with more
non-null parsed fields.
"""

import argparse
import json
import sqlite3

from scraper import make_job_id


def count_non_null_parsed_fields(parsed_json: str | None) -> int:
    """Count how many parsed fields are non-null in a JSON string."""
    if not parsed_json:
        return 0
    try:
        data = json.loads(parsed_json)
        return sum(1 for v in data.values() if v is not None)
    except Exception:
        return 0


def migrate(db_path: str, dry_run: bool = False) -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT job_id, title, company, parsed FROM jobs")
    rows = cur.fetchall()

    updates: dict[str, tuple[str, int]] = {}  # new_id → (old_id, parsed_field_count)
    collisions = 0
    changed = 0

    for row in rows:
        old_id = row["job_id"]
        title = row["title"] or ""
        company = row["company"] or ""
        new_id = make_job_id(title, company)

        if new_id == old_id:
            continue

        changed += 1
        field_count = count_non_null_parsed_fields(row["parsed"])

        if new_id in updates:
            # Collision: keep the record with more non-null parsed fields
            collisions += 1
            existing_count = updates[new_id][1]
            if field_count > existing_count:
                updates[new_id] = (old_id, field_count)
        else:
            updates[new_id] = (old_id, field_count)

    print(f"Total jobs: {len(rows)}")
    print(f"IDs that will change: {changed}")
    print(f"Collisions resolved (kept richer record): {collisions}")

    if dry_run:
        print("DRY RUN — no changes made.")
        con.close()
        return

    for new_id, (old_id, _) in updates.items():
        cur.execute("UPDATE jobs SET job_id = ? WHERE job_id = ?", (new_id, old_id))

    con.commit()
    con.close()
    print(f"Migration complete. Updated {len(updates)} job IDs.")
    print("Next: clear agent/config/seen_ids/<profile>.txt to avoid missed jobs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recompute job IDs after normalization change.")
    parser.add_argument("--db", default="../data/jobseeker.db", help="Path to SQLite DB")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without modifying DB")
    args = parser.parse_args()

    migrate(args.db, dry_run=args.dry_run)
