import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


# ── Jobs (common data) ────────────────────────────────────────────────────

def upsert_job(db_path: str, job: dict[str, Any]) -> None:
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO jobs
          (job_id, title, company, location, url, location_type, domain,
           parsed, first_seen, last_seen, ingested_at)
        VALUES
          (:job_id, :title, :company, :location, :url, :location_type, :domain,
           :parsed, :first_seen, :last_seen, :ingested_at)
        ON CONFLICT(job_id) DO UPDATE SET
          last_seen   = excluded.last_seen,
          ingested_at = excluded.ingested_at,
          parsed      = excluded.parsed
        """,
        job,
    )
    con.commit()
    con.close()


def get_jobs(
    db_path: str,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: int | None = None,
    hide_applied: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Fetch jobs with per-user scores (if available) and user status.

    Returns raw job data + ujs_score/ujs_tier/ujs_scored (nullable).
    Caller is responsible for heuristic fallback and tier filtering.
    """
    con = _connect(db_path)

    filter_clauses: list[str] = []
    filter_params: list[Any] = []
    if date_from:
        filter_clauses.append("j.first_seen >= ?")
        filter_params.append(date_from)
    if date_to:
        filter_clauses.append("j.first_seen <= ?")
        filter_params.append(date_to)

    where_fragment = ("AND " + " AND ".join(filter_clauses)) if filter_clauses else ""
    hide_fragment = "AND ag.applied_at IS NULL" if hide_applied else ""

    # Deduplicate by (company, normalised title), keeping the row with the
    # highest per-user score (or any row when no scores exist).
    # Score ordering: COALESCE(ujs.score, 0) so unscored jobs sort last.
    sql = f"""
        WITH ranked AS (
            SELECT
                j.job_id, j.title, j.company, j.location, j.location_type,
                j.domain, j.parsed, j.first_seen, j.url,
                json_extract(j.parsed, '$.remote_restriction') AS remote_restriction,
                ujs.score  AS ujs_score,
                ujs.tier   AS ujs_tier,
                ujs.scored AS ujs_scored,
                ROW_NUMBER() OVER (
                    PARTITION BY j.company, LOWER(TRIM(j.title))
                    ORDER BY COALESCE(ujs.score, 0) DESC
                ) AS rn
            FROM jobs j
            LEFT JOIN user_job_scores ujs
                ON ujs.job_id = j.job_id AND ujs.user_id = ?
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
            r.job_id, r.title, r.company, r.location, r.location_type,
            r.domain, r.parsed, r.first_seen, r.url,
            r.remote_restriction,
            r.ujs_score, r.ujs_tier, r.ujs_scored,
            ag.applied_at,
            ag.dismissed_at
        FROM ranked r
        LEFT JOIN status_groups ag
            ON ag.company = r.company AND ag.title_key = LOWER(TRIM(r.title))
        WHERE r.rn = 1
          AND ag.dismissed_at IS NULL
          {hide_fragment}
        ORDER BY COALESCE(r.ujs_score, 0) DESC
        LIMIT ?
    """
    params: list[Any] = [user_id] + filter_params + [user_id, limit]
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_job_by_id(db_path: str, job_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_user_job_score(db_path: str, user_id: int, job_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute(
        "SELECT * FROM user_job_scores WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    ).fetchone()
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


def get_total_job_count(db_path: str) -> int:
    con = _connect(db_path)
    row = con.execute("SELECT COUNT(*) AS cnt FROM jobs").fetchone()
    con.close()
    return row["cnt"] if row else 0


def cleanup_old_jobs(db_path: str, days: int = 90) -> int:
    """Delete jobs not seen in the last `days` days and their dependent rows.

    Returns the number of jobs deleted.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    con = _connect(db_path)
    # Delete dependent rows first (SQLite FK enforcement is off by default)
    con.execute(
        "DELETE FROM user_job_scores WHERE job_id IN (SELECT job_id FROM jobs WHERE last_seen < ?)",
        (cutoff,),
    )
    con.execute(
        "DELETE FROM user_job_status WHERE job_id IN (SELECT job_id FROM jobs WHERE last_seen < ?)",
        (cutoff,),
    )
    cur = con.execute("DELETE FROM jobs WHERE last_seen < ?", (cutoff,))
    deleted = cur.rowcount
    con.commit()
    con.close()
    return deleted


# ── Per-user scores ───────────────────────────────────────────────────────

def upsert_user_job_score(
    db_path: str, user_id: int, job_id: str,
    score: int, tier: str, scored_json: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, scored_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, job_id) DO UPDATE SET
          score     = excluded.score,
          tier      = excluded.tier,
          scored    = excluded.scored,
          scored_at = excluded.scored_at
        """,
        (user_id, job_id, score, tier, scored_json, now),
    )
    con.commit()
    con.close()


def get_ingest_status(db_path: str) -> dict:
    """Return aggregate stats useful for monitoring pipeline health."""
    con = _connect(db_path)
    row = con.execute(
        "SELECT COUNT(*) AS total_jobs, MAX(ingested_at) AS last_ingested_at FROM jobs"
    ).fetchone()
    scores_row = con.execute(
        "SELECT COUNT(DISTINCT user_id) AS scored_profiles, COUNT(*) AS total_scored FROM user_job_scores"
    ).fetchone()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    old_row = con.execute(
        "SELECT COUNT(*) AS old_jobs FROM jobs WHERE last_seen < ?", (cutoff,)
    ).fetchone()
    con.close()
    return {
        "total_jobs": row["total_jobs"],
        "last_ingested_at": row["last_ingested_at"],
        "scored_profiles": scores_row["scored_profiles"],
        "total_scored": scores_row["total_scored"],
        "jobs_older_than_90d": old_row["old_jobs"],
    }


def get_user_id_by_profile_id(db_path: str, profile_id: str) -> int | None:
    con = _connect(db_path)
    row = con.execute(
        "SELECT id FROM users WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    con.close()
    return row["id"] if row else None


# ── User status ───────────────────────────────────────────────────────────

def set_job_dismissed(db_path: str, user_id: int, job_id: str) -> None:
    """Mark a job as dismissed (negative example). Dismissed jobs are hidden from all lists."""
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


# ── Users ─────────────────────────────────────────────────────────────────

def get_user_by_google_id(db_path: str, google_id: str) -> dict | None:
    con = _connect(db_path)
    row = con.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def create_user(db_path: str, user: dict[str, Any]) -> dict:
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


# ── Sessions ──────────────────────────────────────────────────────────────

def create_session(db_path: str, token: str, user_id: int, expires_at: str) -> None:
    con = _connect(db_path)
    con.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    con.commit()
    con.close()


def get_session(db_path: str, token: str) -> dict | None:
    """Return the session row only if it exists and has not expired."""
    con = _connect(db_path)
    row = con.execute(
        "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    ).fetchone()
    con.close()
    return dict(row) if row else None


def delete_session(db_path: str, token: str) -> None:
    con = _connect(db_path)
    con.execute("DELETE FROM sessions WHERE token = ?", (token,))
    con.commit()
    con.close()


def set_session_impersonation(db_path: str, token: str, impersonated_user_id: int | None) -> None:
    """Set or clear the impersonated_user_id for an active session."""
    con = _connect(db_path)
    con.execute(
        "UPDATE sessions SET impersonated_user_id = ? WHERE token = ?",
        (impersonated_user_id, token),
    )
    con.commit()
    con.close()


def get_user_by_id(db_path: str, user_id: int) -> dict | None:
    """Return a user row by primary key."""
    con = _connect(db_path)
    row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def set_user_profile_id(db_path: str, user_id: int, profile_id: str | None) -> None:
    """Directly set a user's profile_id (admin operation)."""
    con = _connect(db_path)
    con.execute("UPDATE users SET profile_id = ? WHERE id = ?", (profile_id, user_id))
    con.commit()
    con.close()


def update_user_profile_id(db_path: str, user_id: int, profile_id: str) -> None:
    con = _connect(db_path)
    con.execute("UPDATE users SET profile_id = ? WHERE id = ?", (profile_id, user_id))
    con.commit()
    con.close()


def save_user_cv_md(db_path: str, user_id: int, cv_md: str) -> None:
    """Persist cv_md content in the users table so it survives redeploys."""
    con = _connect(db_path)
    con.execute("UPDATE users SET cv_md = ? WHERE id = ?", (cv_md, user_id))
    con.commit()
    con.close()


def get_user_cv_md(db_path: str, user_id: int) -> str | None:
    """Return the user's stored cv_md, or None if not set."""
    con = _connect(db_path)
    row = con.execute("SELECT cv_md FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return row["cv_md"] if row else None


def save_user_profile_yaml(db_path: str, user_id: int, profile_yaml: str) -> None:
    """Persist profile YAML in the users table so it survives redeploys."""
    con = _connect(db_path)
    con.execute("UPDATE users SET profile_yaml = ? WHERE id = ?", (profile_yaml, user_id))
    con.commit()
    con.close()


def get_user_profile_yaml(db_path: str, user_id: int) -> str | None:
    """Return the user's stored profile YAML, or None if not set."""
    con = _connect(db_path)
    row = con.execute("SELECT profile_yaml FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return row["profile_yaml"] if row else None


def set_user_admin(db_path: str, user_id: int, is_admin: bool) -> None:
    """Grant or revoke admin privileges for a user."""
    con = _connect(db_path)
    con.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id))
    con.commit()
    con.close()


def get_all_users(db_path: str) -> list[dict]:
    """Return all users ordered by creation date (newest first)."""
    con = _connect(db_path)
    rows = con.execute(
        """SELECT id, email, name, avatar_url, profile_id, is_admin, created_at, last_login,
                  (cv_md IS NOT NULL AND cv_md != '') AS has_cv,
                  (profile_yaml IS NOT NULL AND profile_yaml != '') AS has_yaml
           FROM users ORDER BY created_at DESC"""
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def reset_user_onboarding(db_path: str, user_id: int) -> None:
    """Clear profile_id, cv_md, and profile_yaml so a user goes through onboarding again.

    Applied/dismissed job history (user_job_status) is preserved.
    """
    con = _connect(db_path)
    con.execute(
        "UPDATE users SET profile_id = NULL, cv_md = NULL, profile_yaml = NULL WHERE id = ?",
        (user_id,),
    )
    con.commit()
    con.close()
