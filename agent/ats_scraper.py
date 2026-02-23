"""
ATS Direct Scraper: polls Greenhouse, Lever, and Ashby public APIs.
No auth required. Returns standardized job dicts compatible with pipeline.
"""

import yaml
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper import make_job_id


def load_watchlist(path="config/watchlist.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _fetch_greenhouse(token, company_name, title_patterns):
    """Fetch all jobs from a Greenhouse board, filter by title."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   {company_name} (Greenhouse): error - {e}")
        return []

    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not any(p in title.lower() for p in title_patterns):
            continue

        loc = j.get("location", {}).get("name", "")
        content = j.get("content", "")

        jobs.append({
            "id": make_job_id(title, company_name, loc),
            "title": title,
            "company": company_name,
            "location": loc,
            "description": content,
            "job_url": j.get("absolute_url", ""),
            "date_posted": j.get("updated_at", ""),
            "job_type": "",
            "is_remote": "remote" in loc.lower() or "remote" in title.lower(),
            "min_amount": None,
            "max_amount": None,
            "currency": "",
            "interval": "",
            "site": "greenhouse",
            "search_term_used": f"watchlist:{token}",
        })

    return jobs


def _fetch_lever(token, company_name, title_patterns):
    """Fetch all jobs from a Lever postings page."""
    url = f"https://api.lever.co/v0/postings/{token}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   {company_name} (Lever): error - {e}")
        return []

    jobs = []
    for j in data:
        title = j.get("text", "")
        if not any(p in title.lower() for p in title_patterns):
            continue

        loc = j.get("categories", {}).get("location", "")
        # Lever doesn't include description in list, need individual fetch
        desc_plain = j.get("descriptionPlain", "")
        lists_text = ""
        for lst in j.get("lists", []):
            lists_text += lst.get("text", "") + "\n"
            lists_text += "\n".join(lst.get("content", "")) + "\n"

        jobs.append({
            "id": make_job_id(title, company_name, loc),
            "title": title,
            "company": company_name,
            "location": loc,
            "description": desc_plain + "\n" + lists_text,
            "job_url": j.get("hostedUrl", ""),
            "date_posted": "",
            "job_type": j.get("categories", {}).get("commitment", ""),
            "is_remote": "remote" in loc.lower(),
            "min_amount": None,
            "max_amount": None,
            "currency": "",
            "interval": "",
            "site": "lever",
            "search_term_used": f"watchlist:{token}",
        })

    return jobs


def _fetch_ashby(token, company_name, title_patterns):
    """Fetch all jobs from an Ashby job board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   {company_name} (Ashby): error - {e}")
        return []

    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not any(p in title.lower() for p in title_patterns):
            continue

        loc = j.get("location", "")
        if isinstance(loc, dict):
            loc = loc.get("name", "")

        desc = j.get("descriptionHtml", "") or j.get("descriptionPlain", "")

        jobs.append({
            "id": make_job_id(title, company_name, loc),
            "title": title,
            "company": company_name,
            "location": loc,
            "description": desc,
            "job_url": j.get("jobUrl", j.get("applyUrl", "")),
            "date_posted": j.get("publishedAt", ""),
            "job_type": j.get("employmentType", ""),
            "is_remote": "remote" in (loc or "").lower(),
            "min_amount": None,
            "max_amount": None,
            "currency": "",
            "interval": "",
            "site": "ashby",
            "search_term_used": f"watchlist:{token}",
        })

    return jobs


def run_watchlist_scraper(config_path="config/watchlist.yaml"):
    """Poll all ATS in watchlist concurrently. Returns list of job dicts."""
    config = load_watchlist(config_path)
    title_patterns = [p.lower() for p in config.get("title_patterns", ["product manager"])]

    tasks = []
    for company in (config.get("greenhouse") or []):
        tasks.append(("greenhouse", company["token"], company["name"]))
    for company in (config.get("lever") or []):
        tasks.append(("lever", company["token"], company["name"]))
    for company in (config.get("ashby") or []):
        tasks.append(("ashby", company["token"], company["name"]))

    print(f"\nPolling {len(tasks)} ATS boards...")

    all_jobs = {}
    fetchers = {
        "greenhouse": _fetch_greenhouse,
        "lever": _fetch_lever,
        "ashby": _fetch_ashby,
    }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for ats, token, name in tasks:
            f = executor.submit(fetchers[ats], token, name, title_patterns)
            futures[f] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                jobs = future.result()
                for j in jobs:
                    if j["id"] not in all_jobs:
                        all_jobs[j["id"]] = j
                if jobs:
                    print(f"   {name}: {len(jobs)} PM roles found")
            except Exception as e:
                print(f"   {name}: error - {e}")

    jobs_list = list(all_jobs.values())
    print(f"Watchlist total: {len(jobs_list)} PM roles across {len(tasks)} companies")
    return jobs_list


if __name__ == "__main__":
    jobs = run_watchlist_scraper()
    for j in jobs:
        print(f"\n{j['title']} @ {j['company']} ({j['location']})")
        print(f"  {j['job_url']}")
