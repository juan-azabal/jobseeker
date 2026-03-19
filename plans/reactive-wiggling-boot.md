# Scraper Health Monitoring — Implementation Spec

## Context

Scrapers (JobSpy/Indeed/LinkedIn, ATS/Greenhouse/Lever/Ashby, WTTJ/Algolia) can silently break: 0 results, HTTP errors, schema drift (stub descriptions). Currently the only signal is "user gets empty digest." This feature detects degradation post-scrape and alerts via PostHog, GHA annotations, and email before users notice.

Strategic plan: `plans/plan.md`. This spec implements the MVP scope.

## Key Architecture Insight

`_unified_scrape()` in `main.py:55-88` runs **once** across all profiles before the per-profile loop. This simplifies the plan's "two-phase" design: metadata collection happens once after `_unified_scrape()`, not per-profile. The plan's D7 (aggregate across profiles) is inherently satisfied because scraping is already unified.

## Files

| Action | File | Purpose |
|--------|------|---------|
| Create | `agent/scraper_health.py` | Core module: dataclasses, collection, evaluation, alerts, GHA formatting |
| Create | `agent/templates/scraper_health_alert.html.j2` | Simple ops alert email template |
| Create | `agent/tests/test_scraper_health.py` | Unit tests (~35 tests) |
| Modify | `agent/main.py` | Wire health check after `_unified_scrape()`, alerts after profile loop, exit code |
| Modify | `agent/notifier.py` | Extract `send_smtp()` helper for reuse |

## Data Structures

### ScraperMeta (per-source raw metrics)

```python
@dataclass
class ScraperMeta:
    source: str                  # "indeed", "linkedin", "wttj", "greenhouse", "lever", "ashby"
    job_count: int
    error: str | None            # exception message if scraper failed
    has_description_pct: float   # fraction with non-empty description
    median_desc_length: int      # median len(description) for non-empty
    has_location_pct: float      # fraction with non-empty location
    has_company_pct: float       # fraction with non-empty company
```

### SourceHealth (evaluated verdict for one source)

```python
@dataclass
class SourceHealth:
    source: str
    verdict: str                 # "ok" | "warning" | "critical"
    job_count: int
    reasons: list[str]           # human-readable diagnostics
```

### HealthReport (overall)

```python
@dataclass
class HealthReport:
    sources: list[SourceHealth]
    overall: str                 # "ok" | "warning" | "critical"
    timestamp: str               # ISO
```

### Thresholds (constants dict in scraper_health.py)

```python
THRESHOLDS = {
    "indeed":     {"min_jobs": 3, "min_desc_pct": 0.5, "min_desc_len": 100},
    "linkedin":   {"min_jobs": 3, "min_desc_pct": 0.5, "min_desc_len": 100},
    "wttj":       {"min_jobs": 3, "min_desc_pct": 0.7, "min_desc_len": 100},
    "greenhouse": {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
    "lever":      {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
    "ashby":      {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
}
```

## Evaluation Rules

1. `error is not None` → CRITICAL (diagnostic: the error message)
2. `job_count == 0` → CRITICAL (diagnostic: "zero_results")
3. `job_count < min_jobs` → WARNING (diagnostic: "low_count")
4. `has_description_pct < min_desc_pct` → WARNING (diagnostic: "schema_drift")
5. `median_desc_length < min_desc_len` → WARNING (diagnostic: "schema_drift")
6. Two+ warnings on same source → escalate to CRITICAL
7. Overall = worst across all sources

## Phases

### Phase 1: ScraperMeta collection + evaluation (2 files created)

**Create `agent/scraper_health.py`** (~200 lines):
- `ScraperMeta`, `SourceHealth`, `HealthReport` dataclasses
- `THRESHOLDS` dict
- `collect_source_meta(raw_jobs: list[RawJob], errors: dict[str, str]) -> list[ScraperMeta]`
  - Groups `raw_jobs` by `source` field, computes stats per group
  - Adds entries for sources in `errors` dict that had 0 jobs (scraper failed entirely)
- `evaluate_health(metas: list[ScraperMeta]) -> HealthReport`
  - Applies threshold rules per source, returns report
- `format_gha_annotations(report: HealthReport) -> list[str]`
  - Returns `::warning::` / `::error::` strings for GHA
- `health_report_to_dict(report: HealthReport) -> dict`
  - Serializes for PostHog/structlog

**Create `agent/tests/test_scraper_health.py`** (~30 tests):
- Collection: mixed sources, empty list, field completeness, median edge cases
- Evaluation: error→critical, zero→critical, low_count→warning, schema_drift→warning, two warnings→critical, all ok
- GHA annotations: warning/error formatting, ok produces nothing
- Serialization: round-trip dict

### Phase 2: SMTP extraction from notifier.py (1 file modified)

**Modify `agent/notifier.py`**:
- Extract `send_smtp(to: str, subject: str, html_body: str) -> bool` from lines 179-235
  - Reads `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` from env
  - TLS on smtp.gmail.com:587
  - Returns bool, never raises
- Refactor `send_digest()` to call `send_smtp()` internally
- **All existing notifier tests must pass unchanged**

### Phase 3: Alert email + wiring in main.py (3 files modified/created)

**Create `agent/templates/scraper_health_alert.html.j2`**:
- Simple HTML table: source | verdict | job_count | reasons
- Subject: `"Scraper Health Alert: {n_critical} critical, {n_warning} warning"`
- Minimal styling (ops alert, not user-facing)

**Modify `agent/scraper_health.py`** — add:
- `send_health_alert(report: HealthReport) -> bool`
  - Imports `send_smtp` from notifier
  - Recipient: `ADMIN_EMAIL` env var, fallback to `NOTIFY_EMAIL`
  - Renders template with Jinja2, calls `send_smtp()`
  - Returns False if all OK (nothing to send), or on any failure
  - Never raises

**Modify `agent/main.py`**:

1. Capture scraper errors in `_unified_scrape()`:
   ```python
   scrape_errors: dict[str, str] = {}
   # In existing try/except blocks, add:
   # scrape_errors["ats"] = str(e)
   # scrape_errors["wttj"] = str(e)
   ```
   Return signature changes to `tuple[list[dict], int, list[RawJob], dict[str, str]]`

2. After `_unified_scrape()`, before profile loop (line ~139):
   ```python
   from scraper_health import collect_source_meta, evaluate_health, ...
   metas = collect_source_meta(raw_jobs, scrape_errors)
   health_report = evaluate_health(metas)
   # structlog + PostHog
   ```

3. After profile loop (after line ~161):
   ```python
   # GHA annotations
   for line in format_gha_annotations(health_report):
       print(line)
   # Email alert (best-effort)
   if health_report.overall != "ok":
       send_health_alert(health_report)
   # Exit code: only if ALL sources critical
   if all(s.verdict == "critical" for s in health_report.sources):
       sys.exit(1)
   ```

4. Wrap health logic in try/except so health module failure never breaks pipeline.

**Add tests** to `agent/tests/test_scraper_health.py`:
- `send_health_alert` renders template and calls `send_smtp` (mock smtp)
- `send_health_alert` skips when all OK
- `send_health_alert` returns False on missing env vars

### Phase 4: PostHog events + docs (2 files)

**Modify `agent/main.py`**:
- Emit `scraper_health_check` PostHog event with serialized report (using existing `_capture` pattern from `pipeline.py`)

**Update docs** (GATE):
- `agent/CLAUDE.md`: add `scraper_health.py` to project structure, update architecture
- Project `CLAUDE.md`: update project state
- `INVARIANTS.md`: add `ADMIN_EMAIL` env var note
- `docs/env-vars.md`: add `ADMIN_EMAIL`

## New Env Var

- `ADMIN_EMAIL` — recipient for ops alerts. Optional. Falls back to `NOTIFY_EMAIL`.

## Reused Patterns

- **parse_quality.py** (`agent/parse_quality.py`): same pattern — pure metrics module, fixed thresholds, dict output. Follow this structure.
- **PostHog capture** (`agent/pipeline.py:45-66`): `_capture(profile_id, event_name, props)` with graceful no-op.
- **structlog** (`agent/pipeline.py`): `logger = structlog.get_logger(__name__)`, JSON in CI.
- **notifier.py SMTP** (`agent/notifier.py:179-235`): Gmail TLS pattern to extract.

## Verification

1. `cd agent && pytest tests/` — all existing 625+ tests pass
2. `pytest tests/test_scraper_health.py` — new tests pass (~35)
3. Manual: `python main.py --profile 1` with `POSTHOG_API_KEY` set → check PostHog for `scraper_health_check` event
4. Manual: temporarily set a threshold impossibly high → verify GHA annotation output and email
5. Verify: if `scraper_health.py` import fails, pipeline still runs (try/except in main.py)
