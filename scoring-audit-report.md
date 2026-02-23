# Scoring Audit Report

## Summary
- Total items found: 26
- 🔴 Hardcoded-personal: 5
- 🟡 Calibration: 12
- 🟢 Generic: 9

## Detailed Findings

---

### Scoring Rubric (LLM prompt)

#### 1. Rubric assumes PM specialization
- **Category**: 🟢 Generic
- **File**: `agent/prompts/scoring-rubric.md` (line 15)
- **What it does**: Uses `{name}`, `{core_str}`, `{target_str}` placeholders interpolated from the user profile at runtime.
- **Why this category**: Fully profile-driven — `_build_scoring_prompt()` in `scorer.py` reads `target.domains` and `target.seniority` from the profile YAML to compute `core_str`, `adjacent_str`, `target_str`. Works for any profile.

#### 2. Rubric dimension weights (0-25, 0-20, 0-20, 0-20, 0-15)
- **Category**: 🟡 Calibration
- **File**: `agent/prompts/scoring-rubric.md` (lines 20-44)
- **What it does**: Domain fit gets 25 max, seniority 20, technical depth 20, profile evidence 20, strategic impact 15. These proportions are the same for all users.
- **Why this category**: Reasonable defaults but not all users value these dimensions equally. A career changer might weight strategic_impact higher than domain_fit.

#### 3. Rubric calibration guidance
- **Category**: 🟡 Calibration
- **File**: `agent/prompts/scoring-rubric.md` (line 69)
- **What it does**: "70+ means strong fit, apply. 50-69 means reasonable fit, worth exploring. Under 50 means weak fit, skip."
- **Why this category**: These thresholds are baked into the LLM prompt and influence how it assigns scores. They may not suit all users (e.g., a junior dev might want to apply at 50+).

#### 4. "EU or remote" in candidate context
- **Category**: 🔴 Hardcoded-personal
- **File**: `agent/prompts/scoring-rubric.md` (line 16)
- **What it does**: Hard-codes "EU or remote" as the target geography in the candidate context sent to the LLM.
- **Why this category**: Not derived from profile. A US-based user would get incorrect scoring context. Should be derived from `user.home_locations` or a new `target.geography` field.
- **Code snippet**: `Target: {target_str} PM, {core_str} roles, EU or remote.`

#### 5. "PM" role assumption in rubric
- **Category**: 🔴 Hardcoded-personal
- **File**: `agent/prompts/scoring-rubric.md` (line 15-16)
- **What it does**: The rubric says `{name} — experienced PM` and `{target_str} PM`. The word "PM" is hardcoded.
- **Why this category**: A software engineer user would get a rubric describing them as a PM. Needs a `target.role_type` or similar field.
- **Code snippet**: `{name} — experienced PM, specializing in {core_str}.`

---

### Scorer Module (scorer.py)

#### 6. Domain threshold for "core" vs "adjacent"
- **Category**: 🟡 Calibration
- **File**: `agent/scorer.py` (lines 49-52)
- **What it does**: Domains with weight >= 12 are "core", 6-11 are "adjacent". These thresholds determine what the LLM rubric says is a "direct match" vs "adjacent domain".
- **Why this category**: The 12/6 thresholds work with the current weight scale (0-15) but aren't documented or configurable. If a user uses a different weight scale, the classification breaks.
- **Code snippet**: `core_domains = [d for d, s in top_domains if s >= 12]`

#### 7. Seniority threshold for "target levels"
- **Category**: 🟡 Calibration
- **File**: `agent/scorer.py` (lines 54-56)
- **What it does**: Seniority levels with weight >= 10 become "target levels" in the rubric. Fallback is "Senior".
- **Why this category**: The >= 10 threshold is undocumented. Fallback "Senior" is a sensible default but could be wrong for a junior user.
- **Code snippet**: `target_levels = [l for l, s in top_levels if s >= 10]`

#### 8. Adjacent domain fallback
- **Category**: 🔴 Hardcoded-personal
- **File**: `agent/scorer.py` (line 52)
- **What it does**: When no adjacent domains are found (weight 6-11), falls back to `"SaaS, B2B"`.
- **Why this category**: "SaaS, B2B" is specific to Juan's profile. A healthcare PM would get an incorrect fallback.
- **Code snippet**: `adjacent_str = ", ".join(adjacent_domains) if adjacent_domains else "SaaS, B2B"`

---

### Heuristic Scoring (main.py)

#### 9. Heuristic score: domain weight mapping
- **Category**: 🟢 Generic
- **File**: `agent/main.py` (lines 89-98, 146-148)
- **What it does**: Reads `target.domains` dict from user profile (e.g., `data: 15, adtech: 15, ml: 12`). Maps parsed domain → profile weight.
- **Why this category**: Fully profile-driven. Each user's YAML defines their own domain weights.

#### 10. Heuristic score: seniority weight mapping
- **Category**: 🟢 Generic
- **File**: `agent/main.py` (lines 95, 151)
- **What it does**: Reads `target.seniority` dict from profile (e.g., `principal: 15, staff: 15, senior: 5`). Maps parsed seniority → weight.
- **Why this category**: Fully profile-driven.

#### 11. Heuristic score: location scoring (10/8/6 points)
- **Category**: 🟡 Calibration
- **File**: `agent/main.py` (lines 153-162)
- **What it does**: Remote (non-restricted) = 10 pts, hybrid in home city = 8 pts, onsite in home city = 6 pts.
- **Why this category**: Point values are hardcoded. A user who strongly prefers remote might want 15 pts for remote and 2 for onsite.

#### 12. Heuristic score: skill overlap (4 pts per match, max 30)
- **Category**: 🟡 Calibration
- **File**: `agent/main.py` (lines 164-172)
- **What it does**: Each matched skill from profile = 4 pts, capped at 30. Skills list from `profile.skills`.
- **Why this category**: The multiplier (4) and cap (30) are hardcoded. A user with many niche skills might want different tuning.

#### 13. Heuristic score: red flag penalty (-5 each, max -15)
- **Category**: 🟡 Calibration
- **File**: `agent/main.py` (line 175)
- **What it does**: Each red flag deducts 5 points, capped at -15 total.
- **Why this category**: Penalty values are reasonable defaults but hardcoded.

#### 14. Domain keyword override map
- **Category**: 🔴 Hardcoded-personal
- **File**: `agent/main.py` (lines 101-111)
- **What it does**: When the parser says domain is "other", this keyword map reclassifies to data/ml/adtech/saas based on JD text. Keywords include "Snowplow", "dbt", "header bidding", "Kafka".
- **Why this category**: The keyword lists are curated for Juan's domains of interest (data, adtech, ML). A fintech PM wouldn't have "fintech" detection keywords here. Should be derived from profile domains or moved to config.
- **Code snippet**: `_DOMAIN_KEYWORDS = {"data": ["data platform", "snowflake", ...], "adtech": ["programmatic", "header bidding", ...], ...}`

#### 15. Home locations fallback
- **Category**: 🔴 Hardcoded-personal
- **File**: `agent/main.py` (line 86)
- **What it does**: Module-level default `_HOME_LOCATIONS = ["barcelona", "madrid", "spain", "españa"]` — used before `_load_heuristic_config()` runs.
- **Why this category**: Hardcoded to Juan's cities. Would incorrectly score location for another user if `_load_heuristic_config` doesn't run. In practice this default is always overwritten, but it's still a trap.
- **Code snippet**: `_HOME_LOCATIONS = ["barcelona", "madrid", "spain", "españa"]`

---

### Tier Classification

#### 16. Tier thresholds (A >= 50, B >= 30, C < 30)
- **Category**: 🟡 Calibration
- **File**: `agent/main.py` (lines 350-352), `api/ingest.py` (lines 9-14)
- **What it does**: A (Apply) = score >= 50, B (Review) = 30-49, C (Skip) = < 30. Used in both agent digest and web app ingest.
- **Why this category**: These are reasonable defaults but should be per-user configurable. A conservative user might want A >= 70.

#### 17. Reloc filtering for non-A tiers
- **Category**: 🟢 Generic
- **File**: `agent/main.py` (lines 350-352)
- **What it does**: Relocation jobs only appear in Tier A. Tier B and C exclude jobs requiring relocation.
- **Why this category**: This is a sound generic rule — if a job doesn't score well AND requires moving, it's not worth showing.

#### 18. Reloc penalty in web app (-15 pts)
- **Category**: 🟡 Calibration
- **File**: `api/routes/jobs.py` (lines 97-109)
- **What it does**: Subtracts 15 points from relocation jobs for the web display. Applied per-user using `home_locations`.
- **Why this category**: The penalty amount (15) is hardcoded. Some users might value relocation differently.

---

### Pre-filter (prefilter.py)

#### 19. US-only detection
- **Category**: 🟢 Generic
- **File**: `agent/prefilter.py` (lines 84-126)
- **What it does**: Detects US-only roles by scanning for US state abbreviations, city names, and visa requirement phrases. Used to filter jobs for EU-based users.
- **Why this category**: The detection logic itself is generic. The fact that it's used for filtering is EU-centric but the detection function doesn't assume a specific user — the caller decides what to do with the result.

#### 20. Pre-filter title keywords (PM-specific)
- **Category**: 🟡 Calibration (shared config)
- **File**: `agent/config/preferences.yaml` (lines 15-24)
- **What it does**: `title_must_contain_one_of: ["product manager", "product lead", "product owner", ...]`. Only PM titles pass the prefilter.
- **Why this category**: This is in a shared config file, not per-user. If Noura wanted to search for different roles, she'd be blocked by the same PM-only filter. Should be per-profile or the shared default should be overridable.

#### 21. Pre-filter title exclusions
- **Category**: 🟡 Calibration (shared config)
- **File**: `agent/config/preferences.yaml` (lines 28-40)
- **What it does**: Excludes "project manager", "program manager", "growth", "insurance", etc.
- **Why this category**: Same issue as #20 — shared config, not per-profile. "Growth" exclusion is opinionated.

#### 22. Pre-filter deal breakers
- **Category**: 🟡 Calibration (shared config)
- **File**: `agent/config/preferences.yaml` (lines 4-12)
- **What it does**: Rejects "junior", "intern", "APM", "0-2 years", "1-3 years".
- **Why this category**: Reasonable for senior users but a shared config. A mid-level user would be incorrectly filtered.

#### 23. Home locations fallback in prefilter
- **Category**: 🟢 Generic
- **File**: `agent/prefilter.py` (line 164)
- **What it does**: Falls back to `["spain", "europe", "eu", "emea"]` when no home_locations passed.
- **Why this category**: The fallback is EU-centric, but the primary path always receives `home_locations` from the user profile via `main.py` line 533. The fallback only applies to direct prefilter calls without a profile.

---

### Search Configuration

#### 24. Search terms and locations
- **Category**: 🔴 (but out of scoring scope)
- **File**: `agent/config/searches.yaml`
- **What it does**: Defines search queries like "Senior Product Manager data platform" in "Spain", "Product Manager AdTech" in "Netherlands". These are Juan-specific searches.
- **Why this category**: Not technically scoring, but determines what jobs enter the pipeline. Currently shared across all users. Each user should have their own search config (referenced from profile YAML).

#### 25. Watchlist companies
- **Category**: 🔴 (but out of scoring scope)
- **File**: `agent/config/watchlist.yaml`
- **What it does**: Polls specific companies' ATS boards (Elastic, GitLab, MongoDB, Datadog, ClickHouse, Grafana, dbt Labs). These are Juan's target companies.
- **Why this category**: Same issue — shared config with one user's target companies. Should be per-profile.

---

### Parser

#### 26. Parser domain taxonomy
- **Category**: 🟢 Generic
- **File**: `agent/prompts/parser-prompt.md` (line 17)
- **What it does**: Parser classifies domains into: `adtech|data|ml|fintech|saas|ecommerce|healthcare|other`.
- **Why this category**: This is a reasonable generic taxonomy. The LLM picks the best match. However, it's limited — if a user cares about "edtech" or "biotech", those would fall into "other" and miss domain-specific scoring. Extensible via `_DOMAIN_KEYWORDS` in main.py.

---

### Notifier

#### 27. Notifier home locations fallback
- **Category**: 🟢 Generic
- **File**: `agent/notifier.py` (line 59)
- **What it does**: `_is_reloc()` falls back to `["barcelona", "madrid", "spain", "españa"]` if no home_locations passed.
- **Why this category**: The primary path always passes profile `home_locations` from `_build_context()` → `_flatten_job()`. The fallback is only hit in standalone testing. But it should still be cleaned up — a neutral fallback like `[]` would be better.

---

### Vectorstore

#### 28. Default knowledge config fallback
- **Category**: 🟢 Generic
- **File**: `agent/vectorstore.py` (lines 18-23)
- **What it does**: When no profile is passed, falls back to Juan's knowledge dir and collection name. Only used in standalone `if __name__ == "__main__"` testing.
- **Why this category**: The main pipeline always passes a profile. The defaults are testing-only convenience. Not a production issue but should be noted.

---

## Recommendations

### P0 — Must fix before multi-user launch

1. **Remove "PM" and "EU or remote" from scoring rubric** (findings #4, #5): Add `target.role_type` (e.g., "PM", "SWE", "Designer") and `target.geography` (e.g., "EU or remote", "US") to the profile schema. Interpolate into the rubric template alongside existing placeholders.

2. **Remove "SaaS, B2B" adjacent domain fallback** (finding #8): Use an empty string or derive from the user's second-tier domains.

3. **Remove hardcoded home locations default** (finding #15): Change `_HOME_LOCATIONS` default to `[]`. The profile always overwrites this, but the default is a landmine.

4. **Make searches.yaml and watchlist.yaml per-profile** (findings #24, #25): Profile YAML already has `searches:` and `watchlist:` path fields. Wire `main.py` to use them so each user gets their own search terms and target companies.

5. **Move preferences.yaml prefilter to per-profile** (findings #20, #21, #22): The `title_must_contain_one_of`, `title_exclude`, and `deal_breakers` lists should be overridable per profile. A `preferences:` field in the profile YAML already points to the shared config — allow per-profile overrides.

### P1 — Should fix (improve scoring quality per user)

6. **Domain keyword override map** (finding #14): Move `_DOMAIN_KEYWORDS` from hardcoded dict to a config file or derive from the user's domain list + a generic keyword bank.

7. **Make heuristic scoring weights configurable** (findings #11, #12, #13): Location bonus (10/8/6), skill multiplier (4), skill cap (30), red flag penalty (5/-15) — expose as profile config with sensible defaults.

8. **Make tier thresholds per-user** (finding #16): Add `scoring.tier_a_threshold` and `scoring.tier_b_threshold` to profile YAML. Default 50/30.

9. **Make reloc penalty configurable** (finding #18): The -15 point penalty in `api/routes/jobs.py` should read from the user's profile or a settings table.

### P2 — Nice to have

10. **Extend parser domain taxonomy** (finding #26): Add common domains like "edtech", "biotech", "gaming", "logistics" to reduce "other" classification rate.

11. **Make LLM rubric dimension weights configurable** (finding #2): Allow advanced users to adjust the 25/20/20/20/15 split.

12. **Clean up notifier/vectorstore fallbacks** (findings #27, #28): Replace Juan-specific defaults with neutral values.
