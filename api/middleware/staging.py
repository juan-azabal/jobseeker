"""Staging gate middleware.

In staging environments, only admin users may access the API.
Non-admin requests receive HTTP 403.  Excludes auth, health, and the
machine-to-machine db-export endpoint so those remain reachable.
"""

import os

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api import config
from api.db.queries import get_session, get_user_by_id

logger = structlog.get_logger(__name__)

# Paths that bypass the staging gate regardless of user or auth state.
_EXCLUDED_PREFIXES = ("/api/auth/",)
_EXCLUDED_EXACT = ("/api/health", "/api/health/ready")
_EXCLUDED_DB_EXPORT = "/api/admin/db-export"


def _is_excluded(path: str, method: str) -> bool:
    if any(path.startswith(p) for p in _EXCLUDED_PREFIXES):
        return True
    if path in _EXCLUDED_EXACT:
        return True
    if path == _EXCLUDED_DB_EXPORT and method.upper() == "GET":
        return True
    return False


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


class StagingGateMiddleware(BaseHTTPMiddleware):
    """Return 403 for non-admin users when ENVIRONMENT=staging."""

    async def dispatch(self, request: Request, call_next):
        if config.ENVIRONMENT != "staging":
            return await call_next(request)

        if _is_excluded(request.url.path, request.method):
            return await call_next(request)

        token = request.cookies.get("jsk")
        if not token:
            logger.info("Staging gate: blocked unauthenticated request", path=request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": "Staging environment: admin access only"},
            )

        session = get_session(_db_path(), token)
        if not session:
            return JSONResponse(
                status_code=403,
                content={"detail": "Staging environment: admin access only"},
            )

        user = get_user_by_id(_db_path(), session["user_id"])
        if not user or not user.get("is_admin"):
            logger.info(
                "Staging gate: blocked non-admin",
                user_id=session["user_id"],
                path=request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Staging environment: admin access only"},
            )

        return await call_next(request)
