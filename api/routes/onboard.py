import base64
import logging
import os
import sys
import tempfile
import uuid
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
    get_user_id_by_profile_id,
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


def _generate_profile_id(name: str) -> str:  # noqa: ARG001 — name ignored, kept for compat
    """Generate a random 8-char hex profile ID. Not derived from name to avoid collisions."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Per-user searches generation
# ---------------------------------------------------------------------------

_DOMAIN_SEARCH_TERMS: dict[str, str] = {
    "data":        "data",
    "ml":          "ML AI",
    "adtech":      "AdTech advertising",
    "ecommerce":   "ecommerce marketplace",
    "fintech":     "fintech payments",
    "saas":        "SaaS B2B",
    "platform":    "platform developer tools",
    "analytics":   "analytics data",
    "healthtech":  "healthtech digital health",
    "edtech":      "edtech education",
    "growth":      "growth user acquisition",
    "marketplace": "marketplace",
    "developer":   "developer tools",
    "api":         "API platform",
    "mobile":      "mobile app",
    "gaming":      "gaming",
    "crypto":      "blockchain crypto web3",
    "hr":          "HR people tech",
    "proptech":    "proptech real estate",
    "legaltech":   "legaltech",
    "security":    "cybersecurity",
    "logistics":   "logistics supply chain",
    "travel":      "travel hospitality",
    "media":       "media content",
}

_DOMAIN_ALIASES: dict[str, str] = {
    "ia": "ml", "ai": "ml", "llm": "ml", "martech": "adtech",
}

_IC_TITLES: dict[str, str] = {
    "junior":    "Junior Product Manager",
    "mid":       "Product Manager",
    "senior":    "Senior Product Manager",
    "staff":     "Staff Product Manager",
    "principal": "Principal Product Manager",
    "director":  "Principal Product Manager",  # IC director → keep principal title
    "vp":        "Staff Product Manager",
}
_MGMT_TITLES: dict[str, str] = {
    "junior":    "Product Manager",
    "mid":       "Senior Product Manager",
    "senior":    "Head of Product",
    "staff":     "Head of Product",
    "principal": "Head of Product",
    "director":  "Director of Product",
    "vp":        "VP Product",
}

_LOCATION_MAP: dict[str, str] = {
    "spain": "Spain", "españa": "Spain", "barcelona": "Spain", "madrid": "Spain",
    "netherlands": "Netherlands", "amsterdam": "Netherlands",
    "germany": "Germany", "berlin": "Germany", "munich": "Germany",
    "france": "France", "paris": "France",
    "uk": "UK", "london": "UK", "england": "UK",
    "portugal": "Portugal", "lisbon": "Portugal",
    "italy": "Italy", "milan": "Italy",
    "sweden": "Sweden", "stockholm": "Sweden",
    "denmark": "Denmark", "copenhagen": "Denmark",
    "belgium": "Belgium", "brussels": "Belgium",
    "ireland": "Ireland", "dublin": "Ireland",
    "remote": "",
}


def _generate_searches_yaml(profile: dict) -> str:
    """Generate a per-user searches.yaml based on their profile (level, track, domains, locations).

    Uses programmatic rules — no LLM. Called during first-time onboarding.
    Returns the YAML string to write as {profile_id}-searches.yaml.
    """
    level = (profile.get("target_level") or profile.get("current_level") or "senior").lower()
    track = (profile.get("track") or "ic").lower()

    # Normalize and sort domains by weight (top 3)
    raw_domains = profile.get("domains") or {}
    normalized: dict[str, int] = {}
    for d, w in raw_domains.items():
        canonical = _DOMAIN_ALIASES.get(d.lower(), d.lower())
        normalized[canonical] = max(normalized.get(canonical, 0), int(w))
    top_domains = [d for d, _ in sorted(normalized.items(), key=lambda x: -x[1])[:3]]

    # Resolve title
    title_map = _MGMT_TITLES if track == "management" else _IC_TITLES
    title = title_map.get(level, "Senior Product Manager")

    # Normalize locations (deduplicated, ordered)
    home_locs: list[str] = profile.get("home_locations") or []
    primary_locations: list[str] = []
    for loc in home_locs:
        mapped = _LOCATION_MAP.get(loc.lower(), "")
        if mapped and mapped not in primary_locations:
            primary_locations.append(mapped)
    if not primary_locations:
        primary_locations = [""]  # blank = global search

    searches: list[dict] = []

    # Main searches: title + domain × location on Indeed + Google
    for domain in (top_domains or [""])[:3]:
        domain_term = _DOMAIN_SEARCH_TERMS.get(domain, domain) if domain else ""
        query = f"{title} {domain_term}".strip() if domain_term else title
        for location in primary_locations[:2]:
            # Skip exact duplicates (e.g. if same location appears twice)
            entry = {"term": query, "location": location,
                     "sites": ["indeed", "google"], "results_wanted": 20, "hours_old": 72}
            if entry not in searches:
                searches.append(entry)

    # LinkedIn broad: title + remote
    searches.append({
        "term": f"{title} remote",
        "location": primary_locations[0] if primary_locations[0] else "",
        "sites": ["linkedin"],
        "results_wanted": 15,
        "hours_old": 72,
    })

    # LinkedIn targeted: top domain
    if top_domains:
        domain_term = _DOMAIN_SEARCH_TERMS.get(top_domains[0], top_domains[0])
        searches.append({
            "term": f"{title} {domain_term}",
            "location": "",
            "sites": ["linkedin"],
            "results_wanted": 10,
            "hours_old": 72,
        })

    return yaml.dump({"searches": searches, "is_remote": True},
                     default_flow_style=False, allow_unicode=True, sort_keys=False)


def _write_profile_files(
    jobagent_dir: str,
    profile_id: str,
    cv_markdown: str,
    profile_yaml: str,
    searches_yaml: str = "",
) -> None:
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    with open(os.path.join(profiles_dir, f"{profile_id}.yaml"), "w") as f:
        f.write(profile_yaml)

    if searches_yaml:
        with open(os.path.join(profiles_dir, f"{profile_id}-searches.yaml"), "w") as f:
            f.write(searches_yaml)

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
    base_id = _generate_profile_id(body.profile.get("name", "user"))
    # Avoid collision: if another user already owns this profile_id, append a suffix
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    profile_id = base_id
    suffix = 2
    while True:
        existing_owner = get_user_id_by_profile_id(db_path, profile_id)
        if existing_owner is None:
            break  # profile_id is free
        profile_id = f"{base_id}{suffix}"
        suffix += 1
    if profile_id != base_id:
        logger.warning(
            "profile_id collision: %r already taken, assigning %r to user_id=%d",
            base_id, profile_id, user["id"],
        )
    profile_yaml = _build_profile_yaml(
        body.profile, profile_id, body.salary_min, body.location_preference
    )

    # Generate per-user searches and patch the profile YAML to reference it
    searches_yaml = _generate_searches_yaml(body.profile)
    searches_rel_path = f"config/profiles/{profile_id}-searches.yaml"
    try:
        profile_data = yaml.safe_load(profile_yaml)
        profile_data["searches"] = searches_rel_path
        profile_yaml = yaml.dump(profile_data, default_flow_style=False,
                                 allow_unicode=True, sort_keys=False)
        logger.info("Generated per-user searches for %s (%d searches)",
                    profile_id, len(yaml.safe_load(searches_yaml).get("searches", [])))
    except Exception:
        logger.exception("Failed to patch searches path for %s — using global default", profile_id)
        searches_yaml = ""

    _write_profile_files(jobagent_dir, profile_id, body.cv_markdown, profile_yaml, searches_yaml)

    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    update_user_profile_id(db_path, user["id"], profile_id)
    save_user_cv_md(db_path, user["id"], body.cv_markdown)
    save_user_profile_yaml(db_path, user["id"], profile_yaml)

    # Sync profile to GitHub repo and trigger the scraping pipeline (fire-and-forget)
    try:
        await _sync_and_trigger_pipeline(profile_id, profile_yaml, body.cv_markdown, searches_yaml)
    except Exception:
        logger.exception("Pipeline sync/trigger failed for %s (non-fatal)", profile_id)

    return {"profile_id": profile_id}


async def _push_searches_to_github(profile_id: str, searches_yaml: str) -> None:
    """Push only the searches file to GitHub (no pipeline trigger)."""
    gh_token = os.environ.get("GH_ACTIONS_TOKEN", "")
    gh_repo = os.environ.get("GH_REPO", "")
    gh_ref = os.environ.get("GH_REF", "main")
    if not gh_token or not gh_repo:
        return
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    gh_path = f"agent/config/profiles/{profile_id}-searches.yaml"
    url = f"https://api.github.com/repos/{gh_repo}/contents/{gh_path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers, params={"ref": gh_ref})
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        gh_body = {
            "message": f"chore: update searches for {profile_id} [skip ci]",
            "content": base64.b64encode(searches_yaml.encode()).decode(),
            "branch": gh_ref,
        }
        if sha:
            gh_body["sha"] = sha
        put_resp = await client.put(url, json=gh_body, headers=headers)
        if put_resp.status_code in (200, 201):
            logger.info("GitHub searches sync OK: %s", gh_path)
        else:
            logger.warning(
                "GitHub searches sync FAILED: %s HTTP %d — %s",
                gh_path, put_resp.status_code, put_resp.text[:200],
            )


async def _sync_and_trigger_pipeline(
    profile_id: str, profile_yaml: str, cv_markdown: str, searches_yaml: str = ""
) -> None:
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
        if searches_yaml:
            files_to_push.append(
                (f"agent/config/profiles/{profile_id}-searches.yaml", searches_yaml)
            )
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

    # Regenerate per-user searches from the updated profile
    # level/track come from the YAML (not editable in UI yet, but already in the profile)
    target_block = raw.get("target") or {}
    profile_for_searches = {
        "target_level": target_block.get("level", "senior"),
        "track": target_block.get("track", "ic"),
        "domains": body.domains,
        "home_locations": body.home_locations,
    }
    try:
        searches_yaml = _generate_searches_yaml(profile_for_searches)
        searches_path = os.path.join(
            jobagent_dir, "config", "profiles", f"{profile_id}-searches.yaml"
        )
        with open(searches_path, "w") as f:
            f.write(searches_yaml)
        logger.info("Regenerated searches for profile %s after profile edit", profile_id)
        # Push updated searches to GitHub (fire-and-forget)
        await _push_searches_to_github(profile_id, searches_yaml)
    except Exception:
        logger.exception("Searches regeneration failed for %s (non-fatal)", profile_id)

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
