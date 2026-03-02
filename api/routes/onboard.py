import base64
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
import yaml

import structlog

logger = structlog.get_logger(__name__)

from api.middleware.auth import get_current_user
from api import analytics
from api.db.queries import (
    save_user_cv_md,
    get_user_cv_md,
    save_user_profile_yaml,
    get_user_profile_yaml,
)
from api.onboard_utils import (
    docx_to_markdown as _docx_to_markdown,
    _extract_profile as _onboard_extract_profile,
    _build_profile_yaml as _onboard_build_profile_yaml,
)
from shared.file_extract import extract_text_from_file

MAX_CV_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


def docx_to_markdown(path: str) -> str:
    return _docx_to_markdown(path)


def _extract_profile_from_cv(cv_text: str) -> dict:
    import os  # noqa: PLC0415

    if os.getenv("POSTHOG_API_KEY"):
        from posthog.ai.openai import OpenAI  # noqa: PLC0415
    else:
        from openai import OpenAI  # noqa: PLC0415

    return _onboard_extract_profile(cv_text, OpenAI())


class GenerateProfileRequest(BaseModel):
    cv_markdown: str


@router.post("/generate-profile", dependencies=[Depends(get_current_user)])
async def generate_profile(body: GenerateProfileRequest):
    profile = _extract_profile_from_cv(body.cv_markdown)
    # Bootstrap seniority_weights from extracted current/target level so the
    # ProfileEditor can show them as editable sliders from the start.
    profile.setdefault("seniority_weights", _derive_seniority_weights(profile))
    return profile


def _build_profile_yaml(profile: dict, profile_id: str, salary_min: int, location_preference: str) -> str:
    return _onboard_build_profile_yaml(
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
    "data": "data",
    "ml": "ML AI",
    "adtech": "AdTech advertising",
    "ecommerce": "ecommerce marketplace",
    "fintech": "fintech payments",
    "saas": "SaaS B2B",
    "platform": "platform developer tools",
    "analytics": "analytics data",
    "healthtech": "healthtech digital health",
    "edtech": "edtech education",
    "growth": "growth user acquisition",
    "marketplace": "marketplace",
    "developer": "developer tools",
    "api": "API platform",
    "mobile": "mobile app",
    "gaming": "gaming",
    "crypto": "blockchain crypto web3",
    "hr": "HR people tech",
    "proptech": "proptech real estate",
    "legaltech": "legaltech",
    "security": "cybersecurity",
    "logistics": "logistics supply chain",
    "travel": "travel hospitality",
    "media": "media content",
}

_DOMAIN_ALIASES: dict[str, str] = {
    "ia": "ml",
    "ai": "ml",
    "llm": "ml",
    "martech": "adtech",
}

_IC_TITLES: dict[str, str] = {
    "junior": "Junior Product Manager",
    "mid": "Product Manager",
    "senior": "Senior Product Manager",
    "staff": "Staff Product Manager",
    "principal": "Principal Product Manager",
    "director": "Principal Product Manager",  # IC director → keep principal title
    "vp": "Staff Product Manager",
}
_MGMT_TITLES: dict[str, str] = {
    "junior": "Product Manager",
    "mid": "Senior Product Manager",
    "senior": "Head of Product",
    "staff": "Head of Product",
    "principal": "Head of Product",
    "director": "Director of Product",
    "vp": "VP Product",
}

_LOCATION_MAP: dict[str, str] = {
    "spain": "Spain",
    "españa": "Spain",
    "barcelona": "Spain",
    "madrid": "Spain",
    "netherlands": "Netherlands",
    "amsterdam": "Netherlands",
    "germany": "Germany",
    "berlin": "Germany",
    "munich": "Germany",
    "france": "France",
    "paris": "France",
    "uk": "UK",
    "london": "UK",
    "england": "UK",
    "portugal": "Portugal",
    "lisbon": "Portugal",
    "italy": "Italy",
    "milan": "Italy",
    "sweden": "Sweden",
    "stockholm": "Sweden",
    "denmark": "Denmark",
    "copenhagen": "Denmark",
    "belgium": "Belgium",
    "brussels": "Belgium",
    "ireland": "Ireland",
    "dublin": "Ireland",
    "remote": "",
}

# city/country → canonical country name, used to derive the relocation-rejection rule
# in per-user preferences.yaml. Keep in sync with _LOCATION_MAP.
_HOME_TO_COUNTRY: dict[str, str] = {
    "spain": "Spain",
    "españa": "Spain",
    "barcelona": "Spain",
    "madrid": "Spain",
    "valencia": "Spain",
    "bilbao": "Spain",
    "netherlands": "Netherlands",
    "amsterdam": "Netherlands",
    "rotterdam": "Netherlands",
    "germany": "Germany",
    "berlin": "Germany",
    "munich": "Germany",
    "hamburg": "Germany",
    "france": "France",
    "paris": "France",
    "lyon": "France",
    "uk": "UK",
    "london": "UK",
    "england": "UK",
    "manchester": "UK",
    "portugal": "Portugal",
    "lisbon": "Portugal",
    "porto": "Portugal",
    "italy": "Italy",
    "milan": "Italy",
    "rome": "Italy",
    "sweden": "Sweden",
    "stockholm": "Sweden",
    "denmark": "Denmark",
    "copenhagen": "Denmark",
    "belgium": "Belgium",
    "brussels": "Belgium",
    "ireland": "Ireland",
    "dublin": "Ireland",
    "switzerland": "Switzerland",
    "zurich": "Switzerland",
    "austria": "Austria",
    "vienna": "Austria",
    "poland": "Poland",
    "warsaw": "Poland",
    "czechia": "Czechia",
    "prague": "Czechia",
    "finland": "Finland",
    "helsinki": "Finland",
    "norway": "Norway",
    "oslo": "Norway",
}


# Seniority level → experience-year phrases to exclude from job titles.
# Levels below the target are treated as junior relative to the user's target.
# Note: "APM" is intentionally excluded — it matches "APM (Application Performance Monitoring)"
# in tech job descriptions, causing false positives. "associate product manager" already covers
# the intended exclusion in titles.
_SENIORITY_DEALBREAKERS: dict[str, list[str]] = {
    "junior": [],
    "mid": ["intern", "internship"],
    "senior": [
        "junior",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate product manager",
        "0-2 years",
        "1-3 years",
    ],
    "staff": [
        "junior",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate product manager",
        "0-2 years",
        "1-3 years",
        "2-4 years",
    ],
    "principal": [
        "junior",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate product manager",
        "0-2 years",
        "1-3 years",
        "2-4 years",
    ],
    "director": [
        "junior",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate product manager",
        "0-2 years",
        "1-3 years",
        "2-4 years",
    ],
    "vp": [
        "junior",
        "intern",
        "internship",
        "entry level",
        "entry-level",
        "associate product manager",
        "0-2 years",
        "1-3 years",
        "2-4 years",
    ],
}

# IC track title keywords (no director/VP — those are management-track roles)
_IC_TITLE_KEYWORDS: list[str] = [
    "product manager",
    "product lead",
    "product owner",
    "principal pm",
    "staff pm",
    "senior pm",
]
# Management track includes IC keywords + leadership titles
_MGMT_TITLE_KEYWORDS: list[str] = _IC_TITLE_KEYWORDS + [
    "director of product",
    "head of product",
    "group product manager",
    "vp product",
    "vp of product",
]


def _derive_seniority_weights(profile: dict) -> dict[str, int]:
    """Bootstrap seniority_weights from CV-extracted current/target level.

    Called during generate-profile and first-time save-profile to give users
    a sensible starting point they can then adjust in the ProfileEditor.
    """
    current = (profile.get("current_level") or "").lower().strip()
    target = (profile.get("target_level") or "").lower().strip()
    weights: dict[str, int] = {}
    if target:
        weights[target] = 15  # primary aspirational level
    if current and current != target:
        weights[current] = 10  # level already demonstrated
    return weights


def _generate_searches_yaml(profile: dict) -> str:
    """Generate a per-user searches.yaml based on their profile (level, track, domains, locations).

    Uses programmatic rules — no LLM. Called during first-time onboarding.
    Returns the YAML string to write as {profile_id}-searches.yaml.
    """
    # Prefer seniority_weights (user-defined) over the old level field.
    sw = profile.get("seniority_weights") or {}
    if sw:
        level = max(sw, key=lambda k: sw[k])
    else:
        level = (profile.get("target_level") or profile.get("current_level") or "senior").lower()
    track = (profile.get("track") or "ic").lower()

    # Normalize and sort domains by weight (top 3)
    raw_domains = profile.get("domains") or {}
    normalized: dict[str, int] = {}
    for d, w in raw_domains.items():
        canonical = _DOMAIN_ALIASES.get(d.lower(), d.lower())
        normalized[canonical] = max(normalized.get(canonical, 0), int(w))
    top_domains = [d for d, _ in sorted(normalized.items(), key=lambda x: -x[1])[:3]]

    # Resolve top-2 distinct title variants from seniority_weights
    title_map = _MGMT_TITLES if track == "management" else _IC_TITLES
    titles: list[str] = []
    for lvl, _ in sorted(sw.items(), key=lambda x: -x[1]):
        t = title_map.get(lvl)
        if t and t not in titles:
            titles.append(t)
        if len(titles) == 2:
            break
    if not titles:
        titles = [title_map.get(level, "Senior Product Manager")]
    title = titles[0]
    title2 = titles[1] if len(titles) > 1 else None

    # Normalize locations from home_locations (deduplicated, ordered)
    home_locs: list[str] = profile.get("home_locations") or []
    primary_locations: list[str] = []
    for loc in home_locs:
        mapped = _LOCATION_MAP.get(loc.lower(), "")
        if mapped and mapped not in primary_locations:
            primary_locations.append(mapped)
    # Extend with high-weight countries from country_weights (cap 3 total)
    country_weights_map = profile.get("country_weights") or {}
    for c, w in sorted(country_weights_map.items(), key=lambda x: -x[1]):
        if len(primary_locations) >= 3:
            break
        if w <= 0 or c == "remote":
            continue
        mapped = _LOCATION_MAP.get(c.lower(), "")
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
            entry = {
                "term": query,
                "location": location,
                "sites": ["indeed", "google"],
                "results_wanted": 20,
                "hours_old": 72,
            }
            if entry not in searches:
                searches.append(entry)

    # LinkedIn broad: title + remote
    searches.append(
        {
            "term": f"{title} remote",
            "location": primary_locations[0] if primary_locations[0] else "",
            "sites": ["linkedin"],
            "results_wanted": 15,
            "hours_old": 72,
        }
    )

    # LinkedIn targeted: top domain
    if top_domains:
        domain_term = _DOMAIN_SEARCH_TERMS.get(top_domains[0], top_domains[0])
        searches.append(
            {
                "term": f"{title} {domain_term}",
                "location": "",
                "sites": ["linkedin"],
                "results_wanted": 10,
                "hours_old": 72,
            }
        )

    # LinkedIn: 2nd title variant (if distinct from primary)
    if title2:
        searches.append(
            {
                "term": f"{title2} remote",
                "location": primary_locations[0] if primary_locations[0] else "",
                "sites": ["linkedin"],
                "results_wanted": 15,
                "hours_old": 72,
            }
        )

    # LinkedIn skill-based: title + top profile skill (extra precision signal)
    skills = profile.get("skills") or []
    if skills:
        top_skill = skills[0]
        searches.append(
            {
                "term": f"{title} {top_skill}",
                "location": primary_locations[0] if primary_locations and primary_locations[0] else "",
                "sites": ["linkedin"],
                "results_wanted": 15,
                "hours_old": 72,
            }
        )

    return yaml.dump(
        {"searches": searches, "is_remote": True}, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def _generate_preferences_yaml(profile: dict) -> str:
    """Generate per-user preferences YAML fully from profile data.

    No hardcoded salary, cities, or seniority assumptions — everything derived.
    deal_breakers and title_must_contain_one_of depend on seniority_weights + track.
    """
    home_locs = profile.get("home_locations") or []
    salary_min = int(profile.get("salary_min") or 60000)
    exclude_companies = list(profile.get("exclude_companies") or [])
    sw = profile.get("seniority_weights") or {}
    track = (profile.get("track") or "ic").lower()

    # Seniority-aware deal_breakers
    top_level = max(sw, key=lambda k: sw[k]) if sw else "senior"
    deal_breakers = list(_SENIORITY_DEALBREAKERS.get(top_level, _SENIORITY_DEALBREAKERS["senior"]))

    # Title keywords depend on IC vs management track
    title_keywords = _MGMT_TITLE_KEYWORDS if track == "management" else _IC_TITLE_KEYWORDS

    # Onsite cities: map home_locations to canonical country/city names
    accept_cities: list[str] = []
    for loc in home_locs:
        mapped = _LOCATION_MAP.get(loc.lower(), "")
        if mapped and mapped not in accept_cities:
            accept_cities.append(mapped)

    # Primary country for relocation rejection rule
    primary_country = None
    for loc in home_locs:
        c = _HOME_TO_COUNTRY.get(loc.lower())
        if c:
            primary_country = c
            break

    location_block: dict = {
        "accept_remote": True,
        "accept_hybrid": True,
        "accept_onsite_cities": accept_cities,
    }
    if primary_country:
        location_block["reject_if_requires_relocation_outside"] = primary_country

    data = {
        "prefilter": {
            "deal_breakers": deal_breakers,
            "title_must_contain_one_of": title_keywords,
            "title_exclude": [
                # Note: "growth" intentionally excluded — "Product Manager, Growth" is a
                # legitimate PM role. Non-PM growth roles fail title_must_contain_one_of.
                "business development",
                "crm manager",
                "marketing manager",
                "project manager",
                "program manager",
                "sales",
                "account manager",
                "customer success",
                "deposit product",
                "lending",
                "insurance",
            ],
            "exclude_companies": [
                "Gartner",
                "Capterra",
                "GetApp",
                "Software Advice",
                "G2",
            ]
            + exclude_companies,
            "location": location_block,
        },
        "scoring": {"auto_generate_package": 65, "manual_review": 50, "auto_reject": 50},
        "salary": {"min_eur": salary_min, "max_eur": salary_min + 40000, "currency": "EUR"},
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _write_profile_files(
    jobagent_dir: str,
    profile_id: str,
    cv_markdown: str,
    profile_yaml: str,
    searches_yaml: str = "",
    preferences_yaml: str = "",
) -> None:
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    with open(os.path.join(profiles_dir, f"{profile_id}.yaml"), "w") as f:
        f.write(profile_yaml)

    if searches_yaml:
        with open(os.path.join(profiles_dir, f"{profile_id}-searches.yaml"), "w") as f:
            f.write(searches_yaml)

    if preferences_yaml:
        with open(os.path.join(profiles_dir, f"{profile_id}-preferences.yaml"), "w") as f:
            f.write(preferences_yaml)

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
    # profile_id is always set from first login — never None for authenticated users.
    profile_id = user["profile_id"]
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")

    if user.get("onboarded"):
        # User already has a profile (profile_yaml in DB) — update cv.md and restore YAML if lost.
        if body.cv_markdown:  # Guard: never overwrite existing cv_md with empty string
            save_user_cv_md(db_path, user["id"], body.cv_markdown)
            # Also write to disk for the current process lifetime
            knowledge_dir = os.path.join(jobagent_dir, "knowledge", profile_id)
            os.makedirs(knowledge_dir, exist_ok=True)
            with open(os.path.join(knowledge_dir, "cv.md"), "w") as f:
                f.write(body.cv_markdown)

        # Recovery: if profile YAML is completely gone (not in DB, not on disk), regenerate it.
        # This breaks the redirect loop caused by Railway ephemeral filesystem wipes.
        # We only regenerate when YAML is truly absent — never overwrite an existing one.
        yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
        stored_yaml = get_user_profile_yaml(db_path, user["id"])
        if not stored_yaml and not os.path.exists(yaml_path):
            try:
                logger.info("Profile YAML missing for %s — regenerating from submitted profile data", profile_id)
                recovered_yaml = _build_profile_yaml(
                    body.profile, profile_id, body.salary_min, body.location_preference
                )
                os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
                with open(yaml_path, "w") as f:
                    f.write(recovered_yaml)
                save_user_profile_yaml(db_path, user["id"], recovered_yaml)
            except Exception:
                logger.exception("YAML recovery failed for %s — continuing without YAML", profile_id)

        return {"profile_id": profile_id}

    # First-time setup: profile_id was assigned at login, just generate YAML + searches.
    logger.info("First-time onboarding for user_id=%d profile_id=%r", user["id"], profile_id)
    profile_yaml = _build_profile_yaml(body.profile, profile_id, body.salary_min, body.location_preference)

    # Generate per-user searches and patch the profile YAML to reference it.
    # Also inject seniority_weights (user-editable, not in the agent's _build_profile_yaml).
    profile_for_gen = {**body.profile, "salary_min": body.salary_min}
    searches_yaml = _generate_searches_yaml(profile_for_gen)
    preferences_yaml = _generate_preferences_yaml(profile_for_gen)
    searches_rel_path = f"config/profiles/{profile_id}-searches.yaml"
    try:
        profile_data = yaml.safe_load(profile_yaml)
        profile_data["searches"] = searches_rel_path
        profile_data["preferences"] = f"config/profiles/{profile_id}-preferences.yaml"
        # Store user-defined seniority_weights (prefer what the user set in ProfileEditor)
        sw = body.profile.get("seniority_weights") or _derive_seniority_weights(body.profile)
        if sw:
            profile_data.setdefault("target", {})["seniority_weights"] = sw
        # Inject search_titles from the profile editor
        st = body.profile.get("search_titles") or []
        if st:
            profile_data.setdefault("target", {})["search_titles"] = st
        profile_yaml = yaml.dump(profile_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info(
            "Generated per-user searches for %s (%d searches)",
            profile_id,
            len(yaml.safe_load(searches_yaml).get("searches", [])),
        )
    except Exception:
        logger.exception("Failed to patch searches+preferences paths for %s — using global defaults", profile_id)
        searches_yaml = ""
        preferences_yaml = ""

    _write_profile_files(
        jobagent_dir,
        profile_id,
        body.cv_markdown,
        profile_yaml,
        searches_yaml,
        preferences_yaml,
    )

    save_user_cv_md(db_path, user["id"], body.cv_markdown)
    save_user_profile_yaml(db_path, user["id"], profile_yaml)

    # Sync profile to GitHub repo and trigger the scraping pipeline (fire-and-forget)
    try:
        await _sync_and_trigger_pipeline(
            profile_id,
            profile_yaml,
            body.cv_markdown,
            searches_yaml,
            preferences_yaml,
        )
    except Exception:
        logger.exception("Pipeline sync/trigger failed for %s (non-fatal)", profile_id)

    analytics.capture(
        user["id"],
        "onboard_completed",
        {
            "profile_id": profile_id,
            "domains_count": len(body.profile.get("domains") or {}),
            "skills_count": len(body.profile.get("skills") or []),
        },
    )
    return {"profile_id": profile_id}


async def _push_file_to_github(gh_path: str, content: str, message: str) -> None:
    """Push a single file to GitHub (no pipeline trigger)."""
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
    url = f"https://api.github.com/repos/{gh_repo}/contents/{gh_path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers, params={"ref": gh_ref})
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        gh_body: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": gh_ref,
        }
        if sha:
            gh_body["sha"] = sha
        put_resp = await client.put(url, json=gh_body, headers=headers)
        if put_resp.status_code in (200, 201):
            logger.info("GitHub file sync OK: %s", gh_path)
        else:
            logger.warning(
                "GitHub file sync FAILED: %s HTTP %d — %s",
                gh_path,
                put_resp.status_code,
                put_resp.text[:200],
            )


async def _sync_and_trigger_pipeline(
    profile_id: str,
    profile_yaml: str,
    cv_markdown: str,
    searches_yaml: str = "",
    preferences_yaml: str = "",
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
            files_to_push.append((f"agent/config/profiles/{profile_id}-searches.yaml", searches_yaml))
        if preferences_yaml:
            files_to_push.append((f"agent/config/profiles/{profile_id}-preferences.yaml", preferences_yaml))
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
                    path,
                    put_resp.status_code,
                    put_resp.text[:300],
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
                resp.status_code,
                profile_id,
                resp.text[:300],
            )


def _yaml_to_flat_profile(raw: dict) -> dict:
    """Normalize nested YAML (jobagent format) → flat dict ProfileEditor expects."""
    user_block = raw.get("user") or {}
    target_block = raw.get("target") or {}
    stored_sw = target_block.get("seniority_weights") or {}
    if not stored_sw:
        stored_sw = _derive_seniority_weights({"target_level": target_block.get("level", "senior")})
    return {
        "name": user_block.get("name", ""),
        "email": user_block.get("email", None),
        "languages": user_block.get("languages", []),
        "home_locations": user_block.get("home_locations", []),
        "current_level": "",
        "track": target_block.get("track", "ic"),
        "target_level": target_block.get("level", ""),
        "role_type": target_block.get("role_type", ""),
        "role_function": target_block.get("role_function", ""),
        "seniority_weights": stored_sw,
        "domains": dict(target_block.get("domains") or {}),
        "skills": list(raw.get("skills") or []),
        # exclude_companies lives at YAML root level (not under user block)
        "exclude_companies": list(raw.get("exclude_companies") or []),
        "salary_min": target_block.get("salary_min", 60000),
        "location_preference": user_block.get("location_preference", "b"),
        "country_weights": dict(target_block.get("country_weights") or {}),
        "company_type_weights": dict(target_block.get("company_type_weights") or {}),
        "search_titles": list(target_block.get("search_titles") or []),
    }


def _apply_flat_to_yaml(raw: Any, flat: dict) -> None:
    """Apply flat profile dict values to a ruamel CommentedMap in-place.

    Writes all UI-managed fields; preserves untouched YAML keys (story banks, etc.).
    """
    from ruamel.yaml.comments import CommentedMap, CommentedSeq  # noqa: PLC0415

    raw.setdefault("user", CommentedMap())
    raw.setdefault("target", CommentedMap())

    raw["user"]["name"] = flat.get("name", "")
    if flat.get("home_locations") is not None:
        raw["user"]["home_locations"] = list(flat["home_locations"])
    if flat.get("location_preference"):
        raw["user"]["location_preference"] = flat["location_preference"]

    if flat.get("salary_min") is not None:
        raw["target"]["salary_min"] = flat["salary_min"]
    if flat.get("target_level"):
        raw["target"]["level"] = flat["target_level"]

    for field in ("role_type", "role_function", "track"):
        val = (flat.get(field) or "").strip()
        if val:
            raw["target"][field] = val
        elif field in raw["target"]:
            del raw["target"][field]

    raw["target"]["domains"] = CommentedMap(flat.get("domains") or {})
    if flat.get("seniority_weights"):
        raw["target"]["seniority_weights"] = CommentedMap(flat["seniority_weights"])
    raw["target"]["country_weights"] = CommentedMap(flat.get("country_weights") or {})
    raw["target"]["company_type_weights"] = CommentedMap(flat.get("company_type_weights") or {})

    raw["skills"] = CommentedSeq(flat.get("skills") or [])

    search_titles = flat.get("search_titles")
    if search_titles is not None:
        raw["target"]["search_titles"] = CommentedSeq(search_titles)

    # exclude_companies at YAML root (not under user block)
    exclude = list(flat.get("exclude_companies") or [])
    if exclude:
        raw["exclude_companies"] = exclude


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

    profile_data = _yaml_to_flat_profile(raw)

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
    seniority_weights: dict[str, int] = {}
    country_weights: dict[str, int] = {}
    company_type_weights: dict[str, int] = {}
    skills: list[str]
    salary_min: int = 60000
    location_preference: str = "b"
    role_type: str = ""
    role_function: str = ""
    track: str = "ic"
    search_titles: list[str] = []


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
    import io  # noqa: PLC0415

    ry = YAML()
    ry.preserve_quotes = True
    with open(yaml_path) as f:
        raw = ry.load(f)

    # Build flat dict from request body and apply to YAML
    flat = {
        "name": body.name,
        "home_locations": body.home_locations,
        "location_preference": body.location_preference,
        "salary_min": body.salary_min,
        "domains": body.domains,
        "seniority_weights": body.seniority_weights,
        "country_weights": dict(body.country_weights),
        "company_type_weights": dict(body.company_type_weights),
        "skills": body.skills,
        "role_type": body.role_type,
        "role_function": body.role_function,
        "track": body.track,
        "exclude_companies": list(raw.get("exclude_companies") or []),
        "search_titles": body.search_titles,
    }
    _apply_flat_to_yaml(raw, flat)

    buf = io.StringIO()
    ry.dump(raw, buf)
    updated_yaml = buf.getvalue()
    with open(yaml_path, "w") as f:
        f.write(updated_yaml)

    # Persist updated YAML to DB so it survives redeploys
    save_user_profile_yaml(db_path_patch, user["id"], updated_yaml)

    # Regenerate per-user searches + preferences from the updated profile.
    # Use request body fields; fall back to YAML for fields not in the request.
    target_block = raw.get("target") or {}
    profile_for_gen = {
        "seniority_weights": body.seniority_weights or target_block.get("seniority_weights") or {},
        "target_level": target_block.get("level", "senior"),
        "track": body.track or target_block.get("track", "ic"),
        "role_type": body.role_type or target_block.get("role_type", ""),
        "role_function": body.role_function or target_block.get("role_function", ""),
        "domains": body.domains,
        "home_locations": body.home_locations,
        "skills": body.skills,
        "country_weights": dict(body.country_weights),
        "salary_min": body.salary_min,
        # exclude_companies lives at YAML root level (not under user block) — fix C5
        "exclude_companies": list(raw.get("exclude_companies") or []),
    }
    try:
        searches_yaml = _generate_searches_yaml(profile_for_gen)
        searches_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}-searches.yaml")
        with open(searches_path, "w") as f:
            f.write(searches_yaml)
        logger.info("Regenerated searches for profile %s after profile edit", profile_id)
        # Push updated searches to GitHub (fire-and-forget)
        await _push_file_to_github(
            f"agent/config/profiles/{profile_id}-searches.yaml",
            searches_yaml,
            f"chore: update searches for {profile_id} [skip ci]",
        )
    except Exception:
        logger.exception("Searches regeneration failed for %s (non-fatal)", profile_id)

    try:
        preferences_yaml = _generate_preferences_yaml(profile_for_gen)
        prefs_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}-preferences.yaml")
        with open(prefs_path, "w") as f:
            f.write(preferences_yaml)
        logger.info("Regenerated preferences for profile %s after profile edit", profile_id)
        await _push_file_to_github(
            f"agent/config/profiles/{profile_id}-preferences.yaml",
            preferences_yaml,
            f"chore: update preferences for {profile_id} [skip ci]",
        )
    except Exception:
        logger.exception("Preferences regeneration failed for %s (non-fatal)", profile_id)

    analytics.capture(
        user["id"],
        "profile_saved",
        {
            "domains_count": len(body.domains),
            "skills_count": len(body.skills),
            "fields_changed": list(UpdateProfileRequest.model_fields.keys()),
        },
    )
    return {"ok": True}


class AddSkillRequest(BaseModel):
    skill: str


@router.post("/profile/skills")
async def add_skill(body: AddSkillRequest, user: dict = Depends(get_current_user)):
    """Add a single skill to the user's profile. Deduplicates, persists to YAML + DB."""
    profile_id = user.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found")

    skill = body.skill.strip().lower()
    if not skill:
        raise HTTPException(status_code=400, detail="Skill cannot be empty")

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "agent"))
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")

    # Restore YAML from DB if filesystem was wiped
    if not os.path.exists(yaml_path):
        stored_yaml = get_user_profile_yaml(db_path, user["id"])
        if not stored_yaml:
            raise HTTPException(status_code=404, detail="Profile file not found")
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        with open(yaml_path, "w") as f:
            f.write(stored_yaml)

    from ruamel.yaml import YAML  # noqa: PLC0415
    from ruamel.yaml.comments import CommentedSeq  # noqa: PLC0415
    import io  # noqa: PLC0415

    ry = YAML()
    ry.preserve_quotes = True
    with open(yaml_path) as f:
        raw = ry.load(f)

    skills = list(raw.get("skills") or [])
    # Deduplicate (case-insensitive)
    existing_lower = {s.lower() for s in skills}
    if skill not in existing_lower:
        skills.append(skill)
        raw["skills"] = CommentedSeq(skills)

        buf = io.StringIO()
        ry.dump(raw, buf)
        updated_yaml = buf.getvalue()
        with open(yaml_path, "w") as f:
            f.write(updated_yaml)

        # Persist to DB
        save_user_profile_yaml(db_path, user["id"], updated_yaml)

    # Pre-compute embedding for the new skill (non-blocking)
    try:
        from api.embeddings import get_embedding, clear_memory_cache

        get_embedding(skill, db_path)
        clear_memory_cache()  # invalidate so subsequent requests pick up the new skill
    except Exception:
        pass  # best-effort, don't block response

    analytics.capture(user["id"], "skill_added", {"skill_name": skill, "source": "job_detail"})
    return {"skills": skills}


class ReplaceCVRequest(BaseModel):
    cv_markdown: str
    extracted_profile: dict


@router.patch("/replace-cv")
async def replace_cv(body: ReplaceCVRequest, user: dict = Depends(get_current_user)):
    """Server-side additive merge of a new CV extraction into the existing profile.

    Returns merged_profile and a diff summary showing what changed.
    The profile is saved to DB before returning — no separate save step needed.
    """
    from ruamel.yaml import YAML  # noqa: PLC0415
    import io  # noqa: PLC0415
    from api.profile_merge import merge_profiles, compute_diff  # noqa: PLC0415

    profile_id = user.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found")

    jobagent_dir = os.path.abspath(os.environ.get("JOBAGENT_DIR", "agent"))
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")

    # Restore YAML from DB if the filesystem was wiped
    if not os.path.exists(yaml_path):
        stored_yaml = get_user_profile_yaml(db_path, user["id"])
        if not stored_yaml:
            raise HTTPException(status_code=404, detail="Profile file not found")
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        with open(yaml_path, "w") as f:
            f.write(stored_yaml)

    ry = YAML()
    ry.preserve_quotes = True
    with open(yaml_path) as f:
        raw = ry.load(f)

    # Normalize existing YAML to flat dict, merge with new extraction, write back
    existing_flat = _yaml_to_flat_profile(raw)
    merged = merge_profiles(existing_flat, body.extracted_profile)
    diff = compute_diff(existing_flat, merged)

    # Preserve salary_min and location_preference from existing (not in merge strategy)
    merged["salary_min"] = existing_flat.get("salary_min", 60000)
    merged["location_preference"] = existing_flat.get("location_preference", "b")

    _apply_flat_to_yaml(raw, merged)

    buf = io.StringIO()
    ry.dump(raw, buf)
    updated_yaml = buf.getvalue()
    with open(yaml_path, "w") as f:
        f.write(updated_yaml)

    # Persist to DB
    if body.cv_markdown:
        save_user_cv_md(db_path, user["id"], body.cv_markdown)
        knowledge_dir = os.path.join(jobagent_dir, "knowledge", profile_id)
        os.makedirs(knowledge_dir, exist_ok=True)
        with open(os.path.join(knowledge_dir, "cv.md"), "w") as f:
            f.write(body.cv_markdown)
    save_user_profile_yaml(db_path, user["id"], updated_yaml)

    # Push to GitHub (fire-and-forget)
    try:
        await _push_file_to_github(
            f"agent/config/profiles/{profile_id}.yaml",
            updated_yaml,
            f"chore: replace-cv merge for {profile_id} [skip ci]",
        )
        if body.cv_markdown:
            await _push_file_to_github(
                f"agent/knowledge/{profile_id}/cv.md",
                body.cv_markdown,
                f"chore: replace-cv markdown for {profile_id} [skip ci]",
            )
    except Exception:
        logger.exception("GitHub sync failed after replace-cv for %s (non-fatal)", profile_id)

    analytics.capture(
        user["id"],
        "profile_cv_replaced",
        {
            "skills_added_count": len(diff["skills_added"]),
            "domains_added_count": len(diff["domains_added"]),
            "fields_updated": diff["fields_updated"],
        },
    )

    return {"merged_profile": merged, "diff": diff}


@router.post("/upload-cv", dependencies=[Depends(get_current_user)])
async def upload_cv(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx") and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported")

    contents = await file.read()
    if len(contents) > MAX_CV_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    try:
        markdown = extract_text_from_file(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"markdown": markdown}
