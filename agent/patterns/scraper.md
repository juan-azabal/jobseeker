# Pattern: Scraper Module

## Contract

Every scraper module exports a function that returns `list[dict]`, where each dict is a raw job with the standard field set below. The function signature may accept a config path but must have sensible defaults.

## Standard Job Dict (raw, pre-filter)

```python
{
    "id":               str,   # deterministic 12-char hex — from make_job_id()
    "title":            str,
    "company":          str,
    "location":         str,   # raw string, may be empty
    "description":      str,   # full text, markdown preferred
    "job_url":          str,
    "date_posted":      str,   # ISO date or empty string
    "job_type":         str,   # "fulltime", "contract", etc., or empty
    "is_remote":        bool,
    "min_amount":       float | None,
    "max_amount":       float | None,
    "currency":         str,
    "interval":         str,   # "yearly", "monthly", etc.
    "site":             str,   # source identifier: "indeed", "greenhouse", "lever", etc.
    "search_term_used": str,
}
```

## Deduplication

**Always use `make_job_id()` from `scraper.py:16`. Never reimplement.**

```python
from scraper import make_job_id

job_id = make_job_id(title, company)  # location is optional, ignored for dedup
```

`make_job_id()` hashes `normalized_title|normalized_company` with MD5, returns first 12 hex chars. This is location-independent — the same role posted in two cities produces one ID.

## Existing Implementations

| Function | File | Source | Status |
|---|---|---|---|
| `run_scraper(config_path)` | `scraper.py` | JobSpy (Indeed, Google, LinkedIn) | Working |
| `run_watchlist_scraper(config_path)` | `ats_scraper.py` | Greenhouse, Lever, Ashby public APIs | Working |
| `run_wttj_scraper()` | `wttj_scraper.py` | Welcome to the Jungle (Algolia, app ID CSEKHVMS53) | Working |

## Adding a New Scraper

1. Create `{source}_scraper.py`
2. Import `make_job_id` from `scraper.py`
3. Export a function `run_{source}_scraper(...) -> list[dict]` returning standard job dicts
4. Register in `main.py` where jobs are collected (search for `run_scraper` and `run_watchlist_scraper` calls)
5. Update `CLAUDE.md` project structure and architecture diagram

## Invariants

- Job IDs are deterministic: same title+company always produces the same ID regardless of run or source
- Scrapers are independent: one failing does not block others (each wrapped in try/except in main.py)
- All scrapers run before prefilter — dedup happens at the collection stage
- Descriptions should be raw text or markdown; HTML is acceptable but less preferred
