import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from api.db.queries import get_all_users, reset_user_onboarding, set_session_impersonation, set_user_profile_id, get_user_by_id
from api.middleware.auth import get_current_admin, SESSION_COOKIE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class TriggerRequest(BaseModel):
    profile: str | None = None  # None → run all active profiles


class SetProfileIdRequest(BaseModel):
    profile_id: str | None = None


@router.get("/users")
def list_users(admin: dict = Depends(get_current_admin)):
    """Return all registered users with admin flags."""
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    users = get_all_users(db_path)
    safe_keys = {"id", "email", "name", "avatar_url", "profile_id", "is_admin",
                 "created_at", "last_login", "has_cv", "has_yaml"}
    return [{k: v for k, v in u.items() if k in safe_keys} for u in users]


@router.post("/impersonate/{user_id}")
def start_impersonation(user_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    """Start viewing the app as another user (admin only).

    Sets impersonated_user_id on the current session. All subsequent API calls will
    use the impersonated user's identity until stop_impersonation is called.
    """
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    target = get_user_by_id(db_path, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No session cookie")
    set_session_impersonation(db_path, token, user_id)
    admin_label = admin.get("real_user_name") or admin.get("email", "?")
    logger.info("Admin %s started impersonating user_id=%d (%s)", admin_label, user_id, target["email"])
    return {"ok": True, "impersonating": user_id}


@router.delete("/impersonate")
def stop_impersonation(request: Request, admin: dict = Depends(get_current_admin)):
    """Stop impersonating — return to viewing as the real admin account."""
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No session cookie")
    set_session_impersonation(db_path, token, None)
    logger.info("Impersonation stopped (real_user_id=%s)", admin.get("real_user_id") or admin.get("id"))
    return {"ok": True}


@router.patch("/users/{user_id}/profile-id")
def admin_set_profile_id(user_id: int, body: SetProfileIdRequest, admin: dict = Depends(get_current_admin)):
    """Override a user's profile_id (admin only). Use to fix misassigned IDs."""
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    target = get_user_by_id(db_path, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    new_id = body.profile_id.strip() if body.profile_id else None
    set_user_profile_id(db_path, user_id, new_id)
    logger.info("Admin set profile_id=%r for user_id=%d (%s)", new_id, user_id, target["email"])
    return {"ok": True, "user_id": user_id, "profile_id": new_id}


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
        "INGEST_API_KEY",
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


class ResetSeenIdsRequest(BaseModel):
    profile_id: str  # profile_id used for seen_ids filename (e.g. "juan", not "juanAza")


@router.post("/reset-seen-ids")
async def reset_seen_ids(body: ResetSeenIdsRequest, admin: dict = Depends(get_current_admin)):
    """Clear a profile's seen_ids file on GitHub so all jobs are re-scraped on next run.

    The seen_ids file tracks which jobs have already been processed. Clearing it
    forces a full re-scrape, useful when previous syncs failed and jobs were
    marked as seen without reaching Railway.

    Requires env vars: GH_ACTIONS_TOKEN, GH_REPO, GH_REF.
    """
    import base64

    gh_token = os.environ.get("GH_ACTIONS_TOKEN", "")
    gh_repo = os.environ.get("GH_REPO", "")
    gh_ref = os.environ.get("GH_REF", "main")

    if not gh_token or not gh_repo:
        raise HTTPException(
            status_code=503,
            detail="GH_ACTIONS_TOKEN / GH_REPO not configured",
        )

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    file_path = f"agent/config/seen_ids/{body.profile_id}.txt"
    api_url = f"https://api.github.com/repos/{gh_repo}/contents/{file_path}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Get current file SHA (required for update)
        get_resp = await client.get(api_url, headers=headers, params={"ref": gh_ref})
        if get_resp.status_code == 404:
            logger.info("No seen_ids file for %s — nothing to reset", body.profile_id)
            return {"status": "not_found", "profile_id": body.profile_id}

        if get_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub API GET returned {get_resp.status_code}: {get_resp.text[:200]}",
            )

        current_sha = get_resp.json()["sha"]

        # Overwrite with empty content
        put_resp = await client.put(
            api_url,
            json={
                "message": f"chore: reset seen_ids for {body.profile_id} [skip ci]",
                "content": base64.b64encode(b"").decode(),
                "sha": current_sha,
                "branch": gh_ref,
            },
            headers=headers,
        )

    if put_resp.status_code in (200, 201):
        logger.info("seen_ids reset for %s by admin %s", body.profile_id, admin["email"])
        return {"status": "reset", "profile_id": body.profile_id}

    raise HTTPException(
        status_code=502,
        detail=f"GitHub API PUT returned {put_resp.status_code}: {put_resp.text[:200]}",
    )


@router.get("/embedding-diagnostics")
def embedding_diagnostics(admin: dict = Depends(get_current_admin)):
    """Show similarity scores between admin's profile skills and recent job skills.

    Returns sorted list of {job_skill, best_match, similarity, status} for
    threshold tuning. Curl-only, no UI.
    """
    import json
    import sqlite3

    from api.scoring import load_profile_data
    from api.skill_matcher import match_skills

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    profile = load_profile_data(admin.get("profile_id"))
    if not profile or not profile.get("skills"):
        raise HTTPException(status_code=400, detail="Admin has no profile or no skills configured")

    user_skills = profile["skills"]

    # Collect first 30 unique must_have_skills across recent jobs
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT parsed FROM jobs WHERE parsed IS NOT NULL ORDER BY first_seen DESC LIMIT 200"
        ).fetchall()
    finally:
        conn.close()

    job_skills: list[str] = []
    seen: set[str] = set()
    for (parsed_json,) in rows:
        try:
            parsed = json.loads(parsed_json)
            for skill in parsed.get("must_have_skills", []) or []:
                if isinstance(skill, str) and skill.strip():
                    norm = skill.strip().lower()
                    if norm not in seen:
                        seen.add(norm)
                        job_skills.append(skill.strip())
                        if len(job_skills) >= 30:
                            break
        except (json.JSONDecodeError, TypeError):
            continue
        if len(job_skills) >= 30:
            break

    if not job_skills:
        return []

    results = match_skills(user_skills, job_skills, db_path)
    output = [
        {
            "job_skill": r.job_skill,
            "best_match": r.user_skill,
            "similarity": round(r.similarity, 4),
            "status": r.status,
        }
        for r in results
    ]
    output.sort(key=lambda x: x["similarity"], reverse=True)
    return output


@router.post("/backfill-embeddings", status_code=202)
def backfill_embeddings(
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_current_admin),
):
    """Compute and cache embeddings for all known skills.

    Runs in background — returns 202 immediately so Railway/proxies don't time out.
    Progress visible in server logs.
    """
    from api.embeddings import get_embeddings_batch
    from api.db.init import init_db

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    email = admin["email"]

    def _run() -> None:
        try:
            import json
            import sqlite3
            import yaml

            init_db(db_path)

            # Collect skills from user profiles
            profile_skills: set[str] = set()
            job_skills: set[str] = set()

            conn = sqlite3.connect(db_path)
            try:
                for (yaml_text,) in conn.execute(
                    "SELECT profile_yaml FROM users WHERE profile_yaml IS NOT NULL"
                ).fetchall():
                    try:
                        profile = yaml.safe_load(yaml_text)
                        for s in profile.get("skills", []):
                            if isinstance(s, str) and s.strip():
                                profile_skills.add(s.strip().lower())
                    except Exception:
                        continue

                for (parsed_json,) in conn.execute(
                    "SELECT parsed FROM jobs WHERE parsed IS NOT NULL"
                ).fetchall():
                    try:
                        parsed = json.loads(parsed_json)
                        for key in ("must_have_skills", "nice_to_have_skills", "technical_stack"):
                            for s in parsed.get(key, []) or []:
                                if isinstance(s, str) and s.strip():
                                    job_skills.add(s.strip().lower())
                    except Exception:
                        continue
            finally:
                conn.close()

            all_skills = list(profile_skills | job_skills)
            if not all_skills:
                logger.info("Embedding backfill: no skills found (triggered by %s)", email)
                return

            result = get_embeddings_batch(all_skills, db_path)
            logger.info(
                "Embedding backfill completed: %d/%d cached (triggered by %s)",
                len(result), len(all_skills), email,
            )
        except Exception as exc:
            logger.error("Embedding backfill failed (triggered by %s): %s", email, exc)

    background_tasks.add_task(_run)
    logger.info("Embedding backfill started in background (triggered by %s)", email)
    return {"status": "started", "message": "Backfill running in background — check server logs for progress"}


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
