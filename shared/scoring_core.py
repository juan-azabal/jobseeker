"""Shared scoring core — single source of truth for scoring logic.

Used by both api/ and agent/. Stateless functions with explicit params.
Agent adapter (agent/scoring.py) wraps these with profile globals.

No imports from api/ or agent/. Only stdlib + pytz + structlog.
"""

from datetime import datetime

import pytz
import structlog

from shared.scoring_data import (
    DOMAIN_ALIASES,  # noqa: F401 — re-exported for api/scoring.py
    DOMAIN_KEYWORDS,
    GRADE_POINTS,
    VALID_DOMAINS,  # noqa: F401 — re-exported for api/scoring.py
    _CITY_TO_COUNTRY,
    _LANG_SIGNALS,
    _NULL_FLAG,
    _REGION_ALIASES,
)

logger = structlog.get_logger(__name__)


def infer_domain(parsed: dict) -> str:
    """Override 'other' domain using keyword detection.

    Scans responsibilities_summary, truly_required, technical_stack for
    DOMAIN_KEYWORDS matches. Returns the best-matching domain or 'other'.
    """
    domain = parsed.get("domain", "other")
    if domain != "other":
        return domain

    all_text = " ".join(
        [
            parsed.get("responsibilities_summary", ""),
            " ".join(parsed.get("truly_required") or parsed.get("must_have_skills") or []),
            " ".join(parsed.get("technical_stack") or []),
        ]
    ).lower()

    best_domain = "other"
    best_count = 0
    for d, keywords in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in all_text)
        if count > best_count:
            best_count = count
            best_domain = d

    return best_domain if best_count >= 1 else "other"


def grade_to_points(grade: str | None, default: int = 10) -> int:
    """Convert a categorical grade (A/B/C) to integer points.

    Args:
        grade: Grade string ("A", "B", or "C"). Case-insensitive.
        default: Points to return when grade is None or unrecognised.
    """
    if grade is None:
        return default
    return GRADE_POINTS.get(grade.upper(), default)


# ---------------------------------------------------------------------------
# Timezone detection (Step 1.2)
# Copied from api/geo.py — geo.py keeps its copy for non-scoring callers.
# SYNC RULE: if TZ_TERMS logic changes, update api/geo.py too.
# ---------------------------------------------------------------------------


def _build_tz_abbreviations() -> frozenset[str]:
    abbrevs: set[str] = set()
    for tz_name in pytz.all_timezones:
        try:
            tz = pytz.timezone(tz_name)
            abbrevs.add(tz.localize(datetime(2024, 1, 15)).strftime("%Z").lower())
            abbrevs.add(tz.localize(datetime(2024, 7, 15)).strftime("%Z").lower())
        except Exception:
            pass
    abbrevs = {a for a in abbrevs if not a.startswith(("+", "-")) and len(a) >= 2}
    abbrevs.update(["timezone", "time zone", "hours", "time-zone", "tz"])
    return frozenset(abbrevs)


_TZ_TERMS: frozenset[str] = _build_tz_abbreviations()


def is_pure_timezone(restriction: str) -> bool:
    """Return True if every comma-separated token is a timezone term.

    Used to distinguish 'CET timezone hours' (not reloc) from 'Germany' (reloc).
    Copied from api/geo.py — keep both in sync if TZ_TERMS logic changes.
    """
    if not restriction:
        return False
    for tok in restriction.split(","):
        tok = tok.strip().lower()
        if not tok:
            continue
        if not any(tz in tok for tz in _TZ_TERMS):
            return False
    return True


# ---------------------------------------------------------------------------
# Eligibility penalty
# ---------------------------------------------------------------------------


def compute_eligibility_penalty(
    home_locations: list[str],
    home_regions: list[str],
    location_preference: str,
    parsed: dict,
    job: dict,
) -> int:
    """Return -20 when a job excludes the user from working there legally.

    For REMOTE jobs: fires when remote_restriction is non-empty and user's home
    country/region is NOT in the restriction text.

    For ONSITE/HYBRID jobs: fires when job country is identifiable AND is NOT
    in the user's home countries. Conservative: unidentifiable → 0.

    Returns -20 when ineligible, 0 otherwise.
    """
    loc_type = parsed.get("location_type", "")

    # --- REMOTE path ---
    restriction = (parsed.get("remote_restriction") or "").strip()
    if loc_type == "remote":
        if not restriction or restriction.lower() in ("null", "none"):
            return 0
        if is_pure_timezone(restriction):
            return 0
        if location_preference == "d":
            return 0

        restriction_lower = restriction.lower()

        home_countries: set[str] = set()
        for loc in home_locations:
            home_countries.add(_CITY_TO_COUNTRY.get(loc, loc))
            home_countries.add(loc)

        if any(country in restriction_lower for country in home_countries if country):
            return 0

        for region in home_regions:
            aliases = _REGION_ALIASES.get(region.lower(), [region.lower()])
            if any(alias in restriction_lower for alias in aliases):
                return 0
        if "europe" in restriction_lower and home_regions:
            return 0

        return -20

    # --- ONSITE / HYBRID path ---
    locations_mentioned = [loc.lower() for loc in (parsed.get("locations_mentioned") or [])]
    job_countries: set[str] = set()
    for loc in locations_mentioned:
        resolved = _CITY_TO_COUNTRY.get(loc)
        if resolved:
            job_countries.add(resolved)

    if not job_countries:
        raw_loc = (job.get("location") or "").lower().replace(",", " ")
        for city_key, country in _CITY_TO_COUNTRY.items():
            if city_key in raw_loc:
                job_countries.add(country)

    if not job_countries:
        return 0

    if location_preference == "d":
        return 0

    if not home_locations:
        return 0

    home_countries_onsite: set[str] = set()
    for loc in home_locations:
        home_countries_onsite.add(_CITY_TO_COUNTRY.get(loc, loc))
        home_countries_onsite.add(loc)

    if any(c in home_countries_onsite for c in job_countries):
        return 0

    return -20


# ---------------------------------------------------------------------------
# Heuristic score
# ---------------------------------------------------------------------------


def heuristic_score(
    profile: dict,
    parsed: dict,
    job: dict,
    is_reloc: bool = False,
    domain_override: str | None = None,
    skill_score: int = 0,
) -> int:
    """Compute heuristic fit score 0-100 from parsed job data + user profile.

    Score budget:
      Domain          0-15   (keyword cascade; semantic fallback handled by caller)
      Seniority       0-15
      Skills          0-30   (pre-computed by caller, passed as skill_score)
      Location        0-10
      Country bonus   ±10
      Language bonus  0-10
      Company type    ±15
      Red flags       0 to -15
      Eligibility     0 or -20

    Args:
        profile: dict with keys: domains, seniority, home_locations, home_regions,
                 location_preference, country_weights, languages, company_type_weights.
        parsed: job's parsed JSON blob.
        job: raw job row (for location and title fields).
        is_reloc: unused — kept for API compatibility.
        domain_override: user-corrected domain; skips cascade when set.
        skill_score: pre-computed skill score from caller (API or agent adapter).
    """
    if not parsed:
        return 0

    score = 0

    # ── Domain (0-15) ──────────────────────────────────────────────────────
    if domain_override is not None:
        score += (profile.get("domains") or {}).get(domain_override, 0)
    else:
        domain = infer_domain(parsed)
        if domain != "other":
            score += (profile.get("domains") or {}).get(domain, 0)
        # else: 0 — semantic fallback is caller's responsibility (api/)

    # ── Seniority (0-15) ───────────────────────────────────────────────────
    score += (profile.get("seniority") or {}).get(parsed.get("seniority", "unknown"), 0)

    # ── Skills (pre-computed by caller) ────────────────────────────────────
    score += skill_score

    # ── Location (0-10) ────────────────────────────────────────────────────
    loc_pref = (profile.get("location_preference") or "b").lower()
    loc_type = parsed.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    home_locations = profile.get("home_locations") or []
    home_regions = profile.get("home_regions") or []

    remote_restriction = (parsed.get("remote_restriction") or "").strip()
    _is_geo_restricted = (
        loc_type == "remote"
        and bool(remote_restriction)
        and remote_restriction.lower() not in ("null", "none")
        and not is_pure_timezone(remote_restriction)
    )
    # Check user eligibility for geo-restricted remote jobs
    _user_eligible = not _is_geo_restricted
    if _is_geo_restricted:
        restriction_lower = remote_restriction.lower()
        home_countries_check: set[str] = set()
        for _loc in home_locations:
            home_countries_check.add(_CITY_TO_COUNTRY.get(_loc, _loc))
            home_countries_check.add(_loc)
        if any(c in restriction_lower for c in home_countries_check if c):
            _user_eligible = True
        elif home_regions and (
            "europe" in restriction_lower or any(r.lower() in restriction_lower for r in home_regions)
        ):
            _user_eligible = True

    def _remote_loc_pts() -> int:
        if _is_geo_restricted:
            return 8 if _user_eligible else 2
        return 10

    if loc_pref == "a":
        if loc_type == "remote":
            score += _remote_loc_pts()
        elif loc_type == "hybrid":
            score += 4
    elif loc_pref == "b":
        if loc_type == "remote":
            score += _remote_loc_pts()
        elif loc_type == "hybrid" and any(c in job_loc for c in home_locations):
            score += 8
        elif loc_type == "onsite" and any(c in job_loc for c in home_locations):
            score += 6
    elif loc_pref == "c":
        all_home = home_locations + home_regions
        if loc_type == "remote":
            score += _remote_loc_pts()
        elif loc_type in ("hybrid", "onsite") and any(c in job_loc for c in all_home):
            score += 8
        elif loc_type == "hybrid":
            score += 3
    elif loc_pref == "d":
        if loc_type == "remote":
            score += _remote_loc_pts()
        elif loc_type == "hybrid":
            score += 10
        elif loc_type == "onsite":
            score += 8

    # ── Country weights (±10) ──────────────────────────────────────────────
    country_weights = profile.get("country_weights") or {}
    if country_weights:
        locations_mentioned = [loc.lower() for loc in (parsed.get("locations_mentioned") or [])]
        normalized_locs = {_CITY_TO_COUNTRY.get(loc, loc) for loc in locations_mentioned}
        if loc_type == "remote" and not _is_geo_restricted:
            normalized_locs.add("remote")
        if normalized_locs:
            best = max(country_weights.get(loc, 0) for loc in normalized_locs)
            score += max(-10, min(10, best))

    # ── Language bonus (0-10) ──────────────────────────────────────────────
    languages = profile.get("languages") or []
    if languages:
        exp_req = parsed.get("experience_requirements") or ""
        if isinstance(exp_req, list):
            exp_req = " ".join(exp_req)
        lang_text = " ".join(
            [
                exp_req,
                parsed.get("responsibilities_summary") or "",
                job.get("title") or "",
                (job.get("description") or "")[:1000],
            ]
        ).lower()
        lang_bonus = 0
        for lang in languages:
            signals = _LANG_SIGNALS.get(lang.lower())
            if signals is None:
                continue
            if any(s in lang_text for s in signals):
                lang_bonus += 5
        score += min(10, lang_bonus)

    # ── Company type (±15) ─────────────────────────────────────────────────
    company_type_weights = profile.get("company_type_weights") or {}
    if company_type_weights:
        company_type = (parsed.get("company_type") or "").lower()
        if company_type:
            ct_score = company_type_weights.get(company_type, 0)
            score += max(-15, min(15, ct_score))

    # ── Red flags (-5 each, max -15) ───────────────────────────────────────
    real_flags = [f for f in (parsed.get("red_flags") or []) if f.strip().lower() not in _NULL_FLAG]
    score -= min(15, len(real_flags) * 5)

    # ── Eligibility penalty (-20) ──────────────────────────────────────────
    score += compute_eligibility_penalty(
        home_locations=home_locations,
        home_regions=home_regions,
        location_preference=loc_pref,
        parsed=parsed,
        job=job,
    )

    return max(0, min(100, score))
