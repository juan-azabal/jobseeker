import os
from fastapi import Depends, HTTPException, Request
from api.db.queries import get_session, get_user_by_google_id
import sqlite3

SESSION_COOKIE = "jsk"


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _get_user_by_id(db_path: str, user_id: int) -> dict | None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(_db_path(), token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = _get_user_by_id(_db_path(), session["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
