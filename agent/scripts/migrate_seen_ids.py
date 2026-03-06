"""Migrate seen_ids .txt files → Railway DB.

One-time migration: reads each file in agent/config/seen_ids/*.txt,
posts all job IDs to POST /api/agent/seen-ids/{profile_id}.

Usage:
    cd agent && ../venv/bin/python scripts/migrate_seen_ids.py [--dry-run]

Requires RAILWAY_URL and INGEST_API_KEY env vars (or a .env file).
"""

import os
import sys
from pathlib import Path

# Allow running from agent/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv(override=True)

from profile_client import post_seen_ids  # noqa: E402


def _load_ids(path: Path) -> list[str]:
    """Return non-empty lines from a seen_ids .txt file."""
    try:
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    except OSError:
        return []


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    railway_url = os.environ.get("RAILWAY_URL", "").strip()
    ingest_key = os.environ.get("INGEST_API_KEY", "").strip()
    if not railway_url or not ingest_key:
        print("ERROR: RAILWAY_URL and INGEST_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    seen_dir = Path(__file__).parent.parent / "config" / "seen_ids"
    if not seen_dir.exists():
        print(f"ERROR: {seen_dir} not found.", file=sys.stderr)
        sys.exit(1)

    files = sorted(seen_dir.glob("*.txt"))
    if not files:
        print("No .txt files found in seen_ids/. Nothing to migrate.")
        return

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating {len(files)} profile(s) to {railway_url}")
    total_posted = 0

    for txt_file in files:
        profile_id = txt_file.stem
        job_ids = _load_ids(txt_file)
        if not job_ids:
            print(f"  {profile_id}: (empty, skipping)")
            continue

        print(f"  {profile_id}: {len(job_ids)} IDs", end="")
        if dry_run:
            print(" [would POST]")
            continue

        try:
            added = post_seen_ids(railway_url, ingest_key, profile_id, job_ids)
            print(f" → {added} new")
            total_posted += added
        except RuntimeError as e:
            print(f" → ERROR: {e}", file=sys.stderr)

    if not dry_run:
        print(f"\nDone. Total new IDs persisted: {total_posted}")


if __name__ == "__main__":
    main()
