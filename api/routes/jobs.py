import json
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from api.db.queries import get_jobs, get_job_by_id, set_job_applied
from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

PERIOD_DAYS = {"today": 0, "week": 7, "month": 30}


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _period_to_date_from(period: str | None) -> str | None:
    if not period or period == "all":
        return None
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    if days == 0:
        return date.today().isoformat()
    return (date.today() - timedelta(days=days)).isoformat()


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to a URL/filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len]


@router.get("")
def list_jobs(
    tier: Annotated[list[str], Query()] = [],
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: dict = Depends(get_current_user),
):
    effective_date_from = date_from or _period_to_date_from(period)
    tiers = [t.upper() for t in tier] if tier else None
    jobs = get_jobs(
        _db_path(),
        tiers=tiers,
        date_from=effective_date_from,
        date_to=date_to,
        user_id=user["id"],
    )
    return {
        "jobs": jobs,
        "filters": {"tier": tier, "period": period or "all"},
        "total": len(jobs),
    }


@router.get("/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    row["parsed"] = json.loads(row["parsed"]) if row.get("parsed") else None
    row["scored"] = json.loads(row["scored"]) if row.get("scored") else None
    return row


class ApplyPayload(BaseModel):
    applied: bool


@router.post("/{job_id}/apply")
def apply_job(job_id: str, payload: ApplyPayload, user: dict = Depends(get_current_user)):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    set_job_applied(_db_path(), user["id"], job_id, payload.applied)
    return {"job_id": job_id, "applied": payload.applied}


@router.post("/{job_id}/generate-cv")
def generate_cv_endpoint(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Generate an ATS-compliant tailored CV .docx for the given job.

    Flow:
    1. Load job (404 if not found)
    2. Load user cv.md from jobagent knowledge dir (empty string if missing)
    3. Build prompts (422 if no JD extractable)
    4. Call LLM (500 if LLM fails)
    5. Build .docx, run ATS audit
    6. Return FileResponse with X-ATS-Audit header, cleanup via BackgroundTask
    """
    from api.cv.prompt import build_cv_prompts
    from api.cv.llm import generate_cv
    from api.cv.docx_builder import build_docx
    from api.cv.ats_audit import audit_docx

    # 1. Load job
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # 2. Load user cv.md if available
    user_cv_markdown = ""
    profile_id = user.get("profile_id")
    if profile_id:
        jobagent_dir = os.environ.get("JOBAGENT_DIR", "../jobagent")
        cv_path = Path(jobagent_dir) / "knowledge" / profile_id / "cv.md"
        if cv_path.exists():
            user_cv_markdown = cv_path.read_text(encoding="utf-8")

    # 3. Build prompts
    try:
        system_prompt, user_prompt = build_cv_prompts(row, user_cv_markdown)
    except ValueError as e:
        return JSONResponse(
            status_code=422,
            content={"error": "no_jd", "detail": "Job description not available for CV generation"},
        )

    # 4. Call LLM
    try:
        cv_markdown = generate_cv(system_prompt, user_prompt)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "llm_error", "detail": str(e)},
        )

    # 5. Build .docx and run ATS audit
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp_path = tmp.name
    tmp.close()

    build_docx(cv_markdown, tmp_path)
    audit_result = audit_docx(tmp_path)

    ats_header = (
        "pass"
        if audit_result["passed"]
        else f"fail:{len(audit_result['violations'])} violations"
    )

    # Build download filename: cv-{company}-{title}.docx (max 60 chars total)
    company_slug = _slugify(row.get("company", "company"))
    title_slug = _slugify(row.get("title", "cv"), max_len=20)
    filename = f"cv-{company_slug}-{title_slug}.docx"

    # 6. Cleanup tempfile after response is sent
    background_tasks.add_task(lambda: Path(tmp_path).unlink(missing_ok=True))

    return FileResponse(
        path=tmp_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
        headers={"X-ATS-Audit": ats_header},
    )
