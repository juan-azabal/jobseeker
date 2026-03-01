import json
from datetime import datetime, timezone
from pathlib import Path

import structlog
from api.db.queries import upsert_job, get_job_by_id, upsert_user_job_score, get_user_id_by_profile_id, cleanup_old_jobs
from api.scoring import compute_tier

logger = structlog.get_logger(__name__)


def _to_date(date_str: str | None) -> str:
    if not date_str:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).date().isoformat()


def ingest_from_list(db_path: str, raw_jobs: list[dict], profile_id: str | None = None) -> dict:
    """Ingest a list of job dicts into the database.

    Common job data (title, company, parsed, etc.) goes into the shared `jobs` table.
    When profile_id is provided, per-user scores go into `user_job_scores`.
    """
    inserted = 0
    updated = 0
    skipped = 0
    scored = 0

    now = datetime.now(timezone.utc).isoformat()

    # Resolve profile_id → user_id for per-user score storage
    user_id = None
    if profile_id:
        user_id = get_user_id_by_profile_id(db_path, profile_id)
        if user_id is None:
            logger.warning(
                "profile_id=%r not found in users table — RAG scores will NOT be stored "
                "(db=%s). User must log in at least once before scores can be saved.",
                profile_id,
                db_path,
            )
        else:
            logger.info("Resolved profile_id=%r → user_id=%d", profile_id, user_id)

    for raw in raw_jobs:
        job_id = raw.get("id") or raw.get("job_id")
        if not job_id:
            skipped += 1
            logger.debug("Skipped job with no id — keys present: %s", list(raw.keys()))
            continue

        parsed = raw.get("parsed") or {}
        # Preserve raw description in parsed blob so CV generation can use it
        if raw.get("description") and not parsed.get("description"):
            parsed = dict(parsed)
            parsed["description"] = raw["description"]
        location_type = parsed.get("location_type") or ("remote" if raw.get("is_remote") else "unknown")
        domain = parsed.get("domain")
        role_function = parsed.get("role_function")
        company_ctx = parsed.get("company_context") or {}

        date_posted = _to_date(raw.get("date_posted"))
        existing = get_job_by_id(db_path, job_id)

        # Upsert common job data (shared across all users)
        sources = raw.get("sources") or []
        record = {
            "job_id": job_id,
            "title": raw.get("title"),
            "company": raw.get("company"),
            "location": raw.get("location"),
            "url": raw.get("job_url"),
            "location_type": location_type,
            "domain": domain,
            "parsed": json.dumps(parsed),
            "role_function": role_function,
            "first_seen": existing["first_seen"] if existing else date_posted,
            "last_seen": date_posted,
            "ingested_at": now,
            # Enriched scraper fields (populated by RawJob merger; null-safe)
            "company_url": raw.get("company_url"),
            "company_logo": raw.get("company_logo"),
            "company_industry": raw.get("company_industry"),
            "company_size": raw.get("company_employees_label"),
            "job_level": raw.get("job_level"),
            "salary_min": raw.get("min_amount"),
            "salary_max": raw.get("max_amount"),
            "salary_currency": raw.get("currency"),
            "salary_interval": raw.get("interval"),
            "salary_source": raw.get("salary_source"),
            "country": raw.get("country"),
            "city": raw.get("city"),
            "remote_type": raw.get("remote_type"),
            "sources": json.dumps(sources),
            # Parser v1.5 fields (extracted from parsed JSON blob into real columns)
            "role_in_plain_english": parsed.get("role_in_plain_english"),
            "company_stage": company_ctx.get("stage"),
            "company_tone": company_ctx.get("tone"),
        }

        upsert_job(db_path, record)
        if existing:
            updated += 1
        else:
            inserted += 1

        # Store per-user score when profile_id is provided and job has a RAG score
        if user_id:
            rag = raw.get("rag_score")
            if rag and isinstance(rag, dict):
                scored_json = json.dumps(rag)
                is_v2 = rag.get("technical_depth") is not None
                if is_v2:
                    # v2 rubric: store categorical grades; numeric score computed at query time
                    upsert_user_job_score(
                        db_path,
                        user_id,
                        job_id,
                        score=0,
                        tier="C",
                        scored_json=scored_json,
                        technical_grade=rag.get("technical_depth"),
                        profile_grade=rag.get("profile_evidence"),
                        scored_v2=1,
                    )
                    scored += 1
                elif rag.get("score") is not None:
                    # v1 rubric: store numeric score unchanged
                    score = rag["score"]
                    tier = compute_tier(score)
                    upsert_user_job_score(db_path, user_id, job_id, score, tier, scored_json)
                    scored += 1

    # Prune jobs not seen in the last 90 days to keep the DB bounded
    deleted = cleanup_old_jobs(db_path)

    # Pre-compute embeddings for new job skills (best-effort, non-blocking)
    try:
        _precompute_skill_embeddings(db_path, raw_jobs)
    except Exception as exc:
        logger.warning("Embedding pre-computation failed (non-fatal): %s", exc)

    return {"inserted": inserted, "updated": updated, "skipped": skipped, "scored": scored, "deleted": deleted}


def _precompute_skill_embeddings(db_path: str, raw_jobs: list[dict]) -> None:
    """Extract unique skills from ingested jobs and cache their embeddings."""
    try:
        from api.embeddings import get_embeddings_batch

        skills: set[str] = set()
        for raw in raw_jobs:
            parsed = raw.get("parsed") or {}
            for key in (
                "truly_required",
                "must_have_skills",
                "preferred_skills",
                "nice_to_have_skills",
                "technical_stack",
            ):
                for s in parsed.get(key, []) or []:
                    if isinstance(s, str) and s.strip():
                        skills.add(s.strip().lower())

        if skills:
            get_embeddings_batch(list(skills), db_path)
            logger.info("Pre-computed embeddings for %d job skills", len(skills))
    except Exception as exc:
        logger.warning("Embedding pre-computation failed (non-fatal): %s", exc)


def ingest(db_path: str, jobagent_dir: str, profile_id: str | None = None) -> dict:
    """File-based ingest: read JSON files from agent/output/ and ingest."""
    output_dir = Path(jobagent_dir) / "output"
    json_files = sorted(output_dir.glob("jobs_*.json"))

    all_jobs = []
    for f in json_files:
        try:
            all_jobs.extend(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            pass

    return ingest_from_list(db_path, all_jobs, profile_id=profile_id)


if __name__ == "__main__":
    import argparse
    from api.db.init import init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("--jobagent-dir", default="agent")
    parser.add_argument("--db", default="data/jobseeker.db")
    args = parser.parse_args()

    init_db(args.db)
    result = ingest(args.db, args.jobagent_dir)
    print(f"Ingest complete: {result['inserted']} inserted, {result['updated']} updated, {result['skipped']} skipped")
