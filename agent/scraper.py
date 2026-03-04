"""
Scraper module: wraps JobSpy to fetch jobs from multiple boards.
Returns list[RawJob] — standardised intermediate representation.
"""

import math
import re
import time
import yaml
import hashlib
from jobspy import scrape_jobs

from models import RawJob
from search_generator import LINKEDIN_DELAY_SECS


def _sanitize_str(val) -> str:
    """Convert a DataFrame field value to a clean string.

    Replaces pandas NaN (float), None, and the string literal 'nan'
    (produced by str(float('nan'))) with an empty string.
    """
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def load_search_config(path="config/searches.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _normalize_for_id(text: str) -> str:
    """Normalize title or company name for stable deduplication across sources.

    Strips gender suffixes, legal entity suffixes, punctuation variants, and
    extra whitespace so the same job from different sources gets the same ID.
    """
    s = text.lower().strip()
    # Strip gender/diversity parenthetical suffixes (e.g. (f/m/d), (h/f), (all genders))
    s = re.sub(r"\s*\([fmhwd/]+\)\s*$", "", s)
    s = re.sub(r"\s*\(all\s+genders?\)\s*$", "", s)
    # Strip Greenhouse-style cross-geo suffix: "| Country/Region | WorkMode"
    # e.g. "Senior PM | Canada | Remote" → "Senior PM"
    # Only strips when the last segment is a known work-mode keyword.
    s = re.sub(
        r"\s*\|\s*[^|]+\s*\|\s*(remote|hybrid|onsite|on-site|office)\s*$",
        "",
        s,
    )
    # Strip common legal entity suffixes from company names
    for suffix in [
        ", inc.",
        ", inc",
        " inc.",
        " inc",
        ", ltd",
        " ltd",
        ", s.l.",
        " s.l.",
        ", s.a.",
        " s.a.",
        ", gmbh",
        " gmbh",
        ", b.v.",
        " b.v.",
        ", llc.",
        " llc.",
        ", llc",
        " llc",
        ", corp.",
        " corp.",
        ", corp",
        " corp",
        ", ag",
        " ag",
    ]:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    # Replace all punctuation with spaces, then collapse whitespace
    s = re.sub(r"[^\w\s]", " ", s)
    s = " ".join(s.split())
    return s


def make_job_id(title: str, company: str) -> str:
    """Deterministic ID for deduplication across sources.

    Uses title+company only (normalized) to catch cross-source dupes.
    Normalization removes gender suffixes, legal entity suffixes,
    punctuation variants, and extra whitespace.
    """
    t = _normalize_for_id(title)
    c = _normalize_for_id(company)
    raw = f"{t}|{c}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _to_remote_type(is_remote_flag) -> str | None:
    """Map JobSpy bool is_remote flag to RawJob remote_type string."""
    if is_remote_flag is True or is_remote_flag == 1:
        return "fulltime"
    if is_remote_flag is False or is_remote_flag == 0:
        return "no"
    return None


def _or_none(val) -> str | None:
    """Like _sanitize_str but returns None instead of '' for missing values."""
    s = _sanitize_str(val)
    return s if s else None


def _float_or_none(val) -> float | None:
    """Return float value or None if missing/NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def run_scraper(config_path="config/searches.yaml") -> list[RawJob]:
    """Scrape jobs from all configured boards. Returns list[RawJob]."""
    config = load_search_config(config_path)
    country = config.get("country_indeed", "Spain")
    is_remote = config.get("is_remote", False)

    all_jobs: dict[str, RawJob] = {}  # keyed by job_id for dedup

    for search in config["searches"]:
        term = search.get("term", search.get("search_term", ""))
        location = search.get("location", "")
        sites = search.get("sites", ["indeed", "google"])
        google_search_term = search.get("google_search_term", None)
        use_linkedin = "linkedin" in sites

        print(f"\nSearching: '{term}' in {location or 'anywhere'} [{','.join(sites)}]...")

        try:
            kwargs = dict(
                site_name=sites,
                search_term=term,
                location=location,
                results_wanted=search.get("results_wanted", 20),
                hours_old=search.get("hours_old", 72),
                is_remote=search.get("is_remote", is_remote),
                country_indeed=country,
                description_format="markdown",
            )

            if use_linkedin:
                kwargs["linkedin_fetch_description"] = True

            if google_search_term:
                kwargs["google_search_term"] = google_search_term

            results = scrape_jobs(**kwargs)

            for _, row in results.iterrows():
                title = _sanitize_str(row.get("title", ""))
                company = _sanitize_str(row.get("company", ""))

                if not title or not company:
                    continue

                job_id = make_job_id(title, company)

                if job_id not in all_jobs:
                    source = _sanitize_str(row.get("site", "")) or "unknown"
                    all_jobs[job_id] = RawJob(
                        id=job_id,
                        title=title,
                        company=company,
                        source=source,
                        # Core fields
                        job_url=_or_none(row.get("job_url")),
                        location=_or_none(row.get("location")),
                        description=_or_none(row.get("description")),
                        job_type=_or_none(row.get("job_type")),
                        date_posted=_or_none(row.get("date_posted")),
                        search_term_used=term or None,
                        # Remote
                        remote_type=_to_remote_type(row.get("is_remote")),
                        # Salary
                        min_amount=_float_or_none(row.get("min_amount")),
                        max_amount=_float_or_none(row.get("max_amount")),
                        currency=_or_none(row.get("currency")),
                        interval=_or_none(row.get("interval")),
                        salary_source=_or_none(row.get("salary_source")),
                        # Company metadata
                        company_url=_or_none(row.get("company_url")),
                        company_industry=_or_none(row.get("company_industry")),
                        company_employees_label=_or_none(row.get("company_num_employees")),
                        company_revenue_label=_or_none(row.get("company_revenue")),
                        company_logo=_or_none(row.get("company_logo")),
                        # Role metadata
                        job_level=_or_none(row.get("job_level")),
                        job_function=_or_none(row.get("job_function")),
                        # Contact
                        emails=(
                            [e.strip() for e in row["emails"].split(",") if e.strip()] if row.get("emails") else None
                        ),
                    )

            print(f"   Found {len(results)} results ({len(all_jobs)} unique total)")

        except Exception as e:
            print(f"   Error: {e}")
            continue

    jobs_list = list(all_jobs.values())
    print(f"\nTotal unique jobs scraped: {len(jobs_list)}")
    return jobs_list


def _build_kwargs(query: dict) -> dict:
    """Map a query dict to scrape_jobs() keyword arguments."""
    kwargs: dict = {
        "site_name": query["site"],
        "search_term": query["term"],
        "location": query["location"],
        "results_wanted": query["results_wanted"],
        "hours_old": query["hours_old"],
        "description_format": query.get("description_format", "markdown"),
    }
    if "is_remote" in query and query["is_remote"] is not None:
        kwargs["is_remote"] = query["is_remote"]
    if query["site"] == "indeed" and "country_indeed" in query:
        kwargs["country_indeed"] = query["country_indeed"]
    if query["site"] == "linkedin" and query.get("linkedin_fetch_description"):
        kwargs["linkedin_fetch_description"] = True
    return kwargs


def run_scraper_from_queries(queries: list[dict]) -> list[RawJob]:
    """Scrape jobs from pre-built query dicts. Returns deduplicated list[RawJob].

    Applies LINKEDIN_DELAY_SECS sleep after each LinkedIn query (rate-limit safety).
    Indeed queries run without delay.
    """
    if not queries:
        return []

    all_jobs: dict[str, RawJob] = {}

    for query in queries:
        site = query["site"]
        term = query["term"]
        location = query.get("location", "")

        print(f"\nSearching: '{term}' in {location or 'anywhere'} [{site}]...")
        try:
            results = scrape_jobs(**_build_kwargs(query))
            for _, row in results.iterrows():
                title = _sanitize_str(row.get("title", ""))
                company = _sanitize_str(row.get("company", ""))
                if not title or not company:
                    continue
                job_id = make_job_id(title, company)
                if job_id not in all_jobs:
                    source = _sanitize_str(row.get("site", "")) or "unknown"
                    all_jobs[job_id] = RawJob(
                        id=job_id,
                        title=title,
                        company=company,
                        source=source,
                        job_url=_or_none(row.get("job_url")),
                        location=_or_none(row.get("location")),
                        description=_or_none(row.get("description")),
                        job_type=_or_none(row.get("job_type")),
                        date_posted=_or_none(row.get("date_posted")),
                        search_term_used=term or None,
                        remote_type=_to_remote_type(row.get("is_remote")),
                        min_amount=_float_or_none(row.get("min_amount")),
                        max_amount=_float_or_none(row.get("max_amount")),
                        currency=_or_none(row.get("currency")),
                        interval=_or_none(row.get("interval")),
                        salary_source=_or_none(row.get("salary_source")),
                        company_url=_or_none(row.get("company_url")),
                        company_industry=_or_none(row.get("company_industry")),
                        company_employees_label=_or_none(row.get("company_num_employees")),
                        company_revenue_label=_or_none(row.get("company_revenue")),
                        company_logo=_or_none(row.get("company_logo")),
                        job_level=_or_none(row.get("job_level")),
                        job_function=_or_none(row.get("job_function")),
                        emails=(
                            [e.strip() for e in row["emails"].split(",") if e.strip()] if row.get("emails") else None
                        ),
                    )
            print(f"   Found {len(results)} results ({len(all_jobs)} unique total)")
        except Exception as e:
            print(f"   Error: {e}")

        if site == "linkedin":
            time.sleep(LINKEDIN_DELAY_SECS)

    return list(all_jobs.values())


if __name__ == "__main__":
    jobs = run_scraper()
    for j in jobs[:5]:
        print(f"\n{j.title} @ {j.company} ({j.location})")
        print(f"  URL: {j.job_url}")
