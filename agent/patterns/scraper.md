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
    title_variants=list[str] | None,  # original titles when cross-geo variants merge; None for single-source jobs
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

`_normalize_for_id()` applies these transforms in order:
1. Lowercase + strip
2. Strip gender/diversity suffixes: `(f/m/d)`, `(h/f)`, `(all genders)`
3. Strip Greenhouse-style cross-geo suffix: `| Country/Region | WorkMode`
   — workmode whitelist: `remote|hybrid|onsite|on-site|office`
   — e.g. `"Senior PM | Canada | Remote"` → `"Senior PM"` (same ID as `"Senior PM | Spain | Remote"`)
4. Strip legal entity suffixes from company names: Inc., Ltd, GmbH, B.V., LLC, Corp, AG, S.L., S.A.
5. Replace remaining punctuation with spaces, collapse whitespace

## Existing Implementations

| Function | File | Source | Returns |
|---|---|---|---|
| `run_scraper(config_path)` | `scraper.py` | JobSpy (Indeed, Google, LinkedIn, Glassdoor) | `list[RawJob]` |
| `run_watchlist_scraper(config_path, target_countries)` | `ats_scraper.py` | Greenhouse, Lever, Ashby public APIs | `tuple[list[RawJob], int]` (jobs, geo_rejected_count) |
| `run_wttj_scraper(target_countries)` | `wttj_scraper.py` | Welcome to the Jungle (Algolia, app ID CSEKHVMS53) | `list[RawJob]` |
| `merge_jobs(jobs)` | `merger.py` | all scrapers combined | `list[RawJob]` |

## Pipeline wiring (main.py)

```python
all_raw: list[RawJob] = run_scraper(...)           # Step 1a
ats_jobs, ats_geo_rej = run_watchlist_scraper(...) # Step 1b — returns (jobs, geo_rejected_count)
all_raw.extend(ats_jobs)
all_raw.extend(run_wttj_scraper(...))               # Step 1c
raw_jobs: list[RawJob] = merge_jobs(all_raw)        # Step 1.5: dedup + field-group merge
jobs: list[dict] = _to_dicts(raw_jobs)             # shim: list[RawJob] → list[dict]
```

## Merger (merger.py)

`merge_jobs()` groups by job id and picks the richest data per field group:

```python
SOURCE_RANK = {
    "greenhouse": 1, "lever": 2, "ashby": 3,
    "wttj": 4, "linkedin": 5,
    "indeed": 6, "glassdoor": 7, "google": 8,
}
```

Field groups and their preferred source order:

| Group | Preferred sources (first = wins) |
|---|---|
| `description` | greenhouse, lever, ashby, linkedin, wttj, indeed, glassdoor, google |
| `salary` | wttj, indeed, glassdoor, linkedin, google, greenhouse, lever, ashby |
| `company_meta` | indeed, glassdoor, linkedin, wttj, greenhouse, lever, ashby, google |
| `job_level` | linkedin, indeed, wttj, greenhouse, lever, ashby, glassdoor, google |
| `remote_type` | wttj, linkedin, indeed, glassdoor, google, greenhouse, lever, ashby |
| `org_structure` | greenhouse, lever, ashby, wttj, linkedin, indeed, glassdoor, google |
| `location` | indeed, linkedin, glassdoor, google, wttj, greenhouse, lever, ashby |

Special rules:
- **description**: prefers longer plain text over HTML, then longer length
- **List fields** (`departments`, `locations_structured`, `emails`): union across all sources
- **`sources`**: list of all contributing source names, ordered by SOURCE_RANK
- **`title_variants`**: sorted list of all unique original titles from the merged group; None for single-source jobs. Populated explicitly, not via the field-group loop.

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
- Cross-geo Greenhouse variants (`"Senior PM | Canada | Remote"` / `"Senior PM | Spain | Remote"`) produce the same `job_id` and are merged into one record with `title_variants` preserving both originals
