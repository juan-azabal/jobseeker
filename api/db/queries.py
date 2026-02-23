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
