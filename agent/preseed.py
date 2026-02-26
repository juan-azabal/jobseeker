"""
Pre-seeder: maps structured RawJob fields (from scraper/merger) to parser schema.

Runs BEFORE LLM parsing. Returns a dict of pre-determined fields that the
parser can use to skip re-extracting what we already know from structured data.

Usage:
    from preseed import preseed_parsed
    seed = preseed_parsed(job_dict)  # may be {}
"""

from __future__ import annotations

# ── Seniority mapping ────────────────────────────────────────────────────────
# Source: LinkedIn job_level values (used by JobSpy). Other sources use free-text.
# Parser enum: junior|mid|senior|staff|principal|director|vp|unknown

_SENIORITY_MAP: list[tuple[list[str], str]] = [
    # Check most specific first
    (["principal"],                              "principal"),
    (["staff"],                                  "staff"),
    (["vp", "vice president"],                   "vp"),
    (["executive", "c-level", "c level"],        "vp"),
    (["director"],                               "director"),
    (["mid-senior", "mid senior", "senior", "lead", "sr"],  "senior"),
    (["associate", "mid-level", "mid level"],    "mid"),
    (["entry", "junior", "internship", "intern", "graduate", "trainee"], "junior"),
]

# Values that should NOT be pre-seeded (no useful signal)
_SENIORITY_SKIP = {"not applicable", "n/a", ""}


def _map_seniority(job_level: str | None) -> str | None:
    """Map LinkedIn/JobSpy job_level → parser seniority enum value."""
    if not job_level:
        return None
    normalized = job_level.lower().strip()
    if normalized in _SENIORITY_SKIP:
        return None
    for keywords, mapped in _SENIORITY_MAP:
        if any(kw in normalized for kw in keywords):
            return mapped
    return None


# ── Location type mapping ────────────────────────────────────────────────────

_REMOTE_TYPE_TO_LOCATION: dict[str, str] = {
    "fulltime": "remote",
    "partial":  "hybrid",
    "no":       "onsite",
}


def _map_location_type(remote_type: str | None) -> str | None:
    if not remote_type:
        return None
    return _REMOTE_TYPE_TO_LOCATION.get(remote_type)


# ── Salary formatting ────────────────────────────────────────────────────────

_CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF",
    "SEK": "SEK", "DKK": "DKK", "NOK": "NOK", "PLN": "PLN",
}


def _format_salary(
    min_amount: float | None,
    max_amount: float | None,
    currency: str,
    interval: str,
) -> str | None:
    if min_amount is None:
        return None
    sym = _CURRENCY_SYMBOLS.get(currency.upper(), currency)
    interval_label = {"yearly": "year", "monthly": "month", "hourly": "hour"}.get(
        (interval or "").lower(), interval or "year"
    )

    def fmt(n: float) -> str:
        if n >= 1000:
            return f"{n:,.0f}"
        return f"{n:.0f}"

    if max_amount is not None:
        return f"{sym}{fmt(min_amount)} - {sym}{fmt(max_amount)}/{interval_label}"
    return f"{sym}{fmt(min_amount)}+/{interval_label}"


# ── Domain mapping ───────────────────────────────────────────────────────────
# Maps company_industry strings (LinkedIn etc.) → canonical domain enum.
# Lower-priority fallback: source_category (WTTJ new_profession.sub_category_reference).

# LinkedIn industry → canonical domain.
# Keys are lowercase substrings; first match wins. Order matters (specific first).
_INDUSTRY_DOMAIN: list[tuple[str, str]] = [
    # Fintech
    ("financial services",        "fintech"),
    ("banking",                   "fintech"),
    ("insurance",                 "fintech"),
    ("investment management",     "fintech"),
    ("venture capital",           "fintech"),
    ("capital markets",           "fintech"),
    ("accounting",                "fintech"),
    # Healthcare
    ("hospital & health care",    "healthtech"),
    ("health care",               "healthtech"),
    ("healthcare",                "healthtech"),
    ("medical device",            "healthtech"),
    ("medical practice",          "healthtech"),
    # Biotech
    ("pharmaceuticals",           "biotech"),
    ("biotechnology",             "biotech"),
    ("life sciences",             "biotech"),
    # Edtech
    ("e-learning",                "edtech"),
    ("education management",      "edtech"),
    ("primary/secondary education", "edtech"),
    ("higher education",          "edtech"),
    # Gaming
    ("computer games",            "gaming"),
    ("online media",              "media"),
    ("games",                     "gaming"),
    # Cybersecurity
    ("computer & network security", "cybersecurity"),
    ("network security",          "cybersecurity"),
    # Retail
    ("retail",                    "retail"),
    ("consumer goods",            "retail"),
    # Automotive
    ("automotive",                "automotive"),
    # Defense
    ("defense & space",           "defense"),
    ("military",                  "defense"),
    # Legal tech
    ("law practice",              "legal_tech"),
    ("legal services",            "legal_tech"),
    # HR tech
    ("staffing & recruiting",     "hr_tech"),
    ("human resources",           "hr_tech"),
    # Logistics
    ("logistics & supply chain",  "logistics"),
    ("transportation/trucking",   "logistics"),
    ("warehousing",               "logistics"),
    ("package/freight delivery",  "logistics"),
    # Food & bev
    ("food & beverages",          "food_bev"),
    ("restaurants",               "food_bev"),
    ("food production",           "food_bev"),
    # Travel
    ("airlines/aviation",         "travel"),
    ("hospitality",               "travel"),
    ("leisure, travel",           "travel"),
    # Media
    ("media production",          "media"),
    ("broadcast media",           "media"),
    ("publishing",                "media"),
    ("entertainment",             "media"),
    # Energy
    ("oil & energy",              "energy"),
    ("utilities",                 "energy"),
    ("renewables & environment",  "climate"),
    ("environmental services",    "climate"),
    # Telecom
    ("telecommunications",        "telecom"),
    ("wireless",                  "telecom"),
    # Construction
    ("construction",              "construction"),
    ("civil engineering",         "construction"),
    ("real estate",               "construction"),
    # Govtech
    ("government administration", "govtech"),
    ("public policy",             "govtech"),
    # Manufacturing
    ("manufacturing",             "manufacturing"),
    ("machinery",                 "manufacturing"),
    ("industrial automation",     "manufacturing"),
    # AI/ML
    ("artificial intelligence",   "ai_ml"),
    ("machine learning",          "ai_ml"),
    # Data
    ("data analytics",            "data"),
    # SaaS / generic tech (broad — keep last)
    ("computer software",         "saas"),
    ("information technology",    "saas"),
    ("internet",                  "saas"),
    ("technology",                "saas"),
    ("software development",      "saas"),
]


def _industry_to_domain(industry: str | None) -> str | None:
    if not industry:
        return None
    low = industry.lower().strip()
    for key, domain in _INDUSTRY_DOMAIN:
        if key in low:
            return domain
    return None


# WTTJ source_category keyword → domain
_SOURCE_CATEGORY_DOMAIN: list[tuple[str, str]] = [
    ("data-analytic",       "data"),
    ("data-engineer",       "data"),
    ("business-intelligen", "data"),
    ("machine-learning",    "ai_ml"),
    ("artificial-intellig", "ai_ml"),
    ("deep-learning",       "ai_ml"),
    ("cybersecurit",        "cybersecurity"),
    ("information-securit", "cybersecurity"),
    ("fintech",             "fintech"),
    ("banking",             "fintech"),
    ("insurtech",           "fintech"),
    ("health",              "healthtech"),
    ("medtech",             "healthtech"),
    ("edtech",              "edtech"),
    ("e-learning",          "edtech"),
    ("gaming",              "gaming"),
    ("game-dev",            "gaming"),
    ("ecommerce",           "ecommerce"),
    ("marketplace",         "marketplace"),
    ("adtech",              "adtech"),
    ("martech",             "adtech"),
    ("cloud",               "infra"),
    ("devops",              "infra"),
    ("infrastructure",      "infra"),
    ("saas",                "saas"),
]


def _source_category_to_domain(source_category: str | None) -> str | None:
    if not source_category:
        return None
    low = source_category.lower()
    for key, domain in _SOURCE_CATEGORY_DOMAIN:
        if key in low:
            return domain
    return None


def _map_domain(company_industry: str | None, source_category: str | None) -> str | None:
    """Map industry or source_category → canonical domain. None if no match."""
    domain = _industry_to_domain(company_industry)
    if domain:
        return domain
    return _source_category_to_domain(source_category)


# ── Location extraction ──────────────────────────────────────────────────────

def _extract_locations(job: dict) -> list[str] | None:
    """Extract location strings from structured location fields."""
    locations: list[str] = []
    seen: set[str] = set()

    def _add(val: str | None) -> None:
        if val and val not in seen:
            seen.add(val)
            locations.append(val)

    # Primary: locations_structured (WTTJ offices list)
    structured = job.get("locations_structured")
    if structured and isinstance(structured, list):
        for office in structured:
            if isinstance(office, dict):
                _add(office.get("city") or None)
                _add(office.get("country") or None)

    # Fallback: flat city / country fields
    if not locations:
        _add(job.get("city") or None)
        _add(job.get("country") or None)

    return locations if locations else None


# ── Main entry point ─────────────────────────────────────────────────────────

def preseed_parsed(job: dict) -> dict:
    """Map structured RawJob fields to parser output schema.

    Returns a dict of pre-determined fields (never None values).
    An empty dict means no structured data was available to pre-seed.

    Args:
        job: job dict from the pipeline (post-merge, post-_to_dicts).

    Returns:
        dict with a subset of parser schema fields, values guaranteed non-null.
    """
    result: dict = {}

    # Seniority from job_level
    seniority = _map_seniority(job.get("job_level"))
    if seniority:
        result["seniority"] = seniority

    # Location type from remote_type
    location_type = _map_location_type(job.get("remote_type"))
    if location_type:
        result["location_type"] = location_type

    # Salary — only when source is direct structured data
    salary_source = (job.get("salary_source") or "").lower()
    min_amount = job.get("min_amount")
    if min_amount is not None and "direct_data" in salary_source:
        sal = _format_salary(
            min_amount,
            job.get("max_amount"),
            job.get("currency") or "USD",
            job.get("interval") or "yearly",
        )
        if sal:
            result["salary_mentioned"] = sal

    # Domain from company_industry or WTTJ source_category
    domain = _map_domain(job.get("company_industry"), job.get("source_category"))
    if domain:
        result["domain"] = domain

    # Experience years from structured range
    exp_min = job.get("experience_min")
    exp_max = job.get("experience_max")
    if exp_min is not None:
        result["years_experience_min"] = exp_min
    if exp_max is not None:
        result["years_experience_max"] = exp_max

    # Locations from structured fields
    locations = _extract_locations(job)
    if locations:
        result["locations_mentioned"] = locations

    return result
