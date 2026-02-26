"""
Welcome to the Jungle scraper.
Uses WTTJ's Algolia-powered search API (public, no auth needed beyond Referer).
Returns list[RawJob] — standardised intermediate representation.
"""

import requests
from scraper import make_job_id
from models import RawJob


# WTTJ's public Algolia credentials (embedded in their frontend JS)
# Updated Feb 2026: new app ID CSEKHVMS53, indexes are locale-specific
ALGOLIA_APP_ID = "CSEKHVMS53"
ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
ALGOLIA_INDEX = "wttj_jobs_production_en"

# Required: Algolia key is restricted to requests from WTTJ's domain
_ALGOLIA_HEADERS = {
    "x-algolia-application-id": ALGOLIA_APP_ID,
    "x-algolia-api-key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
    "Referer": "https://www.welcometothejungle.com/",
    "Origin": "https://www.welcometothejungle.com",
}
_ALGOLIA_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"


def _to_str(val) -> str:
    """Coerce Algolia field value to string (handles list, None, str)."""
    if not val:
        return ""
    if isinstance(val, list):
        return "\n".join(str(v) for v in val)
    return str(val)


def _search_wttj_algolia(queries) -> list[RawJob]:
    """Search WTTJ via Algolia. Returns list[RawJob]."""
    all_jobs: dict[str, RawJob] = {}

    for query in queries:
        body = {
            "query": query["term"],
            "hitsPerPage": query.get("results_wanted", 25),
        }
        if query.get("filters"):
            body["filters"] = query["filters"]

        try:
            r = requests.post(_ALGOLIA_URL, json=body, headers=_ALGOLIA_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", [])

            for h in hits:
                title = h.get("name", "")
                org = h.get("organization", {})
                company = org.get("name", "") if isinstance(org, dict) else ""

                if not title or not company:
                    continue

                # Skip interns/juniors at scrape level
                if any(x in title.lower() for x in ["intern", "internship", "junior", "apprenti"]):
                    continue

                # Structured offices — store raw list + extract primary fields
                offices = h.get("offices", [])
                offices_list = offices if isinstance(offices, list) else []
                locations_structured = offices_list if offices_list else None
                first_office = offices_list[0] if offices_list and isinstance(offices_list[0], dict) else {}
                primary_city = first_office.get("city") or None
                primary_country = first_office.get("country_code") or None

                # Display location string for backward compat
                if primary_city and primary_country and primary_country != "ES":
                    loc = f"{primary_city}, {primary_country}"
                elif primary_city:
                    loc = primary_city
                elif primary_country:
                    loc = primary_country
                else:
                    loc = None

                # Remote type
                remote = h.get("remote", "") or ""
                remote_type = remote if remote in ("fulltime", "partial", "no") else None

                # Build job URL
                org_slug = org.get("slug", "") if isinstance(org, dict) else ""
                job_slug = h.get("slug") or h.get("reference", "")
                if org_slug and job_slug:
                    job_url = f"https://www.welcometothejungle.com/en/companies/{org_slug}/jobs/{job_slug}"
                else:
                    job_url = None

                # Description: combine summary + profile + key_missions
                desc_parts = [
                    _to_str(h.get("summary")),
                    _to_str(h.get("profile")),
                    _to_str(h.get("key_missions")),
                ]
                description = "\n\n".join(p for p in desc_parts if p) or None

                # Salary
                sal_min = h.get("salary_yearly_minimum") or h.get("salary_minimum")
                sal_max = h.get("salary_maximum")
                sal_currency = h.get("salary_currency") or "EUR"
                sal_period = h.get("salary_period") or "yearly"

                # Experience range
                exp_min = h.get("experience_level_minimum")
                exp_max = h.get("experience_level_maximum")

                # source_category from new_profession sub_category_reference
                new_profession = h.get("new_profession") or {}
                source_cat = new_profession.get("sub_category_reference") if isinstance(new_profession, dict) else None

                job_id = make_job_id(title, company)
                if job_id not in all_jobs:
                    all_jobs[job_id] = RawJob(
                        id=job_id,
                        title=title,
                        company=company,
                        source="wttj",
                        # Core fields
                        job_url=job_url,
                        location=loc,
                        description=description,
                        job_type=h.get("contract_type") or None,
                        date_posted=h.get("published_at") or None,
                        search_term_used=query["term"] or None,
                        # Remote
                        remote_type=remote_type,
                        # Structured location
                        country=primary_country,
                        city=primary_city,
                        locations_structured=locations_structured,
                        # Salary
                        min_amount=float(sal_min) if sal_min is not None else None,
                        max_amount=float(sal_max) if sal_max is not None else None,
                        currency=sal_currency,
                        interval=sal_period,
                        # Experience (WTTJ structured)
                        experience_min=int(exp_min) if exp_min is not None else None,
                        experience_max=int(exp_max) if exp_max is not None else None,
                        # Language
                        language=h.get("language") or None,
                        # Category
                        source_category=source_cat,
                    )

            print(f"   WTTJ Algolia: '{query['term']}' -> {len(hits)} results, {len(all_jobs)} unique total")

        except Exception as e:
            print(f"   WTTJ Algolia error for '{query['term']}': {e}")

    return list(all_jobs.values())


def _search_wttj_google(queries) -> list[RawJob]:
    """Fallback: use Google to find WTTJ listings. Returns list[RawJob]."""
    from jobspy import scrape_jobs

    all_jobs: dict[str, RawJob] = {}
    for query in queries:
        try:
            results = scrape_jobs(
                site_name=["google"],
                search_term=query["google_search_term"],
                location="",
                results_wanted=query.get("results_wanted", 15),
                hours_old=query.get("hours_old", 168),
                description_format="markdown",
            )

            for _, row in results.iterrows():
                title = str(row.get("title", "")).strip()
                company = str(row.get("company", "")).strip()
                url = str(row.get("job_url", ""))

                if not title or not company:
                    continue
                if "welcometothejungle" not in url and "wttj" not in url:
                    continue

                loc = str(row.get("location", "")).strip() or None
                desc = str(row.get("description", "")).strip() or None
                is_remote_str = "remote" in title.lower() or (loc and "remote" in loc.lower())
                remote_type = "fulltime" if is_remote_str else "no"

                job_id = make_job_id(title, company)
                if job_id not in all_jobs:
                    all_jobs[job_id] = RawJob(
                        id=job_id,
                        title=title,
                        company=company,
                        source="wttj",
                        job_url=url or None,
                        location=loc,
                        description=desc,
                        date_posted=str(row.get("date_posted", "")).strip() or None,
                        search_term_used=query["google_search_term"] or None,
                        remote_type=remote_type,
                    )

            print(f"   WTTJ Google: '{query['google_search_term']}' -> {len(results)} raw, {len(all_jobs)} unique")
        except Exception as e:
            print(f"   WTTJ Google error: {e}")

    return list(all_jobs.values())


def _build_geo_filter(target_countries: list[str]) -> str:
    """Build Algolia geo filter: target country offices OR any remote job.

    Args:
        target_countries: ISO 2-letter country codes (e.g. ["ES", "NL", "DE"]).

    Returns:
        Algolia filter string fragment, e.g.:
        "(offices.country_code:ES OR offices.country_code:NL OR remote:fulltime OR remote:partial)"
    """
    parts = [f"offices.country_code:{code}" for code in target_countries]
    parts += ["remote:fulltime", "remote:partial"]
    return "(" + " OR ".join(parts) + ")"


def run_wttj_scraper(target_countries: list[str] | None = None):
    """Search WTTJ for PM roles via Algolia. Falls back to Google on failure.

    Args:
        target_countries: ISO 2-letter country codes to include as onsite targets
            (e.g. ["ES", "NL", "DE", "GB", "IE"]). Remote jobs from any country
            always pass. Defaults to ["ES"] when not provided.
    """
    if target_countries is None:
        target_countries = ["ES"]

    # Primary: Algolia search
    # new_profession.sub_category_reference:product-management-wNjYw ensures all results are PM
    # roles (not engineers, data analysts, etc.) - no need to prefilter by title anymore.
    # Geographic filter: onsite jobs restricted to target_countries; remote jobs always pass.
    _PM = "new_profession.sub_category_reference:product-management-wNjYw"
    _GEO = _build_geo_filter(target_countries)
    _FILTER = f"{_PM} AND {_GEO}"

    queries = [
        {"term": "data", "filters": _FILTER, "results_wanted": 40},
        {"term": "platform", "filters": _FILTER, "results_wanted": 40},
        {"term": "analytics", "filters": _FILTER, "results_wanted": 30},
        {"term": "AI machine learning", "filters": _FILTER, "results_wanted": 30},
        {"term": "adtech advertising", "filters": _FILTER, "results_wanted": 30},
        {"term": "principal staff", "filters": _FILTER, "results_wanted": 25},
    ]

    google_queries = [
        {
            "google_search_term": "site:welcometothejungle.com product manager data Spain OR remote",
            "results_wanted": 15,
            "hours_old": 168,
        },
        {
            "google_search_term": "site:welcometothejungle.com senior product manager platform Europe OR remote",
            "results_wanted": 15,
            "hours_old": 168,
        },
    ]

    print("\nSearching Welcome to the Jungle...")

    try:
        jobs = _search_wttj_algolia(queries)
        print(f"   WTTJ total: {len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"   WTTJ Algolia failed ({e}), falling back to Google...")

    jobs = _search_wttj_google(google_queries)
    print(f"   WTTJ total (Google fallback): {len(jobs)} jobs")
    return jobs


if __name__ == "__main__":
    jobs = run_wttj_scraper()
    for j in jobs[:10]:
        print(f"\n{j.title} @ {j.company} ({j.location})")
        print(f"  Remote: {j.remote_type} | Salary: {j.min_amount}-{j.max_amount} {j.currency}")
        print(f"  {j.job_url}")
