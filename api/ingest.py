import json
import os
from datetime import datetime, timezone
from pathlib import Path

from api.db.queries import upsert_job, get_job_by_id


def _compute_tier(score: int) -> str:
    if score >= 50:
        return "A"
    if score >= 30:
        return "B"
    return "C"


def _to_date(date_str: str | None) -> str:
    if not date_str:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).date().isoformat()


def ingest(db_path: str, jobagent_dir: str) -> dict:
    output_dir = Path(jobagent_dir) / "output"
    json_files = sorted(output_dir.glob("jobs_*.json"))

    inserted = 0
    updated = 0
    skipped = 0

    now = datetime.now(timezone.utc).isoformat()

    for f in json_files:
        try:
            jobs = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue

        for raw in jobs:
            job_id = raw.get("id") or raw.get("job_id")
            if not job_id:
                skipped += 1
                continue

            rag = raw.get("rag_score") or {}
            # Use RAG score when available; fall back to heuristic fit_score saved by
            # jobagent's save_results(). Default 0 only when neither is present.
            score = rag.get("score", 0) if rag else int(raw.get("fit_score") or 0)
            tier = _compute_tier(score)

            parsed = raw.get("parsed") or {}
            # Preserve raw description in parsed blob so CV generation can use it
            if raw.get("description") and not parsed.get("description"):
                parsed = dict(parsed)
                parsed["description"] = raw["description"]
            location_type = parsed.get("location_type") or ("remote" if raw.get("is_remote") else "unknown")
            domain = parsed.get("domain")

            date_posted = _to_date(raw.get("date_posted"))

            existing = get_job_by_id(db_path, job_id)

            record = {
                "job_id": job_id,
                "title": raw.get("title"),
                "company": raw.get("company"),
                "location": raw.get("location"),
                "url": raw.get("job_url"),
                "location_type": location_type,
                "domain": domain,
                "score": score,
                "tier": tier,
                "parsed": json.dumps(parsed),
                "scored": json.dumps(rag) if rag else None,
                "first_seen": existing["first_seen"] if existing else date_posted,
                "last_seen": date_posted,
                "ingested_at": now,
            }

            upsert_job(db_path, record)
            if existing:
                updated += 1
            else:
                inserted += 1

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


if __name__ == "__main__":
    import argparse
    from api.db.init import init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("--jobagent-dir", default="../jobagent")
    parser.add_argument("--db", default="data/jobseeker.db")
    args = parser.parse_args()

    init_db(args.db)
    result = ingest(args.db, args.jobagent_dir)
    print(f"Ingest complete: {result['inserted']} inserted, {result['updated']} updated, {result['skipped']} skipped")
