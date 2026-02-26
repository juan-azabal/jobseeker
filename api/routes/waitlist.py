import os
import re
import sqlite3

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.middleware.auth import get_current_admin

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["waitlist"])

_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


class WaitlistRequest(BaseModel):
    email: str


@router.post("/api/waitlist", status_code=201)
def join_waitlist(body: WaitlistRequest):
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
