import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


# ── Jobs (common data) ────────────────────────────────────────────────────


def upsert_job(db_path: str, job: dict[str, Any]) -> None:
    # Ensure all expected keys are present (None for missing fields)
    defaults: dict[str, Any] = {
        "role_function": None,
        "company_url": None,
        "company_logo": None,
        "company_industry": None,
        "company_size": None,
        "job_level": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_interval": None,
        "salary_source": None,
        "country": None,
        "city": None,
        "remote_type": None,
        "sources": None,
        "role_in_plain_english": None,
        "company_stage": None,
        "company_tone": None,
    }
    job = {**defaults, **job}
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO jobs
          (job_id, title, company, location, url, location_type, domain,
           parsed, role_function, first_seen, last_seen, ingested_at,
           company_url, company_logo, company_industry, company_size,
           job_level, salary_min, salary_max, salary_currency, salary_interval,
           salary_source, country, city, remote_type, sources,
           role_in_plain_english, company_stage, company_tone)
        VALUES
          (:job_id, :title, :company, :location, :url, :location_type, :domain,
           :parsed, :role_function, :first_seen, :last_seen, :ingested_at,
           :company_url, :company_logo, :company_industry, :company_size,
           :job_level, :salary_min, :salary_max, :salary_currency, :salary_interval,
           :salary_source, :country, :city, :remote_type, :sources,
           :role_in_plain_english, :company_stage, :company_tone)
        ON CONFLICT(job_id) DO UPDATE SET
          last_seen             = excluded.last_seen,
          ingested_at           = excluded.ingested_at,
          parsed                = excluded.parsed,
          role_function         = excluded.role_function,
          company_url           = COALESCE(excluded.company_url,           jobs.company_url),
          company_logo          = COALESCE(excluded.company_logo,          jobs.company_logo),
          company_industry      = COALESCE(excluded.company_industry,      jobs.company_industry),
          company_size          = COALESCE(excluded.company_size,          jobs.company_size),
          job_level             = COALESCE(excluded.job_level,             jobs.job_level),
          salary_min            = COALESCE(excluded.salary_min,            jobs.salary_min),
          salary_max            = COALESCE(excluded.salary_max,            jobs.salary_max),
          salary_currency       = COALESCE(excluded.salary_currency,       jobs.salary_currency),
          salary_interval       = COALESCE(excluded.salary_interval,       jobs.salary_interval),
          salary_source         = COALESCE(excluded.salary_source,         jobs.salary_source),
          country               = COALESCE(excluded.country,               jobs.country),
          city                  = COALESCE(excluded.city,                  jobs.city),
          remote_type           = COALESCE(excluded.remote_type,           jobs.remote_type),
          sources               = excluded.sources,
          role_in_plain_english = COALESCE(excluded.role_in_plain_english, jobs.role_in_plain_english),
          company_stage         = COALESCE(excluded.company_stage,         jobs.company_stage),
          company_tone          = COALESCE(excluded.company_tone,          jobs.company_tone)
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

    Returns raw job data + ujs_score/ujs_tier/ujs_scored/ujs_technical_grade/
    ujs_profile_grade/ujs_scored_v2 (all nullable).
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
                j.domain, j.parsed, j.role_function, j.first_seen, j.url,
                json_extract(j.parsed, '$.remote_restriction') AS remote_restriction,
                j.company_url, j.company_logo, j.company_industry, j.company_size,
                j.job_level, j.salary_min, j.salary_max, j.salary_currency,
                j.salary_interval, j.salary_source, j.country, j.city,
                j.remote_type, j.sources,
                j.role_in_plain_english, j.company_stage, j.company_tone,
                ujs.score           AS ujs_score,
                ujs.tier            AS ujs_tier,
                ujs.scored          AS ujs_scored,
                ujs.technical_grade AS ujs_technical_grade,
                ujs.profile_grade   AS ujs_profile_grade,
                ujs.scored_v2       AS ujs_scored_v2,
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
            r.domain, r.parsed, r.role_function, r.first_seen, r.url,
            r.remote_restriction,
            r.company_url, r.company_logo, r.company_industry, r.company_size,
            r.job_level, r.salary_min, r.salary_max, r.salary_currency,
            r.salary_interval, r.salary_source, r.country, r.city,
            r.remote_type, r.sources,
            r.role_in_plain_english, r.company_stage, r.company_tone,
            r.ujs_score, r.ujs_tier, r.ujs_scored,
            r.ujs_technical_grade, r.ujs_profile_grade, r.ujs_scored_v2,
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


def batch_get_parsed(db_path: str, job_ids: list[str]) -> list[tuple[str, str]]:
    """Return (job_id, parsed) for jobs that exist with non-null parsed data."""
    if not job_ids:
        return []
    con = _connect(db_path)
    placeholders = ",".join("?" for _ in job_ids)
    rows = con.execute(
        f"SELECT job_id, parsed FROM jobs WHERE job_id IN ({placeholders}) AND parsed IS NOT NULL",
        job_ids,
    ).fetchall()
    con.close()
    return [(r["job_id"], r["parsed"]) for r in rows]


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
    db_path: str,
    user_id: int,
    job_id: str,
    score: int,
    tier: str,
    scored_json: str | None,
    technical_grade: str | None = None,
    profile_grade: str | None = None,
    scored_v2: int = 0,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO user_job_scores
          (user_id, job_id, score, tier, scored, scored_at,
           technical_grade, profile_grade, scored_v2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, job_id) DO UPDATE SET
          score           = excluded.score,
          tier            = excluded.tier,
          scored          = excluded.scored,
          scored_at       = excluded.scored_at,
          technical_grade = excluded.technical_grade,
          profile_grade   = excluded.profile_grade,
          scored_v2       = excluded.scored_v2
        """,
        (user_id, job_id, score, tier, scored_json, now, technical_grade, profile_grade, scored_v2),
    )
    con.commit()
    con.close()


def get_ingest_status(db_path: str) -> dict:
    """Return aggregate stats useful for monitoring pipeline health."""
    con = _connect(db_path)
    row = con.execute("SELECT COUNT(*) AS total_jobs, MAX(ingested_at) AS last_ingested_at FROM jobs").fetchone()
    scores_row = con.execute(
        "SELECT COUNT(DISTINCT user_id) AS scored_profiles, COUNT(*) AS total_scored FROM user_job_scores"
    ).fetchone()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    old_row = con.execute("SELECT COUNT(*) AS old_jobs FROM jobs WHERE last_seen < ?", (cutoff,)).fetchone()
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
    row = con.execute("SELECT id FROM users WHERE profile_id = ?", (profile_id,)).fetchone()
    con.close()
    return row["id"] if row else None


def get_profile_id_by_user_id(db_path: str, user_id: int) -> str | None:
    """Return the profile_id label for a given user_id, or None if not found."""
    con = _connect(db_path)
    row = con.execute("SELECT profile_id FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return row["profile_id"] if row else None


# ── User status ───────────────────────────────────────────────────────────


def set_domain_override(db_path: str, user_id: int, job_id: str, domain: str | None) -> None:
    """Set or clear the per-user domain override for a job.

    Uses INSERT ... ON CONFLICT DO UPDATE so only domain_override is touched;
    applied_at and dismissed_at are never overwritten.
    """
    con = _connect(db_path)
    con.execute(
        """
        INSERT INTO user_job_status (user_id, job_id, domain_override)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, job_id) DO UPDATE SET domain_override = excluded.domain_override
        """,
        (user_id, job_id, domain),
    )
    con.commit()
    con.close()


def get_domain_override(db_path: str, user_id: int, job_id: str) -> str | None:
    """Return the user's domain override for a job, or None if not set."""
    con = _connect(db_path)
    row = con.execute(
        "SELECT domain_override FROM user_job_status WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    ).fetchone()
    con.close()
    return row["domain_override"] if row else None


def get_all_domain_overrides(db_path: str, user_id: int) -> dict[str, str]:
    """Return all non-null domain overrides for a user as {job_id: domain}."""
    con = _connect(db_path)
    rows = con.execute(
        "SELECT job_id, domain_override FROM user_job_status WHERE user_id = ? AND domain_override IS NOT NULL",
        (user_id,),
    ).fetchall()
    con.close()
    return {row["job_id"]: row["domain_override"] for row in rows}


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
          last_login = excluded.last_login,
          profile_id = COALESCE(users.profile_id, excluded.profile_id)
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


def get_profile_yaml_by_profile_id(db_path: str, profile_id: str) -> str | None:
    """Return the stored profile YAML for the first user with the given profile_id.

    Used by scoring.py as a DB fallback when the profile YAML file is absent from disk
    (e.g. after a Railway redeploy that wiped the ephemeral filesystem).
    Returns None if no matching user or YAML not yet persisted.
    """
    con = _connect(db_path)
    row = con.execute(
        "SELECT profile_yaml FROM users WHERE profile_id = ? AND profile_yaml IS NOT NULL LIMIT 1",
        (profile_id,),
    ).fetchone()
    con.close()
    return row["profile_yaml"] if row else None


# ── Skill embeddings cache ────────────────────────────────────────────────


def get_cached_embeddings(db_path: str, skills: list[str]) -> dict[str, list[float]]:
    """Bulk fetch cached embeddings from skill_embeddings table."""
    import json as _json

    if not skills:
        return {}
    con = _connect(db_path)
    placeholders = ",".join("?" for _ in skills)
    rows = con.execute(
        f"SELECT skill_text, embedding FROM skill_embeddings WHERE skill_text IN ({placeholders}) AND model = ?",
        skills + ["text-embedding-3-small"],
    ).fetchall()
    con.close()
    return {row["skill_text"]: _json.loads(row["embedding"]) for row in rows}


def save_embedding(db_path: str, skill_text: str, embedding: list[float], model: str) -> None:
    """Upsert a single embedding into the cache."""
    import json as _json

    con = _connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
        (skill_text, model, _json.dumps(embedding)),
    )
    con.commit()
    con.close()


def save_embeddings_batch(db_path: str, items: list[tuple[str, list[float], str]]) -> None:
    """Bulk insert embeddings. items: list of (skill_text, embedding, model)."""
    import json as _json

    if not items:
        return
    con = _connect(db_path)
    con.executemany(
        "INSERT OR REPLACE INTO skill_embeddings (skill_text, model, embedding) VALUES (?, ?, ?)",
        [(text, model, _json.dumps(emb)) for text, emb, model in items],
    )
    con.commit()
    con.close()


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


# ── Domain reparse ────────────────────────────────────────────────────────


def get_other_domain_jobs(db_path: str) -> list[dict]:
    """Return all jobs where the parsed domain is 'other' or NULL.

    Returns minimal rows: job_id, company, title, parsed.
    """
    con = _connect(db_path)
    rows = con.execute(
        """
        SELECT job_id, company, title, parsed
        FROM jobs
        WHERE parsed IS NOT NULL
          AND (
            json_extract(parsed, '$.domain') = 'other'
            OR json_extract(parsed, '$.domain') IS NULL
            OR domain = 'other'
          )
        """
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def update_job_domain(db_path: str, job_id: str, domain: str) -> None:
    """Update the jobs.domain column for a single job."""
    con = _connect(db_path)
    con.execute("UPDATE jobs SET domain = ? WHERE job_id = ?", (domain, job_id))
    con.commit()
    con.close()


# ── Domain correction analytics ───────────────────────────────────────────


# ── Master CV JSON ────────────────────────────────────────────────────────


def save_master_cv_json(db_path: str, user_id: int, json_str: str) -> None:
    """Persist Master CV JSON string for a user."""
    con = _connect(db_path)
    con.execute("UPDATE users SET master_cv_json = ? WHERE id = ?", (json_str, user_id))
    con.commit()
    con.close()


def get_master_cv_json(db_path: str, user_id: int) -> str | None:
    """Return stored Master CV JSON string for a user, or None if absent."""
    con = _connect(db_path)
    row = con.execute("SELECT master_cv_json FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    if row is None:
        return None
    return row["master_cv_json"]


# ── CV processing status ───────────────────────────────────────────────────


def set_cv_processing_status(
    db_path: str,
    user_id: int,
    status: str | None,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """Set cv_processing_status for a user.

    status values: None (clear), "processing", "done", "failed".
    When status="processing": auto-sets started_at to utcnow.
    When status=None: clears all three columns.
    result/error are JSON-encoded into cv_pending_result.
    """
    import json as _json  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415

    if status is None:
        con = _connect(db_path)
        con.execute(
            "UPDATE users SET cv_processing_status=NULL, cv_processing_started_at=NULL, cv_pending_result=NULL WHERE id=?",
            (user_id,),
        )
        con.commit()
        con.close()
        return

    started_at = None
    if status == "processing":
        started_at = datetime.now(timezone.utc).isoformat()

    pending = None
    if result is not None:
        pending = _json.dumps(result)
    elif error is not None:
        pending = _json.dumps({"error": error})

    con = _connect(db_path)
    if started_at is not None:
        con.execute(
            "UPDATE users SET cv_processing_status=?, cv_processing_started_at=?, cv_pending_result=? WHERE id=?",
            (status, started_at, pending, user_id),
        )
    else:
        con.execute(
            "UPDATE users SET cv_processing_status=?, cv_pending_result=? WHERE id=?",
            (status, pending, user_id),
        )
    con.commit()
    con.close()


def get_cv_processing_status(db_path: str, user_id: int) -> dict:
    """Return cv processing status dict: {status, started_at, result}.

    result is parsed from JSON if present, else None.
    """
    import json as _json  # noqa: PLC0415

    con = _connect(db_path)
    row = con.execute(
        "SELECT cv_processing_status, cv_processing_started_at, cv_pending_result FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    con.close()
    if row is None:
        return {"status": None, "started_at": None, "result": None}
    result = None
    if row["cv_pending_result"]:
        try:
            result = _json.loads(row["cv_pending_result"])
        except Exception:
            result = None
    return {
        "status": row["cv_processing_status"],
        "started_at": row["cv_processing_started_at"],
        "result": result,
    }


# ── Domain correction analytics ───────────────────────────────────────────


def get_domain_corrections(db_path: str) -> list[dict]:
    """Aggregate user domain corrections: cases where user override != parsed domain.

    Returns list of {from_domain, to_domain, count} ordered by count DESC.
    """
    con = _connect(db_path)
    rows = con.execute(
        """
        SELECT
            COALESCE(json_extract(j.parsed, '$.domain'), 'other') AS parsed_domain,
            us.domain_override,
            COUNT(*) AS cnt
        FROM user_job_status us
        JOIN jobs j ON j.job_id = us.job_id
        WHERE us.domain_override IS NOT NULL
          AND us.domain_override != COALESCE(json_extract(j.parsed, '$.domain'), 'other')
        GROUP BY parsed_domain, domain_override
        ORDER BY cnt DESC
        """
    ).fetchall()
    con.close()
    return [{"from": row["parsed_domain"], "to": row["domain_override"], "count": row["cnt"]} for row in rows]


# ── Agent pipeline ────────────────────────────────────────────────────────


def get_active_profile_ids(db_path: str) -> list[str]:
    """Return profile_ids for all onboarded users with active profiles.

    A user is considered active if:
    - profile_id IS NOT NULL (has been onboarded)
    - profile_yaml IS NOT NULL (has profile data)
    - profile_yaml does not contain 'active: false' in user block
    """
    con = _connect(db_path)
    rows = con.execute(
        """SELECT profile_id, profile_yaml FROM users
           WHERE profile_id IS NOT NULL
             AND profile_yaml IS NOT NULL
             AND profile_yaml != ''"""
    ).fetchall()
    con.close()

    result = []
    for row in rows:
        try:
            parsed = yaml.safe_load(row["profile_yaml"])
            if isinstance(parsed, dict) and parsed.get("user", {}).get("active", True) is False:
                continue
        except Exception:
            pass  # include on YAML parse error
        result.append(row["profile_id"])

    return sorted(result)
