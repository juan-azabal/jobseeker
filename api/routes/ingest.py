import os

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _verify_ingest_key(x_ingest_key: str = Header(...)):
    """Validate machine-to-machine auth via X-Ingest-Key header.

    Reads INGEST_API_KEY at request time so Railway env var changes
    take effect without restarting (and avoids stale module-level capture).
    """
    ingest_secret = os.environ.get("INGEST_API_KEY", "")
    if not ingest_secret or x_ingest_key != ingest_secret:
        raise HTTPException(status_code=403, detail="Invalid ingest key")


class IngestPayload(BaseModel):
    jobs: list[dict]
    user_id: int | None = None  # preferred: integer user_id
    profile_id: str | None = None  # backward compat: resolved to user_id if no user_id


@router.get("/status", dependencies=[Depends(_verify_ingest_key)])
def ingest_status():
    """Return aggregate pipeline health stats (total jobs, last ingest time, scored counts)."""
    from api.db.queries import get_ingest_status

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    return get_ingest_status(db_path)


class BatchLookupPayload(BaseModel):
    job_ids: list[str]


@router.post("/batch-lookup", dependencies=[Depends(_verify_ingest_key)])
def batch_lookup(payload: BatchLookupPayload):
    """Return parsed data for jobs already in the DB.

    Used by the agent to skip re-parsing jobs that another user's pipeline
    already processed. Only returns jobs with non-null parsed data.
    """
    import json
    from api.db.queries import batch_get_parsed

    if not payload.job_ids:
        return {"jobs": {}}

    # Safety cap — avoid huge IN clauses
    ids = payload.job_ids[:500]

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    rows = batch_get_parsed(db_path, ids)
    result: dict[str, dict] = {}
    for job_id, parsed_str in rows:
        try:
            result[job_id] = json.loads(parsed_str)
        except (json.JSONDecodeError, TypeError):
            continue

    logger.info("batch-lookup: requested=%d, found=%d", len(ids), len(result))
    return {"jobs": result}


@router.post("", dependencies=[Depends(_verify_ingest_key)])
def ingest_jobs(payload: IngestPayload):
    """Receive job data from GitHub Actions and ingest into the database.

    Resolution order for per-user scoring:
    1. user_id (integer) — used directly if present
    2. profile_id (string) — resolved to user_id via DB lookup (backward compat)
    """
    from api.db.queries import get_user_id_by_profile_id
    from api.ingest import ingest_from_list

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")

    # Resolve user_id: prefer explicit int, fall back to profile_id lookup
    user_id = payload.user_id
    if user_id is None and payload.profile_id:
        user_id = get_user_id_by_profile_id(db_path, payload.profile_id)
        if user_id is None:
            logger.warning(
                "Ingest: profile_id=%r not found — RAG scores will NOT be stored",
                payload.profile_id,
            )
        else:
            logger.info("Ingest: resolved profile_id=%r → user_id=%d", payload.profile_id, user_id)

    logger.info(
        "Ingest request: %d jobs, user_id=%r, db_path=%s",
        len(payload.jobs),
        user_id,
        db_path,
    )
    result = ingest_from_list(db_path, payload.jobs, user_id=user_id)
    logger.info(
        "Ingest complete: inserted=%d updated=%d skipped=%d scored=%d deleted=%d (db=%s)",
        result.get("inserted", 0),
        result.get("updated", 0),
        result.get("skipped", 0),
        result.get("scored", 0),
        result.get("deleted", 0),
        db_path,
    )
    return result
