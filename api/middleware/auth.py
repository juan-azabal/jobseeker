import os
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request
from api.db.queries import get_session, get_user_by_google_id, get_user_by_id

logger = structlog.get_logger(__name__)

SESSION_COOKIE = "jsk"


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        logger.warning("Auth failed: no session cookie")
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(_db_path(), token)
    if not session:
        logger.warning("Auth failed: invalid or expired session")
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    real_user = get_user_by_id(_db_path(), session["user_id"])
    if not real_user:
        logger.warning("Auth failed: user not found", user_id=session["user_id"])
        raise HTTPException(status_code=401, detail="User not found")

    # Bind user_id to structlog contextvars so the request logging middleware
    # includes it automatically without a DB call in the middleware itself.
    structlog.contextvars.bind_contextvars(user_id=real_user["id"])

    # Impersonation: admins can view the app as another user
    impersonated_id = session.get("impersonated_user_id")
    if impersonated_id and real_user.get("is_admin"):
        impersonated = get_user_by_id(_db_path(), impersonated_id)
        if impersonated:
            logger.debug(
                "Auth: admin impersonating user",
                real_user_id=real_user["id"],
                impersonated_user_id=impersonated_id,
            )
            return {
                **_safe_user_dict(impersonated),
                "is_impersonating": True,
                "real_user_id": real_user["id"],
                "real_user_name": real_user.get("name", ""),
            }

    logger.debug(
        "Auth: user authenticated",
        user_id=real_user["id"],
        profile_id=real_user.get("profile_id"),
    )
    return _safe_user_dict(real_user)


def _safe_user_dict(row: dict) -> dict:
    """Return only the fields that are safe to expose to the frontend.

    Excludes large blobs (cv_md, profile_yaml) and internal identifiers (google_id).
    Adds the computed ``onboarded`` flag so the frontend can gate the onboarding flow
    without checking profile_id (which is now always set from first login).
    """
    return {
        "id": row["id"],
        "email": row.get("email"),
        "name": row.get("name"),
        "avatar_url": row.get("avatar_url"),
        "profile_id": row.get("profile_id"),
        "is_admin": bool(row.get("is_admin")),
        # onboarded = CV + profile YAML have been persisted; used by frontend to gate /onboard
        "onboarded": bool(row.get("profile_yaml")),
    }


def get_current_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Require admin privileges. Also works when the admin is impersonating another user."""
    if user.get("is_admin"):
        return user
    # When impersonating a non-admin, the real user is still admin — allow admin endpoints.
    if user.get("is_impersonating") and user.get("real_user_id"):
        real_user = get_user_by_id(_db_path(), user["real_user_id"])
        if real_user and real_user.get("is_admin"):
            return user
    raise HTTPException(status_code=403, detail="Admin access required")
