import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

INGEST_SECRET = os.environ.get("INGEST_API_KEY", "")


def _verify_ingest_key(x_ingest_key: str = Header(...)):
    """Validate machine-to-machine auth via X-Ingest-Key header."""
    if not INGEST_SECRET or x_ingest_key != INGEST_SECRET:
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
    result = ingest_from_list(db_path, payload.jobs, profile_id=payload.profile_id)
    return result
