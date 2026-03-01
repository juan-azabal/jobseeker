"""Per-user heuristic job scoring (query-time, no LLM).

Core logic in shared/scoring_core.py. API adds: semantic domain fallback, semantic skill matching.
"""

import os
from pathlib import Path

import yaml

import structlog
from api.skill_matcher import SkillMatch, match_skills
from shared.scoring_core import (
    DOMAIN_KEYWORDS,
    DOMAIN_ALIASES,
    VALID_DOMAINS as VALID_DOMAINS,  # re-exported: api.routes.jobs imports from here
    grade_to_points,
    infer_domain,
    compute_eligibility_penalty,
    heuristic_score as _shared_heuristic_score,
)

logger = structlog.get_logger(__name__)

# Backward-compat private aliases — tests and routes import these from api.scoring.
_DOMAIN_KEYWORDS = DOMAIN_KEYWORDS
_DOMAIN_ALIASES = DOMAIN_ALIASES
_infer_domain = infer_domain

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


def compute_tier(score: int) -> str:
    """A (green) = 61+, B (yellow) = 41–60, C (skip) = 0–40."""
    if score > 60:
        return "A"
    if score > 40:
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
        from api.db.queries import get_profile_yaml_by_profile_id  # avoid circular import

        stored_yaml = get_profile_yaml_by_profile_id(db_path, profile_id)
        if not stored_yaml:
            return None
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(stored_yaml)
        logger.info(
            "Restored profile YAML from DB for profile_id=%r → %s",
            profile_id,
            profile_path,
        )
        return yaml.safe_load(stored_yaml)
    except Exception as exc:
        logger.error(
            "Failed to restore profile YAML from DB for profile_id=%r: %s",
            profile_id,
            exc,
        )
        return None


def load_profile_data(profile_id: str | None) -> dict | None:
    """Load profile YAML and return scoring-relevant fields.

    Returns dict with keys: domains, seniority, skills, home_locations,
    home_regions, languages, location_preference, country_weights,
    company_type_weights.
    Returns None if profile_id is missing or file not found.
    """
    if not profile_id:
        return None

    jobagent_dir = os.environ.get("JOBAGENT_DIR", "agent")
    profile_path = Path(jobagent_dir) / "config" / "profiles" / f"{profile_id}.yaml"

    try:
        raw = yaml.safe_load(profile_path.read_text())
    except FileNotFoundError:
        raw = _load_profile_yaml_from_db(profile_id, profile_path)
        if raw is None:
            logger.warning(
                "Profile YAML not found for profile_id=%r at %s and not in DB — "
                "heuristic scoring disabled for this user",
                profile_id,
                profile_path,
            )
            return None
    except Exception as exc:
        logger.error(
            "Failed to load profile YAML for profile_id=%r at %s: %s",
            profile_id,
            profile_path,
            exc,
        )
        return None

    user_block = raw.get("user", {})
    target_block = raw.get("target", {})
    home_locations = [loc.lower() for loc in user_block.get("home_locations", [])]

    try:
        from api.geo import derive_home_regions

        home_regions = derive_home_regions(home_locations)
    except Exception as exc:
        logger.warning("derive_home_regions failed for profile_id=%r: %s", profile_id, exc)
        home_regions = []

    # Normalize domain names to canonical enum values, merging aliases.
    raw_domains = {k.lower(): v for k, v in (target_block.get("domains") or {}).items()}
    normalized_domains: dict[str, int] = {}
    for domain, weight in raw_domains.items():
        canonical = DOMAIN_ALIASES.get(domain, domain)
        normalized_domains[canonical] = max(normalized_domains.get(canonical, 0), weight)

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
        "languages": [lang.lower() for lang in user_block.get("languages", [])],
        "location_preference": (user_block.get("location_preference") or "b").lower(),
        "country_weights": {k.lower(): int(v) for k, v in (target_block.get("country_weights") or {}).items()},
        "company_type_weights": {
            k.lower(): int(v) for k, v in (target_block.get("company_type_weights") or {}).items()
        },
        "role_function": target_block.get("role_function") or None,
        "role_type": target_block.get("role_type") or None,
    }


_SEMANTIC_DOMAIN_THRESHOLD = 0.75
_SEMANTIC_DOMAIN_MAX = 15


def _semantic_domain_score(profile: dict, parsed: dict, job: dict, db_path: str | None) -> int:
    """Semantic domain scoring when enum and keyword detection both fail.

    Fires only when infer_domain() returns 'other' (cascade: enum → keywords → semantic).
    Uses embedding similarity between the job text and user domain labels.

    Returns a score in [-15, 15]. Returns 0 if no domain matches >= 0.75 threshold,
    no db_path, or no domains in profile.
    """
    if not db_path:
        return 0

    domains = profile.get("domains", {})
    if not domains:
        return 0

    job_text = " ".join(
        filter(
            None,
            [
                job.get("company", ""),
                parsed.get("domain", ""),
                job.get("title", ""),
            ],
        )
    ).strip()
    if not job_text:
        return 0

    domain_names = list(domains.keys())

    from api.embeddings import get_embeddings_batch, cosine_similarity

    all_texts = [job_text] + domain_names
    embeddings = get_embeddings_batch(all_texts, db_path)

    job_emb = embeddings.get(job_text.strip().lower())
    if job_emb is None:
        return 0

    best_sim = 0.0
    best_domain = None
    for domain_name in domain_names:
        domain_emb = embeddings.get(domain_name.strip().lower())
        if domain_emb is None:
            continue
        sim = cosine_similarity(job_emb, domain_emb)
        if sim > best_sim:
            best_sim = sim
            best_domain = domain_name

    if best_sim < _SEMANTIC_DOMAIN_THRESHOLD or best_domain is None:
        return 0

    weight = domains[best_domain]
    score = int(weight * best_sim)
    return max(-_SEMANTIC_DOMAIN_MAX, min(_SEMANTIC_DOMAIN_MAX, score))


def precompute_skill_lookup(
    profile_skills: list[str],
    all_job_skills: list[str],
    db_path: str,
) -> dict[str, SkillMatch]:
    """Match user skills against all unique job skills in one call.

    Returns dict keyed by normalized job skill for O(1) per-job lookup.
    """
    results = match_skills(profile_skills, all_job_skills, db_path)
    return {m.job_skill.strip().lower().replace("-", " "): m for m in results}


def _score_skills(
    profile: dict,
    parsed: dict,
    db_path: str | None,
    skill_lookup: dict[str, SkillMatch] | None = None,
) -> int:
    """Score skills dimension (0-30).

    Must-have: 5 pts matched, 2 pts partial, cap 20.
    Nice-to-have + technical_stack: 3 pts matched, cap 10.
    """
    profile_skills = profile.get("skills", [])
    must_have_list = parsed.get("truly_required") or parsed.get("must_have_skills") or []
    nice_list = list(
        set(
            (parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])
            + (parsed.get("technical_stack") or [])
        )
    )

    if skill_lookup is not None:
        must_pts = sum(
            5
            if (m := skill_lookup.get(s.strip().lower().replace("-", " "))) and m.status == "matched"
            else 2
            if m and m.status == "partial"
            else 0
            for s in must_have_list
        )
        nice_pts = sum(
            3 if (m := skill_lookup.get(s.strip().lower().replace("-", " "))) and m.status == "matched" else 0
            for s in nice_list
        )
    elif db_path and profile_skills:
        must_results = match_skills(profile_skills, must_have_list, db_path)
        must_pts = sum(5 if m.status == "matched" else 2 if m.status == "partial" else 0 for m in must_results)

        nice_results = match_skills(profile_skills, nice_list, db_path)
        nice_pts = sum(3 if m.status == "matched" else 0 for m in nice_results)
    else:
        norm_must = [s.lower().replace("-", " ") for s in must_have_list]
        nice_text = " ".join(
            [s.lower() for s in (parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])]
            + [s.lower() for s in (parsed.get("technical_stack") or [])]
            + [parsed.get("responsibilities_summary", "").lower()]
        ).replace("-", " ")
        norm_profile = [s.replace("-", " ") for s in profile_skills]

        must_pts = sum(5 for skill in norm_profile if skill in norm_must)
        nice_pts = sum(3 for skill in norm_profile if skill in nice_text and skill not in norm_must)

    return min(20, must_pts) + min(10, nice_pts)


def _compute_eligibility_penalty(profile: dict, parsed: dict, job: dict) -> int:
    """Thin wrapper for backward compatibility with callers using profile dict."""
    return compute_eligibility_penalty(
        home_locations=profile.get("home_locations", []),
        home_regions=profile.get("home_regions", []),
        location_preference=(profile.get("location_preference") or "b"),
        parsed=parsed,
        job=job,
    )


def heuristic_score(
    profile: dict,
    parsed: dict,
    job: dict,
    is_reloc: bool = False,
    db_path: str | None = None,
    skill_lookup: dict[str, SkillMatch] | None = None,
    domain_override: str | None = None,
) -> int:
    """Compute heuristic fit score 0-100. Delegates core logic to shared/scoring_core.

    API-specific additions:
      - Semantic skill matching (via api.embeddings + api.skill_matcher)
      - Semantic domain fallback when keyword detection returns 'other'
    """
    if not parsed:
        return 0
    skill_score = _score_skills(profile, parsed, db_path, skill_lookup=skill_lookup)

    base = _shared_heuristic_score(
        profile=profile,
        parsed=parsed,
        job=job,
        is_reloc=is_reloc,
        domain_override=domain_override,
        skill_score=skill_score,
    )

    # Semantic domain fallback (api-only): only when keyword cascade returns 'other'
    if domain_override is None and infer_domain(parsed) == "other":
        semantic = _semantic_domain_score(profile, parsed, job, db_path)
        return max(0, min(100, base + semantic))

    return base


def hybrid_score(
    profile: dict,
    parsed: dict,
    job: dict,
    is_reloc: bool,
    technical_grade: str | None = None,
    profile_grade: str | None = None,
    db_path: str | None = None,
    skill_lookup: dict[str, SkillMatch] | None = None,
    domain_override: str | None = None,
) -> int:
    """Combine deterministic heuristic score with LLM categorical grades.

    Score = heuristic_score(...) + grade_to_points(technical_grade)
                                 + grade_to_points(profile_grade)

    Grade points: A→20, B→12, C→5, None→10 (neutral midpoint).
    Result is clamped to [0, 100].
    """
    det = heuristic_score(
        profile,
        parsed,
        job,
        is_reloc,
        db_path=db_path,
        skill_lookup=skill_lookup,
        domain_override=domain_override,
    )
    grades = grade_to_points(technical_grade) + grade_to_points(profile_grade)

    # role_function gate: -15 when both profile and job declare role_function and they differ
    profile_rf = (profile.get("role_function") or "").strip().lower()
    job_rf = (parsed.get("role_function") or "").strip().lower()
    role_penalty = 15 if (profile_rf and job_rf and profile_rf != job_rf) else 0

    return max(0, min(100, det + grades - role_penalty))
