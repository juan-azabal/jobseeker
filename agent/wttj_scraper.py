"""
Welcome to the Jungle scraper.
Uses WTTJ's Algolia-powered search API (public, no auth needed beyond Referer).
Returns standardized job dicts compatible with pipeline.
"""

import requests
from scraper import make_job_id


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


def _search_wttj_algolia(queries):
    """Search WTTJ via Algolia. Returns list of job dicts."""
    all_jobs = {}

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

                # Location
                offices = h.get("offices", [])
                if isinstance(offices, list) and offices:
                    loc = offices[0].get("city", "") if isinstance(offices[0], dict) else ""
                    country = offices[0].get("country_code", "") if isinstance(offices[0], dict) else ""
                    if country and country != "ES":
                        loc = f"{loc}, {country}" if loc else country
                else:
                    loc = ""

                remote = h.get("remote", "")
                is_remote = remote in ("fulltime", "partial")

                # Build job URL
                org_slug = org.get("slug", "") if isinstance(org, dict) else ""
                job_slug = h.get("slug", h.get("reference", ""))
                if org_slug and job_slug:
                    job_url = f"https://www.welcometothejungle.com/en/companies/{org_slug}/jobs/{job_slug}"
                else:
                    job_url = ""

                # Description: combine profile + key_missions + summary
                # key_missions can be a list or a string depending on the posting
                def _to_str(val):
                    if not val:
                        return ""
                    if isinstance(val, list):
                        return "\n".join(str(v) for v in val)
                    return str(val)

                desc_parts = [
                    _to_str(h.get("summary")),
                    _to_str(h.get("profile")),
                    _to_str(h.get("key_missions")),
                ]
                description = "\n\n".join(p for p in desc_parts if p)

                sal_min = h.get("salary_yearly_minimum") or h.get("salary_minimum")
                sal_max = h.get("salary_maximum")
                sal_currency = h.get("salary_currency", "EUR")
                sal_period = h.get("salary_period", "yearly")

                job_id = make_job_id(title, company)
                if job_id not in all_jobs:
                    all_jobs[job_id] = {
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "description": description,
                        "job_url": job_url,
                        "date_posted": h.get("published_at", ""),
                        "job_type": h.get("contract_type", ""),
                        "is_remote": is_remote,
                        "min_amount": sal_min,
                        "max_amount": sal_max,
                        "currency": sal_currency,
                        "interval": sal_period,
                        "site": "wttj",
                        "search_term_used": query["term"],
                    }

            print(f"   WTTJ Algolia: '{query['term']}' -> {len(hits)} results, {len(all_jobs)} unique total")

        except Exception as e:
            print(f"   WTTJ Algolia error for '{query['term']}': {e}")

    return list(all_jobs.values())


def _search_wttj_google(queries):
    """Fallback: use Google to find WTTJ listings."""
    from jobspy import scrape_jobs

    all_jobs = {}
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

                job_id = make_job_id(title, company)
                if job_id not in all_jobs:
                    all_jobs[job_id] = {
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "location": str(row.get("location", "")),
                        "description": str(row.get("description", "")),
                        "job_url": url,
                        "date_posted": str(row.get("date_posted", "")),
                        "job_type": "",
                        "is_remote": "remote" in title.lower() or "remote" in str(row.get("location", "")).lower(),
                        "min_amount": None,
                        "max_amount": None,
                        "currency": "",
                        "interval": "",
                        "site": "wttj",
                        "search_term_used": query["google_search_term"],
                    }

            print(f"   WTTJ Google: '{query['google_search_term']}' -> {len(results)} raw, {len(all_jobs)} unique")
        except Exception as e:
            print(f"   WTTJ Google error: {e}")

    return list(all_jobs.values())


def run_wttj_scraper():
    """Search WTTJ for PM roles via Algolia. Falls back to Google on failure."""

    # Primary: Algolia search
    # new_profession.sub_category_reference:product-management-wNjYw ensures all results are PM
    # roles (not engineers, data analysts, etc.) - no need to prefilter by title anymore.
    # Location/remote filtering is left to prefilter.py (handles edge cases better).
    # Filter to PM profession category only - eliminates engineers, analysts, etc.
    # Query terms are intentionally broad since Algolia matches against title+description.
    _PM = "new_profession.sub_category_reference:product-management-wNjYw"

    queries = [
        {"term": "data",         "filters": _PM, "results_wanted": 40},
        {"term": "platform",     "filters": _PM, "results_wanted": 40},
        {"term": "analytics",    "filters": _PM, "results_wanted": 30},
        {"term": "AI machine learning", "filters": _PM, "results_wanted": 30},
        {"term": "adtech advertising",  "filters": _PM, "results_wanted": 30},
        {"term": "principal staff",     "filters": _PM, "results_wanted": 25},
    ]

    google_queries = [
        {"google_search_term": "site:welcometothejungle.com product manager data Spain OR remote", "results_wanted": 15, "hours_old": 168},
        {"google_search_term": "site:welcometothejungle.com senior product manager platform Europe OR remote", "results_wanted": 15, "hours_old": 168},
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
        print(f"\n{j['title']} @ {j['company']} ({j['location']})")
        print(f"  Remote: {j['is_remote']} | Salary: {j['min_amount']}-{j['max_amount']} {j['currency']}")
        print(f"  {j['job_url']}")
