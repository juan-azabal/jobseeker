# Pattern: Filter Module

## Contract

```python
prefilter_jobs(
    jobs: list[dict],
    config_path: str,           # path to preferences YAML (per-user or shared)
    applied_path: str,          # path to applied YAML (per-user)
    seen_path: str,             # path to seen_ids txt (per-user)
    home_locations: list[str] | None = None,
) -> tuple[list[dict], list[dict], dict]
```

Returns `(passed, rejected, stats)`.

- `passed`: jobs that cleared all filters — ready for parsing
- `rejected`: jobs that failed at least one filter — each has `job["reject_reason"]` set
- `stats`: dict of counts by rejection reason (see below)

**No API calls. Pure string matching.**

## Filter Chain (execution order)

Order matters — cheaper/higher-yield checks run first.

| Step | Check | Stat key | Notes |
|---|---|---|---|
| 0a | Already seen in previous digest (`seen_ids.txt`) | `already_seen` | Dedup across runs |
| 0b | Already applied (id or company match in `applied.yaml`) | `already_applied` | Manual tracking |
| 0b | Not interested (id or title match in `applied.yaml`) | `not_interested` | Manual tracking |
| 1 | Excluded company (from `preferences.yaml`) | `excluded_company` | e.g. Gartner, G2 |
| 2 | Deal breaker keyword in title or first 500 chars of description | `deal_breaker` | |
| 3a | Title lacks PM keyword | `no_pm_keyword` | From `title_must_contain_one_of` |
| 3b | Title contains excluded term | `title_excluded` | From `title_exclude` |
| 4 | US-only role (state abbreviations, visa signals, 401k) | `us_only` | Skipped if home location matches |
| 5 | Job aggregator company | `aggregator` | Jobgether, Crossover, Turing, Toptal, arc.dev |

## Stats Dict

```python
stats = {
    "total":            int,  # total jobs input
    "passed":           int,  # jobs that cleared all filters
    "already_seen":     int,
    "already_applied":  int,
    "not_interested":   int,
    "excluded_company": int,
    "deal_breaker":     int,
    "no_pm_keyword":    int,
    "title_excluded":   int,
    "us_only":          int,
    "aggregator":       int,
}
```

## Rejection Annotation

Every rejected job gets `job["reject_reason"]` set to a human-readable string before appending to the `rejected` list. Example: `"deal breaker: 'sales'"`, `"US-only role (no EU location)"`.

## Invariants

- Filter order is fixed and matters: steps execute in the order above, first match wins
- No API calls — this runs before any LLM step
- `prefilter_stats` (the returned `stats`) is passed through to `notifier.py` for the email footer
- Adding a new filter: insert at the appropriate position in the chain, add a new stat key, document it here
