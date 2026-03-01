"""Generate JobSpy search queries from a user profile's search_titles field.

Public API:
  generate_queries(profile) -> list[dict]
  generate_unified_queries(profiles) -> list[dict]

Query generation:
  For each title in profile.target.search_titles × {indeed, linkedin}, one query dict.
  Indeed queries first, then LinkedIn (execution order: no-rate-limit before rate-limited).
"""

import logging

logger = logging.getLogger(__name__)

COUNTRY_INDEED_MAP = {
    "spain": "Spain",
    "españa": "Spain",
    "france": "France",
    "francia": "France",
    "germany": "Germany",
    "alemania": "Germany",
    "uk": "UK",
    "united kingdom": "UK",
    "usa": "USA",
    "united states": "USA",
    "netherlands": "Netherlands",
    "portugal": "Portugal",
    "italy": "Italy",
    "italia": "Italy",
}

LINKEDIN_DELAY_SECS = 2  # Initial hypothesis — investigate 429s during implementation


def generate_queries(profile: dict) -> list[dict]:
    """Generate search query dicts from profile.target.search_titles.

    Returns Indeed queries first, then LinkedIn (rate-limit safety).
    Returns empty list when search_titles is missing or empty.
    """
    titles = profile.get("target", {}).get("search_titles", [])
    if not titles:
        logger.warning("generate_queries: no search_titles in profile — returning empty list")
        return []

    locations = profile.get("user", {}).get("home_locations", [])
    city = locations[0] if locations else ""
    country = locations[1] if len(locations) > 1 else "spain"
    country_indeed = COUNTRY_INDEED_MAP.get(country.lower(), "Spain")

    seen_titles: set[str] = set()
    indeed_queries = []
    linkedin_queries = []
    for title in titles:
        if not title or not title.strip():
            continue
        normalized = title.strip().lower()
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        title = title.strip()
        indeed_queries.append(
            {
                "term": title,
                "location": city,
                "site": "indeed",
                "results_wanted": 25,
                "hours_old": 72,
                "country_indeed": country_indeed,
                "description_format": "markdown",
            }
        )
        linkedin_queries.append(
            {
                "term": title,
                "location": city,
                "site": "linkedin",
                "results_wanted": 15,
                "hours_old": 72,
                "is_remote": False,
                "linkedin_fetch_description": True,
                "description_format": "markdown",
            }
        )
    return indeed_queries + linkedin_queries


def generate_unified_queries(profiles: list[tuple[str, dict]]) -> list[dict]:
    """Generate deduplicated queries across all profiles.

    profiles: list of (profile_id, profile_dict) tuples.
    Deduplicates by (term.lower(), location.lower(), site).
    Returns Indeed queries first, then LinkedIn.
    """
    seen: set[tuple] = set()
    indeed_queries: list[dict] = []
    linkedin_queries: list[dict] = []

    for _profile_id, profile in profiles:
        for query in generate_queries(profile):
            key = (query["term"].lower(), query["location"].lower(), query["site"])
            if key in seen:
                continue
            seen.add(key)
            if query["site"] == "indeed":
                indeed_queries.append(query)
            else:
                linkedin_queries.append(query)

    return indeed_queries + linkedin_queries
