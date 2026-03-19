# System Invariants

## Module Boundaries
- api/ has ZERO imports from agent/ (api/geo.py and api/onboard_utils.py are self-contained copies)
- agent/ has ZERO imports from api/
- shared/ is pure logic: no DB, no network, no side effects, no framework imports
- Frontend (web/) never calls agent/ or shared/ directly; all data via API

## Scoring
- Score is always 0-100, integer, clamped with min/max
- hybrid_score = heuristic_score() + grade_to_points(technical) + grade_to_points(profile), clamped [0,100]
- Heuristic and RAG use identical 0-100 scale
- Scoring functions must only read fields from parsed JSON blob or real DB columns (not computed CTE fields)
- _score_single_job() is the single scoring path for both list and detail endpoints
- Tier thresholds: A>60, B>40, C<=40
- grade_to_points: A=20, B=12, C=5, None=10 (midpoint)
- Eligibility penalty (-20) bypassed for loc_pref="d" and is_pure_timezone()
- Scoring priority: v2 hybrid (scored_v2=1) > v1 RAG (ujs_score present) > unscored (hybrid with defaults)

## Data
- jobs table is shared (no per-user data). Per-user scores in user_job_scores
- profile_id stays in users table as human-readable label; all FK relationships use users.id (int)
- job_id is UUID hash from _normalize_for_id(); immutable after creation
- DB migrations are numbered .sql files in api/db/migrations/; current: 001-025
- profile_yaml and cv_md persisted in users table (not just filesystem)

## Deploy
- Two requirements files: requirements.txt (local/CI) + requirements-web.txt (Dockerfile)
- ANY new import at module level in api/ MUST be added to BOTH requirements files
- Dockerfile must COPY shared/ (not just api/ and agent/)
- NEVER add startCommand to railway.toml (startup.sh handles PORT expansion)
- NEVER modify .github/workflows/deploy.yml (uses curl to Railway GraphQL API)
- Railway auto-deploys on push to main; GHA tests run in parallel (not gating)
- web-image-check CI job validates requirements-web.txt imports
- [skip ci] skips tests + deploy; [skip deploy] skips deploy only

## CV Pipeline
- validate_cv() and content_checks are separate modules (api/cv/validator.py vs api/cv/content_checks.py)
- extract_cv_companies() regex in content_checks.py MUST stay in sync with _parse_companies_from_experience() in plan.py
- 3-page hard cap, 2-page soft cap, max 12 WE bullets
- Master CV path: select → render → rewrite (LLM) → validate → fix → docx
- Legacy path fallback: build_cv_plan → generate_cv → validate → docx
- strip_analysis() in llm.py auto-strips <analysis> tags from LLM output

## Parser
- Parser v1.5 fields: role_in_plain_english, company_context, verbatim_for_cv, truly_required, preferred_skills
- Backward compat: all consumers use get("truly_required") or get("must_have_skills") or [] pattern
- must_have_skills renamed to truly_required; old cached jobs use old field names
- 30 canonical domain enum values; parser-prompt.md v1.3 includes _domain_guide

## Agent Pipeline
- Sequential per-profile execution (not parallel matrix)
- generate_unified_queries() deduplicates across all profiles by (term.lower(), location.lower(), site)
- Pipeline does POST /api/ingest (Step 10b) before email; no local scoring in notifier
- search_titles in target: block controls scraping; seniority_weights/domains control scoring (independent)

## Scraper Health
- `agent/scraper_health.py`: pure collection + evaluation functions; `send_health_alert()` is best-effort (never raises)
- Alert recipient: `ADMIN_EMAIL` env var, falls back to `NOTIFY_EMAIL`
- GHA annotations printed to stdout (`::warning::` / `::error::`) — no workflow file changes needed
- Exit 1 only when ALL sources are critical (entire scrape failed, not a single source)
- Thresholds: `THRESHOLDS` dict in `scraper_health.py` — change there, tests will catch regressions

## Analytics
- PostHog Python SDK: import as `from api import analytics; analytics.capture(...)` (NOT `from api.analytics import capture`)
- Tests patch `api.analytics.capture`
- PostHog host: eu.i.posthog.com (default for api/, agent/, and frontend)
- posthog.ai wrappers: pass posthog_distinct_id at .create() call level

## Dual-Copy Sync Rules
| File A | File B | What to sync |
|--------|--------|--------------|
| api/geo.py | agent/geo.py | Geographic resolution logic |
| api/onboard_utils.py | agent/onboard.py | Onboarding extraction (partial overlap) |
| api/prompts/onboard-extraction.md | agent/prompts/onboard-extraction.md | LLM extraction prompt |
| api/scoring.py (heuristic) | shared/scoring_core.py | Scoring logic, thresholds, penalties |
| api/grade_mapping.py | agent/main.py (_grade_to_points) | Grade-to-points mapping |
| api/cv/content_checks.py (regex) | api/cv/plan.py (regex) | Company extraction regex |
| requirements.txt | requirements-web.txt | Python deps for api/ |

## Decisions Log
| Date | Decision | Discarded | Why |
|------|----------|-----------|-----|
| 2026-02-26 | SQLite for all storage | Postgres | Zero config, Railway volume, single-writer acceptable |
| 2026-02-26 | Heuristic + RAG dual scoring | RAG only | Heuristic covers unscored jobs instantly, free |
| 2026-02-26 | Dual-copy over shared imports | Monolithic shared/ | Agent must run standalone in GHA |
| 2026-02-27 | Server-side merge for CV replace | Client-side overwrite | Prevents data loss, atomic operation |
| 2026-02-28 | Eligibility penalty -20 | Exclude job entirely | Keeps job visible, user decides |
| 2026-03-01 | httpx over requests (notifier) | requests | httpx already in deps, avoids transitive |
| 2026-03-01 | Digest from API (not local) | Local scoring | Single scoring path, no drift |
| 2026-03-02 | Parser as leverage point | Separate enrichment | One prompt change cascades to scorer, CV, UI |
| 2026-03-02 | Master CV ChromaDB selection | LLM selection | Deterministic, cheaper, debuggable |
| 2026-03-02 | Async CV via BackgroundTasks | Celery/Redis | No infra overhead, TestClient runs sync |
| 2026-03-11 | user_id (int) for all FK | profile_id (string) | Stable, no rename cascades |
| 2026-03-19 | Parser v1.5 distillation for CV | Raw JD in prompt | ~40% token reduction on Sonnet call |
