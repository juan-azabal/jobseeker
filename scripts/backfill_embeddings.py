"""One-time backfill: compute and cache embeddings for all known skills.

Reads unique skills from:
  1. User profiles (users.profile_yaml → skills list)
  2. Parsed jobs (jobs.parsed → must_have_skills + nice_to_have_skills)

Then calls get_embeddings_batch() to cache them all.

Usage:
    python -m scripts.backfill_embeddings [--db data/jobseeker.db]
"""

import argparse
import json
import logging
import os
import sqlite3

import yaml

from api.db.init import init_db
from api.embeddings import get_embeddings_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _collect_profile_skills(db_path: str) -> set[str]:
    """Extract all skills from user profile YAMLs stored in DB."""
    skills: set[str] = set()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT profile_yaml FROM users WHERE profile_yaml IS NOT NULL").fetchall()
        for (yaml_text,) in rows:
            try:
                profile = yaml.safe_load(yaml_text)
                for s in profile.get("skills", []):
                    if isinstance(s, str) and s.strip():
                        skills.add(s.strip().lower())
            except Exception:
                continue
    finally:
        conn.close()
    return skills


def _collect_job_skills(db_path: str) -> set[str]:
    """Extract all unique skills from parsed job data."""
    skills: set[str] = set()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT parsed FROM jobs WHERE parsed IS NOT NULL").fetchall()
        for (parsed_json,) in rows:
            try:
                parsed = json.loads(parsed_json)
                for key in ("must_have_skills", "nice_to_have_skills", "technical_stack"):
                    for s in parsed.get(key, []) or []:
                        if isinstance(s, str) and s.strip():
                            skills.add(s.strip().lower())
            except (json.JSONDecodeError, TypeError):
                continue
    finally:
        conn.close()
    return skills


def backfill(db_path: str) -> dict:
    """Compute and cache embeddings for all known skills."""
    init_db(db_path)

    profile_skills = _collect_profile_skills(db_path)
    job_skills = _collect_job_skills(db_path)
    all_skills = profile_skills | job_skills

    if not all_skills:
        logger.info("No skills found to backfill.")
        return {"total": 0, "cached": 0}

    logger.info(
        "Found %d unique skills (%d from profiles, %d from jobs).",
        len(all_skills),
        len(profile_skills),
        len(job_skills),
    )

    result = get_embeddings_batch(list(all_skills), db_path)

    logger.info(
        "Cached %d embeddings for %d unique skills.",
        len(result),
        len(all_skills),
    )
    return {"total": len(all_skills), "cached": len(result)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill skill embeddings cache")
    parser.add_argument(
        "--db",
        default=os.environ.get("DB_PATH", "data/jobseeker.db"),
        help="SQLite database path",
    )
    args = parser.parse_args()
    backfill(args.db)
