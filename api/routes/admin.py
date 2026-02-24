import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.db.queries import get_all_users, reset_user_onboarding
from api.middleware.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class TriggerRequest(BaseModel):
    profile: str | None = None  # None → run all active profiles


@router.get("/users")
def list_users(admin: dict = Depends(get_current_admin)):
    """Return all registered users with admin flags."""
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    users = get_all_users(db_path)
    safe_keys = {"id", "email", "name", "avatar_url", "profile_id", "is_admin",
                 "created_at", "last_login", "has_cv", "has_yaml"}
    return [{k: v for k, v in u.items() if k in safe_keys} for u in users]


@router.post("/users/{user_id}/reset-onboarding")
def reset_onboarding(user_id: int, admin: dict = Depends(get_current_admin)):
    """Clear profile_id, cv_md, profile_yaml for a user so they go through onboarding again.

    Applied/dismissed job history is preserved.
    """
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    reset_user_onboarding(db_path, user_id)
    logger.info("Onboarding reset for user %s by admin %s", user_id, admin["email"])
    return {"ok": True, "user_id": user_id}


@router.get("/env-check")
def env_check(admin: dict = Depends(get_current_admin)):
    """Diagnostic: confirm which critical env vars the running process can see.

    Returns boolean flags only — never the actual values.
    """
    vars_to_check = [
        "GH_ACTIONS_TOKEN",
        "GH_REPO",
        "GH_REF",
        "ADMIN_EMAILS",
        "DB_PATH",
        "SECRET_KEY",
        "GOOGLE_CLIENT_ID",
    ]
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    return {
        "present": {k: bool(os.environ.get(k, "")) for k in vars_to_check},
        "gh_token_length": len(os.environ.get("GH_ACTIONS_TOKEN", "")),
        "gh_repo_value": os.environ.get("GH_REPO", "(not set)"),   # safe to expose
        "gh_ref_value": os.environ.get("GH_REF", "(not set)"),     # safe to expose
        "db_path_value": db_path,                                   # safe to expose
        "db_file_exists": os.path.exists(db_path),
        "all_env_keys": sorted(os.environ.keys()),                  # names only, no values
    }


@router.post("/trigger-pipeline")
async def trigger_pipeline(body: TriggerRequest = TriggerRequest(), admin: dict = Depends(get_current_admin)):
    """Dispatch the GHA scraping pipeline for a specific profile or all active profiles.

    Requires env vars: GH_ACTIONS_TOKEN, GH_REPO, GH_REF.
    """
    gh_token = os.environ.get("GH_ACTIONS_TOKEN", "")
    gh_repo = os.environ.get("GH_REPO", "")
    gh_ref = os.environ.get("GH_REF", "main")
    gh_workflow = "jobagent_daily.yml"

    if not gh_token or not gh_repo:
        raise HTTPException(
            status_code=503,
            detail="GH_ACTIONS_TOKEN / GH_REPO not configured — pipeline trigger unavailable",
        )

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    dispatch_url = f"https://api.github.com/repos/{gh_repo}/actions/workflows/{gh_workflow}/dispatches"
    inputs = {"profile": body.profile} if body.profile else {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            dispatch_url,
            json={"ref": gh_ref, "inputs": inputs},
            headers=headers,
        )

    if resp.status_code == 204:
        profile_label = body.profile or "all active profiles"
        logger.info("Pipeline triggered for %s by admin %s", profile_label, admin["email"])
        return {"status": "triggered", "profile": body.profile}

    logger.warning(
        "Pipeline trigger returned %s: %s (triggered by %s)",
        resp.status_code, resp.text, admin["email"],
    )
    raise HTTPException(
        status_code=502,
        detail=f"GitHub API returned {resp.status_code}: {resp.text[:200]}",
    )
