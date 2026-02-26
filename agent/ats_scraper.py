"""
ATS Direct Scraper: polls Greenhouse, Lever, and Ashby public APIs.
No auth required. Returns list[RawJob].
"""

import yaml
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper import make_job_id
from models import RawJob


def load_watchlist(path="config/watchlist.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _fetch_greenhouse(token, company_name, title_patterns) -> list[RawJob]:
    """Fetch all jobs from a Greenhouse board, filter by title. Returns list[RawJob]."""
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

        loc = j.get("location", {}).get("name", "") or None
        content = j.get("content", "") or None

        # departments: list of {id, name, ...} dicts → list[str] of names
        raw_depts = j.get("departments") or []
        dept_names = [d["name"] for d in raw_depts if isinstance(d, dict) and d.get("name")]
        departments = dept_names if dept_names else None

        is_remote = "remote" in (loc or "").lower() or "remote" in title.lower()
        remote_type = "fulltime" if is_remote else "no"

        jobs.append(RawJob(
            id=make_job_id(title, company_name),
            title=title,
            company=company_name,
            source="greenhouse",
            location=loc,
            description=content,
            job_url=j.get("absolute_url") or None,
            date_posted=j.get("updated_at") or None,
            search_term_used=f"watchlist:{token}",
            remote_type=remote_type,
            departments=departments,
        ))

    return jobs


def _fetch_lever(token, company_name, title_patterns) -> list[RawJob]:
    """Fetch all jobs from a Lever postings page. Returns list[RawJob]."""
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

        cats = j.get("categories", {}) or {}
        loc = cats.get("location", "") or None
        # Lever doesn't include description in list
        desc_plain = j.get("descriptionPlain", "") or ""
        lists_text = ""
        for lst in j.get("lists", []):
            lists_text += lst.get("text", "") + "\n"
            lists_text += "\n".join(lst.get("content", "")) + "\n"
        description = (desc_plain + "\n" + lists_text).strip() or None

        # departments from categories.department; team from categories.team
        dept = cats.get("department")
        departments = [dept] if dept else None
        team = cats.get("team") or None

        is_remote = "remote" in (loc or "").lower()
        remote_type = "fulltime" if is_remote else "no"

        jobs.append(RawJob(
            id=make_job_id(title, company_name),
            title=title,
            company=company_name,
            source="lever",
            location=loc,
            description=description,
            job_url=j.get("hostedUrl") or None,
            job_type=cats.get("commitment") or None,
            search_term_used=f"watchlist:{token}",
            remote_type=remote_type,
            departments=departments,
            team=team,
        ))

    return jobs


def _fetch_ashby(token, company_name, title_patterns) -> list[RawJob]:
    """Fetch all jobs from an Ashby job board. Returns list[RawJob]."""
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
        loc = loc or None

        desc = (j.get("descriptionHtml", "") or j.get("descriptionPlain", "")) or None

        # department and team from top-level Ashby fields
        dept = j.get("department") or None
        departments = [dept] if dept else None
        team = j.get("team") or None

        is_remote = "remote" in (loc or "").lower()
        remote_type = "fulltime" if is_remote else "no"

        jobs.append(RawJob(
            id=make_job_id(title, company_name),
            title=title,
            company=company_name,
            source="ashby",
            location=loc,
            description=desc,
            job_url=j.get("jobUrl") or j.get("applyUrl") or None,
            date_posted=j.get("publishedAt") or None,
            job_type=j.get("employmentType") or None,
            search_term_used=f"watchlist:{token}",
            remote_type=remote_type,
            departments=departments,
            team=team,
        ))

    return jobs


def run_watchlist_scraper(config_path="config/watchlist.yaml") -> list[RawJob]:
    """Poll all ATS in watchlist concurrently. Returns list[RawJob]."""
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

    all_jobs: dict[str, RawJob] = {}
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
                    if j.id not in all_jobs:
                        all_jobs[j.id] = j
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
        print(f"\n{j.title} @ {j.company} ({j.location})")
        print(f"  {j.job_url}")
