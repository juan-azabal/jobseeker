import os
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Track applied migrations so each runs exactly once (idempotent restarts).
    con.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (filename TEXT PRIMARY KEY, applied_at TEXT)"
    )
    con.commit()

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for mf in migration_files:
        row = con.execute(
            "SELECT 1 FROM _migrations WHERE filename = ?", (mf.name,)
        ).fetchone()
        if row:
            continue  # already applied
        con.executescript(mf.read_text())
        con.execute(
            "INSERT INTO _migrations (filename, applied_at) VALUES (?, datetime('now'))",
            (mf.name,),
        )
        con.commit()

    con.close()
