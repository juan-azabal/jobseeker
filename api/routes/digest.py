"""GET /api/digest/{user_id} — machine-to-machine endpoint for the email notifier.

Returns today's scored and tiered jobs for a user, using the exact same
scoring path as list_jobs(period="today"). Auth: X-Ingest-Key header.

Phase 1.4: path param changed from profile_id (str) to user_id (int).
"""

import os
from datetime import date

import structlog
from fastapi import APIRouter, Depends, HTTPException

from api.db.queries import get_jobs, get_profile_id_by_user_id
from api.routes.ingest import _verify_ingest_key
from api.routes.jobs import _load_user_geo, _score_and_tier_jobs
from api.scoring import load_profile_data

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/digest", tags=["digest"])

_RESPONSE_FIELDS = frozenset(
    {
        "job_id",
        "title",
        "company",
        "location",
        "location_type",
        "url",
        "score",
        "tier",
        "geo_restricted",
        "domain",
        "role_function",
        "eligibility_warning",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_interval",
        "first_seen",
    }
)

_INTERNAL_FIELDS = (
    "_parsed_dict",
    "parsed",
    "ujs_score",
    "ujs_tier",
    "ujs_scored",
    "ujs_technical_grade",
    "ujs_profile_grade",
    "ujs_scored_v2",
)


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _strip_job(job: dict) -> dict:
    """Return only response-safe fields, dropping internal scoring state."""
    for field in _INTERNAL_FIELDS:
        job.pop(field, None)
    return {k: v for k, v in job.items() if k in _RESPONSE_FIELDS}


@router.get("/{user_id}", dependencies=[Depends(_verify_ingest_key)])
def get_digest(user_id: int):
    """Return today's scored jobs for the given user_id.

    Used by the agent notifier (Step 11) to ensure email and web scores match.
    """
    db_path = _db_path()
    today = date.today().isoformat()

    profile_id = get_profile_id_by_user_id(db_path, user_id)
    if profile_id is None:
        raise HTTPException(status_code=404, detail=f"User not found: {user_id}")

    jobs = get_jobs(db_path, date_from=today, user_id=user_id)

    profile = load_profile_data(profile_id)
    home_locations, home_regions = _load_user_geo(profile_id)

    jobs = _score_and_tier_jobs(jobs, profile, home_locations, home_regions, user_id=user_id)

    stripped = [_strip_job(job) for job in jobs]

    summary = {
        "tier_a": sum(1 for j in stripped if j.get("tier") == "A"),
        "tier_b": sum(1 for j in stripped if j.get("tier") == "B"),
        "tier_c": sum(1 for j in stripped if j.get("tier") == "C"),
        "total": len(stripped),
    }

    logger.info(
        "Digest served",
        profile_id=profile_id,
        user_id=user_id,
        total=summary["total"],
        tier_a=summary["tier_a"],
        tier_b=summary["tier_b"],
    )

    return {
        "jobs": stripped,
        "summary": summary,
        "profile_id": profile_id,
        "date": today,
    }
