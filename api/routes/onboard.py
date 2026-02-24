import base64
import logging
import os
import sys
import tempfile
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
import yaml

logger = logging.getLogger(__name__)

from api.middleware.auth import get_current_user
from api.db.queries import (
    update_user_profile_id,
    save_user_cv_md, get_user_cv_md,
    save_user_profile_yaml, get_user_profile_yaml,
)

MAX_CV_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


def _load_jobagent():
    """Add JOBAGENT_DIR to sys.path so we can import from jobagent."""
    jobagent_dir = os.environ.get("JOBAGENT_DIR", "agent")
    jobagent_dir = os.path.abspath(jobagent_dir)
    if jobagent_dir not in sys.path:
        sys.path.insert(0, jobagent_dir)


_load_jobagent()


def docx_to_markdown(path: str) -> str:
    from onboard import docx_to_markdown as _dtm  # noqa: PLC0415
    return _dtm(path)


def _extract_profile_from_cv(cv_text: str) -> dict:
    from onboard import _extract_profile  # noqa: PLC0415
    from openai import OpenAI  # noqa: PLC0415
    return _extract_profile(cv_text, OpenAI())


class GenerateProfileRequest(BaseModel):
    cv_markdown: str


@router.post("/generate-profile", dependencies=[Depends(get_current_user)])
async def generate_profile(body: GenerateProfileRequest):
    profile = _extract_profile_from_cv(body.cv_markdown)
    return profile


def _build_profile_yaml(profile: dict, profile_id: str, salary_min: int, location_preference: str) -> str:
    from onboard import _build_profile_yaml as _bpy  # noqa: PLC0415
    return _bpy(
        extracted=profile,
        profile_id=profile_id,
        email=profile.get("email") or "",
        salary_min=salary_min,
        location_choice=location_preference,
        home_locations=profile.get("home_locations", []),
    )


def _generate_profile_id(name: str) -> str:
    from onboard import _generate_profile_id as _gpi  # noqa: PLC0415
    return _gpi(name)


def _write_profile_files(jobagent_dir: str, profile_id: str, cv_markdown: str, profile_yaml: str) -> None:
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    with open(os.path.join(profiles_dir, f"{profile_id}.yaml"), "w") as f:
        f.write(profile_yaml)

    knowledge_dir = os.path.join(jobagent_dir, "knowledge", profile_id)
    os.makedirs(knowledge_dir, exist_ok=True)
    with open(os.path.join(knowledge_dir, "cv.md"), "w") as f:
        f.write(cv_markdown)

    seen_ids_dir = os.path.join(jobagent_dir, "config", "seen_ids")
    os.makedirs(seen_ids_dir, exist_ok=True)
    seen_ids_path = os.path.join(seen_ids_dir, f"{profile_id}.txt")
    if not os.path.exists(seen_ids_path):
        open(seen_ids_path, "w").close()


class SaveProfileRequest(BaseModel):
    cv_markdown: str
    profile: dict[str, Any]
    salary_min: int = 60000
    location_preference: str = "b"


@router.post("/save-profile")
async def save_profile(body: SaveProfileRequest, request: Request, user: dict = Depends(get_current_user)):
    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "agent"))
    existing_profile_id = user.get("profile_id")

    if existing_profile_id:
        # User already has a profile — update cv.md and restore YAML if completely lost.
        db_path = os.environ.get("DB_PATH", "data/jobseeker.db")

        if body.cv_markdown:  # Guard: never overwrite existing cv_md with empty string
            save_user_cv_md(db_path, user["id"], body.cv_markdown)
            # Also write to disk for the current process lifetime
            knowledge_dir = os.path.join(jobagent_dir, "knowledge", existing_profile_id)
            os.makedirs(knowledge_dir, exist_ok=True)
            with open(os.path.join(knowledge_dir, "cv.md"), "w") as f:
                f.write(body.cv_markdown)

        # Recovery: if profile YAML is completely gone (not in DB, not on disk), regenerate it.
        # This breaks the redirect loop caused by Railway ephemeral filesystem wipes.
        # We only regenerate when YAML is truly absent — never overwrite an existing one.
        yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{existing_profile_id}.yaml")
        stored_yaml = get_user_profile_yaml(db_path, user["id"])
        if not stored_yaml and not os.path.exists(yaml_path):
            try:
                logger.info("Profile YAML missing for %s — regenerating from submitted profile data", existing_profile_id)
                recovered_yaml = _build_profile_yaml(
                    body.profile, existing_profile_id, body.salary_min, body.location_preference
                )
                os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
                with open(yaml_path, "w") as f:
                    f.write(recovered_yaml)
                save_user_profile_yaml(db_path, user["id"], recovered_yaml)
            except Exception:
                logger.exception("YAML recovery failed for %s — continuing without YAML", existing_profile_id)

        return {"profile_id": existing_profile_id}

    # First-time setup: generate full YAML from CV data
    profile_id = _generate_profile_id(body.profile.get("name", "user"))
    profile_yaml = _build_profile_yaml(
        body.profile, profile_id, body.salary_min, body.location_preference
    )
    _write_profile_files(jobagent_dir, profile_id, body.cv_markdown, profile_yaml)

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    update_user_profile_id(db_path, user["id"], profile_id)
    save_user_cv_md(db_path, user["id"], body.cv_markdown)
    save_user_profile_yaml(db_path, user["id"], profile_yaml)

    # Sync profile to GitHub repo and trigger the scraping pipeline (fire-and-forget)
    try:
        await _sync_and_trigger_pipeline(profile_id, profile_yaml, body.cv_markdown)
    except Exception:
        logger.exception("Pipeline sync/trigger failed for %s (non-fatal)", profile_id)

    return {"profile_id": profile_id}


async def _sync_and_trigger_pipeline(profile_id: str, profile_yaml: str, cv_markdown: str) -> None:
    """Push profile files to GitHub repo and trigger the agent pipeline.

    Requires env vars: GH_ACTIONS_TOKEN (PAT with contents:write + actions:write),
    GH_REPO (e.g. "owner/repo"), GH_REF (default "main").
    """
    gh_token = os.environ.get("GH_ACTIONS_TOKEN", "")
    gh_repo = os.environ.get("GH_REPO", "")
    gh_ref = os.environ.get("GH_REF", "main")
    gh_workflow = "jobagent_daily.yml"

    if not gh_token or not gh_repo:
        logger.info("GH_ACTIONS_TOKEN/GH_REPO not set — skipping pipeline trigger")
        return

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Push profile files to the repo
        files_to_push = [
            (f"agent/config/profiles/{profile_id}.yaml", profile_yaml),
            (f"agent/knowledge/{profile_id}/cv.md", cv_markdown),
            (f"agent/config/seen_ids/{profile_id}.txt", ""),
        ]
        for path, content in files_to_push:
            url = f"https://api.github.com/repos/{gh_repo}/contents/{path}"

            # Check if file exists (need SHA for update)
            resp = await client.get(url, headers=headers, params={"ref": gh_ref})
            sha = resp.json().get("sha") if resp.status_code == 200 else None

            body = {
                "message": f"chore: add profile {profile_id} [skip ci]",
                "content": base64.b64encode(content.encode()).decode(),
                "branch": gh_ref,
            }
            if sha:
                body["sha"] = sha

            put_resp = await client.put(url, json=body, headers=headers)
            if put_resp.status_code in (200, 201):
                logger.info("GitHub sync OK: %s (HTTP %d)", path, put_resp.status_code)
            else:
                logger.warning(
                    "GitHub sync FAILED: %s HTTP %d — %s",
                    path, put_resp.status_code, put_resp.text[:300],
                )

        # Trigger the pipeline workflow
        dispatch_url = f"https://api.github.com/repos/{gh_repo}/actions/workflows/{gh_workflow}/dispatches"
        resp = await client.post(
            dispatch_url,
            json={"ref": gh_ref, "inputs": {"profile": profile_id}},
            headers=headers,
        )
        if resp.status_code == 204:
            logger.info("Pipeline triggered for profile %s", profile_id)
        else:
            logger.warning(
                "Pipeline trigger returned HTTP %d for profile %s — %s",
                resp.status_code, profile_id, resp.text[:300],
            )


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    profile_id = user.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found")

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "agent"))
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    cv_path = os.path.join(jobagent_dir, "knowledge", profile_id, "cv.md")
    db_path_get = os.environ.get("DB_PATH", "data/jobseeker.db")

    # Restore YAML from DB if the filesystem was wiped (e.g. Railway redeploy)
    if not os.path.exists(yaml_path):
        stored_yaml = get_user_profile_yaml(db_path_get, user["id"])
        if not stored_yaml:
            raise HTTPException(status_code=404, detail="Profile file not found")
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        with open(yaml_path, "w") as f:
            f.write(stored_yaml)

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    # Normalize nested YAML (jobagent format) → flat format ProfileEditor expects
    user_block = raw.get("user", {})
    target_block = raw.get("target", {})
    profile_data = {
        "name": user_block.get("name", ""),
        "email": user_block.get("email", None),
        "languages": user_block.get("languages", []),
        "home_locations": user_block.get("home_locations", []),
        "current_level": "",
        "track": "",
        "target_level": "",
        "domains": target_block.get("domains", {}),
        "skills": raw.get("skills", []),
        "exclude_companies": user_block.get("exclude_companies", []),
        # UI preferences (may not exist in manually-created YAMLs — use sensible defaults)
        "salary_min": target_block.get("salary_min", 60000),
        "location_preference": user_block.get("location_preference", "b"),
    }

    # Prefer DB-stored cv_md (survives redeploys); fall back to disk
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    cv_markdown = get_user_cv_md(db_path, user["id"]) or ""
    if not cv_markdown and os.path.exists(cv_path):
        with open(cv_path) as f:
            cv_markdown = f.read()
        # Opportunistic: persist to DB now so the next redeploy won't lose it
        if cv_markdown:
            save_user_cv_md(db_path, user["id"], cv_markdown)

    return {"profile": profile_data, "cv_markdown": cv_markdown}


class UpdateProfileRequest(BaseModel):
    name: str
    home_locations: list[str]
    domains: dict[str, int]
    skills: list[str]
    salary_min: int = 60000
    location_preference: str = "b"


@router.patch("/profile")
async def update_profile(body: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Surgically update the safe/UI-editable fields in the profile YAML.
    Uses ruamel.yaml to preserve comments, story banks, seniority weights, etc."""
    profile_id = user.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found")

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "agent"))
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    db_path_patch = os.environ.get("DB_PATH", "data/jobseeker.db")

    # Restore YAML from DB if the filesystem was wiped (e.g. Railway redeploy)
    if not os.path.exists(yaml_path):
        stored_yaml = get_user_profile_yaml(db_path_patch, user["id"])
        if not stored_yaml:
            raise HTTPException(status_code=404, detail="Profile file not found")
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        with open(yaml_path, "w") as f:
            f.write(stored_yaml)

    from ruamel.yaml import YAML  # noqa: PLC0415
    from ruamel.yaml.comments import CommentedMap, CommentedSeq  # noqa: PLC0415
    import io  # noqa: PLC0415

    ry = YAML()
    ry.preserve_quotes = True
    with open(yaml_path) as f:
        raw = ry.load(f)

    # Patch only safe, UI-managed fields
    raw.setdefault("user", CommentedMap())
    raw.setdefault("target", CommentedMap())

    raw["user"]["name"] = body.name
    raw["user"]["home_locations"] = body.home_locations
    raw["user"]["location_preference"] = body.location_preference
    raw["target"]["salary_min"] = body.salary_min

    # Replace domains preserving any inline comments already on the node
    domains_node = CommentedMap(body.domains)
    raw["target"]["domains"] = domains_node

    # Replace skills as a plain list
    raw["skills"] = CommentedSeq(body.skills)

    buf = io.StringIO()
    ry.dump(raw, buf)
    updated_yaml = buf.getvalue()
    with open(yaml_path, "w") as f:
        f.write(updated_yaml)

    # Persist updated YAML to DB so it survives redeploys
    save_user_profile_yaml(db_path_patch, user["id"], updated_yaml)

    return {"ok": True}


@router.post("/upload-cv", dependencies=[Depends(get_current_user)])
async def upload_cv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    contents = await file.read()
    if len(contents) > MAX_CV_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        markdown = docx_to_markdown(tmp_path)
    finally:
        os.unlink(tmp_path)

    return {"markdown": markdown}
