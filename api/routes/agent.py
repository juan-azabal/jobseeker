"""Agent-facing endpoints for the GHA pipeline.

All routes are authenticated with X-Ingest-Key (same as /api/ingest).
These endpoints replace the file-based profile and seen_ids access pattern.

Phase 1.3: primary identifiers are integer user_id.
  - /api/agent/profiles         → returns [{"user_id": N, "profile_id": "..."}]
  - /api/agent/profile/{user_id}     → accepts integer user_id (primary)
  - /api/agent/profile-by-name/{profile_id} → backward compat; removed in Phase 2
  - /api/agent/seen-ids/{user_id}    → accepts integer user_id
"""

import os
import sqlite3

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from api.db.queries import (
    get_active_profiles,
    get_profile_id_by_user_id,
    get_profile_yaml_by_profile_id,
    get_profile_yaml_by_user_id,
)

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
    """Return active profiles for the GHA pipeline.

    Response: [{"user_id": N, "profile_id": "..."}, ...]
    Replaces: reading YAML file names from agent/config/profiles/
    """
    return get_active_profiles(db)


@router.get("/profile/{user_id}", dependencies=[Depends(_verify_ingest_key)])
def get_profile(user_id: int, db: str = Depends(_db_path)):
    """Return the profile_yaml string for the given integer user_id.

    Response: {"user_id": N, "profile_id": "...", "profile_yaml": "..."}
    Replaces: reading agent/config/profiles/{profile_id}.yaml from disk
    """
    yaml_str = get_profile_yaml_by_user_id(db, user_id)
    if yaml_str is None:
        raise HTTPException(status_code=404, detail=f"User {user_id!r} not found or no profile")
    profile_id = get_profile_id_by_user_id(db, user_id) or ""
    return {"user_id": user_id, "profile_id": profile_id, "profile_yaml": yaml_str}


@router.get("/profile-by-name/{profile_id}", dependencies=[Depends(_verify_ingest_key)])
def get_profile_by_name(profile_id: str, db: str = Depends(_db_path)):
    """Backward-compat endpoint: look up profile by profile_id string.

    Deprecated — removed in Phase 2. Use /api/agent/profile/{user_id} instead.
    Response: {"profile_id": "...", "profile_yaml": "..."}
    """
    yaml_str = get_profile_yaml_by_profile_id(db, profile_id)
    if yaml_str is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")
    return {"profile_id": profile_id, "profile_yaml": yaml_str}


# ---------------------------------------------------------------------------
# Seen IDs endpoints (integer user_id)
# ---------------------------------------------------------------------------


class SeenIdsPayload(BaseModel):
    job_ids: list[str]


@router.get("/seen-ids/{user_id}", dependencies=[Depends(_verify_ingest_key)])
def get_seen_ids(user_id: int, db: str = Depends(_db_path)):
    """Return all seen job IDs for a user.

    Response: {"user_id": N, "job_ids": ["id1", "id2", ...]}
    """
    con = _connect(db)
    rows = con.execute(
        "SELECT job_id FROM seen_job_ids WHERE user_id = ? ORDER BY first_seen_at",
        (user_id,),
    ).fetchall()
    con.close()
    return {"user_id": user_id, "job_ids": [r["job_id"] for r in rows]}


@router.post("/seen-ids/{user_id}", dependencies=[Depends(_verify_ingest_key)])
def add_seen_ids(user_id: int, payload: SeenIdsPayload, db: str = Depends(_db_path)):
    """Upsert seen job IDs for a user (INSERT OR IGNORE).

    Response: {"added": N}
    """
    con = _connect(db)
    con.executemany(
        "INSERT OR IGNORE INTO seen_job_ids (user_id, job_id) VALUES (?, ?)",
        [(user_id, job_id) for job_id in payload.job_ids],
    )
    added = con.total_changes
    con.commit()
    con.close()
    logger.info("seen_ids.added", user_id=user_id, count=added)
    return {"added": added}


@router.delete("/seen-ids/{user_id}", dependencies=[Depends(_verify_ingest_key)])
def clear_seen_ids(user_id: int, db: str = Depends(_db_path)):
    """Clear all seen job IDs for a user.

    Response: {"deleted": N}
    """
    con = _connect(db)
    cur = con.execute("DELETE FROM seen_job_ids WHERE user_id = ?", (user_id,))
    deleted = cur.rowcount
    con.commit()
    con.close()
    logger.info("seen_ids.cleared", user_id=user_id, count=deleted)
    return {"deleted": deleted}
