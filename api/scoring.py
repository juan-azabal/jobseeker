"""Per-user heuristic job scoring.

Ported from agent/main.py _heuristic_score(). Runs at query time for jobs
without RAG scores — no LLM calls, instant, free.
"""

import json
import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Maps profile domain names → parser-emitted domain names.
# Parser enum: adtech|data|ml|fintech|saas|ecommerce|healthcare|other
_DOMAIN_ALIASES: dict[str, str] = {
    "ia": "ml",
    "ai": "ml",
    "llm": "ml",
    "martech": "adtech",
}

# Seniority levels ordered from most junior to most senior
_SENIORITY_LEVELS = ["junior", "mid", "senior", "staff", "principal", "director", "vp"]
_LEVEL_IDX = {lvl: i for i, lvl in enumerate(_SENIORITY_LEVELS)}


def _compute_seniority_weights(level: str, track: str) -> dict[str, int]:
    """Compute seniority match weights from target.level + target.track.

    As per CLAUDE.md convention: seniority weights are computed at load time,
    never stored in YAML.

    Scoring:
      - Exact match: 15
      - 1 level off: 10
      - 2 levels off: 6
      - 3+ levels off: 0
      - director/vp capped at 4 for IC track (different career path)
    """
    level = (level or "senior").lower()
    track = (track or "ic").lower()
    target_idx = _LEVEL_IDX.get(level, 2)  # default to "senior" if unknown

    weights: dict[str, int] = {}
    for seniority, idx in _LEVEL_IDX.items():
        delta = abs(idx - target_idx)
        if delta == 0:
            weights[seniority] = 15
        elif delta == 1:
            weights[seniority] = 10
        elif delta == 2:
            weights[seniority] = 6
        else:
            weights[seniority] = 0

    # Management roles score poorly for IC track
    if track == "ic":
        weights["director"] = min(weights.get("director", 0), 4)
        weights["vp"] = min(weights.get("vp", 0), 4)

    return weights


# Domain override keywords (mirrors agent/main.py _DOMAIN_KEYWORDS)
_DOMAIN_KEYWORDS = {
    "data": [
        "data platform", "data pipeline", "data warehouse", "data lake",
        "lakehouse", "databricks", "snowflake", "clickhouse", "etl",
        "data product", "data governance", "data quality", "data model",
    ],
    "ml": [
        "machine learning", "ml model", "ai agent", "llm", "nlp",
        "inference", "training", "deep learning", "neural",
    ],
    "adtech": [
        "advertising", "ad tech", "programmatic", "dsp", "ssp",
        "header bidding", "rtb", "publisher monetization",
    ],
    "saas": [
        "saas", "subscription", "b2b platform", "developer tool",
        "devops", "observability", "monitoring", "cloud platform",
    ],
}


def compute_tier(score: int) -> str:
    if score >= 50:
        return "A"
    if score >= 30:
        return "B"
    return "C"


def _load_profile_yaml_from_db(profile_id: str, profile_path: Path) -> dict | None:
    """Fetch profile YAML from the DB when the local file is missing.

    Writes the YAML back to disk so subsequent calls within the same process
    hit the filesystem (avoids repeated DB lookups per request).

    Returns the parsed YAML dict on success, None on any failure.
    """
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    try:
        from api.db.queries import get_profile_yaml_by_profile_id  # avoid circular import at module level
        stored_yaml = get_profile_yaml_by_profile_id(db_path, profile_id)
        if not stored_yaml:
            return None
        # Cache back to disk so the next call is a fast file read.
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(stored_yaml)
        logger.info(
            "Restored profile YAML from DB for profile_id=%r → %s",
            profile_id, profile_path,
        )
        return yaml.safe_load(stored_yaml)
    except Exception as exc:
        logger.error(
            "Failed to restore profile YAML from DB for profile_id=%r: %s",
            profile_id, exc,
        )
        return None


def load_profile_data(profile_id: str | None) -> dict | None:
    """Load profile YAML and return scoring-relevant fields.

    Returns dict with keys: domains, seniority, skills, home_locations, home_regions.
    Returns None if profile_id is missing or file not found.
    """
    if not profile_id:
        return None

    jobagent_dir = os.environ.get("JOBAGENT_DIR", "agent")
    profile_path = Path(jobagent_dir) / "config" / "profiles" / f"{profile_id}.yaml"

    try:
        raw = yaml.safe_load(profile_path.read_text())
    except FileNotFoundError:
        # Ephemeral filesystem (e.g. Railway redeploy): try to restore from DB.
        raw = _load_profile_yaml_from_db(profile_id, profile_path)
        if raw is None:
            logger.warning(
                "Profile YAML not found for profile_id=%r at %s and not in DB — "
                "heuristic scoring disabled for this user",
                profile_id, profile_path,
            )
            return None
    except Exception as exc:
        logger.error(
            "Failed to load profile YAML for profile_id=%r at %s: %s",
            profile_id, profile_path, exc,
        )
        return None

    user_block = raw.get("user", {})
    target_block = raw.get("target", {})
    home_locations = [loc.lower() for loc in user_block.get("home_locations", [])]

    # Auto-derive home regions via country-converter
    import sys
    agent_dir = str(Path(jobagent_dir).resolve())
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    try:
        from geo import derive_home_regions
        home_regions = derive_home_regions(home_locations)
    except Exception as exc:
        logger.warning("derive_home_regions failed for profile_id=%r: %s", profile_id, exc)
        home_regions = []

    # Normalize domain names to match parser enum values, merging aliases.
    # e.g. ia→ml, llm→ml, martech→adtech  (takes max weight on collision)
    raw_domains = {k.lower(): v for k, v in (target_block.get("domains") or {}).items()}
    normalized_domains: dict[str, int] = {}
    for domain, weight in raw_domains.items():
        canonical = _DOMAIN_ALIASES.get(domain, domain)
        normalized_domains[canonical] = max(normalized_domains.get(canonical, 0), weight)

    # Prefer explicitly stored seniority_weights; fall back to computing from level+track
    # for backward compat with profiles that pre-date the seniority_weights feature.
    stored_sw = target_block.get("seniority_weights")
    if stored_sw:
        seniority_weights = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        level = target_block.get("level", "")
        track = target_block.get("track", "ic")
        seniority_weights = _compute_seniority_weights(level, track)

    return {
        "domains": normalized_domains,
        "seniority": seniority_weights,
        "skills": [s.lower() for s in (raw.get("skills") or [])],
        "home_locations": home_locations,
        "home_regions": home_regions,
    }


def _infer_domain(parsed: dict) -> str:
    """Override 'other' domain using keyword detection."""
    domain = parsed.get("domain", "other")
    if domain != "other":
        return domain

    all_text = " ".join([
        parsed.get("responsibilities_summary", ""),
        " ".join(parsed.get("must_have_skills") or []),
        " ".join(parsed.get("technical_stack") or []),
    ]).lower()

    best_domain = "other"
    best_count = 0
    for d, keywords in _DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in all_text)
        if count > best_count:
            best_count = count
            best_domain = d

    return best_domain if best_count >= 1 else "other"


def heuristic_score(profile: dict, parsed: dict, job: dict, is_reloc: bool) -> int:
    """Compute heuristic fit score 0-100 from parsed job data + user profile.

    Args:
        profile: dict from load_profile_data()
        parsed: job's parsed JSON blob (dict)
        job: raw job row (for location field)
        is_reloc: whether the job requires relocation for this user
    """
    if not parsed:
        return 0

    score = 0

    # Domain (0-15) with override
    domain = _infer_domain(parsed)
    score += profile["domains"].get(domain, 0)

    # Seniority (0-15)
    score += profile["seniority"].get(parsed.get("seniority", "unknown"), 0)

    # Location (0-10)
    loc_type = parsed.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    home_locations = profile["home_locations"]

    if loc_type == "remote" and not is_reloc:
        score += 10
    elif loc_type == "hybrid" and any(c in job_loc for c in home_locations):
        score += 8
    elif loc_type == "onsite" and any(c in job_loc for c in home_locations):
        score += 6

    # Skill overlap (0-30)
    all_text = " ".join(
        [s.lower() for s in parsed.get("must_have_skills", [])]
        + [s.lower() for s in parsed.get("nice_to_have_skills", [])]
        + [s.lower() for s in parsed.get("technical_stack", [])]
        + [parsed.get("responsibilities_summary", "").lower()]
    )
    matches = sum(1 for skill in profile["skills"] if skill in all_text)
    score += min(30, matches * 4)

    # Red flags (-5 each, max -15)
    score -= min(15, len(parsed.get("red_flags") or []) * 5)

    return max(0, min(100, score))
