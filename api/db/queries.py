import sqlite3
from typing import Any


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def upsert_job(db_path: str, job: dict[str, Any]) -> None:
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO jobs
          (job_id, title, company, location, url, location_type, domain,
           score, tier, parsed, scored, first_seen, last_seen, ingested_at)
        VALUES
          (:job_id, :title, :company, :location, :url, :location_type, :domain,
           :score, :tier, :parsed, :scored, :first_seen, :last_seen, :ingested_at)
        ON CONFLICT(job_id) DO UPDATE SET
          last_seen   = excluded.last_seen,
          ingested_at = excluded.ingested_at,
          score       = excluded.score,
          tier        = excluded.tier,
          scored      = excluded.scored
        """,
        job,
    )
    con.commit()
    con.close()


def get_jobs(
    db_path: str,
    tiers: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    con = _connect(db_path)
    sql = "SELECT job_id, title, company, location, location_type, domain, score, tier, first_seen, url FROM jobs WHERE 1=1"
    params: list[Any] = []

    if tiers:
        placeholders = ",".join("?" * len(tiers))
        sql += f" AND tier IN ({placeholders})"
        params.extend(tiers)
    if date_from:
        sql += " AND first_seen >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND first_seen <= ?"
        params.append(date_to)

    sql += " ORDER BY score DESC"
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_job_by_id(db_path: str, job_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Users ──────────────────────────────────────────────────────────────────

def get_user_by_google_id(db_path: str, google_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def create_user(db_path: str, user: dict[str, Any]) -> dict:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    con = _connect(db_path)
    cur = con.execute(
        """
        INSERT INTO users (google_id, email, name, avatar_url, profile_id, created_at, last_login)
        VALUES (:google_id, :email, :name, :avatar_url, :profile_id, :created_at, :last_login)
        """,
        {**user, "created_at": now, "last_login": now},
    )
    con.commit()
    row = con.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    return dict(row)


def upsert_user(db_path: str, user: dict[str, Any]) -> dict:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO users (google_id, email, name, avatar_url, profile_id, created_at, last_login)
        VALUES (:google_id, :email, :name, :avatar_url, :profile_id, :now, :now)
        ON CONFLICT(google_id) DO UPDATE SET
          email      = excluded.email,
          name       = excluded.name,
          avatar_url = excluded.avatar_url,
          last_login = excluded.last_login
        """,
        {**user, "now": now},
    )
    con.commit()
    row = con.execute("SELECT * FROM users WHERE google_id = ?", (user["google_id"],)).fetchone()
    con.close()
    return dict(row)


# ── Sessions ───────────────────────────────────────────────────────────────

def create_session(db_path: str, token: str, user_id: int, expires_at: str) -> None:
    con = _connect(db_path)
    con.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    con.commit()
    con.close()


def get_session(db_path: str, token: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    con.close()
    return dict(row) if row else None


def delete_session(db_path: str, token: str) -> None:
    con = _connect(db_path)
    con.execute("DELETE FROM sessions WHERE token = ?", (token,))
    con.commit()
    con.close()
