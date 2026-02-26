import os
import re
import sqlite3
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.middleware.auth import get_current_admin

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["waitlist"])

_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

# In-memory IP rate limiter: IP -> list of request timestamps
_rate_limiter: dict[str, list[float]] = {}
_RATE_LIMIT = 5
_RATE_WINDOW = 60.0


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed; False if rate limit exceeded."""
    now = time.time()
    window_start = now - _RATE_WINDOW
    timestamps = _rate_limiter.get(ip, [])
    # Expire old entries
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= _RATE_LIMIT:
        _rate_limiter[ip] = timestamps
        return False
    timestamps.append(now)
    _rate_limiter[ip] = timestamps
    return True


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


class WaitlistRequest(BaseModel):
    email: str


@router.post("/api/waitlist", status_code=201)
def join_waitlist(body: WaitlistRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="rate_limited")

    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="invalid_email")

    db_path = _db_path()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        con.execute("INSERT INTO waitlist (email) VALUES (?)", (email,))
        con.commit()
        logger.info("Waitlist signup", email=email)
        return {"status": "ok"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="already_registered")
    finally:
        con.close()


@router.get("/api/admin/waitlist")
def list_waitlist(admin: dict = Depends(get_current_admin)):
    db_path = _db_path()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, email, created_at FROM waitlist ORDER BY created_at DESC"
    ).fetchall()
    con.close()
    entries = [dict(r) for r in rows]
    return {"total": len(entries), "entries": entries}
