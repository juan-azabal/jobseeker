import os
from fastapi import Depends, HTTPException, Request
from api.db.queries import get_session, get_user_by_google_id, get_user_by_id
from typing import Annotated

SESSION_COOKIE = "jsk"


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(_db_path(), token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    real_user = get_user_by_id(_db_path(), session["user_id"])
    if not real_user:
        raise HTTPException(status_code=401, detail="User not found")

    # Impersonation: admins can view the app as another user
    impersonated_id = session.get("impersonated_user_id")
    if impersonated_id and real_user.get("is_admin"):
        impersonated = get_user_by_id(_db_path(), impersonated_id)
        if impersonated:
            return {
                **impersonated,
                "is_impersonating": True,
                "real_user_id": real_user["id"],
                "real_user_name": real_user.get("name", ""),
            }

    return real_user


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
