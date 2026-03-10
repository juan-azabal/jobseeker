"""Agent-facing endpoints for the GHA pipeline.

All routes are authenticated with X-Ingest-Key (same as /api/ingest).
These endpoints replace the file-based profile and seen_ids access pattern.
"""

import os
import sqlite3

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from api.db.queries import get_active_profile_ids, get_profile_yaml_by_profile_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _verify_ingest_key(x_ingest_key: str = Header(...)):
    """Validate machine-to-machine auth via X-Ingest-Key header."""
    ingest_secret = os.environ.get("INGEST_API_KEY", "")
    if not ingest_secret or x_ingest_key != ingest_secret:
        raise HTTPException(status_code=403, detail="Invalid ingest key")


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------


@router.get("/profiles", dependencies=[Depends(_verify_ingest_key)])
def list_profiles(db: str = Depends(_db_path)):
    """Return active profile IDs for the GHA pipeline.

    A profile is active when the user has profile_id + profile_yaml in DB
    AND yaml.user.active is not false.

    Response: [{"profile_id": "..."}, ...]
    Replaces: reading YAML file names from agent/config/profiles/
    """
    profile_ids = get_active_profile_ids(db)
    return [{"profile_id": pid} for pid in profile_ids]


@router.get("/profile/{profile_id}", dependencies=[Depends(_verify_ingest_key)])
def get_profile(profile_id: str, db: str = Depends(_db_path)):
    """Return the profile_yaml string for the given profile_id.

    Response: {"profile_id": "...", "profile_yaml": "..."}
    Replaces: reading agent/config/profiles/{profile_id}.yaml from disk
    """
    yaml_str = get_profile_yaml_by_profile_id(db, profile_id)
    if yaml_str is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")
    return {"profile_id": profile_id, "profile_yaml": yaml_str}


# ---------------------------------------------------------------------------
# Seen IDs endpoints
# ---------------------------------------------------------------------------


class SeenIdsPayload(BaseModel):
    job_ids: list[str]


@router.get("/seen-ids/{profile_id}", dependencies=[Depends(_verify_ingest_key)])
def get_seen_ids(profile_id: str, db: str = Depends(_db_path)):
    """Return all seen job IDs for a profile.

    Response: {"profile_id": "...", "job_ids": ["id1", "id2", ...]}
    """
    con = _connect(db)
    rows = con.execute(
        "SELECT job_id FROM seen_job_ids WHERE profile_id = ? ORDER BY first_seen_at",
        (profile_id,),
    ).fetchall()
    con.close()
    return {"profile_id": profile_id, "job_ids": [r["job_id"] for r in rows]}


@router.post("/seen-ids/{profile_id}", dependencies=[Depends(_verify_ingest_key)])
def add_seen_ids(profile_id: str, payload: SeenIdsPayload, db: str = Depends(_db_path)):
    """Upsert seen job IDs for a profile (INSERT OR IGNORE).

    Response: {"added": N}
    """
    con = _connect(db)
    con.executemany(
        "INSERT OR IGNORE INTO seen_job_ids (profile_id, job_id) VALUES (?, ?)",
        [(profile_id, job_id) for job_id in payload.job_ids],
    )
    added = con.total_changes
    con.commit()
    con.close()
    logger.info("seen_ids.added", profile_id=profile_id, count=added)
    return {"added": added}


@router.delete("/seen-ids/{profile_id}", dependencies=[Depends(_verify_ingest_key)])
def clear_seen_ids(profile_id: str, db: str = Depends(_db_path)):
    """Clear all seen job IDs for a profile.

    Response: {"deleted": N}
    """
    con = _connect(db)
    con.execute("DELETE FROM seen_job_ids WHERE profile_id = ?", (profile_id,))
    deleted = con.total_changes
    con.commit()
    con.close()
    logger.info("seen_ids.cleared", profile_id=profile_id, count=deleted)
    return {"deleted": deleted}
