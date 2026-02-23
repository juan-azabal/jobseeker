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
          parsed      = excluded.parsed,
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
    user_id: int | None = None,
    hide_applied: bool = False,
    limit: int = 100,
) -> list[dict]:
    con = _connect(db_path)

    # Build optional filter fragments applied inside the ranked CTE
    filter_clauses: list[str] = []
    filter_params: list[Any] = []
    if tiers:
        placeholders = ",".join("?" * len(tiers))
        filter_clauses.append(f"j.tier IN ({placeholders})")
        filter_params.extend(tiers)
    if date_from:
        filter_clauses.append("j.first_seen >= ?")
        filter_params.append(date_from)
    if date_to:
        filter_clauses.append("j.first_seen <= ?")
        filter_params.append(date_to)

    where_fragment = ("AND " + " AND ".join(filter_clauses)) if filter_clauses else ""
    hide_fragment = "AND ag.applied_at IS NULL" if hide_applied else ""

    # Deduplicate by (company, normalised title), keeping the highest-scoring row.
    # applied_groups aggregates applied_at across all duplicates so the badge shows
    # even when the user marked a lower-scored duplicate.
    sql = f"""
        WITH ranked AS (
            SELECT
                j.job_id, j.title, j.company, j.location, j.location_type, j.domain,
                j.score, j.tier, j.first_seen, j.url,
                json_extract(j.parsed, '$.remote_restriction') AS remote_restriction,
                ROW_NUMBER() OVER (
                    PARTITION BY j.company, LOWER(TRIM(j.title))
                    ORDER BY j.score DESC
                ) AS rn
            FROM jobs j
            WHERE 1=1 {where_fragment}
        ),
        status_groups AS (
            SELECT
                j.company,
                LOWER(TRIM(j.title))  AS title_key,
                MAX(s.applied_at)     AS applied_at,
                MAX(s.dismissed_at)   AS dismissed_at
            FROM jobs j
            JOIN user_job_status s ON s.job_id = j.job_id AND s.user_id = ?
            GROUP BY j.company, LOWER(TRIM(j.title))
        )
        SELECT
            r.job_id, r.title, r.company, r.location, r.location_type, r.domain,
            r.score, r.tier, r.first_seen, r.url,
            r.remote_restriction,
            ag.applied_at,
            ag.dismissed_at
        FROM ranked r
        LEFT JOIN status_groups ag
            ON ag.company = r.company AND ag.title_key = LOWER(TRIM(r.title))
        WHERE r.rn = 1
          AND ag.dismissed_at IS NULL
          {hide_fragment}
        ORDER BY r.score DESC
        LIMIT ?
    """
    params: list[Any] = filter_params + [user_id, limit]
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def set_job_dismissed(db_path: str, user_id: int, job_id: str) -> None:
    """Mark a job as dismissed (negative example). Dismissed jobs are hidden from all lists."""
    from datetime import datetime, timezone
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO user_job_status (user_id, job_id, dismissed_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, job_id) DO UPDATE SET dismissed_at = excluded.dismissed_at
        """,
        (user_id, job_id, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def set_job_applied(db_path: str, user_id: int, job_id: str, applied: bool) -> None:
    from datetime import datetime, timezone
    con = _connect(db_path)
    if applied:
        con.execute(
            """
            INSERT INTO user_job_status (user_id, job_id, applied_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, job_id) DO UPDATE SET applied_at = excluded.applied_at
            """,
            (user_id, job_id, datetime.now(timezone.utc).isoformat()),
        )
    else:
        con.execute(
            "DELETE FROM user_job_status WHERE user_id = ? AND job_id = ?",
            (user_id, job_id),
        )
    con.commit()
    con.close()


def get_job_by_id(db_path: str, job_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_job_status_by_title(db_path: str, user_id: int, company: str, title: str) -> dict | None:
    """Return aggregated applied_at / dismissed_at across all duplicates of a (company, title) pair."""
    con = _connect(db_path)
    row = con.execute(
        """
        SELECT MAX(s.applied_at) AS applied_at, MAX(s.dismissed_at) AS dismissed_at
        FROM jobs j
        JOIN user_job_status s ON s.job_id = j.job_id AND s.user_id = ?
        WHERE j.company = ? AND LOWER(TRIM(j.title)) = LOWER(TRIM(?))
        """,
        (user_id, company, title),
    ).fetchone()
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


def update_user_profile_id(db_path: str, user_id: int, profile_id: str) -> None:
    con = _connect(db_path)
    con.execute("UPDATE users SET profile_id = ? WHERE id = ?", (profile_id, user_id))
    con.commit()
    con.close()
