import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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
    profile_id: str | None = None


@router.get("/status", dependencies=[Depends(_verify_ingest_key)])
def ingest_status():
    """Return aggregate pipeline health stats (total jobs, last ingest time, scored counts)."""
    from api.db.queries import get_ingest_status

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    return get_ingest_status(db_path)


@router.post("", dependencies=[Depends(_verify_ingest_key)])
def ingest_jobs(payload: IngestPayload):
    """Receive job data from GitHub Actions and ingest into the database.

    When profile_id is provided, per-user scores are stored in user_job_scores.
    """
    from api.ingest import ingest_from_list

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    logger.info(
        "Ingest request: %d jobs, profile_id=%r, db_path=%s",
        len(payload.jobs), payload.profile_id, db_path,
    )
    result = ingest_from_list(db_path, payload.jobs, profile_id=payload.profile_id)
    logger.info(
        "Ingest complete: inserted=%d updated=%d skipped=%d scored=%d deleted=%d (db=%s)",
        result.get("inserted", 0), result.get("updated", 0),
        result.get("skipped", 0), result.get("scored", 0),
        result.get("deleted", 0), db_path,
    )
    return result
