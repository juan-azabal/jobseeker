import os
import sys
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from api.middleware.auth import get_current_user

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
