import json
import os
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db.queries import get_jobs, get_job_by_id
from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])

PERIOD_DAYS = {"today": 0, "week": 7, "month": 30}


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _period_to_date_from(period: str | None) -> str | None:
    if not period or period == "all":
        return None
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    if days == 0:
        return date.today().isoformat()
    return (date.today() - timedelta(days=days)).isoformat()


@router.get("")
def list_jobs(
    tier: Annotated[list[str], Query()] = [],
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    effective_date_from = date_from or _period_to_date_from(period)
    tiers = [t.upper() for t in tier] if tier else None
    jobs = get_jobs(_db_path(), tiers=tiers, date_from=effective_date_from, date_to=date_to)
    return {
        "jobs": jobs,
        "filters": {"tier": tier, "period": period or "all"},
        "total": len(jobs),
    }


@router.get("/{job_id}")
def get_job(job_id: str):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    row["parsed"] = json.loads(row["parsed"]) if row.get("parsed") else None
    row["scored"] = json.loads(row["scored"]) if row.get("scored") else None
    return row
