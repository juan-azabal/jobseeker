"""Health check endpoints.

GET /api/health       — liveness: always 200 while process is alive.
GET /api/health/ready — readiness: DB + critical env vars. 503 on failure.
"""
import os
import sqlite3

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

_CRITICAL_VARS = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "INGEST_API_KEY"]
_OPTIONAL_VARS = ["OPENAI_API_KEY", "POSTHOG_API_KEY"]


@router.get("/api/health")
async def liveness():
    """Fast liveness probe — returns 200 while the process is alive."""
    return {"status": "ok"}


@router.get("/api/health/ready")
async def readiness():
    """Deep readiness probe: verifies DB connectivity and critical env vars.

    Returns HTTP 200 with ``{"status": "ok"}`` when all core checks pass.
    Returns HTTP 503 with ``{"status": "error"}`` when DB is unreachable or a
    critical env var is missing. Optional vars (OPENAI_API_KEY, POSTHOG_API_KEY)
    generate warnings but do not fail the check.
    """
    checks: dict = {}
    all_ok = True

    # --- DB check ---
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    db_ok, db_detail = _check_db(db_path)
    checks["db"] = {"ok": db_ok, "path": db_path, "detail": db_detail}
    if not db_ok:
        all_ok = False

    # --- Critical env vars ---
    missing_critical = [v for v in _CRITICAL_VARS if not os.environ.get(v)]
    env_ok = len(missing_critical) == 0
    checks["critical_env"] = {
        "ok": env_ok,
        "missing": missing_critical,
    }
    if not env_ok:
        all_ok = False

    # --- Optional vars (warn only) ---
    missing_optional = [v for v in _OPTIONAL_VARS if not os.environ.get(v)]
    warnings = [f"Optional env var not set: {v}" for v in missing_optional]

    status = "ok" if all_ok else "error"
    body = {"status": status, "checks": checks, "warnings": warnings}

    logger.info(
        "Readiness check",
        status=status,
        db_ok=db_ok,
        env_ok=env_ok,
        warnings=warnings,
    )

    return JSONResponse(
        content=body,
        status_code=200 if all_ok else 503,
    )


def _check_db(db_path: str) -> tuple[bool, str]:
    """Attempt a lightweight SELECT 1 against the SQLite DB.

    Returns (True, "ok") on success, (False, error_message) on failure.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        conn.execute("SELECT 1")
        conn.close()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
