import os
import sys
import tempfile
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
import yaml

from api.middleware.auth import get_current_user
from api.db.queries import update_user_profile_id

MAX_CV_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


def _load_jobagent():
    """Add JOBAGENT_DIR to sys.path so we can import from jobagent."""
    jobagent_dir = os.environ.get("JOBAGENT_DIR", "../jobagent")
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
    profile_id = _generate_profile_id(body.profile.get("name", "user"))
    profile_yaml = _build_profile_yaml(
        body.profile, profile_id, body.salary_min, body.location_preference
    )

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "../jobagent"))
    _write_profile_files(jobagent_dir, profile_id, body.cv_markdown, profile_yaml)

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    update_user_profile_id(db_path, user["id"], profile_id)

    return {"profile_id": profile_id}


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    profile_id = user.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found")

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "../jobagent"))
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    cv_path = os.path.join(jobagent_dir, "knowledge", profile_id, "cv.md")

    if not os.path.exists(yaml_path):
        raise HTTPException(status_code=404, detail="Profile file not found")

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
    }

    cv_markdown = ""
    if os.path.exists(cv_path):
        with open(cv_path) as f:
            cv_markdown = f.read()

    return {"profile": profile_data, "cv_markdown": cv_markdown}


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
