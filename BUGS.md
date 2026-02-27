# BUGS.md — Known Issues, Workarounds, Deferred Edge Cases

## Active

*(none)*

## Deferred Edge Cases

### DE-1 — Eligibility penalty: parser-derived restriction field
**Source**: Phase 19 (19.1.1)
**Description**: `remote_restriction` is extracted by the LLM parser from job descriptions. If the parser fails to detect a country restriction (hallucination, unusual phrasing, or very long JD), the penalty won't fire.
**Impact**: Low — false negatives result in over-scoring ineligible jobs (same as pre-Phase-19 behavior).
**Path to fix**: Phase N — add parser confidence scoring; require `remote_restriction` confidence ≥ threshold before applying penalty.

### DE-2 — Region matching: substring sensitivity
**Source**: Phase 19 (19.1.1, 19.5.3)
**Description**: Eligibility checks use substring matching on `restriction.lower()`. Unusual phrasings like "must work from within the European Union" may not match the "eu " or "eu/" aliases.
**Impact**: Low — standard phrasings ("EU only", "Europe only", "EMEA") are covered.
**Path to fix**: Expand `_REGION_ALIASES` dict or use regex word-boundary matching.

### DE-3 — `remote_restriction` not a DB column
**Source**: Phase 19 (scoring parity postmortem, 2026-02-26)
**Description**: `remote_restriction` is computed via `json_extract()` in `get_jobs()` CTE but not stored as a real column. `get_job_by_id()` uses `SELECT *` — no `remote_restriction` column — so it must be injected from the `parsed` JSON blob after fetch.
**Impact**: Engineering debt only; scoring is correct (value comes from parsed JSON either way).
**Path to fix**: Migration to add `remote_restriction TEXT` column; backfill from `json_extract(parsed, '$.remote_restriction')`.

### DE-4 — Eligibility penalty: `loc_pref="d"` edge case
**Source**: Phase 19 (19.1.1)
**Description**: Users with `location_preference="d"` (anywhere in Europe) bypass the eligibility penalty. However, the location block still gives +8 (eligible) or +2 (ineligible) based on restriction text. For `loc_pref="d"` users, the location bonus should always be +10 (no restriction) since they opted into cross-border.
**Impact**: Low — `loc_pref="d"` users currently get +8 for EU-restricted jobs (2 pts below maximum) but no penalty.
**Path to fix**: Short-circuit `_is_geo_restricted_remote = False` when `loc_pref == "d"`.

## Resolved

### RP-1 — Timezone-only restrictions triggered eligibility penalty (2026-02-27)
**Fixed in**: 19.5.3 commit `2137ba6`
`api/scoring.py _compute_eligibility_penalty()` and `_is_geo_restricted_remote` lacked `is_pure_timezone()` check. "CET timezone hours" was treated as a country restriction: +2 location (ineligible) and -20 penalty. Fixed by adding `is_pure_timezone()` guard in both.

### RP-2 — Agent location block missed `_HOME_REGIONS` check for eligibility (2026-02-27)
**Fixed in**: 19.5.3 commit `2137ba6`
`_heuristic_score()` in `agent/main.py` only checked `"europe" in restriction_lower` but not the full `_HOME_REGIONS` list. "EU only" gave `_user_eligible=False` for Barcelona users → +2 location instead of +8. Fixed by mirroring the API's `any(r.lower() in restriction_lower for r in home_regions)` check.
