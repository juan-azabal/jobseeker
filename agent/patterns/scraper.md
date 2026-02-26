# Pattern: Scraper Module

## Contract

Every scraper module exports a function that returns `list[RawJob]` (from `models.py`).
The merge in `main.py` converts to `list[dict]` via `_to_dicts()` before passing to downstream.

## RawJob (models.py)

```python
from models import RawJob

# Required fields
RawJob(id=str, title=str, company=str, source=str)

# Key optional fields
RawJob(
    # Core
    job_url=str | None,
    location=str | None,        # display string, may be None
    description=str | None,
    job_type=str | None,
    date_posted=str | None,
    search_term_used=str | None,
    # Remote
    remote_type=str | None,     # "fulltime" | "partial" | "no" | None
    # Structured location (WTTJ)
    country=str | None,         # ISO 2-letter code
    city=str | None,
    locations_structured=list[dict] | None,  # raw offices[]
    # Salary
    min_amount=float | None,
    max_amount=float | None,
    currency=str | None,
    interval=str | None,        # "yearly" | "monthly" | "hourly"
    salary_source=str | None,
    # Company metadata (JobSpy)
    company_url=str | None,
    company_industry=str | None,
    company_employees_label=str | None,  # from company_num_employees
    company_revenue_label=str | None,    # from company_revenue
    company_logo=str | None,
    # Role metadata (LinkedIn/JobSpy)
    job_level=str | None,
    job_function=str | None,
    # Experience (WTTJ)
    experience_min=int | None,
    experience_max=int | None,
    # Language (WTTJ)
    language=str | None,
    # Org structure (ATS)
    departments=list[str] | None,
    team=str | None,
    # Merge tracking
    sources=list[str],          # filled during merge; starts empty
    source_category=str | None,
)

# Computed property
job.is_remote  # bool: True when remote_type in ("fulltime", "partial")
```

## Deduplication

**Always use `make_job_id()` from `scraper.py`. Never reimplement.**

```python
from scraper import make_job_id

job_id = make_job_id(title, company)
```

`make_job_id()` hashes `normalized_title|normalized_company` with MD5, returns first 12 hex chars.
Normalization removes gender suffixes, legal entity suffixes, punctuation variants.

## Existing Implementations

| Function | File | Source | Returns |
|---|---|---|---|
| `run_scraper(config_path)` | `scraper.py` | JobSpy (Indeed, Google, LinkedIn, Glassdoor) | `list[RawJob]` |
| `run_watchlist_scraper(config_path)` | `ats_scraper.py` | Greenhouse, Lever, Ashby public APIs | `list[RawJob]` |
| `run_wttj_scraper(target_countries)` | `wttj_scraper.py` | Welcome to the Jungle (Algolia, app ID CSEKHVMS53) | `list[RawJob]` |

## Pipeline wiring (main.py)

```python
raw_jobs: list[RawJob] = run_scraper(...)      # Step 1a
ats_jobs: list[RawJob] = run_watchlist_scraper(...)  # Step 1b
wttj_jobs: list[RawJob] = run_wttj_scraper(...)  # Step 1c
# Merge by id (attribute access)
...
jobs: list[dict] = _to_dicts(raw_jobs)  # shim until Phase 2
```

## Adding a New Scraper

1. Create `{source}_scraper.py`
2. Import `make_job_id` from `scraper.py` and `RawJob` from `models.py`
3. Export `run_{source}_scraper(...) -> list[RawJob]`
4. Register in `main.py` Steps 1a-c
5. Update `CLAUDE.md` project structure

## Invariants

- Job IDs are deterministic: same title+company → same ID regardless of run or source
- Scrapers are independent: one failing does not block others (each wrapped in try/except in main.py)
- All scrapers run before prefilter — dedup happens at the collection stage
- Descriptions should be raw text or markdown; HTML is acceptable but less preferred
- `remote_type` replaces the old `is_remote` bool; `is_remote` is now a computed property
