# Phase R2 — Split scoring_core.py + Trim pipeline.py

**Status:** Pending approval
**Prerequisite:** Phase R (PR #31) merged to main

## Problem

Three files currently exceed CLAUDE.md hard limits after Phase R:

| File | Lines | Limit | Violation |
|---|---|---|---|
| `shared/scoring_core.py` | 876 | 400 | +476 |
| `agent/pipeline.py` | 480 | 400 | +80 |
| `shared/scoring_core.py::heuristic_score()` | ~97 code lines | 50 | +47 |
| `agent/pipeline.py::run_pipeline()` | ~70 code lines | 50 | +20 |

---

## Part 1: Split `shared/scoring_core.py` (876L → 4 files ≤ 400L each)

### Why it's large

`DOMAIN_KEYWORDS` alone is 303 lines of pure data (keyword lists per domain). The rest is scoring logic (~570 lines). These are fundamentally different concerns — data vs. functions.

### Proposed split

#### `shared/_data.py` (~400L) — pure constants, no logic
```
DOMAIN_ALIASES    (48L)   — profile domain name → canonical enum
VALID_DOMAINS     (35L)   — frozenset of 30 canonical enum values
DOMAIN_KEYWORDS   (303L)  — per-domain keyword lists (the bulk)
GRADE_POINTS      (5L)    — {A: 20, B: 12, C: 5}
```
No imports from within `shared/`. Zero functions.

#### `shared/_geo.py` (~185L) — location/eligibility logic
```
_build_tz_abbreviations()  (20L)
_TZ_TERMS                  (5L)
is_pure_timezone()         (15L)
_CITY_TO_COUNTRY           (76L)  — city → ISO country code map
_REGION_ALIASES            (9L)   — "europe" → ["spain", "france", ...]
compute_eligibility_penalty()  (80L)
```
Imports from `shared/_data` only.

#### `shared/_heuristic.py` (~280L) — scoring functions
```
_LANG_SIGNALS     (18L)  — language detection keyword lists
_NULL_FLAG        (4L)   — sentinel values for empty red_flags
infer_domain()    (27L)
grade_to_points() (10L)

# Extracted from heuristic_score() — see Part 2:
_score_domain()        (~12L)
_check_geo_eligibility()  (~22L)
_score_location()      (~32L)
_score_country()       (~12L)
_score_language()      (~18L)
_score_company_type()  (~8L)
_score_red_flags()     (~6L)

heuristic_score()  (~30L after extraction)
```
Imports from `shared/_data` and `shared/_geo`.

#### `shared/scoring_core.py` (~30L) — thin re-export facade (NO LOGIC)
```python
from shared._data import (
    DOMAIN_ALIASES, VALID_DOMAINS, DOMAIN_KEYWORDS, GRADE_POINTS,
)
from shared._geo import (
    is_pure_timezone, compute_eligibility_penalty,
)
from shared._heuristic import (
    infer_domain, grade_to_points, heuristic_score,
)

__all__ = [
    "DOMAIN_ALIASES", "VALID_DOMAINS", "DOMAIN_KEYWORDS", "GRADE_POINTS",
    "is_pure_timezone", "compute_eligibility_penalty",
    "infer_domain", "grade_to_points", "heuristic_score",
]
```
All 6 consumers (`api/scoring.py`, `agent/scoring.py`, `agent/display.py`,
`agent/notifier.py`, `api/grade_mapping.py`, tests) import from
`shared.scoring_core` — **zero import changes needed in consumers**.

---

## Part 2: Extract sub-functions from `heuristic_score()` (97 code lines → ≤50)

`heuristic_score()` has 8 discrete scoring dimensions. Each becomes a
private helper in `shared/_heuristic.py`:

### `_score_domain(profile, parsed, domain_override) -> int`
- Lines 744–751 of current file
- Returns 0–15 domain score; skips cascade when `domain_override` is set
- ~12 lines

### `_check_geo_eligibility(loc_type, remote_restriction, home_locations, home_regions) -> tuple[bool, bool]`
- Lines 767–786 of current file
- Returns `(is_geo_restricted, user_eligible)`
- Moves the `_is_geo_restricted` + `_user_eligible` block out of main body
- ~22 lines

### `_score_location(loc_pref, loc_type, job_loc, home_locations, home_regions, is_geo_restricted, user_eligible) -> int`
- Lines 793–819 of current file (the `loc_pref` if/elif ladder)
- Returns 0–10; inner `_remote_loc_pts()` inlined here
- ~32 lines

### `_score_country(country_weights, parsed, loc_type, is_geo_restricted) -> int`
- Lines 821–830 of current file
- Returns ±10 country bonus
- ~12 lines

### `_score_language(languages, parsed, job) -> int`
- Lines 832–853 of current file
- Returns 0–10 language bonus
- ~18 lines

### `_score_company_type(company_type_weights, parsed) -> int`
- Lines 855–861 of current file
- Returns ±15 company type score
- ~8 lines

### `_score_red_flags(parsed) -> int`
- Lines 863–865 of current file
- Returns 0 to -15
- ~6 lines

### `heuristic_score()` after extraction (~30L)
```python
def heuristic_score(profile, parsed, job, is_reloc=False, domain_override=None, skill_score=0) -> int:
    if not parsed:
        return 0
    score = 0
    score += _score_domain(profile, parsed, domain_override)
    score += (profile.get("seniority") or {}).get(parsed.get("seniority", "unknown"), 0)
    score += skill_score
    is_geo_restricted, user_eligible = _check_geo_eligibility(
        parsed.get("location_type"), parsed.get("remote_restriction") or "",
        profile.get("home_locations") or [], profile.get("home_regions") or [],
    )
    score += _score_location(
        (profile.get("location_preference") or "b").lower(),
        parsed.get("location_type", "unknown"),
        (job.get("location") or "").lower(),
        profile.get("home_locations") or [],
        profile.get("home_regions") or [],
        is_geo_restricted, user_eligible,
    )
    score += _score_country(profile.get("country_weights") or {}, parsed,
                            parsed.get("location_type"), is_geo_restricted)
    score += _score_language(profile.get("languages") or [], parsed, job)
    score += _score_company_type(profile.get("company_type_weights") or {}, parsed)
    score -= _score_red_flags(parsed)
    score += compute_eligibility_penalty(
        home_locations=profile.get("home_locations") or [],
        home_regions=profile.get("home_regions") or [],
        location_preference=(profile.get("location_preference") or "b").lower(),
        parsed=parsed, job=job,
    )
    return max(0, min(100, score))
```

---

## Part 3: Trim `agent/pipeline.py` (480L → ≤400L)

`pipeline.py` is 80 lines over budget. The excess is in two places:

### Option A: Extract `_pipeline_io.py` (~120L)
Move the I/O helpers that have no pipeline logic dependency:
- `_to_dicts()` (4L)
- `_append_seen_ids()` (13L)
- `save_results()` (17L)
- `_capture()` (20L)
- `_sync_to_railway()` (30L)
- `_send_digest()` (43L)

Leaves `pipeline.py` at ~360L. `run_pipeline()` stays in `pipeline.py` and
imports from `_pipeline_io`.

### Option B: Extract `_pipeline_notify.py` (~80L)
Move only the outbound I/O:
- `_sync_to_railway()` (30L)
- `_send_digest()` (43L)
- `_log_completion()` (27L)

Leaves `pipeline.py` at ~400L exactly.

**Recommendation: Option B** — narrower change, stays under 400L, keeps related
steps together.

### Also: trim `run_pipeline()` (70 code lines → ≤50)

Extract the 3 optional early-exit branches into named helpers already
called in the function; they are already named `_early_exit()`. The main
loop steps (1–12) can be grouped into 3 phases:
- `_run_scrape_phase()` → Steps 1–3 (~20L)
- `_run_parse_score_phase()` → Steps 4–7 (~20L)
- `_run_output_phase()` → Steps 8–12 (~15L)

This reduces `run_pipeline()` to ~40L of orchestration.

---

## Execution Order

1. **Step R2.1** — Split `shared/scoring_core.py` into `_data.py` + `_geo.py` + `_heuristic.py` + facade
   - Interface first: write `scoring_core.py` facade with correct `__all__`
   - Test: `pytest tests/test_shared_scoring_core.py` must pass before touching consumers
   - Max files touched: 4 (`_data.py` NEW, `_geo.py` NEW, `_heuristic.py` NEW, `scoring_core.py` REWRITE)

2. **Step R2.2** — Extract sub-functions from `heuristic_score()` (lives in `_heuristic.py` after R2.1)
   - One sub-function at a time, re-run tests after each
   - All tests must pass before moving to next dimension
   - Max files touched: 1 (`shared/_heuristic.py`)

3. **Step R2.3** — Trim `agent/pipeline.py` (Option B: extract `_pipeline_notify.py`)
   - Move `_sync_to_railway`, `_send_digest`, `_log_completion` to new file
   - Update imports in `pipeline.py`
   - Max files touched: 2 (`pipeline.py` + `_pipeline_notify.py` NEW)

4. **Step R2.4** — Extract `run_pipeline()` phase helpers
   - Max files touched: 1 (`pipeline.py`)

Each step is one commit. Gate: all tests pass after every step.

---

## Risk assessment

**Low risk:**
- `scoring_core.py` split: pure refactor, zero logic changes. All consumers
  import from the facade — no import-path changes needed.
- Sub-function extraction: pure mechanical refactor. Each sub-function has
  clear I/O (no hidden shared state except `_CITY_TO_COUNTRY` which stays
  in `_geo.py`).

**Medium risk:**
- `pipeline.py` split: `_sync_to_railway` and `_send_digest` interact with
  env vars and external services. Tests for these (`test_sync_railway.py`)
  exist and cover the main paths.

**Not a risk:**
- Consumer imports: `shared.scoring_core` facade guarantees no consumer
  needs to change its import path.
