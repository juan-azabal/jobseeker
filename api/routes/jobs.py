import json
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import structlog

logger = structlog.get_logger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from api.db.queries import (
    get_jobs,
    get_job_by_id,
    get_job_status_by_title,
    get_user_job_score,
    get_total_job_count,
    set_job_applied,
    set_job_dismissed,
    get_user_cv_md,
    get_master_cv_json,
    set_domain_override,
    get_domain_override,
    get_all_domain_overrides,
)
from api.geo import (
    UNIVERSAL_TERMS,
    build_region_pattern,
    matches_region,
    is_pure_timezone,
)
from api.middleware.auth import get_current_user
from api.scoring import compute_tier, hybrid_score, load_profile_data, VALID_DOMAINS, _compute_eligibility_penalty
from api.skill_matcher import match_skills
from api import analytics

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


def _is_remote_requiring_reloc(job: dict, home_locations: list[str], home_regions: list[str]) -> bool:
    """Return True if a remote job pins the worker to a place outside home."""
    title_lower = (job.get("title") or "").lower()
    job_loc = (job.get("location") or "").lower()

    restriction = (job.get("remote_restriction") or "").lower()
    # Only use LLM-parsed restriction as fallback when the raw DB field is an empty
    # string (scraper found the field but it was blank) — NOT when it is NULL (scraper
    # found no explicit restriction at all). NULL raw + LLM inference causes false
    # positives that incorrectly geo-restrict jobs listed for the user's home country.
    if not restriction and job.get("remote_restriction") == "":
        parsed = job.get("parsed")
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = {}
        if isinstance(parsed, dict):
            restriction = (parsed.get("remote_restriction") or "").lower()
    if restriction in ("null", "none"):
        restriction = ""

    combined = f"{title_lower} {job_loc} {restriction}"

    if home_locations and any(home in combined for home in home_locations):
        return False
    region_re = build_region_pattern(home_regions)
    if matches_region(combined, region_re):
        return False
    if any(term in combined for term in UNIVERSAL_TERMS):
        return False
    if re.search(r"remote from \w", title_lower):
        return True
    if "(remote)" in job_loc and job_loc.replace("(remote)", "").strip():
        return True
    if restriction:
        if not is_pure_timezone(restriction):
            return True

    return False


def _compute_reloc(job: dict, home_locations: list[str], home_regions: list[str]) -> bool:
    """Return True if this job requires relocation for the given user."""
    loc_type = job.get("location_type") or ""
    job_loc = (job.get("location") or "").lower()
    if loc_type == "remote":
        return _is_remote_requiring_reloc(job, home_locations, home_regions)
    return not any(h in job_loc for h in home_locations)


def _score_single_job(
    job: dict,
    parsed: dict,
    profile: dict | None,
    home_locations: list[str],
    home_regions: list[str],
    user_id: int | None,
    db_path: str,
    skill_lookup: dict | None = None,
) -> int:
    """Score an unscored job using the heuristic path (no LLM grades).

    Computes relocation, loads domain_override from DB, calls hybrid_score
    with default grade bonus (+20 neutral), then applies relocation penalty.
    Returns 0 if profile is None.
    """
    if not profile:
        return 0
    is_reloc = _compute_reloc(job, home_locations, home_regions) if home_locations else False
    domain_override = get_domain_override(db_path, user_id, job.get("job_id", "")) if user_id is not None else None
    score = hybrid_score(
        profile,
        parsed,
        job,
        is_reloc,
        db_path=db_path,
        skill_lookup=skill_lookup,
        domain_override=domain_override,
    )
    if is_reloc and score > 0:
        loc_type = job.get("location_type") or parsed.get("location_type") or ""
        penalty = 5 if loc_type == "remote" else 15
        score = max(0, score - penalty)
    return score


def _score_and_tier_jobs(
    jobs: list[dict],
    profile: dict | None,
    home_locations: list[str],
    home_regions: list[str],
    user_id: int | None = None,
) -> list[dict]:
    """Apply per-user scoring: use RAG score when available, heuristic otherwise.

    Also applies relocation penalty and assigns tier. Sorts by score DESC.
    Batch-loads domain overrides from user_job_status for the current user.
    """
    # Batch-load domain overrides for this user
    domain_overrides: dict[str, str] = {}
    if user_id is not None:
        domain_overrides = get_all_domain_overrides(_db_path(), user_id)

    # Pre-parse all jobs and collect unique skills for batch semantic matching
    for job in jobs:
        parsed = job.get("parsed")
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = {}
            job["_parsed_dict"] = parsed
        else:
            job["_parsed_dict"] = parsed or {}

    for job in jobs:
        # Compute relocation
        is_reloc = _compute_reloc(job, home_locations, home_regions) if home_locations else False
        job["geo_restricted"] = is_reloc

        # Score: v2 hybrid → v1 RAG → hybrid with defaults
        # skill_lookup is intentionally NOT pre-computed globally: batching all
        # jobs' skills at once (300+ unique) exceeds the embedding pair limit and
        # triggers substring fallback, producing inflated scores. Per-job semantic
        # matching via db_path is consistent and uses the SQLite embedding cache.
        job_domain_override = domain_overrides.get(job["job_id"]) if profile else None
        if job.get("ujs_scored_v2") == 1 and profile:
            # v2: hybrid_score with actual LLM grades
            score = hybrid_score(
                profile,
                job["_parsed_dict"],
                job,
                is_reloc,
                technical_grade=job.get("ujs_technical_grade"),
                profile_grade=job.get("ujs_profile_grade"),
                db_path=_db_path(),
                domain_override=job_domain_override,
            )
            # v2: apply relocation penalty (same as _score_single_job unscored path)
            if is_reloc and score > 0:
                loc_type = job.get("location_type") or job["_parsed_dict"].get("location_type") or ""
                penalty = 5 if loc_type == "remote" else 15
                score = max(0, score - penalty)
        else:
            # v1 or unscored: re-score via current profile (v1 stored scores ignored)
            score = _score_single_job(
                job,
                job["_parsed_dict"],
                profile,
                home_locations,
                home_regions,
                user_id,
                _db_path(),
            )

        job["score"] = score
        job["tier"] = compute_tier(score)

        # Eligibility warning: expose restriction text when penalty fired
        parsed_dict = job["_parsed_dict"]
        if profile and _compute_eligibility_penalty(profile, parsed_dict, job) < 0:
            restriction = (parsed_dict.get("remote_restriction") or "").strip()
            if not restriction:
                # Onsite/hybrid: derive indicator from locations_mentioned or job location
                locs = [l for l in (parsed_dict.get("locations_mentioned") or []) if l]
                restriction = locs[0] if locs else (job.get("location") or "onsite")
            job["eligibility_warning"] = restriction or None
        else:
            job["eligibility_warning"] = None

    jobs.sort(key=lambda j: j["score"], reverse=True)
    return jobs


def _slugify(text: str, max_len: int = 30) -> str:
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
    hide_applied: bool = Query(default=False),
    hide_geo_restricted: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    effective_date_from = date_from or _period_to_date_from(period)
    jobs = get_jobs(
        _db_path(),
        date_from=effective_date_from,
        date_to=date_to,
        user_id=user["id"],
        hide_applied=hide_applied,
        limit=limit,
    )

    profile = load_profile_data(user["id"])
    home_locations = profile.get("home_locations", []) if profile else []
    home_regions = profile.get("home_regions", []) if profile else []

    jobs = _score_and_tier_jobs(jobs, profile, home_locations, home_regions, user_id=user["id"])

    # Apply post-scoring filters
    if tier:
        tiers_upper = {t.upper() for t in tier}
        jobs = [j for j in jobs if j["tier"] in tiers_upper]

    if hide_geo_restricted:
        jobs = [j for j in jobs if not j.get("geo_restricted")]

    # Strip internal fields and post-process enriched fields for response
    _ENRICHED_FIELDS = (
        "company_url",
        "company_logo",
        "company_industry",
        "company_size",
        "job_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_interval",
        "salary_source",
        "country",
        "city",
        "remote_type",
        "sources",
        "role_in_plain_english",
        "company_stage",
        "company_tone",
        "truly_required",
        "preferred_skills",
        "verbatim_for_cv",
        "company_context",
    )
    for job in jobs:
        job.pop("ujs_score", None)
        job.pop("ujs_tier", None)
        job.pop("ujs_scored", None)
        job.pop("ujs_technical_grade", None)
        job.pop("ujs_profile_grade", None)
        job.pop("ujs_scored_v2", None)
        job.pop("parsed", None)
        # Extract v1.5 parser fields from parsed blob before discarding it
        _pd = job.pop("_parsed_dict", None) or {}
        job["truly_required"] = _pd.get("truly_required") or _pd.get("must_have_skills")
        job["preferred_skills"] = _pd.get("preferred_skills") or _pd.get("nice_to_have_skills")
        job["verbatim_for_cv"] = _pd.get("verbatim_for_cv")
        job["company_context"] = _pd.get("company_context")
        # Parse sources JSON string → list
        if job.get("sources") is not None:
            try:
                job["sources"] = json.loads(job["sources"])
            except (json.JSONDecodeError, TypeError):
                job["sources"] = []
        # Omit null enriched fields from response
        for field in _ENRICHED_FIELDS:
            if job.get(field) is None:
                job.pop(field, None)

    total_in_db = get_total_job_count(_db_path())

    return {
        "jobs": jobs,
        "filters": {"tier": tier, "period": period or "all", "hide_geo_restricted": hide_geo_restricted},
        "total": len(jobs),
        "total_in_db": total_in_db,
    }


@router.get("/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        row["parsed"] = json.loads(row["parsed"]) if row.get("parsed") else None
    except (json.JSONDecodeError, TypeError):
        logger.warning("Malformed parsed JSON for job_id=%s", job_id)
        row["parsed"] = None

    # Inject remote_restriction from parsed so _is_remote_requiring_reloc() behaves
    # identically to the list path (which pre-extracts it via SQL json_extract).
    # SELECT * FROM jobs has no remote_restriction column, so it would otherwise be None.
    if isinstance(row.get("parsed"), dict) and row.get("remote_restriction") is None:
        row["remote_restriction"] = row["parsed"].get("remote_restriction")

    # Per-user score
    ujs = get_user_job_score(_db_path(), user["id"], job_id)
    profile = load_profile_data(user["id"])
    home_locations = profile.get("home_locations", []) if profile else []
    home_regions = profile.get("home_regions", []) if profile else []
    is_reloc = _compute_reloc(row, home_locations, home_regions) if home_locations else False
    domain_override = get_domain_override(_db_path(), user["id"], job_id)

    if ujs and ujs.get("scored_v2") == 1 and profile:
        # v2: hybrid_score with actual LLM grades
        score = hybrid_score(
            profile,
            row["parsed"] or {},
            row,
            is_reloc,
            technical_grade=ujs.get("technical_grade"),
            profile_grade=ujs.get("profile_grade"),
            db_path=_db_path(),
            domain_override=domain_override,
        )
        # v2: apply relocation penalty (same as unscored branch via _score_single_job)
        if is_reloc and score > 0:
            loc_type = row.get("location_type") or (row.get("parsed") or {}).get("location_type") or ""
            penalty = 5 if loc_type == "remote" else 15
            score = max(0, score - penalty)
        row["score"] = score
        row["tier"] = compute_tier(score)
        try:
            row["scored"] = json.loads(ujs["scored"]) if ujs.get("scored") else None
        except (json.JSONDecodeError, TypeError):
            logger.warning("Malformed scored JSON for job_id=%s user_id=%s", job_id, user["id"])
            row["scored"] = None
    else:
        # v1 or unscored: re-score via current profile (v1 stored scores ignored)
        row["score"] = _score_single_job(
            row,
            row["parsed"] or {},
            profile,
            home_locations,
            home_regions,
            user["id"],
            _db_path(),
        )
        row["tier"] = compute_tier(row["score"])
        row["scored"] = None

    # Scoring method: communicate to frontend how this score was computed
    if ujs and ujs.get("scored_v2") == 1:
        row["scoring_method"] = "rag_v2"
    else:
        row["scoring_method"] = "heuristic"

    # Aggregate applied/dismissed across all duplicates of this (company, title)
    status = get_job_status_by_title(_db_path(), user["id"], row["company"], row["title"])
    row["applied_at"] = status.get("applied_at") if status else None
    row["dismissed_at"] = status.get("dismissed_at") if status else None

    # Expose domain override in response (already computed above for scoring)
    row["domain_override"] = domain_override
    row["geo_restricted"] = is_reloc

    # Eligibility warning: expose restriction text when penalty fired
    parsed_for_penalty = row.get("parsed") or {}
    if profile and _compute_eligibility_penalty(profile, parsed_for_penalty, row) < 0:
        restriction = (parsed_for_penalty.get("remote_restriction") or "").strip()
        if not restriction:
            # Onsite/hybrid: derive indicator from locations_mentioned or job location
            locs = [l for l in (parsed_for_penalty.get("locations_mentioned") or []) if l]
            restriction = locs[0] if locs else (row.get("location") or "onsite")
        row["eligibility_warning"] = restriction or None
    else:
        row["eligibility_warning"] = None

    # Skill matches: compute semantic match status for each skill
    row["skill_matches"] = _compute_skill_matches(row, user)

    # Extract v1.5 parser fields from parsed blob to top-level for easy access
    _pd = row.get("parsed") or {}
    row["truly_required"] = _pd.get("truly_required") or _pd.get("must_have_skills")
    row["preferred_skills"] = _pd.get("preferred_skills") or _pd.get("nice_to_have_skills")
    row["verbatim_for_cv"] = _pd.get("verbatim_for_cv")
    row["company_context"] = _pd.get("company_context")

    # Parse sources JSON string → list; omit null enriched fields
    if row.get("sources") is not None:
        try:
            row["sources"] = json.loads(row["sources"])
        except (json.JSONDecodeError, TypeError):
            row["sources"] = []
    _ENRICHED_FIELDS = (
        "company_url",
        "company_logo",
        "company_industry",
        "company_size",
        "job_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_interval",
        "salary_source",
        "country",
        "city",
        "remote_type",
        "sources",
        "role_in_plain_english",
        "company_stage",
        "company_tone",
        "truly_required",
        "preferred_skills",
        "verbatim_for_cv",
        "company_context",
    )
    for field in _ENRICHED_FIELDS:
        if row.get(field) is None:
            row.pop(field, None)

    analytics.capture(
        user["id"],
        "job_viewed",
        {
            "job_id": job_id,
            "company": row.get("company"),
            "domain": row.get("domain"),
            "rag_score": ujs["score"] if ujs else None,
            "heuristic_score": row["score"] if not ujs else None,
            "tier": row.get("tier"),
        },
    )
    return row


def _compute_skill_matches(row: dict, user: dict) -> dict | None:
    """Compute skill match data for job detail response.

    Returns None if user has no profile or job has no parsed skills.
    """
    profile = load_profile_data(user["id"])
    if not profile:
        return None

    parsed = row.get("parsed") or {}
    must_have = parsed.get("truly_required") or parsed.get("must_have_skills") or []
    nice_to_have = list(
        set(
            (parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])
            + (parsed.get("technical_stack") or [])
        )
    )

    if not must_have and not nice_to_have:
        return None

    user_skills = profile.get("skills", [])
    db = _db_path()

    def _serialize_matches(results):
        return [
            {
                "skill": m.job_skill,
                "status": m.status,
                "matched_to": m.user_skill,
                "similarity": round(m.similarity, 2),
            }
            for m in results
        ]

    must_results = match_skills(user_skills, must_have, db) if must_have else []
    nice_results = match_skills(user_skills, nice_to_have, db) if nice_to_have else []

    return {
        "must_have": _serialize_matches(must_results),
        "nice_to_have": _serialize_matches(nice_results),
    }


class ApplyPayload(BaseModel):
    applied: bool


@router.post("/{job_id}/apply")
def apply_job(job_id: str, payload: ApplyPayload, user: dict = Depends(get_current_user)):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    set_job_applied(_db_path(), user["id"], job_id, payload.applied)
    ujs = get_user_job_score(_db_path(), user["id"], job_id)
    analytics.capture(
        user["id"],
        "job_applied",
        {
            "job_id": job_id,
            "company": row.get("company"),
            "domain": row.get("domain"),
            "score": ujs["score"] if ujs else None,
            "tier": ujs["tier"] if ujs else None,
        },
    )
    return {"job_id": job_id, "applied": payload.applied}


@router.post("/{job_id}/dismiss")
def dismiss_job(job_id: str, user: dict = Depends(get_current_user)):
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    set_job_dismissed(_db_path(), user["id"], job_id)
    ujs = get_user_job_score(_db_path(), user["id"], job_id)
    analytics.capture(
        user["id"],
        "job_dismissed",
        {
            "job_id": job_id,
            "company": row.get("company"),
            "domain": row.get("domain"),
            "score": ujs["score"] if ujs else None,
            "tier": ujs["tier"] if ujs else None,
        },
    )
    return {"job_id": job_id, "dismissed": True}


class DomainOverrideRequest(BaseModel):
    domain: str | None  # None clears the override


@router.patch("/{job_id}/domain")
def set_job_domain_override(
    job_id: str,
    body: DomainOverrideRequest,
    user: dict = Depends(get_current_user),
):
    """Set or clear the per-user domain override for a job.

    A valid domain value stores the override and uses it in heuristic scoring.
    Passing null clears the override and reverts to the normal cascade.
    """
    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.domain is not None and body.domain not in VALID_DOMAINS:
        raise HTTPException(status_code=422, detail=f"Invalid domain: {body.domain!r}")
    old_domain = get_domain_override(_db_path(), user["id"], job_id)
    set_domain_override(_db_path(), user["id"], job_id, body.domain)
    analytics.capture(
        user["id"],
        "domain_overridden",
        {
            "job_id": job_id,
            "old_domain": old_domain,
            "new_domain": body.domain,
        },
    )
    return {"ok": True, "domain": body.domain}


@router.post("/{job_id}/generate-cv")
def generate_cv_endpoint(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Generate an ATS-compliant tailored CV .docx for the given job."""
    from api.cv.plan import build_cv_plan
    from api.cv.prompt import build_cv_prompts
    from api.cv.llm import generate_cv
    from api.cv.docx_builder import build_docx
    from api.cv.ats_audit import audit_docx
    from api.cv.validator import validate_cv, build_fix_prompt

    row = get_job_by_id(_db_path(), job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Prefer DB-stored cv_md (survives redeploys); fall back to disk
    user_cv_markdown = get_user_cv_md(_db_path(), user["id"]) or ""
    cv_md_source = "none"
    if user_cv_markdown:
        cv_md_source = "db"
    else:
        profile_id = user.get("profile_id")
        if profile_id:
            jobagent_dir = os.environ.get("JOBAGENT_DIR", "agent")
            cv_path = Path(jobagent_dir) / "knowledge" / profile_id / "cv.md"
            if cv_path.exists():
                user_cv_markdown = cv_path.read_text(encoding="utf-8")
                cv_md_source = "disk"

    logger.info(
        "CV generation started",
        job_id=job_id,
        user_id=user["id"],
        cv_md_source=cv_md_source,
        cv_md_len=len(user_cv_markdown),
    )

    # Inject per-user scored data if available (for plan building)
    ujs = get_user_job_score(_db_path(), user["id"], job_id)
    if ujs and ujs.get("scored"):
        row["scored"] = ujs["scored"]

    # Plan is built from the job data + the user's CV (from DB) — no disk files
    plan = build_cv_plan(row, user_cv_markdown)
    profile_data = load_profile_data(user["id"])

    # ── Master CV two-step pipeline (Phase 4) ──────────────────────────────
    cv_plan_header: str | None = None
    master_cv_json_str = get_master_cv_json(_db_path(), user["id"])
    if master_cv_json_str:
        try:
            import json as _json
            from api.cv.select import select_cv_content
            from api.cv.rewrite import rewrite_cv_content

            master_cv = _json.loads(master_cv_json_str)
            parsed_job = row.get("parsed") or {}
            if isinstance(parsed_job, str):
                try:
                    parsed_job = _json.loads(parsed_job)
                except (ValueError, TypeError):
                    parsed_job = {}

            selected = select_cv_content(master_cv, parsed_job, user["id"])
            if selected:
                cv_plan_header = _json.dumps(
                    {
                        "entries": [
                            {"id": e["id"], "company": e["company"], "relevance": e["relevance_score"]}
                            for e in selected["work"]
                        ],
                        "skill_intersection": selected["skill_intersection"],
                    }
                )
                cv_markdown = rewrite_cv_content(selected, row, distinct_id=str(user["id"]))
                logger.info(
                    "CV generation via Master CV pipeline",
                    job_id=job_id,
                    user_id=user["id"],
                    entries=len(selected["work"]),
                )
                fix_applied = False
                validation = {"passed": True, "warnings": []}
                tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
                tmp_path = tmp.name
                tmp.close()
                build_docx(cv_markdown, tmp_path)
                audit_result = audit_docx(tmp_path)
                ats_header = "pass" if audit_result["passed"] else f"fail:{len(audit_result['violations'])} violations"
                cv_validation_header = _json.dumps({"passed": True, "warning_count": 0})
                company_slug = _slugify(row.get("company", "company"))
                title_slug = _slugify(row.get("title", "cv"), max_len=20)
                filename = f"cv-{company_slug}-{title_slug}.docx"
                provider = os.environ.get("CV_LLM_PROVIDER", "anthropic")
                model = os.environ.get("CV_LLM_MODEL", "")
                background_tasks.add_task(lambda: Path(tmp_path).unlink(missing_ok=True))
                background_tasks.add_task(
                    analytics.capture,
                    user["id"],
                    "cv_generated",
                    {
                        "job_id": job_id,
                        "company": row.get("company"),
                        "provider": provider,
                        "model": model,
                        "pipeline": "master_cv",
                        "validation_passed": True,
                        "fix_applied": False,
                        "ats_passed": audit_result["passed"],
                        "ats_violation_count": len(audit_result.get("violations", [])),
                    },
                )
                response_headers = {
                    "X-ATS-Audit": ats_header,
                    "X-CV-Validation": cv_validation_header,
                    "X-CV-Fix-Applied": "false",
                }
                if cv_plan_header:
                    response_headers["X-CV-Plan"] = cv_plan_header
                return FileResponse(
                    path=tmp_path,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename=filename,
                    headers=response_headers,
                )
        except Exception:
            logger.warning("Master CV pipeline failed, falling back to legacy", job_id=job_id, exc_info=True)
    # ── Legacy pipeline ────────────────────────────────────────────────────

    try:
        system_prompt, user_prompt = build_cv_prompts(row, user_cv_markdown, plan, profile_data)
    except FileNotFoundError as e:
        logger.error("CV generation failed: missing reference file", job_id=job_id, user_id=user["id"], detail=str(e))
        return JSONResponse(
            status_code=422,
            content={"error": "missing_references", "detail": str(e)},
        )
    except ValueError as e:
        logger.error("CV generation failed: no JD text", job_id=job_id, user_id=user["id"], detail=str(e))
        return JSONResponse(
            status_code=422,
            content={"error": "no_jd", "detail": "Job description not available for CV generation"},
        )

    try:
        cv_markdown = generate_cv(system_prompt, user_prompt, distinct_id=str(user["id"]))
    except Exception as e:
        logger.error("CV generation failed: LLM error", job_id=job_id, user_id=user["id"], exc_info=True, detail=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "llm_error", "detail": str(e)},
        )

    fix_applied = False
    validation = validate_cv(cv_markdown, plan)

    if not validation["passed"]:
        try:
            fix_system, fix_user = build_fix_prompt(cv_markdown, validation["errors"])
            cv_markdown = generate_cv(fix_system, fix_user, distinct_id=str(user["id"]))
            fix_applied = True
        except Exception:
            pass

        validation = validate_cv(cv_markdown, plan)

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    build_docx(cv_markdown, tmp_path)

    audit_result = audit_docx(tmp_path)
    ats_header = "pass" if audit_result["passed"] else f"fail:{len(audit_result['violations'])} violations"

    cv_validation_header = json.dumps(
        {
            "passed": validation["passed"],
            "warning_count": len(validation.get("warnings", [])),
        }
    )

    company_slug = _slugify(row.get("company", "company"))
    title_slug = _slugify(row.get("title", "cv"), max_len=20)
    filename = f"cv-{company_slug}-{title_slug}.docx"

    provider = os.environ.get("CV_LLM_PROVIDER", "anthropic")
    model = os.environ.get("CV_LLM_MODEL", "")
    background_tasks.add_task(lambda: Path(tmp_path).unlink(missing_ok=True))
    background_tasks.add_task(
        analytics.capture,
        user["id"],
        "cv_generated",
        {
            "job_id": job_id,
            "company": row.get("company"),
            "provider": provider,
            "model": model,
            "validation_passed": validation["passed"],
            "fix_applied": fix_applied,
            "ats_passed": audit_result["passed"],
            "ats_violation_count": len(audit_result.get("violations", [])),
        },
    )

    return FileResponse(
        path=tmp_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
        headers={
            "X-ATS-Audit": ats_header,
            "X-CV-Validation": cv_validation_header,
            "X-CV-Fix-Applied": "true" if fix_applied else "false",
        },
    )
