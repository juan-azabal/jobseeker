"""
Scraper module: wraps JobSpy to fetch jobs from multiple boards.
Returns a list of standardized job dicts.
"""

import re
import yaml
import hashlib
from jobspy import scrape_jobs


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
    s = re.sub(r'\s*\([fmhwd/]+\)\s*$', '', s)
    s = re.sub(r'\s*\(all\s+genders?\)\s*$', '', s)
    # Strip common legal entity suffixes from company names
    for suffix in [', inc.', ', inc', ' inc.', ' inc',
                   ', ltd', ' ltd', ', s.l.', ' s.l.',
                   ', s.a.', ' s.a.', ', gmbh', ' gmbh',
                   ', b.v.', ' b.v.', ', llc.', ' llc.',
                   ', llc', ' llc', ', corp.', ' corp.',
                   ', corp', ' corp', ', ag', ' ag']:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    # Replace all punctuation with spaces, then collapse whitespace
    s = re.sub(r'[^\w\s]', ' ', s)
    s = ' '.join(s.split())
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


def run_scraper(config_path="config/searches.yaml"):
    config = load_search_config(config_path)
    country = config.get("country_indeed", "Spain")
    is_remote = config.get("is_remote", False)

    all_jobs = {}  # keyed by job_id for dedup

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
                title = str(row.get("title", "")).strip()
                company = str(row.get("company", "")).strip()
                loc = str(row.get("location", "")).strip()

                if not title or not company:
                    continue

                job_id = make_job_id(title, company)

                if job_id not in all_jobs:
                    all_jobs[job_id] = {
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "description": str(row.get("description", "")),
                        "job_url": str(row.get("job_url", "")),
                        "date_posted": str(row.get("date_posted", "")),
                        "job_type": str(row.get("job_type", "")),
                        "is_remote": bool(row.get("is_remote", False)),
                        "min_amount": row.get("min_amount"),
                        "max_amount": row.get("max_amount"),
                        "currency": str(row.get("currency", "")),
                        "interval": str(row.get("interval", "")),
                        "site": str(row.get("site", "")),
                        "search_term_used": term,
                    }

            print(f"   Found {len(results)} results ({len(all_jobs)} unique total)")

        except Exception as e:
            print(f"   Error: {e}")
            continue

    jobs_list = list(all_jobs.values())
    print(f"\nTotal unique jobs scraped: {len(jobs_list)}")
    return jobs_list


if __name__ == "__main__":
    jobs = run_scraper()
    for j in jobs[:5]:
        print(f"\n{j['title']} @ {j['company']} ({j['location']})")
        print(f"  URL: {j['job_url']}")
