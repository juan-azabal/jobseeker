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


@router.post("", dependencies=[Depends(_verify_ingest_key)])
def ingest_jobs(payload: IngestPayload):
    """Receive job data from GitHub Actions and ingest into the database."""
    from api.ingest import ingest_from_list

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    result = ingest_from_list(db_path, payload.jobs)
    return result
