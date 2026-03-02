"""Deterministic profile derivation from Master CV JSON.

derive_profile_from_master_cv() returns a flat dict compatible with ProfileEditor
(same shape as _yaml_to_flat_profile() in api/routes/onboard.py).
"""

from __future__ import annotations

from shared.scoring_data import DOMAIN_KEYWORDS

_MANAGEMENT_SIGNALS = ("head of", "director", "vp", "vice president", "chief", "cpo", "cto", "ceo")
_SENIOR_SIGNALS = ("senior", "sr.", "sr ", "lead", "principal", "staff")
_DIRECTOR_SIGNALS = ("head of", "director", "vp", "vice president", "chief")

_ROLE_FUNCTION_MAP = {
    "product": ("product manager", "pm", "product owner", "po "),
    "engineering": ("engineer", "developer", "software", "backend", "frontend", "fullstack", "sre", "devops"),
    "design": ("designer", "ux", "ui", "product design"),
    "data": ("data scientist", "data analyst", "analytics", "machine learning", "ml engineer"),
    "marketing": ("marketing", "growth", "seo", "content"),
    "sales": ("sales", "account executive", "business development", "ae "),
    "ops": ("operations", "ops", "program manager", "project manager", "scrum"),
    "support": ("customer success", "customer support", "support engineer"),
}


def derive_profile_from_master_cv(master_cv: dict) -> dict:
    """Return a flat profile dict from a Master CV JSON dict.

    Compatible with the shape returned by _yaml_to_flat_profile().
    """
    work = master_cv.get("work") or []
    skills_section = master_cv.get("skills") or []
    basics = master_cv.get("basics") or {}
    languages = master_cv.get("languages") or []

    skills = _derive_skills(work, skills_section)
    domains = _derive_domains(work)
    most_recent = work[0] if work else None

    current_level = _infer_level(most_recent)
    track = _infer_track(most_recent)
    role_type = most_recent["position"] if most_recent else ""
    role_function = _infer_role_function(most_recent)
    home_locations = _derive_home_locations(basics)

    return {
        "name": basics.get("name") or "",
        "email": basics.get("email"),
        "languages": [lang["language"] for lang in languages],
        "home_locations": home_locations,
        "current_level": current_level,
        "target_level": current_level,
        "track": track,
        "role_type": role_type,
        "role_function": role_function,
        "skills": skills,
        "domains": domains,
        "seniority_weights": {},
        "exclude_companies": [],
        "salary_min": 60000,
        "location_preference": "b",
        "country_weights": {},
        "company_type_weights": {},
        "search_titles": [],
    }


def _derive_skills(work: list[dict], skills_section: list[dict]) -> list[str]:
    """Union of work[].skills_used + skills[].name + skills[].keywords — lowercase deduped."""
    seen: set[str] = set()
    result: list[str] = []

    def _add(raw: str) -> None:
        key = raw.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(raw.strip())

    for entry in work:
        for skill in entry.get("skills_used") or []:
            _add(skill)

    for skill_entry in skills_section:
        _add(skill_entry.get("name", ""))
        for kw in skill_entry.get("keywords") or []:
            _add(kw)

    return result


def _derive_domains(work: list[dict]) -> dict[str, int]:
    """Infer domain dict from company names and positions using DOMAIN_KEYWORDS."""
    domain_hits: dict[str, int] = {}

    for entry in work:
        text = f"{entry.get('company', '')} {entry.get('position', '')} {entry.get('summary', '')}".lower()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    domain_hits[domain] = domain_hits.get(domain, 0) + 1
                    break

    return {domain: min(hits * 5, 15) for domain, hits in domain_hits.items()}


def _infer_level(entry: dict | None) -> str:
    """Infer seniority from most recent position title."""
    if not entry:
        return "mid"
    title = entry.get("position", "").lower()
    if any(sig in title for sig in _DIRECTOR_SIGNALS):
        return "director"
    if any(sig in title for sig in _SENIOR_SIGNALS):
        return "senior"
    if "junior" in title or "jr" in title or "intern" in title:
        return "junior"
    return "mid"


def _infer_track(entry: dict | None) -> str:
    """Infer IC vs management from most recent position."""
    if not entry:
        return "ic"
    title = entry.get("position", "").lower()
    if any(sig in title for sig in _MANAGEMENT_SIGNALS):
        return "management"
    return "ic"


def _infer_role_function(entry: dict | None) -> str:
    """Map most recent position to a role_function enum value."""
    if not entry:
        return "other"
    title = entry.get("position", "").lower()
    for func, signals in _ROLE_FUNCTION_MAP.items():
        if any(sig in title for sig in signals):
            return func
    return "other"


def _derive_home_locations(basics: dict) -> list[str]:
    """Return [city, country] from basics.location, filtering empty strings."""
    location = basics.get("location") or {}
    city = location.get("city") or ""
    country = location.get("country") or ""
    return [v for v in [city, country] if v]
