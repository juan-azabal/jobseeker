"""Heuristic scoring globals and functions for agent pipeline.

Module globals are populated by load_heuristic_config() once per run.
All functions read from these globals — no I/O, no API calls.

Exports:
  load_heuristic_config(profile)  — populate globals from profile dict
  heuristic_score(job)            — quick fit score 0-100
  heuristic_gate(jobs, profile)   — split jobs into (to_score, skipped)
"""

import re

from shared.scoring_core import (
    infer_domain as _infer_domain,
    heuristic_score as _shared_heuristic_score,
)
from user_config import compute_seniority_weights

# ---------------------------------------------------------------------------
# Module globals — populated by load_heuristic_config()
# ---------------------------------------------------------------------------

_PROFILE_SKILLS = None
_DOMAIN_SCORES = None
_SENIORITY_SCORES = None
_SALARY_THRESHOLD = 130000
_HOME_LOCATIONS: list = []
_HOME_REGIONS: list = []
_HOME_REGION_RE = None
_COUNTRY_WEIGHTS: dict = {}
_LOCATION_PREFERENCE: str = "b"


def load_heuristic_config(profile: dict) -> None:
    """Populate module-level heuristic constants from user profile."""
    from geo import derive_home_regions, build_region_pattern  # noqa: PLC0415

    global _PROFILE_SKILLS, _DOMAIN_SCORES, _SENIORITY_SCORES
    global _SALARY_THRESHOLD, _HOME_LOCATIONS, _HOME_REGIONS, _HOME_REGION_RE
    global _COUNTRY_WEIGHTS, _LOCATION_PREFERENCE

    _PROFILE_SKILLS = [s.lower() for s in (profile.get("skills") or [])]
    _DOMAIN_SCORES = {k.lower(): v for k, v in (profile.get("target", {}).get("domains") or {}).items()}
    target = profile.get("target", {})
    stored_sw = target.get("seniority_weights") or target.get("seniority")
    if stored_sw:
        _SENIORITY_SCORES = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        _SENIORITY_SCORES = compute_seniority_weights(target.get("level", ""), target.get("track", "ic"))
    _SALARY_THRESHOLD = profile.get("target", {}).get("salary_display_threshold", 130000)
    _HOME_LOCATIONS = [loc.lower() for loc in (profile.get("user", {}).get("home_locations") or [])]
    _HOME_REGIONS = derive_home_regions(_HOME_LOCATIONS)
    _HOME_REGION_RE = build_region_pattern(_HOME_REGIONS)
    _COUNTRY_WEIGHTS = {k.lower(): int(v) for k, v in (target.get("country_weights") or {}).items()}
    _LOCATION_PREFERENCE = (profile.get("user", {}).get("location_preference") or "b").lower()


def heuristic_score(job: dict) -> int:
    """Quick fit score 0-100 from parsed data. No API calls.

    Delegates to shared/scoring_core.heuristic_score() with:
      - Agent-specific skill scoring: simple keyword overlap (matches * 4, cap 30)
      - Profile dict built from module-level globals set by load_heuristic_config()
    """
    p = job.get("parsed")
    if not p:
        return 0

    # Agent-specific skill scoring — simple overlap, not semantic (matches * 4, cap 30)
    all_text = " ".join(
        [s.lower() for s in (p.get("truly_required") or p.get("must_have_skills") or [])]
        + [s.lower() for s in (p.get("preferred_skills") or p.get("nice_to_have_skills") or [])]
        + [s.lower() for s in p.get("technical_stack", [])]
        + [p.get("responsibilities_summary", "").lower()]
    )
    matches = sum(1 for skill in (_PROFILE_SKILLS or []) if skill in all_text)
    skill_score = min(30, matches * 4)

    # Update parsed domain for display (infer_domain may refine "other")
    p["domain"] = _infer_domain(p)

    profile = {
        "domains": _DOMAIN_SCORES or {},
        "seniority": _SENIORITY_SCORES or {},
        "home_locations": _HOME_LOCATIONS,
        "home_regions": _HOME_REGIONS,
        "location_preference": _LOCATION_PREFERENCE,
        "country_weights": _COUNTRY_WEIGHTS,
    }
    return _shared_heuristic_score(profile, p, job, skill_score=skill_score)


def heuristic_gate(jobs: list, profile: dict) -> tuple[list, list]:
    """Split parsed jobs into (to_score, skipped) using a cheap heuristic.

    Jobs that clearly don't fit (wrong domain, wrong seniority, no skill
    overlap, too low salary) skip LLM scoring and remain as heuristic-only
    results in the digest (ADR-006).

    Returns (jobs_to_score, jobs_skipped).
    """
    scoring_cfg = profile.get("scoring", {})
    threshold = scoring_cfg.get("rag_threshold", 0)
    salary_min = scoring_cfg.get("salary_min", 0)

    if threshold == 0:
        return jobs, []

    target = profile.get("target", {})
    target_domains = target.get("domains") or {}
    target_level = (target.get("level") or "").lower()
    profile_skills = {s.lower().replace("-", " ") for s in (profile.get("skills") or [])}

    PRINCIPAL_WORDS = {"principal", "staff", "director", "vp", "head", "chief"}
    SENIOR_WORDS = {"senior", "lead", "sr"}

    to_score, skipped = [], []

    for job in jobs:
        parsed = job.get("parsed") or {}
        score = 0

        # ── Domain (0–20) ─────────────────────────────────────────────────
        domain = (parsed.get("domain") or "").lower()
        if not domain or domain == "other":
            score += 10  # uncertain → partial credit
        else:
            domain_weight = target_domains.get(domain, 0)
            if domain_weight > 0:
                score += 20  # desired domain → full credit
            elif domain_weight < 0:
                score += 0  # explicitly deprioritized → no credit in gate

        # ── Seniority (0–20) ──────────────────────────────────────────────
        seniority = (parsed.get("seniority") or "").lower()
        if not seniority:
            score += 10  # unspecified → partial credit
        elif target_level in ("principal", "staff"):
            if any(w in seniority for w in PRINCIPAL_WORDS):
                score += 20
            elif any(w in seniority for w in SENIOR_WORDS):
                score += 10
        elif target_level in ("senior", "lead"):
            if any(w in seniority for w in SENIOR_WORDS | PRINCIPAL_WORDS):
                score += 20
        else:
            score += 10  # no target level → partial credit

        # ── Skill overlap (0–20, 5 pts/match, cap 4) ──────────────────────
        job_skills = [
            s.lower().replace("-", " ")
            for s in (parsed.get("truly_required") or parsed.get("must_have_skills") or [])
            + (parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])
        ]
        matches = sum(1 for js in job_skills if any(ps in js or js in ps for ps in profile_skills))
        score += min(20, matches * 5)

        # ── Salary gate (hard block, applied after score) ─────────────────
        if salary_min > 0:
            salary_text = (parsed.get("salary_mentioned") or "").lower()
            nums = re.findall(r"[\d,]+", salary_text)
            if nums:
                try:
                    val = int(nums[0].replace(",", ""))
                    # Treat values under 1000 as "k" (e.g. "80k")
                    if val < 1000:
                        val *= 1000
                    if val < salary_min:
                        skipped.append(job)
                        continue
                except ValueError:
                    pass

        (to_score if score >= threshold else skipped).append(job)

    return to_score, skipped
