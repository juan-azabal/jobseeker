# JobSearch (Monorepo)

## Description
Job search platform: web CRM (browse, filter, manage scored jobs) + autonomous scraping/scoring engine. Daily email digest links to the web for full detail. Users self-onboard via CV upload.

## Monorepo Layout
- `api/` — FastAPI backend
- `web/` — React frontend
- `agent/` — scraping/scoring engine (formerly standalone `jobagent` repo)
- `shared/` — shared scoring core (single source of truth; imported by api/ and agent/)
- `data/` — SQLite DB (gitignored)
- `tests/` — backend tests
- `scripts/` — utility scripts

## Commands
- Dev backend: `venv/bin/uvicorn api.main:app --reload --port 8000`
- Dev frontend: `cd web && npm run dev`
- Dev both: `bash dev.sh`
- Ingest jobs: `python -m api.ingest`
- Run agent: `cd agent && ../venv/bin/python main.py --profile juan --notify`
- Test backend: `pytest tests/`
- Test frontend: `cd web && npm test`
- Test agent: `cd agent && pytest tests/`
- Lint: `ruff check .`
- Format: `ruff format .`

## Structure
- Backend: `api/`
  - `api/main.py` — FastAPI app
  - `api/routes/` — one file per resource (auth, jobs, onboard, ingest, admin, digest)
  - `api/middleware/auth.py` — session auth + admin guards (`get_current_user`, `get_current_admin`)
  - `api/middleware/staging.py` — blocks non-admin requests in ENVIRONMENT=staging (returns 403)
  - `api/db/` — SQLite init, migrations (001–016), queries
  - `api/ingest.py` — pipeline output → SQLite
  - `api/scoring.py` — per-user heuristic scoring (ported from agent)
  - `api/embeddings.py` — OpenAI embedding service with SQLite cache (text-embedding-3-small)
  - `api/skill_matcher.py` — semantic skill matching (cosine similarity ≥0.80=match, ≥0.68=partial, fallback to substring)
  - `api/geo.py` — geographic region utilities (API-side copy of agent/geo.py)
  - `api/onboard_utils.py` — CV parsing + profile YAML generation (extracted from agent/onboard.py)
  - `api/prompts/` — LLM prompts for API-side features (onboard-extraction.md)
  - `api/cv/` — CV generation pipeline (plan, prompt, llm, validator, docx_builder, ats_audit, select, render, rewrite)
  - `api/analytics.py` — PostHog Python client (init, capture, identify_user, capture_exception)
  - `api/logging_config.py` — structlog configuration (JSON in CI, ConsoleRenderer locally)
  - `api/db/snapshot.py` — async `download_prod_snapshot()`: streams SQLite backup from prod, validates magic bytes, atomic replace
- Frontend: `web/`
  - `web/src/components/` — FilterBar, JobCard, ProfileEditor, ScoreBreakdown, FileUpload, UserMenu, DomainSelector, WaitlistForm, MockDashboard, MockJobDetail, MockCVButton, AddSourceModal, AddEntryModal
  - `web/src/pages/` — Landing, Login, Onboard, Jobs, JobDetail, Profile, Admin
  - `web/src/context/AuthContext.tsx` — auth state provider
  - `web/src/types/job.ts` — job TypeScript types
  - `web/src/types/masterCv.ts` — Master CV JSON schema TypeScript types
  - `web/src/constants/domains.ts` — 30-domain canonical enum, display labels, grouped categories
  - `web/src/analytics.ts` — posthog-js wrapper (initPostHog, identifyUser, resetPostHog)
- Agent: `agent/`
  - `agent/main.py` — thin CLI wrapper: parse args → load profile → call run_pipeline()
  - `agent/pipeline.py` — pipeline orchestrator (scrape → parse → score → notify); `run_pipeline()` + `PipelineOptions`
  - `agent/scoring.py` — heuristic scoring + config loader (wraps shared/scoring_core.py with module globals)
  - `agent/display.py` — `ranked_jobs()`, `print_summary()` (display/ranking logic)
  - `agent/reloc.py` — relocation detection (`is_remote_requiring_reloc()`)
  - `agent/salary.py` — salary parsing + EUR conversion (`extract_max_salary_eur()`)
  - `agent/models.py` — RawJob Pydantic model (source-agnostic scraper output)
  - `agent/merger.py` — merge duplicate RawJobs from multiple scrapers (source-group field priority)
  - `agent/preseed.py` — maps structured RawJob fields to parser schema (pre-seeds before LLM call)
  - `agent/logging_setup.py` — structlog configuration for the agent
  - `agent/api_cache.py` — cross-user parsed-job cache via Railway DB
  - `agent/search_generator.py` — `generate_queries(profile)` + `generate_unified_queries(profiles)` — cross-user dedup by (term, location, site)
  - `agent/scraper.py` — `run_scraper_from_queries(queries)` + `make_job_id()` dedup → returns `list[RawJob]`
  - `agent/ats_scraper.py` — Greenhouse/Lever/Ashby API poller → returns `list[RawJob]`
  - `agent/wttj_scraper.py` — Welcome to the Jungle (Algolia API) → returns `list[RawJob]`
  - `agent/prefilter.py` — keyword filter + US-only detection (no API calls)
  - `agent/parser.py` — gpt-4o-mini: structured JSON extraction from JD; pre-seeded with structured fields
  - `agent/scorer.py` — gpt-4o: RAG scoring against full CV via ChromaDB
  - `agent/notifier.py` — Gmail SMTP digest sender (Jinja2 template)
  - `agent/user_config.py` — profile loading + seniority weight computation
  - `agent/geo.py` — geographic region detection (country-converter, babel, pytz)
  - `agent/vectorstore.py` — ChromaDB knowledge base for scoring
  - `agent/onboard.py` — CLI onboarding: CV → profile YAML + knowledge/cv.md
  - `agent/gap_tracker.py` — persists gap/strength data to JSONL
  - `agent/config/profiles/*.yaml` — per-user profiles + searches/preferences/watchlist
  - `agent/config/seen_ids/*.txt` — per-user seen job ID lists
  - `agent/knowledge/{user_id}/cv.md` — CV knowledge base (per user, read-only)
  - `agent/output/` — job results JSON (gitignored)
  - `agent/prompts/` — LLM prompts (parser-prompt, scoring-rubric, onboard-extraction)
  - `agent/scripts/` — reparse_all, rescore_all, build_ingest_payload, list_active_profiles, check_active
  - `agent/schemas/` — JSON output contracts (parsed_job, scored_job, digest_context, gap_history_entry)
  - `agent/patterns/` — interface contracts per module
  - `agent/docs/decisions/` — ADRs (001–007)
- Tests: `tests/` (backend, 683 tests), `web/src/*.test.tsx` (frontend), `agent/tests/` (agent, 517 tests)
  - `agent/tests/fixtures.py` — shared BASELINE_PROFILE fixture (fixed dict, not from juan.yaml)
  - `agent/tests/test_notifier_v2.py` — v2 rag_score compat in _build_context (P15 fix)
  - `agent/tests/test_ranked_jobs_v2.py` — hybrid score in ranked_jobs + print_summary mode label (P16/P18 fix)
  - `agent/tests/test_gap_tracker_v2.py` — grade points stored in gap history for v2 jobs (P17 fix)
  - `tests/test_profile_merge.py` — 20 unit tests for merge_profiles() pure function (Phase 18)
  - `tests/test_profile_track.py` — 4 integration tests: track change regenerates searches with correct titles (Phase 18)
  - `tests/test_profile_e2e.py` — 12 E2E regression tests: all write paths, CV replace additive, C5 regression (Phase 18)
  - `web/src/components/CVReplaceSummary.tsx` — read-only diff view after CV replace (Phase 18)
  - `api/profile_merge.py` — merge_profiles() + compute_diff() pure functions (Phase 18)
- Shared: `shared/`
  - `shared/scoring_core.py` — scoring logic (domain inference, grade mapping, eligibility penalty, heuristic score); imported by both `api/` and `agent/`
  - `shared/scoring_data.py` — scoring data constants (domains, keywords, city map, lang signals)
  - `shared/master_cv_scoring.py` — `build_scoring_context(master_cv, job, query_fn=None)` → enriched skill evidence + recent roles string for RAG prompt injection (≤6000 chars)
- DB: `data/jobseeker.db` (gitignored)
- Static build: `web/dist/` (gitignored)
- Scripts: `scripts/seed_dev.py` — dev database seeder, `scripts/backfill_embeddings.py` — one-time skill embedding backfill

## Environment Variables

### Backend (api/)
| Variable | Description | Default |
|---|---|---|
| `DB_PATH` | SQLite database path | `data/jobseeker.db` |
| `SESSION_SECRET` | Session signing key | `dev-secret-change-in-prod` |
| `GOOGLE_CLIENT_ID` | OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | — |
| `BASE_URL` | Backend base URL for OAuth callbacks | `http://localhost:8000` |
| `FRONTEND_URL` | Frontend URL for post-login redirect | — |
| `JOBAGENT_DIR` | Path to agent directory | `agent` |
| `INGEST_API_KEY` | Shared secret for ingest/batch-lookup endpoints | — |
| `ADMIN_EMAILS` | Comma-separated admin emails (auto-promote on login) | — |
| `GH_ACTIONS_TOKEN` | GitHub PAT (contents:write + actions:write) | — |
| `GH_REPO` | GitHub repo `owner/repo` for workflow dispatch | — |
| `GH_REF` | Git branch for workflow dispatch | `main` |
| `ENVIRONMENT` | Runtime environment (`production`\|`staging`) | `production` |
| `PROD_API_URL` | Production base URL for staging DB snapshot | — |
| `DB_EXPORT_API_KEY` | Shared secret for `/api/admin/db-export` | — |
| `LLM_MODEL_PARSING` | Override parsing model for cheap staging inference | `gpt-4o-mini` |
| `LLM_MODEL_SCORING` | Override scoring model for cheap staging inference | `gpt-4o-mini` |
| `VITE_ENVIRONMENT` | Frontend env string (`staging` shows banner) | — |

### CV Generation (api/cv/)
| Variable | Description | Default |
|---|---|---|
| `CV_LLM_PROVIDER` | LLM provider (anthropic\|openai) | `anthropic` |
| `CV_LLM_MODEL` | Model override | provider default |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `CV_REFERENCES_DIR` | CV reference files directory | `api/cv/references/` |

### Agent
| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (parsing + scoring) | — |
| `GMAIL_ADDRESS` | Gmail sender for digests | — |
| `GMAIL_APP_PASSWORD` | Gmail app password | — |
| `RAILWAY_URL` | Railway API base URL (cross-user cache) | — |
| `INGEST_API_KEY` | Shared secret for Railway API | — |
| `APP_BASE_URL` | Platform URL for digest links | `https://jobseeker-production.up.railway.app` |
| `DIGEST_TEMPLATE` | Email template filename (rollback toggle) | `email_digest.html.j2` |

## Deployment
- **Auto-deploy IS ENABLED on Railway.** Every push to main triggers a Railway build automatically. GHA gate (tests) runs in parallel — Railway doesn't wait for it. Do NOT assume deploy is blocked until GHA passes.
- GHA `deploy.yml` calls `serviceInstanceRedeploy` after tests pass. This triggers a fresh build from the **latest commit on main**. It is a full rebuild, not just a restart.
- **NEVER modify `.github/workflows/deploy.yml`** — it uses curl to Railway's GraphQL API. Do NOT replace with `railway up`, deploy hooks, or any other method.
- Railway uses the **`Dockerfile`** at repo root (not Nixpacks). The Dockerfile must copy ALL source directories needed at runtime — including `shared/`.
- **`startCommand` in `railway.toml` is executed WITHOUT a shell on Railway V2** — `$PORT` does NOT expand. Use `startup.sh` (already in Dockerfile CMD) which uses `exec uvicorn ... --port "${PORT:-8000}"`.
- NEVER add `startCommand` back to `railway.toml`. The CMD in Dockerfile calls `startup.sh` which handles PORT correctly.
- Before pushing to main: run tests locally (`pytest tests/` + `cd agent && pytest tests/`).
- Commits to main should be logically grouped, not one-per-file.
- Railway MCP is READ-ONLY: logs and deployment status only.
- Railway CLI (`railway logs --deployment <id>`) is the fastest way to diagnose failed deployments.
- GHA secrets: `RAILWAY_TOKEN`, `RAILWAY_SERVICE_ID`, `RAILWAY_ENVIRONMENT_ID`.
- **Deploy flow**: PR → Railway despliega staging automáticamente (GitHub integration). `ci.yml` corre tests + `web-image-check` en paralelo. Validás en staging. Merge a main → Railway despliega producción + `deploy.yml` re-triggers después de tests. Never merge without staging validation.
- **`[skip ci]`** skips all tests + production redeploy. **`[skip deploy]`** skips production redeploy only (tests still run).

## Conventions
- Commits: conventional (`type: description`)
- Backend has zero import dependency on agent/ (api/geo.py + api/onboard_utils.py are self-contained copies)
- API routes: one file per resource in `api/routes/`
- SQL: raw sqlite3, migrations in `api/db/migrations/` as numbered .sql files
- Frontend: functional components, React Context for global state, TypeScript strict
- All secrets via env vars, never committed
- Test naming: `test_*.py` (backend), `*.test.tsx` (frontend)

## Architecture

### Ingestion Pipeline (enriched, post-overhaul)
```
Step 1:  JobSpy + ATS + WTTJ → RawJob (Pydantic, source-specific fields)
Step 1b: Merge by job_id — per-field source priority (salary from WTTJ, job_level from LinkedIn,
         company_industry from Indeed, departments from ATS, etc.)
Step 2:  Prefilter (uses structured country/city when available, falls back to freetext)
Step 3:  Pre-seed ParsedJob from structured fields (seniority, salary, location_type, domain)
Step 4:  LLM Parse ONLY null fields (gpt-4o-mini, reduced token cost)
Step 5:  Post-parse validation — structured source wins for factual conflicts
```

### Agent Pipeline (12 steps)
```
Step 0:    generate_unified_queries(all_profiles) — search_titles × location × site, deduped
Step 1a-c: Scrape (JobSpy via queries + ATS watchlist + WTTJ) → RawJob → merge_jobs() → dicts
Step 2:    Prefilter (keywords, US-only, deal breakers, seen_ids — no API calls)
Step 3:    Local cache split (cached vs new jobs)
Step 3b:   Cross-user DB cache (fetch already-parsed from Railway DB via api_cache.py)
Step 4:    Parse new jobs (gpt-4o-mini, ~$0.001/job; pre-seeded from structured fields)
Step 5:    RAG score (gpt-4o via ChromaDB, ~$0.04/job)
Step 5b:   Gap tracking (persist strengths/gaps to JSONL)
Step 6:    Update local cache
Step 7:    Combine cached + new results
Step 8:    Auto-skip low-score relocation jobs
Steps 9-12: Summary, save snapshot, mark seen, email digest (if --notify)
```

### GHA Pipeline (sequential, 4 jobs)
```
list-profiles → digest (sequential loop per profile) → persist-seen-ids → verify-health
```
Each profile runs fully (scrape→parse→score→sync to Railway) before the next starts, so subsequent profiles skip re-parsing overlapping jobs. `timeout-minutes: 60`.

### Ingest Flow
```
Agent output JSON → POST /api/ingest → upsert jobs table (shared) + user_job_scores (per-user RAG)
```

### Scoring: dual-path
- **RAG score** (agent, gpt-4o): stored in `user_job_scores`, preferred when available
- **Heuristic score** (api/scoring.py, no LLM): computed at query time for unscored jobs (domain 0-15, seniority 0-15, location 0-10, skills 0-30, red_flags -15)

## Project State

### Completed
- Phase 0 — Scaffold
- Phase 1 — MVP: Ingest + browse jobs with period/tier filters
- Phase 2 — Auth: Google OAuth (authlib + SessionMiddleware, HTTP-only cookie, protected API, frontend guards)
- Phase 3 — Onboarding: CV upload (.docx) → generate-profile → edit → save-profile → jobagent files written
- Phase 4 — UI overhaul + job tracking + profile page
  - Design: dark theme (zinc-950), violet-500 primary accent, semantic tier colors (emerald/amber/zinc)
  - Job tracking: `user_job_status` table (migration 003), per-user `applied_at`, `POST /jobs/{id}/apply`
  - CV generation: single-job "Generate CV" button; bulk selection + floating action bar
  - Profile page `/profile`: view/edit current profile, "Replace CV" flow to re-upload and regenerate
  - Header: sticky frosted-glass, logo links to `/jobs`, hamburger menu (Jobs / My Profile / Sign out)
  - Profile editing: add/remove domains (with weight slider), add/remove skills inline
  - Data safety: `save_profile` with existing `profile_id` only updates `cv.md` — never overwrites YAML
  - Tier C hidden by default in listing filters
- Phase 5 — CV Generation (in-app tailored CV download)
  - LLM provider configurable via CV_LLM_PROVIDER (anthropic|openai), model via CV_LLM_MODEL
  - .docx built with python-docx for ATS compliance
  - ATS audit runs post-build as safety net, result in X-ATS-Audit response header
  - "Generate CV" button: POSTs to /api/jobs/{id}/generate-cv, triggers browser download
- Phase 6 — CV Output Quality
  - Plan-driven architecture: deterministic build_cv_plan() → plan-aware prompts → LLM → validate → fix → docx → ATS audit
  - Programmatic CV validator: errors (title/years downgrade, slop) + warnings (missing language/theme, bullet budget, gerund-start)
  - Content volume controls: 3-page hard cap, 2-page soft cap, max 12 WE bullets total
- Phase 7 — Deparameterize Scoring (rubric role_type/geography, adjacent domains, home locations)
- Phase 8 — Per-Profile Pipeline (searches, watchlist, prefilter per-user)
- Phase 9 — Per-User Scoring + New-User Bootstrap
  - DB: `jobs` table is shared, `user_job_scores` table holds per-user RAG scores
  - Heuristic scorer at query time for unscored jobs (no LLM, instant, free)
  - Ingest: `ingest_from_list()` accepts optional `profile_id`; common data → `jobs`, per-user RAG → `user_job_scores`
  - Onboarding triggers GHA pipeline via `workflow_dispatch` (fire-and-forget)
  - Frontend: empty state with "Scanning job boards" + 60s auto-poll when `totalInDb === 0`
- Phase 10 — Ops: Persistence, Health Monitoring, Admin
  - Railway volume (`/data`) holds SQLite; `cv_md` + `profile_yaml` persisted in `users` table (migrations 006, 007)
  - Auto-prune: `cleanup_old_jobs()` deletes jobs + dependent rows older than 90 days on every ingest
  - `GET /api/ingest/status` (X-Ingest-Key protected): pipeline health stats
  - Admin system: auto-promote via `ADMIN_EMAILS` env; `/admin` page with pipeline trigger + users table
- Phase 11 — Cross-User Dedup + Sequential Pipeline
  - `POST /api/ingest/batch-lookup`: check Railway DB for already-parsed jobs (X-Ingest-Key auth, 500 id cap)
  - `agent/api_cache.py`: fetch_existing_parsed() — graceful fallback if API unavailable
  - GHA workflow: sequential profile loop (not parallel matrix). Each profile syncs to Railway before next starts
  - Saves ~$0.001/job per overlapping job across users (gpt-4o-mini parse cost avoided)
- Phase 12 — Semantic Skill Matching
  - Embeddings: OpenAI text-embedding-3-small, 256 dims (via `dimensions` param), cached in SQLite (skill_embeddings table, migration 011; migration 012 clears stale 1536-dim cache)
  - Matching: cosine similarity (numpy) ≥0.80 = match, ≥0.68 = partial. Fallback to exact substring if no API key.
  - Scoring: heuristic_score() uses semantic matching for skills dimension (partial match = 2pts, full = 5pts)
  - Job list: batch pre-computation via `precompute_skill_lookup()`. One `match_skills` call for all unique job skills, O(1) per-job lookup.
  - Job detail: GET /api/jobs/{id} returns skill_matches with match status per skill
  - Add skill: POST /api/onboard/profile/skills — one-click add from job detail
  - Frontend: skill chips colored by match status (green/amber/default); unmatched AND partial chips clickable to add exact skill; partial tooltip shows similarity % and prompt to add; skip button on detail; select all toggle on list
  - Backfill: scripts/backfill_embeddings.py for existing data; auto-embed on ingest; POST /api/admin/backfill-embeddings
  - Diagnostics: GET /api/admin/embedding-diagnostics — curl-only, shows similarity scores for threshold tuning
  - Admin: "Backfill embeddings" button + "Clear seen" button per user
  - Performance: in-process LRU cache, numpy cosine similarity (~1000x faster than pure Python)
- Phase 13 — Domain Scoring Fix (v2)
  - 13.1 (B1/RAG): `_build_scoring_prompt()` injects graduated PENALTY clause; strong (≤-15) caps domain_fit at 3, mild (<0 >-15) caps at 10; omitted when no negative domains
  - 13.2 (B2/parser): domain enum expanded to 30 canonical values; parser-prompt.md v1.3 includes `_domain_guide` definitions; `ml→ai_ml`, `game→gaming`, `healthcare→healthtech` renames; DB migration 013 normalizes existing data
  - 13.2 (B2/heuristic): `_DOMAIN_KEYWORDS` in both `api/scoring.py` + `agent/main.py` covers 29 domains (≥2-word rule; brand exceptions: databricks, snowflake, kubernetes, terraform); `_DOMAIN_ALIASES` full 30-domain mapping
  - 13.3 (B4/gate): `_heuristic_gate()` uses dict for target_domains; negative weight → 0 gate credit; not in dict → 0
  - 13.4a: `PATCH /api/jobs/{id}/domain` stores per-user domain override; `heuristic_score()` gets `domain_override` param; cascade: user_override → _infer_domain() → parsed.domain; RAG scores NOT invalidated; DB migration 014
  - 13.4b: `DomainSelector` grouped dropdown in JobDetailPage; amber border for "other" domain; pencil icon for active override; 6 category groups + search filter
  - 13.5: `POST /api/admin/reparse-domains` re-classifies domain='other' jobs with keywords (synchronous, writes jobs.domain only); `GET /api/admin/reparse-domains/preview`; `GET /api/admin/domain-corrections` aggregated analytics; AdminPage domain section
  - 13.6: Keyword collision regression tests (fintech vs data, hr_tech vs other); keyword fixes: `financial institution`/`financial services` → fintech, `training management`/`learning and development` → hr_tech, `analytics platform` → `data analytics platform` (data); audit script column fix; 415 backend + 194 agent tests passing
- Phase 14 — Instrumentation + Observability
  - 14.1: structlog configured globally for api/ (`api/logging_config.py`); all existing loggers migrated; JSON in CI, ConsoleRenderer locally
  - 14.2: `GET /api/health/ready` deep health check — DB connectivity + row counts; safe for Railway / GHA polling
  - 14.3: PostHog Python SDK (`api/analytics.py`): `init_posthog()` at app startup, `identify_user()` in auth callback, `capture_exception()` on unhandled 500s; no-op when POSTHOG_API_KEY absent
  - 14.4: 8 server-side user action events via `analytics.capture()`: job_viewed, job_applied, job_dismissed, cv_generated (via BackgroundTasks), skill_added, domain_overridden, profile_saved, onboard_completed
  - 14.5: posthog-js frontend (`web/src/analytics.ts`): `initPostHog()` before first render, `identifyUser()` on auth load, `resetPostHog()` on logout; SPA route tracking via `capture_pageview: 'history_change'`
  - 14.6: LLM calls wrapped with `posthog.ai.anthropic.Anthropic` / `posthog.ai.openai.OpenAI` — token usage + latency tracked per user in PostHog; `distinct_id` threaded from route layer; onboard extraction also wrapped
  - 14.7: Agent structlog + PostHog pipeline events (`agent/logging_setup.py`); `agent_pipeline_start` and `agent_pipeline_complete` events with profile_id, mode, cost_usd, tier counts; key diagnostic prints duplicated as structured log fields
- Phase 15 — Landing Page + Waitlist
  - Public landing replaces LoginPage for non-auth visitors (no app header on landing)
  - Branding: favicon (violet SVG circle), meta tags, OG tags, Instrument Serif display font
  - Design: WCAG 2.2 AA compliant, zinc-950/900/800 elevation, violet-500 accents, scroll reveal animations
  - Waitlist: POST /api/waitlist (public), GET /api/admin/waitlist (admin), DB migration 015
  - MockDashboard: React component with 4 anonymized job cards in browser-frame wrapper
  - WaitlistForm: reusable component with idle/submitting/success/error states + PostHog events
  - Analytics: waitlist_submitted, waitlist_success, waitlist_duplicate, waitlist_error events with source prop
  - Footer: "Built by Juan Azabal" with LinkedIn link
- Phase 16 — Landing Page Iteration: Job Detail + CV
  - MockJobDetail: browser-frame showing score breakdown, skill matching (3 states), strengths, gaps, verdict
  - MockCVButton: CSS-only animated loop (idle→loading→success, 4.5s cycle)
  - CV callout: compact card (not full section), text + animated button
  - How it works expanded to 4 steps
  - Section headings added to MockDashboard ("Your daily feed") and MockJobDetail ("Behind the score")
  - Responsive: MockJobDetail hides gap card + reduces to 1 strength on mobile

Phase 19 — Location Eligibility + Scoring Recalibration (complete: 2026-02-28)
- 19.0.1–19.0.2: Kill v1 RAG scoring path — all jobs react to profile changes (api + agent)
- 19.1.1–19.2.1: Eligibility penalty (-20 pts when geo-restricted remote excludes user's home country); graduated location scoring (+8 eligible, +2 ineligible, +10 unrestricted); country_weights skip injecting 'remote' when geo-restricted (api + agent)
- 19.3.1–19.3.2: Tier thresholds recalibrated — A>60, B>40, C≤40 (api + agent)
- 19.4.1–19.4.2: `eligibility_warning` field in API responses; red "Not eligible" badge in UI (vs amber "Relocation" for geo_restricted)
- 19.5.1–19.5.3: Full agent parity for penalty + location scoring; cross-system regression tests reveal and fix two parity bugs (timezone check + EU region eligibility)
- GATE 19: 639 backend tests + 470 agent tests passing; BUGS.md created

Phase 20 — Email Digest Overhaul (complete: 2026-02-28)
- Rebrand: "JobAgent" → "JobSeeker" in subject, sender name, header, footer
- Platform links: all "Ver" links point to /jobs/{job_id} using hash (same ID used by frontend route + DB)
- Secondary "Oferta original" link in Tier A preserves direct access to external posting
- Prominent CTA: "Ver tu dashboard →" violet button in header + "Ver todos en el dashboard →" after Tier A
- Preheader: hidden text for inbox preview ("{n} para aplicar, {n} para revisar")
- Dark mode: color-scheme meta tags + @media prefers-color-scheme overrides (Apple Mail/iOS)
- Footer: branding line + "Built by Juan Azabal" + LinkedIn link
- Design: violet-500 (#8b5cf6) accent replaces orange-500 (#e97316), dark-first zinc theme (zinc-950/900/800)
- Rollback: DIGEST_TEMPLATE env var switches between v2 (default) and v1 backup (email_digest_v1.html.j2)
- APP_BASE_URL env var for platform URL in digest (default: Railway production URL)
- _build_headline() updated to include score: "{company} · {loc_type} · {score}"
- GATE 20: 517 agent tests passing (1 pre-existing scorer failure); test_digest_template.py with 21 regression tests
  - agent/tests/test_digest_template.py — 22 template regression tests (Phase 20 + 20b)
  - tests/test_digest_endpoint.py — 7 API endpoint tests (Phase 20b)
  - tests/test_digest_parity.py — 2 score/tier parity tests (Phase 20b)
  - agent/tests/test_sync_railway.py — 5 tests for _sync_to_railway() (Phase 20b)

### Current
Ingestion Overhaul — complete (2026-02-26)
- Phase 0.1: WTTJ geographic filter — run_wttj_scraper(target_countries) + Algolia geo filter; juan.yaml: target.wttj_countries: [ES, NL, DE, GB, IE]; 6 tests
- Phase 0.2: make_job_id normalization — _normalize_for_id() strips gender/legal suffixes + punctuation; location param removed; call sites updated; migrate_job_ids.py; 13 tests
- Phase 0.3: nan location sanitization + geography rejection — _sanitize_str() in scraper.py; _is_non_target_onsite() in prefilter.py; 10 tests
- Phase 0.4: smoke test suite — @pytest.mark.smoke, skips without output files; pytest.ini registers marker
- GATE Phase 0 (closed): 246 agent tests passing, 5 smoke tests skipping (no output files in worktree)
- Phase 1.1: RawJob Pydantic model — agent/models.py; required: id/title/company/source; is_remote computed from remote_type; extra='ignore'; 10 tests
- Phase 1.2: JobSpy field enrichment — run_scraper() returns list[RawJob]; captures salary, company metadata (employees_label, revenue_label, industry, url, logo), role metadata (job_level, job_function), emails; remote_type from is_remote bool; 13 tests
- Phase 1.3: WTTJ field enrichment — _search_wttj_algolia() returns list[RawJob]; captures remote_type, locations_structured (raw offices[]), country/city from first office, experience_min/max, language, source_category; 15 tests
- Phase 1.4: ATS field enrichment — _fetch_greenhouse/lever/ashby() return list[RawJob]; Greenhouse: departments[] names; Lever: departments from categories.department, team from categories.team; Ashby: department, team fields; 18 tests
- Phase 1.5: Pipeline wiring — main.py uses attribute access (j.id) for merge; _to_dicts() shim converts list[RawJob]→list[dict] before prefilter; 8 tests
- GATE Phase 1 (closed): 310 agent tests passing (1 pre-existing failure); patterns/scraper.md updated
- Phase 2.1: merge_jobs() — agent/merger.py; SOURCE_RANK + FIELD_GROUPS + FIELD_TO_GROUP; description prefers longer plain text over HTML; list fields (departments, locations_structured, emails) unioned; sources list tracks all contributing sources; 22 tests
- Phase 2.2: Wire merge_jobs() into main.py — all_raw collects all scrapers, merge_jobs() replaces set-based dedup, _to_dicts() shim retained for downstream dicts
- Phase 2.3: Smart description merge — _merge_description() in merger.py; prefers plain text over HTML, then longer; integrated into Phase 2.1
- GATE Phase 2 (closed): 332 agent tests passing (1 pre-existing failure); merger.py documented in project structure
- Phase 3.1: preseed_parsed() — agent/preseed.py; maps job_level→seniority, remote_type→location_type, structured salary (direct_data only), company_industry/source_category→domain, experience_min/max, locations_structured→locations_mentioned; returns only non-null fields; 35 tests
- Phase 3.2: Parser pre-seed integration — parser.py calls preseed_parsed() before LLM; seed appended to system prompt; _FACTUAL_FIELDS (seniority, salary_mentioned, location_type, years_experience_min/max, locations_mentioned) override LLM; interpretive fields (domain, skills, etc.) use LLM; divergences logged at INFO; 9 tests
- GATE Phase 3 (closed): 376 agent tests passing (1 pre-existing failure); preseed.py + parser.py documented in project structure
- Phase 4.1: Migration 019 — adds 14 enriched columns to jobs table: company_url, company_logo, company_industry, company_size, job_level, salary_min, salary_max, salary_currency, salary_interval, salary_source, country, city, remote_type, sources (JSON array); 1 test
- Phase 4.2: Ingest enriched fields — upsert_job() persists all 14 new columns from raw dict; COALESCE on conflict preserves richer existing data for all enriched fields (sources always updated); ingest.py extracts from raw: salary via min_amount/max_amount, company_size from company_employees_label; 10 tests
- Phase 4.3: Expose enriched fields in API — get_jobs() CTE includes all enriched columns; list + detail endpoints parse sources JSON→list; null enriched fields omitted from response; 10 tests
- GATE Phase 4 (closed): 562 backend tests + 376 agent tests passing (1 pre-existing failure); enriched pipeline end-to-end: scrape→merge→preseed→parse→ingest→DB→API

Phase 17 — Decomposed Hybrid Scoring (complete: 17.1–17.7)
- Phase 17.1 — Parser + DB + Ingest: role_function enum
  - Parser prompt v1.4: emits role_function (product|engineering|design|data|marketing|sales|ops|support|other)
  - DB migration 017: role_function column on jobs table, backfilled from parsed JSON
  - Ingest: extracts role_function from parsed, writes to jobs.role_function; upsert_job handles missing key defensively
  - Note: plan referenced migration 016 for role_function but 016 was already taken by waitlist index; used 017 instead; scoring grades will use 018
- Phase 17.2 — Scoring rubric v2 + grade mapping
  - scoring-rubric-v2.md: LLM returns technical_depth + profile_evidence as A/B/C grades; no score_breakdown
  - scorer.py updated: reads rubric v2, max_tokens 800, parses categorical grades
  - api/grade_mapping.py: grade_to_points() — A→20, B→12, C→5, None→10 (midpoint)
  - Old rubric archived as scoring-rubric-v1.md; schemas/scored_job.json + patterns/scorer.md updated
- Phase 17.3 — DB + Ingest: grade storage
  - Migration 018: technical_grade TEXT, profile_grade TEXT, scored_v2 INTEGER NOT NULL DEFAULT 0 on user_job_scores
  - Ingest: v2 detection via rag.get("technical_depth") is not None; v2 stores grades + scored_v2=1, score=0; v1 stores numeric score unchanged
  - queries.py: upsert_user_job_score() accepts technical_grade/profile_grade/scored_v2 params; get_jobs() returns all three columns
- Phase 17.3.4 — Reparse + rescore script for v1→v2 migration
  - agent/scripts/reparse_rescore.py: fetches active jobs from local cache (excludes applied/dismissed via applied.yaml), re-parses with parser v1.4 (adds role_function), re-scores with rubric v2 (technical_depth + profile_evidence), ingests to Railway DB, refreshes local cache
  - --dry-run flag: prints eligible job count + cost estimate (~$0.041/job) without making API calls
  - Usage: cd agent && ../venv/bin/python scripts/reparse_rescore.py --profile juan [--dry-run]
  - agent/tests/test_reparse_rescore.py: 6 tests (dry-run, applied filter, empty cache, Railway POST)
  - GATE 17.3 (closed): DB stores grades ✓ · ingest handles v1+v2 ✓ · queries return grades ✓ · reparse/rescore script ✓ · all tests pass ✓
- Phase 17.4 — hybrid_score() + wiring
  - api/scoring.py: hybrid_score() = heuristic_score() + grade_to_points(technical_grade) + grade_to_points(profile_grade), clamped [0,100]
  - api/routes/jobs.py: scoring priority: v2 (scored_v2=1) → hybrid_score with grades; v1 (ujs_score present) → stored RAG; unscored → hybrid_score with defaults
- Phase 17.5 — role_function gate
  - hybrid_score(): -15 penalty when profile.role_function AND parsed.role_function both set and differ (case-insensitive)
  - get_jobs() CTE: selects j.role_function from jobs table
  - agent/prefilter.py: prefilter_jobs() accepts profile_role_function param; soft gate filters jobs where both sides have role_function and they mismatch; stats["role_function_mismatch"] counter
- Phase 17.6 — Profile fields + onboarding
  - api/scoring.py: load_profile_data() returns role_type and role_function from target block
  - juan.yaml: role_function: product; noura.yaml: role_function: product, role_type: "Director of Product"
  - api/prompts/onboard-extraction.md (+ agent copy): added role_type and role_function to schema + field rules
  - api/onboard_utils.py + agent/onboard.py: _build_profile_yaml() includes role_type and role_function in target block when present
  - web/src/components/ProfileEditor.tsx: role_type text input + role_function dropdown (9 values); wired to save; ROLE_FUNCTION_LABELS uses distinct labels to avoid DOM text collision with domain chips
- Phase 17.7 — Regression test suite
  - tests/test_scoring_regression.py: 9 tests across 3 classes
  - 17.7.1 TestEAGamingRegression: gaming=-20 profile + gaming job → score < 55; gaming=+10 → score > 70; hate < like
  - 17.7.2 TestPMMismatchRegression: product+marketing job scores 15 pts less than product+product job; penalty absent when no profile RF
  - 17.7.3 TestCrossUserDifferentiation: Juan (data=15, kafka/flink) scores ≥10 pts higher than Noura (saas=15) on a data PM role
- Phase 18 — Profile Data Integrity (2026-02-27)
  - 18.1: `merge_profiles()` pure function + `compute_diff()` in `api/profile_merge.py`; 20 unit tests
  - 18.2.1: GET /profile fix — role_type, role_function, track returned; exclude_companies read from YAML root (bug C5)
  - 18.2.2: PATCH /profile fix — role_type, role_function, track written to YAML; exclude_companies in prefs gen from root
  - 18.2.3: add_skill ruamel fix — preserves YAML comments (was destroying them with yaml.dump, bug C6)
  - 18.2.4: Frontend — track dropdown in ProfileEditor (IC/Management); role_type/role_function in TypeScript Profile interface
  - 18.3.1: PATCH /api/onboard/replace-cv endpoint — server-side additive merge with diff return; replaces destructive client-side overwrite
  - 18.3.2: Extracted `_yaml_to_flat_profile()` + `_apply_flat_to_yaml()` helpers — eliminate 3x duplicated field mapping (root cause of A1)
  - 18.4.1: Frontend ProfilePage wired to new replace-cv endpoint (generate-profile → replace-cv → show diff)
  - 18.4.2: CVReplaceSummary component — read-only diff view with new/existing skills + domains, updated fields
  - 18.5.1: Track integration tests — `tests/test_profile_track.py`; 4 tests verifying track change regenerates searches with correct titles
  - 18.6.1: PostHog event `profile_cv_replaced` (skills_added_count, domains_added_count, fields_updated)
  - 18.6.2: E2E regression tests — `tests/test_profile_e2e.py`; 12 tests covering all write paths and C5 regression
  - GATE 18.6 (closed): 598 backend tests passing

Phase 15 — Geo Filtering (complete: 2026-02-27)
- 15.1: resolve_location_country() + derive_target_countries() in geo.py (both copies); geonamescache + country-converter + US state abbrev detection; 15 tests
- 15.2: Regression baseline with synthetic fixtures (15 GEO_TEST_JOBS in fixtures/geo_test_jobs.py); 9 tests documenting before/after behavior
- 15.3: WTTJ partial-remote tightening — _build_geo_filter() excludes partial-remote from non-target countries; Algolia filter: target_country OR fulltime OR partial-in-target; 5 tests
- 15.4: ATS scraper geo filtering — _is_geo_allowed() + run_watchlist_scraper(target_countries) returns tuple[list[RawJob], int]; 8 tests
- 15.5: Unified _is_non_target_geo() in prefilter.py — replaces _is_us_only + _is_non_target_onsite; 3-layer detection (L1=location, L2=city in description, L3=US signals); prefilter_jobs() accepts target_countries; 443 tests
- 15.6: Glassdoor added to LinkedIn searches in juan-searches.yaml; merger enrichment stats logged after merge_jobs()
- 15.7: Geo stats in pipeline summary — geo_rejected_at_scrape + geo_rejected_at_prefilter + geo_passed; structured geo_filter_stats log event
- 15.8: PostHog per-job geo filter tracking — _is_non_target_geo() returns 3-tuple (rejected, country, filter_layer); geo_filter_applied per-job event + geo_filter_run_stats aggregate event in main.py
- 15.9: End-to-end wiring — main.py derives target_countries via derive_target_countries(home_locations); passes to ATS scraper, WTTJ scraper, prefilter_jobs(); 8 integration tests (TestEndToEndGeoFiltering); 458 agent tests passing (1 pre-existing scorer failure)
- GATE 15.9 (closed): all gate conditions verified; _is_us_only + _is_non_target_onsite removed; all filters profile-aware; PostHog events per-job + aggregate

Phase 20b — Email Digest API Architecture (complete: 2026-03-01)
- GET /api/digest/{profile_id}: new endpoint in api/routes/digest.py (X-Ingest-Key auth, same scoring as list_jobs)
- Step 10b: _sync_to_railway() in agent/main.py POSTs to /api/ingest before email (wakes Railway, ensures today's data)
- notifier.py rewritten: fetch_digest() + _flatten_api_job() + _format_salary() + _build_context_from_api(); zero scoring logic
- Eliminated: dual scoring, tier threshold divergence (was 50/30 vs 60/40), _is_reloc(), all from-main-import, _sort_key()
- Removed strength/gap from template: list API doesn't return; old values were inconsistent with RAG output
- API parity: 2 parity tests verify score/tier identical between digest and web list_jobs(period='today')
- GATE 20b: 659 backend tests + 523 agent tests passing (1 pre-existing scorer failure)

Scoring data extraction (complete: 2026-03-01)
- Scoring data extraction: pure data constants in shared/scoring_data.py, logic in shared/scoring_core.py (~370 lines). Re-exports preserve all import paths.
- GATE: 692 backend tests + 429 agent tests passing (1 pre-existing scorer failure); scoring_core.py ~370 lines; no import path broken.

Phase Staging — Staging Environment (complete: 2026-03-01)
- Config: `ENVIRONMENT`, `PROD_API_URL`, `DB_EXPORT_API_KEY`, `LLM_MODEL_PARSING`, `LLM_MODEL_SCORING` in `api/config.py`
- Middleware: `api/middleware/staging.py` — `StagingGateMiddleware` returns 403 for non-admin users when `ENVIRONMENT=staging`
- Export: `GET /api/admin/db-export` (X-API-Key auth) — streams live SQLite database as download
- Import: `POST /api/admin/db-import` (admin auth) — downloads prod snapshot, validates SQLite magic, atomic replace
- Snapshot: `api/db/snapshot.py` — shared `download_prod_snapshot()` used by both import endpoint and startup
- Auto-seed: startup downloads prod DB when `ENVIRONMENT=staging` + DB file missing + both secrets set
- Frontend: `StagingBanner` in `App.tsx` (amber, shows when `VITE_ENVIRONMENT=staging`)
- Admin UI: staging-only "Refresh from production" button in `AdminPage.tsx` (amber section, POST `/api/admin/db-import`)
- Tests: `tests/test_db_export.py` (4), `tests/test_db_import.py` (5), `tests/test_startup_autoseed.py` (5) — 717 backend tests total

Master CV JSON — Multi-source career history (complete: 2026-03-02)
- Phase 1: Parser v1.5 fields → `role_in_plain_english`, `company_stage`, `company_tone` extracted to real DB columns (migration 020); exposed in list + detail API; TypeScript types updated
- Phase 3.1: `shared/master_cv_scoring.py` — `build_scoring_context(master_cv, job)` → skill evidence + recent roles context string (≤6000 chars / ~1500 tokens)
- Phase 3.2: `score_job()` + `score_all()` in `agent/scorer.py` — `knowledge_dir` param reads `master_cv.json`, injects enriched context before LLM call; non-fatal fallback
- Phase 3.3: `build_scoring_context()` gains `query_fn: Callable | None` — ChromaDB semantic gap detection; distance ≤ 0.5 → evidence; > 0.5 → `[GAP]` marker; without `query_fn`: backward-compat "No evidence" (no marker)
- Phase 4: CV generation from Master CV JSON — `api/cv/select.py` (ChromaDB-ranked work entry selection), `api/cv/render.py` (selection → markdown), `api/cv/rewrite.py` (narrow LLM rewrite, tone/emphasis only); wired into `generate_cv_endpoint()` with legacy fallback; `X-CV-Plan` response header
- Phase 5 (UI): `web/src/types/masterCv.ts` (full TS schema), `AddSourceModal` (file + paste → POST /api/onboard/add-source), `AddEntryModal` (work/project, highlights, skills autocomplete → POST /api/onboard/add-entry), `ProfilePage` career history section with source badges, `OnboardPage` LinkedIn guidance card
- GATE: 841 backend tests + 601 agent (5 skipped) passing


Parser Enrichment + CV Pipeline Optimization (complete: 2026-03-02)
- Phase 1: Parser v1.5 — 4 new fields: `role_in_plain_english`, `company_context` (stage/tone/what_they_value), `verbatim_for_cv`, `truly_required`/`preferred_skills` split; backward compat for `must_have_skills`/`nice_to_have_skills`; schemas/parsed_job.json updated
- Phase 2: DB migration 020 (role_in_plain_english, company_stage, company_tone columns); ingest + API expose new fields; TypeScript types updated; null-omit pattern
- Phase 3: CV gen refactored — plan-aware prompt uses parsed distillation (~450 tokens) instead of raw JD (~3-5K tokens); profile target context injected; plan.py uses v1.5 field names; A/B validation script
- Phase 4: JobDetailPage self-sufficient — role_in_plain_english + company_context badges; split Required/Preferred skills; "Keywords to match" with CV presence check; raw JD collapsed
- Phase 5: Scorer rubric v2.1 — `requirement_evidence_map` (5 entries max) + `cv_strategy` fields; plan.py consumes scorer enrichments; UI shows "Your fit — by requirement" + CV strategy above Generate CV button
- GATE: 716 backend tests + 598 agent tests passing; TypeScript clean; no breaking changes for old jobs

Career History UX — Async CV processing (complete: 2026-03-02)
- Phase 1: Bug fixes — replace-cv persists master_cv_json; frontend payload sends extracted_profile + master_cv_json separately; add-source accepts JSON text body (`{"text": "..."}`)
- Phase 2: Async processing via BackgroundTasks — migration 022 (cv_processing_status + cv_processing_result + cv_processing_started_at columns on users); `set/get_cv_processing_status` query helpers; replace-cv and add-source both return 202 immediately; background task wrapper (`_bg_safe_*`) guarantees status="failed" on unhandled exceptions; 5-minute timeout guard in GET /profile; `POST /api/onboard/accept-merge` clears processing state
- Phase 3: Unified CV input flow — Replace CV separate flow removed from ProfilePage; AddSourceModal routes .docx uploads through replace-cv (upload-cv → generate-profile → replace-cv) for full profile merge + diff; .pdf and paste text go through add-source; ProfilePage layout refactored with career history as primary section
- Frontend: Polling (5s) while processing; amber banner for "processing", red banner for "failed"; CVReplaceSummary shown from cvProcessing.result.diff when done
- Tests: `tests/test_replace_cv_async.py` (5), `tests/test_add_source_async.py` (5), `tests/test_cv_processing_status.py` (new), `tests/test_add_source_text.py` (updated 200→202), `tests/test_replace_cv_master.py` (updated 200→202), `tests/test_profile_e2e.py` (updated 200→202), `tests/test_onboard_add_source_api.py` (updated 200→202)
- GATE: 892 backend tests passing

### Pending
- Phase N — Onboarding UX for new profile fields (role_type, geography, searches, preferences)
- Phase R — Refactor & Test Coverage
- Phase F — Ship: Dockerfile, README, deploy

### Decisions
- Staging gate middleware (Phase Staging): `StagingGateMiddleware` is registered after `CorrelationIdMiddleware` so the correlation ID is already set when 403 is returned. Non-admin users on staging see 403 on every request. Admin users and health check routes pass through. `/api/health` is whitelisted (no auth check).
- Staging DB snapshot (Phase Staging): `download_prod_snapshot()` re-raises `httpx.TimeoutException` so the admin route can return 502 (upstream unreachable) vs 400 (bad response). Startup auto-seed catches all exceptions so a failed download never aborts startup.
- DB export authentication (Phase Staging): uses `X-API-Key` header (same `DB_EXPORT_API_KEY` as `INGEST_API_KEY` pattern) rather than admin session cookie — the staging service needs to call it without a browser session.
- Parser enrichment strategy (2026-03-02): parser is single point of leverage — one prompt change cascades to scorer, CV gen, UI without new LLM calls. New fields: `role_in_plain_english` (daily-activity summary), `company_context` (stage/tone/values), `verbatim_for_cv` (exact phrases to mirror in CV), `truly_required`/`preferred_skills` (replaces must_have/nice_to_have). Backward compat: all consumers use `get("truly_required") or get("must_have_skills") or []` pattern so old cached jobs continue to work.
- Master CV JSON scoring injection (2026-03-02): `score_job()` reads `master_cv.json` from `knowledge_dir`, calls `build_scoring_context()` to produce ≤6000-char evidence string, appends to LLM user prompt. Non-fatal: any exception falls through to scoring without enrichment. `score_all()` propagates `knowledge_dir` to all workers.
- Master CV CV generation pipeline (2026-03-02): `select_cv_content()` uses ChromaDB `query_similar_work()` + `query_similar_highlights()` to rank work entries by semantic distance to job description. `render_cv_markdown()` converts selection to markdown. `rewrite_cv_content()` calls `generate_cv()` (LLM) to adapt tone/emphasis only — no fabrication, no removal. Falls back to `render_cv_markdown()` output on any LLM error. `generate_cv_endpoint()` tries Master CV pipeline first; falls back to legacy `build_cv_plan()` path on any exception.
- `X-CV-Plan` header (2026-03-02): `generate_cv_endpoint()` returns `{"entries":[{id,company,relevance}],"skill_intersection":[...]}` in `X-CV-Plan` response header when Master CV pipeline succeeds. Enables client-side transparency about which work entries were used.
- CV prompt token reduction (2026-03-02): plan-aware prompt replaced raw JD (~3-5K tokens) with parsed distillation (~450 tokens): role_in_plain_english + truly_required + preferred_skills + verbatim_for_cv + company_context + key_phrases. Reference files (generate-cv.md, ats-rules.md) removed from plan-aware path — content already captured in _OUTPUT_CONTRACT. Token reduction ~40% on the expensive Sonnet call. Legacy path (no plan) unchanged.
- Scorer v2.1 enrichments (2026-03-02): `requirement_evidence_map` (max 5 entries: requirement→evidence→cv_bullet_hint) + `cv_strategy` (3 sentences). Cost ~200 extra output tokens per score. plan.py uses `_enrich_allocation_from_evidence()` to add cv_hints to bullet_allocation entries when company name appears in evidence text. Graceful: both fields optional — old scores without them work identically.
- Two requirements files — NEVER add an api/ dep to only one (2026-03-02 incident × 3): `requirements.txt` is for local dev + CI tests. `requirements-web.txt` is what the Dockerfile installs. They are NOT kept in sync automatically. Any new `import X` at module level in `api/` MUST be added to `requirements-web.txt`. CI now validates this via the `web-image-check` job (`pip install -r requirements-web.txt && python -c "from api.main import app"`), which gates the deploy job.
- Dockerfile must copy shared/ (2026-03-01 incident): Railway uses the repo Dockerfile, not Nixpacks. When Phase R added `shared/scoring_core.py`, the Dockerfile only copied `api/` and `agent/` → `ModuleNotFoundError: No module named 'shared'` on every startup. Fix: `COPY shared/ ./shared/` in Stage 2. Diagnosis via `railway logs --deployment <id>`.
- Railway V2 startCommand does NOT shell-expand variables (2026-03-01 incident): `startCommand = "uvicorn ... --port $PORT"` in railway.toml passes `$PORT` literally → uvicorn error "invalid value for '--port': '$PORT'". The Dockerfile CMD calls `startup.sh` which uses `exec uvicorn ... --port "${PORT:-8000}"` (bash expands it correctly). Never add startCommand back to railway.toml.
- pyproject.toml must NOT have [project] section (2026-03-01 incident): Nixpacks would have tried `pip install .` but the container uses Dockerfile, not Nixpacks. Keeping only `[tool.ruff]` config in pyproject.toml is correct. PYTHONPATH=${{ github.workspace }} in GHA handles CI import resolution for `shared/`.
- Email digest platform links (Phase 20): uses job_id hash directly (same identifier used by DB WHERE job_id=? and frontend /jobs/:jobId). No integer PK lookup needed. APP_BASE_URL env var (default: Railway production URL). Falls back to external job_url if job_id missing.
- Email digest rebrand (Phase 20): accent color changed from orange (#e97316) to violet (#8b5cf6) to match web app. "JobAgent" retired everywhere (subject, sender From header, template). Platform links preferred over external URLs.
- Digest dark mode (Phase 20): template is dark-first (zinc-950 bg). Added color-scheme meta + @media prefers-color-scheme for Apple Mail/iOS. Gmail strips <style> but renders inline styles correctly. Outlook renders table layout with inline styles.
- Digest rollback (Phase 20): v1 template preserved as email_digest_v1.html.j2. DIGEST_TEMPLATE env var selects template filename. Default: email_digest.html.j2 (v2). Toggle: set DIGEST_TEMPLATE=email_digest_v1.html.j2 for instant rollback.
- No unsubscribe link (Phase 20): deferred until notification preferences exist in /profile. A dead link erodes trust more than no link.
- Email digest architecture (Phase 20b): agent does POST /api/ingest (Step 10b), then GET /api/digest/{profile_id} (Step 11). Same code path as list_jobs(period="today"). If API unreachable, email skipped. No local fallback (reintroduces drift). Trade-off: email depends on Railway uptime. Acceptable.
- Strength/gap removed from email (Phase 20b): list API doesn't return. Old values were inconsistent with RAG output anyway. Clean removal.
- httpx over requests (Phase 20b): httpx already in requirements.txt root (0.28.1). requests only in agent/requirements.txt. Avoids implicit transitive dependency.
- Digest rollback v2 (Phase 20b): v1 template is reference-only. It requires variables (strength, gap, local scores) that the new notifier doesn't produce. Full rollback = git revert of all 20b commits. DIGEST_TEMPLATE env var no longer provides true rollback.
- first_seen filter limitation (Phase 20b): jobs discovered by user A yesterday and re-ingested today for user B have first_seen=yesterday → excluded from "today" digest in both email and web. Consistent but functionally incomplete. Fix: consider last_seen or ingested_at filter.
- Repo cleanup (2026-02-27): Plan files moved to Planes/ (gitignored). Merged worktrees pruned (amazing-austin, competent-neumann, suspicious-jones, trusting-montalcini). Dead code removed: UserMenu.tsx component, update_user_profile_id() function in queries.py. Ruff clean. File copy consistency audited (see docs/copy-sync-report.md) — all dual copies in sync.
- Geo filtering architecture (Phase 15): three-layer detection chain. L1=resolve_location_country() on structured location field (highest confidence). L2=geonamescache city mention in description near context words ("based in", "office in" etc). L3=US visa/auth language ("e-verify", "remote within the us", "must be authorized to work in the u.s"). Conservative: unresolved location + no signals → pass. Remote fulltime always passes regardless of location. "nan" added to sentinel pass-through list (geonamescache resolves it to "CN" via city name match).
- Geo filter layer tracking (Phase 15): _is_non_target_geo() returns 3-tuple (rejected, country, filter_layer). filter_layer: "prefilter_location" | "prefilter_description" | "prefilter_signal" | None. Stored as job["_geo_layer"] for PostHog tracking. PostHog events: geo_filter_applied (per-job) + geo_filter_run_stats (aggregate per pipeline run).
- target_countries derivation (Phase 15): main.py calls derive_target_countries(home_locations) before Step 1b. Passed to ATS scraper, WTTJ scraper (replaces wttj_countries profile field), and prefilter_jobs(). Fallback: uses wttj_countries from profile if home_locations don't resolve to any country.
- ATS scraper return type (Phase 15): run_watchlist_scraper() returns tuple[list[RawJob], int] — second element is total_geo_rejected count for pipeline stats. patterns/scraper.md updated.
- WTTJ geo filter (Phase 15): _build_geo_filter() builds Algolia filter including only target countries + fulltime remote + partial-in-target. Partial remote from non-target countries excluded at scrape time. Aligned with derive_target_countries() output.
- WTTJ geographic filter (Phase 0.1): offices.country_code is a filterable Algolia attribute (verified live). Filter: PM_filter AND (country_code:X OR ... OR remote:fulltime OR remote:partial). target_countries explicit list in profile YAML (not derived from country_weights to avoid name→ISO complexity). Default: [ES] + remote.
- make_job_id migration (Phase 0.2): ID hash changes mean new IDs for existing jobs. Chosen option A: accept one-time re-run cost. Clear seen_ids/<profile>.txt after deploy. migrate_job_ids.py handles SQLite in-place UPDATE; collision resolution keeps record with more non-null parsed fields.
- nan sanitization (Phase 0.3): _sanitize_str() in scraper.py handles float NaN, None, and string literal 'nan'. Applied to all string fields in run_scraper(). ats_scraper.py and wttj_scraper.py already avoided this via explicit str() conversion, but wttj already had proper handling.
- Non-target geo rejection (Phase 0.3): limited value until Phase 1 adds structured country field (currently ~75% empty locations). Filter conservative: empty/unrecognised location → pass. ~30 EU/major country fragments in _COUNTRY_FRAGMENTS dict. reject_if_requires_relocation_outside read from preferences YAML.
- Smoke test (Phase 0.4): uses AGENT_OUTPUT_DIR env var (defaults to agent/output/). Skips when no files present. pytest.ini in agent/ registers 'smoke' marker.
- reparse_rescore.py (Phase 17.3.4): reads from local `output/cache.json` (not Railway API — no auth-free "get jobs" endpoint exists). Excludes jobs listed in `applied.yaml` (covers both applied and auto-skipped). Cost estimate = n_jobs × $0.041 (parse $0.001 + score $0.040). Ingests to Railway via `POST /api/ingest` with `X-Ingest-Key`. Also refreshes local cache so next run uses v2 data immediately.
- react-router v7 uses `react-router` package (not `react-router-dom`)
- `vitest/config` required in vite.config.ts to fix TypeScript `test` key error
- Test files excluded from tsconfig.app.json to avoid TS errors on `global`
- Auth: Google OAuth via authlib, session token in HTTP-only cookie, `get_current_user` FastAPI dependency on jobs router
- LoginPage uses `<a href="/api/auth/login">` (not a button) — tests must use `getByRole('link', ...)`
- API decoupled from agent: `api/geo.py` and `api/onboard_utils.py` are self-contained copies — no sys.path hacks, no `_load_jobagent()`. If shared logic changes, update both copies. `api/prompts/onboard-extraction.md` is also a copy of `agent/prompts/onboard-extraction.md`.
- Run backend tests from project root (`~/Proyectos/jobsearch/`), not from `web/`
- openai added to requirements.txt (needed because jobagent/onboard.py imports it at module level)
- Users with `profile_id: null` are redirected to `/onboard`; test mocks must include `profile_id: 'user'`
- PyYAML available in venv via jobagent dependency — not in requirements.txt but importable as `import yaml`
- YAML profile (jobagent format) is nested: `user.{name,email,home_locations}`, `target.{domains,seniority}`, top-level `skills`. ProfileEditor expects flat format — normalize in `GET /api/onboard/profile`
- Dev session: insert token `dev-jsk-juan` in sessions table; inject cookie via `document.cookie = "jsk=dev-jsk-juan; path=/"`
- CV generation: POST /api/jobs/{id}/generate-cv → plan (deterministic) → LLM (anthropic/openai) → validate → fix (if errors) → python-docx .docx → FileResponse. Headers: X-ATS-Audit, X-CV-Validation, X-CV-Fix-Applied.
- Plan builder (api/cv/plan.py): company_type heuristic from consultancy/in_house keyword signals; location→language map (Paris→French, Berlin→German etc); known-tools filter for key_tools; dimension score ≥16 "high", ≥10 "medium", <10 "low"; earliest PM-role year → years_experience bucket; bullet budget capped at 12 total.
- Validator slop blacklist: "strong track record", "proven ability", "passionate about", "results-driven", "data-driven leader", "leveraging", "utilizing" + more. Gerund-start bullet detection with regex.
- strip_analysis() in llm.py: auto-strips <analysis>...</analysis> from LLM output so prompt.py and endpoint never see chain-of-thought content.
- `save_profile` guard: if `user.profile_id` exists → only write `cv.md`, never regenerate YAML. First-time onboarding (no profile_id) still does full YAML generation.
- Hamburger menu (`HamburgerMenu` component in `App.tsx`) replaces inline nav links; dropdown closes on outside click via `mousedown` listener + `useRef`
- ProfileEditor: `addDomain` adds with weight 10; `removeDomain` deletes key from state; `addSkill`/`removeSkill` mutate array. Enter key supported on both inputs.
- OnboardPage must pass `isNew` to ProfileEditor so first-time save uses POST `/save-profile` (creates YAML) instead of PATCH `/profile` (requires existing profile_id).
- jobagent parser v1.1 (2026-02-23): `must_have_skills` is now technical-only. Soft skills / years of experience / education requirements moved to `experience_requirements` field.
- Per-user scoring: `jobs` table stores shared data only (no score/tier/scored). Per-user RAG scores in `user_job_scores(user_id, job_id, score, tier, scored, scored_at)`. Heuristic scores computed at query time — never stored. Migration `005_user_scores.sql` recreates jobs table.
- Ingest stores per-user scores only when `profile_id` is provided AND the job has a `rag_score` with a non-null `score` value.
- Onboarding triggers pipeline: `save_profile()` (first-time only) pushes files to GitHub repo via Contents API and fires `workflow_dispatch`. Requires `GH_ACTIONS_TOKEN` (PAT with contents:write + actions:write), `GH_REPO`, `GH_REF`.
- cv_md persistence: saved in `users.cv_md` (migration 006) on `POST /save-profile` and opportunistically on `GET /profile`. Guard: empty cv_markdown is never written to DB.
- profile_yaml persistence: saved in `users.profile_yaml` (migration 007) on first-time save and on every `PATCH /profile`. Restored from DB to disk if filesystem was wiped.
- Admin access: `is_admin` column on users (migration 008). `ADMIN_EMAILS` env var auto-promotes on login. `get_current_admin` dependency in `api/middleware/auth.py`.
- `POST /api/admin/trigger-pipeline`: dispatches `jobagent_daily.yml` workflow via GitHub API. Optional `{"profile": "id"}` body. Requires GH_ACTIONS_TOKEN/GH_REPO/GH_REF.
- Job cleanup: `cleanup_old_jobs(db_path, days=90)` deletes from user_job_scores + user_job_status + jobs. Called on every ingest.
- Cross-user dedup: `agent/api_cache.py` calls `POST /api/ingest/batch-lookup` to fetch already-parsed jobs from Railway DB. Graceful fallback if unavailable.
- GHA sequential pipeline: single `digest` job loops profiles sequentially. Each syncs to Railway before next starts. Jobs: `list-profiles` → `digest` → `persist-seen-ids` → `verify-health`. `timeout-minutes: 60`.
- Embeddings: 256 dims (was 1536). `dimensions=256` param in OpenAI API. Migration 012 clears stale cache.
- Embedding storage: JSON-serialized list[float] in BLOB column. Cache key: lowercase trimmed skill text.
- Semantic thresholds: 0.80 match, 0.68 partial. Tuned on skill synonym pairs (analytics↔data analysis, ML↔machine learning).
- Cosine similarity: numpy (was pure Python). ~1000x faster for batch operations.
- Semantic matching in job list: batch pre-computation via `precompute_skill_lookup()`. One `match_skills` call for all unique job skills, O(1) per-job lookup. Detail view unchanged.
- Embedding backfill: POST /api/admin/backfill-embeddings. Required after deploy.
- Embedding diagnostics: GET /api/admin/embedding-diagnostics. Curl-only, shows similarity scores for threshold tuning.
- Seniority weights: -15 to 15 range, consistent with other sliders.
- Seniority "unknown" key: jobs where parser detects no seniority signal emit `seniority: "unknown"`. Exposed in ProfileEditor as "Unspecified" quick-add button (maps to key `"unknown"` in seniority_weights). Backend already supported it via `.get("unknown", 0)`.
- Partial-match skills clickable in job detail: `isClickable = (status === 'none' || status === 'partial') && !!onClick`. Tooltip shows similarity % for partial. Clicking adds the exact job skill (not the matched user skill) to profile. `onClick` passed for `status !== 'matched'`.
- Prev/next job navigation: `JobsPage` passes `{ state: { jobIds: [...] } }` on navigate. `JobDetailRoute` reads `location.state.jobIds`, computes prevId/nextId, passes to `JobDetailPage`. `onNavigate` uses `replace: true` to avoid stacking history entries (preserves "Back to jobs" behavior).
- `.claude/launch.json` in worktrees: use `bash -c "cd /absolute/path && exec venv/bin/uvicorn ..."` for backend so it runs from the correct CWD (finds DB and config). Frontend: `npm run dev --prefix /absolute/path/web`. Avoids broken relative paths when CWD is a worktree subdirectory.
- POST /api/onboard/profile/skills in onboard router (not separate profile router) — consistent with existing PATCH /profile.
- Domain scoring cascade (Phase 13): enum match → `_infer_domain()` keyword override → `_semantic_domain_score()` embedding fallback. Semantic only fires when both prior stages return 'other'. Threshold: 0.75 cosine similarity. Score clamped [-15, 15].
- Domain enum (Phase 13): 30 canonical values (adtech|ai_ml|automotive|biotech|climate|construction|cybersecurity|data|defense|devtools|ecommerce|edtech|energy|fintech|food_bev|gaming|govtech|healthtech|hr_tech|infra|legal_tech|logistics|manufacturing|marketplace|media|retail|saas|telecom|travel|other). parser-prompt.md v1.3 includes `_domain_guide` field (not in output schema — for LLM guidance only). `_DOMAIN_ALIASES` in both `api/scoring.py` and `agent/main.py` normalize profile domain names to canonical enum values.
- RAG penalty clause (Phase 13): graduated tiers in scoring-rubric.md v1.2; strong (≤-15) → cap domain_fit at 3, mild (<0>-15) → cap at 10; injected via `{penalty_clause}` placeholder by `_build_scoring_prompt()`.
- Heuristic gate (Phase 13): `target_domains` changed from set to dict in `_heuristic_gate()`. Domain weight > 0 → +20 gate credit; weight < 0 → 0 credit; not in dict → 0.
- Domain override cascade (Phase 13): `user_override → _infer_domain() → parsed.domain`. RAG scores NOT invalidated on override. Override stored in `user_job_status.domain_override` (migration 014).
- Domain reparse (Phase 13): `POST /api/admin/reparse-domains` is synchronous — keyword matching is pure Python, <1s even for 500 jobs. Writes `jobs.domain` only; `parsed.domain` is immutable post-ingest.
- Domain corrections query (Phase 13): `GET /api/admin/domain-corrections` uses SQL `COALESCE(json_extract(j.parsed, '$.domain'), 'other')` as the "from" value; excludes overrides that match the parsed domain.
- Domain keyword quality (Phase 13): Every keyword ≥2 words to prevent cross-domain collisions across 29 lists. Exceptions: databricks, snowflake, clickhouse, shopify, woocommerce, kubernetes, terraform (unambiguous brand names). `data` uses `data analytics platform` (not bare `analytics platform`) to avoid fintech false positives.
- PostHog Python SDK (Phase 14): `posthog>=7.0.0` in requirements.txt. `api/analytics.py` is the single module that owns init/capture/identify. Routes import `from api import analytics; analytics.capture(...)` (NOT `from api.analytics import capture`) so that `patch("api.analytics.capture")` works in tests.
- structlog configuration (Phase 14): `api/logging_config.py` and `agent/logging_setup.py` both check `CI=true` or `LOG_FORMAT=json` to emit JSON. Locally uses ConsoleRenderer with colors. All api/ loggers use `structlog.get_logger(__name__)`.
- PostHog AI wrappers (Phase 14): `posthog.ai.anthropic.Anthropic` and `posthog.ai.openai.OpenAI` are drop-in replacements. Pass `posthog_distinct_id` and `posthog_properties` at `.create()` call level (not constructor). `distinct_id` is threaded from the route layer as `str(user["id"])`. No-op when PostHog is not initialised (POSTHOG_API_KEY absent).
- posthog-js frontend (Phase 14): `VITE_POSTHOG_KEY` and optional `VITE_POSTHOG_HOST` env vars. `initPostHog()` called in main.tsx before first render. `identifyUser()` called in AuthContext when `/api/auth/me` returns non-null data. `resetPostHog()` called on logout.
- Agent PostHog events (Phase 14): `_capture()` helper in `agent/main.py` uses a module-level `Posthog` singleton (created on first use). Also sets `posthog.api_key` / `posthog.host` via module-level proxy so `posthog.default_client` is available to `posthog.ai` wrappers in parser.py/scorer.py. Events: `agent_pipeline_start` (profile_id, mode, notify), `agent_pipeline_complete` (profile_id, mode, **status**, duration_s, cost_usd, n_parsed, n_scored, tier_a/b/c). `status` values: `"success"`, `"no_jobs"`, `"all_filtered"`.
- Health check endpoint (Phase 14): `GET /api/health/ready` runs a lightweight `SELECT COUNT(*) FROM jobs` to verify DB connectivity. Returns `{"status":"ok","jobs":N}` or `{"status":"error","detail":"..."}` with 503. Safe to poll every minute from Railway / GHA `verify-health` job.
- PostHog AI singleton (Phase 14): `api/cv/llm.py` hoists `_anthropic_client` and `_openai_client` to module level. Created on first `generate_cv()` call, reused for all subsequent calls. Tests patch `posthog.ai.anthropic.Anthropic` / `posthog.ai.openai.OpenAI` (not the bare provider) and call `importlib.reload()` to reset the singleton between tests.
- Agent LLM observability (Phase 14): `parser.py` and `scorer.py` use `posthog.ai.openai.OpenAI` when `POSTHOG_API_KEY` is set, falling back to plain `openai.OpenAI`. `parser.py` lazy-initialises via `_make_openai_client()` helper (no module-level client). `scorer.py` creates the client per `score_job()` call (same lazy pattern).
- PostHog host (Phase 14 fix): `api/analytics.py` reads `POSTHOG_HOST` from env at init time (default `https://eu.i.posthog.com`). Was previously hardcoded to `us.i.posthog.com` — events were silently dropped. `web/src/analytics.ts` and `agent/main.py` also default to EU. Set `POSTHOG_HOST` / `VITE_POSTHOG_HOST` to override.
- structlog `add_logger_name` (Phase 14 fix): `agent/logging_setup.py` uses `PrintLoggerFactory` (not stdlib). `structlog.stdlib.add_logger_name` requires a stdlib logger with `.name` attr → `AttributeError` on first log call. Processor removed from agent; `api/logging_config.py` is unaffected (uses stdlib processors only).
- Scoring baseline tests (Phase 14 fix): `agent/tests/test_scoring_baseline.py`, `test_home_locations.py`, `test_rubric_parameterization.py` now import `BASELINE_PROFILE` from `agent/tests/fixtures.py` instead of calling `load_profile("juan")`. This decouples regression tests from personal profile tuning — changing `juan.yaml` no longer breaks baselines.
- 500 exception test (Phase 14 fix): `tests/test_analytics.py::test_unhandled_exception_calls_capture_exception` now calls the exception handler function directly instead of adding a dynamic route. Dynamic routes added after app init land behind the SPA catch-all `/{path:path}` and return 200 instead of 500 when `web/dist/` exists.
- Landing page design (Phase 15): Instrument Serif (Google Fonts) for headings only. Background hierarchy: zinc-950 → zinc-900 → zinc-800 (elevation via brightness, not shadows). violet-500 only on CTAs and small highlights. WCAG 2.2 AA: ≥4.5:1 normal text, ≥3:1 large text and UI. No app header on landing.
- MockDashboard (Phase 15): React component with 4 hardcoded anonymized job cards in browser-frame wrapper. Visual patterns from JobCard.tsx. Non-interactive (pointer-events-none), decorative.
- Waitlist form (Phase 15): reusable WaitlistForm component, source prop (hero|bottom) for PostHog segmentation. CSS state transitions. POST /api/waitlist returns 201/409/422.
- Branding (Phase 15): favicon.svg = violet circle. Title = "JobSeeker — Know your fit before you apply". OG meta tags for LinkedIn preview. No OG image yet.
- Copy frozen (Phase 15): all landing page copy defined in plan, not generated by Code.
- Google OAuth in test mode acts as access gate — only invited emails can authenticate. No additional whitelist logic needed.
- IntersectionObserver guard (Phase 15): `useScrollReveal` hook checks `typeof IntersectionObserver === 'undefined'` and falls back to adding `.revealed` class immediately. Avoids jsdom test failures.
- MockJobDetail (Phase 16): expands Card 1 (Head of Product, 91). Breakdown scores adjusted for internal consistency: 24/25 + 19/20 + 17/20 + 17/20 + 14/15 = 91. Lower profile_evidence reflects enterprise sales gap. Same browser-frame + opacity treatment as MockDashboard. Mobile: hide gap, show 1 strength.
- MockCVButton (Phase 16): pure CSS animation, no JS state. 4.5s loop, 3 frames with crossfade. violet-600 button matching JobDetailPage.
- CV callout (Phase 16): compact card (max-w-3xl, rounded-2xl, bg-zinc-900/60), NOT full-width section. 80px vertical margin vs 120-160px for major sections. Two-column desktop, stacked mobile.
- Landing section order (Phase 16): Hero → MockDashboard → MockJobDetail → CV callout → How it works (4 steps) → Bottom CTA → Footer.
- Eyebrow "Behind the score" (Phase 16): neutral, advances narrative. Avoids defensive framing.
- Scoring parity (2026-02-26): `_score_single_job()` helper shared by list and detail endpoints. Three branches: v2 hybrid (LLM grades + `hybrid_score()`) → v1 RAG (stored score unchanged) → unscored (`hybrid_score()` with default +20 neutral grades + relocation penalty). See `docs/scoring-parity-postmortem.md` for root causes and architectural fixes needed.
- Global skill_lookup removed (2026-02-26): batching all unique job skills at once (300+) exceeded the 500-pair embedding limit → silent substring fallback → inflated scores. Both list and detail now score per-job via `db_path` using the SQLite embedding cache. Consistent, semantically correct.
- `remote_restriction` injection (2026-02-26): `get_job_by_id()` uses `SELECT *` which has no `remote_restriction` column (only computed via `json_extract` in `get_jobs()`). Injected from `parsed` dict after JSON-parsing in `get_job()`. Architectural fix: add as a real DB column in a future migration.
- Scoring parity rule: scoring functions must never read fields that differ between `get_jobs()` CTE and `SELECT * FROM jobs`. Only fields from `parsed` (JSON blob) or real DB columns are safe. See `docs/scoring-parity-postmortem.md`.
- Enriched field naming (Phase 4): DB column is `company_size` (plan name); raw dict field is `company_employees_label` (RawJob model name). Ingest maps `company_employees_label → company_size` at upsert_job boundary.
- Enriched upsert strategy (Phase 4): COALESCE(excluded.field, jobs.field) for all enriched scalar fields — new value wins if non-null, existing value preserved if new is null. `sources` (JSON array) always updated — reflects scraper origins from the current pipeline run, not accumulated history.
- Enriched API null omission (Phase 4): `_ENRICHED_FIELDS` constant in list_jobs and get_job strips keys where value is None. Prevents sending `"company_industry": null` for every job that has no industry data.
- `_grade_to_points()` in agent (P16 fix): added to `agent/main.py` as module-level helper, mirrors `api/grade_mapping.py:grade_to_points()`. Used by `ranked_jobs()`, `_auto_skip_reloc()`, and `notifier._build_context()`. If grade thresholds change, update both copies.
- v2 `_display_score` logic: three branches in all three scoring sites — `rag is None` → heuristic; `"score" in rag` (v1) → stored numeric; else (v2) → `min(100, max(0, _fit_score + grade_to_points(tech) + grade_to_points(prof)))`.
- Gap tracker v2 score (P17 fix): `gap_tracker.py` uses inline `_gp` dict (not imported from main to avoid circular import). v2 score = sum of grade points only (no heuristic component — profile not available at Step 5b). Ranges: A+A=40, B+C=17, unknown+unknown=20.
- `print_summary()` mode label (P18 fix): `has_v2 = any("technical_depth" in (j.get("rag_score") or {}))`. v2 takes priority: "hybrid score" > "RAG score" > "heuristic fit".
- `merge_profiles()` pure function (Phase 18): takes `existing: dict` + `extracted: dict`, returns merged dict. No I/O, no YAML, no DB. Skills: union, case-insensitive dedup, existing order preserved. Domains: existing weights win for shared keys. Weights (seniority/country/company_type): existing preserved if non-empty. Factual (name, email, languages, home_locations): new wins. role_type, role_function: new wins if non-null/non-empty. track: new wins if non-null. exclude_companies: union, dedup.
- Server-side merge for CV Replace (Phase 18): `PATCH /api/onboard/replace-cv` loads existing profile, calls `merge_profiles()`, saves merged YAML + cv.md before returning. Frontend shows read-only diff from `compute_diff()` return value. Eliminates race conditions and ensures profile is always saved before user sees the diff.
- `_yaml_to_flat_profile()` / `_apply_flat_to_yaml()` (Phase 18): extracted helpers in `api/routes/onboard.py` to eliminate 3x duplicated YAML→flat normalization. `_yaml_to_flat_profile(raw)` normalizes nested YAML (user/target blocks) to flat dict used by merge and scoring. `_apply_flat_to_yaml(raw, flat)` writes flat dict back into ruamel CommentedMap preserving comments. Used by `get_profile()`, `update_profile()`, and `replace_cv()`.
- `exclude_companies` location (Phase 18 / C5 root cause): `_build_profile_yaml()` writes it at YAML root level, not under `user` block. All read paths use `raw.get("exclude_companies")`. Not `raw["user"].get("exclude_companies")`. This was the root cause of C5 — GET returned empty list, prefs gen ignored user exclusions.
- CVReplaceSummary component (Phase 18): replaces full ProfileEditor-in-review-mode pattern. Shows read-only diff: new skills (green, "NEW" badge) + existing skills (gray); new domains + existing; updated factual fields list; preserved weights note. "Looks good" → redirect to /profile.
- Eligibility penalty (Phase 19 / Phase R1): `compute_eligibility_penalty()` returns -20 when job is remote + has restriction + user home not in restriction text. Bypassed for `loc_pref="d"` and pure timezone restrictions (`is_pure_timezone()`). Single source of truth: `shared/scoring_core.py`. Location scoring: geo-restricted remote → +8 if eligible, +2 if ineligible (vs +10 unrestricted). country_weights: `remote` sentinel NOT injected when geo-restricted.
- Tier thresholds (Phase 19): A>60, B>40, C≤40. Previously A≥50, B≥30. Rationale: hybrid scores have wider range (heuristic + up to +40 from grades). Old thresholds made ~40% of jobs tier A; new thresholds restore A/B/C distribution.
- `eligibility_warning` field (Phase 19): `str | None` — the raw `remote_restriction` text when penalty fires; null otherwise. Returned in list and detail API responses. Frontend: red "Not eligible" badge when set; amber "Relocation" badge for `geo_restricted` without eligibility_warning; nothing otherwise.
- `is_pure_timezone()` guard (Phase 19): applied to both `_is_geo_restricted_remote` check and `_compute_eligibility_penalty()` in both api/scoring.py and agent/main.py. Timezone-only restrictions (CET, UTC+2, "EMEA hours") are not country barriers — no penalty, full +10 location bonus.
- Cross-system parity (Phase 19): Two bugs found by regression test `tests/test_eligibility_regression.py`: (1) API `_compute_eligibility_penalty` and `_is_geo_restricted_remote` lacked `is_pure_timezone()` check; (2) agent location block used only `"europe" in restriction` but not full `_HOME_REGIONS` list for eligibility. Both fixed in 19.5.3.
- Auto-search architecture (2026-03-01): `search_titles` in `target:` block is the single source of search intent. `generate_queries(profile)` crosses each title with LinkedIn + Indeed. `generate_unified_queries(profiles)` deduplicates across all active profiles by `(term.lower(), location.lower(), site)`. `main.py` runs unified scraping ONCE, passes `pre_scraped_jobs` to per-profile `run_pipeline()`. `*-searches.yaml` files deprecated (not deleted); `searches:` key removed from profile YAMLs.
- Auto-search site params (2026-03-01): LinkedIn → `results_wanted=15`, `is_remote=False`, `linkedin_fetch_description=True`; Indeed → `results_wanted=25`, `country_indeed` from profile home_locations[1]. Google dropped (JobSpy Issue #302 — consistently 0 results). `LINKEDIN_DELAY_SECS=2` between consecutive LinkedIn queries.
- Auto-search + scoring decoupled (2026-03-01): `search_titles` controls WHAT gets scraped. `seniority_weights`/`domains` control scoring. They are independent. Adding "Product Owner" to search_titles does not affect how Product Owner roles score.
- `onboard.py` generates search_titles (2026-03-01): `_build_search_titles()` derives `["{Level} {role_type}", "{role_type}"]` from extracted fields. Users extend via profile editing.
- Async CV processing (2026-03-02): replace-cv and add-source return 202 immediately; background task runs via FastAPI `BackgroundTasks` (no Redis/Celery). `_bg_safe_*` wrappers guarantee `status="failed"` even when the background function is fully patched in tests. TestClient runs BackgroundTasks synchronously after response — test assertions on DB state are safe immediately after 202.
- cv_processing state machine (2026-03-02): NULL → "processing" (on 202) → "done" | "failed" (after background task). `POST /api/onboard/accept-merge` clears all three columns (sets status=NULL). Timeout guard in `GET /profile`: if status="processing" and started_at > 5 min ago → auto-fail (prevents stuck "processing" banners).
- AddSourceModal routing (2026-03-02): .docx uploads go through upload-cv → generate-profile → replace-cv (3 API calls, full profile merge + diff). .pdf uploads and paste text go through add-source (career history enrichment only). The distinction: .docx is a full CV (profile fields + career history); .pdf/.txt are supplementary sources.
- Frontend cv_processing polling (2026-03-02): `useEffect` with `setInterval(5000)` runs while `cvProcessing.status === 'processing'`. Cleans up on status change. When status transitions to "done" with a `diff`, CVReplaceSummary renders. When status is "failed", dismissible red banner shown. `POST /api/onboard/accept-merge` called when user dismisses diff or banner.

### Known Bugs

### Resolved
- **P22** (2026-02-28) — Agent `_heuristic_score()` location block used only `"europe" in restriction` for eligibility but not `_HOME_REGIONS` — "EU only" gave +2 instead of +8 for EU users. Fixed: now mirrors API's `any(r.lower() in restriction_lower for r in _HOME_REGIONS)` check.
- **P21** (2026-02-28) — API `_compute_eligibility_penalty()` and `_is_geo_restricted_remote` lacked `is_pure_timezone()` check — "CET timezone hours" triggered -20 penalty + +2 location (score 0) instead of +10. Fixed by adding `is_pure_timezone()` guard in both.
- **P20** (2026-02-27) — CV Replace was destructive: `POST /replace-cv` endpoint overwrote existing profile with LLM extraction. Fixed: new `PATCH /replace-cv` does server-side additive merge via `merge_profiles()`; weights/skills/domains from existing profile never lost.
- **P19** (2026-02-27) — role_type, role_function, track not persisting across any write path (A1–A4). Fixed: GET returns them, PATCH reads and writes them, replace-cv preserves them via merge strategy, TypeScript interface includes them.
- **P18** (2026-02-26) — `print_summary()` printed "RAG score" mode for v2 jobs (rag_score dict is truthy but has no numeric score). Fixed: now distinguishes v2→"hybrid score", v1→"RAG score", none→"heuristic fit".
- **P17** (2026-02-26) — `gap_tracker.append_gap_history()` stored `score=0` for all v2 jobs. Fixed: v2 now stores sum of grade points (A+A=40, B+C=17, neutral=20). JSONL history retains LLM scoring context.
- **P16** (2026-02-26) — `ranked_jobs()`, `_auto_skip_reloc()`, and `notifier._build_context()` used heuristic-only for v2 jobs. Fixed: added `_grade_to_points()` to `main.py`; v2 jobs now compute `hybrid_score = _fit_score + grade_to_points(tech) + grade_to_points(prof)` clamped [0,100]. 22 new tests across 3 test files.
- **P15** (2026-02-26) — `notifier._build_context()` crashed with `KeyError: 'score'` on v2-scored jobs. Fixed via `rag.get("score")` with fallback to `_fit_score`, matching the fix already in `ranked_jobs()`. 6 tests added in `test_notifier_v2.py`.
- **P14** (2026-02-26) — List and detail endpoints produced different scores for the same job (diffs 3–20 pts). Root causes: `remote_restriction` absent from `SELECT *`, global skill_lookup triggering substring fallback, divergent scoring paths. Fixed via `_score_single_job()` helper and per-job semantic matching. 0 mismatches across 57 jobs; 541 tests passing.
- **P2** (2026-02-26) — Removed unused `LoginPage` import from `App.tsx`; was breaking production TS build.
- **P1** (2026-02-26) — Appended `'Z'` when parsing `entry.created_at` in AdminPage so UTC timestamps are not mis-parsed as local time.
- **P3** (2026-02-26) — Wrapped WaitlistForm fetch with `AbortController` + 10 s timeout; AbortError surfaces as generic error state.
- **P4** (2026-02-26) — Extended scroll-reveal stagger CSS in `index.css` to `nth-child(6)` (500 ms) and `nth-child(7)` (600 ms).
- **P5** (2026-02-26) — Added in-memory IP rate limiter (5 req/min) to `POST /api/waitlist`; 6th request returns 429.
- **P6** (2026-02-26) — Aligned WaitlistForm email regex with backend by removing `.` from `[^@.]` after `@`; subdomains now accepted.
- **P7** (2026-02-26) — WaitlistForm now shows "Enter a valid email" only for 422; all other non-201/non-409 statuses show "Something went wrong. Try again."
- **P8** (2026-02-26) — Clamped `diffMs = Math.max(0, ...)` in AdminPage waitlist rows; prevents negative "time ago" display on clock skew.
- **P9** (2026-02-26) — Removed pre-fetch `posthog.capture('waitlist_submitted', ...)` from WaitlistForm; `waitlist_success` on 201 is the authoritative event.
- **P10** (2026-02-26) — Replaced manual `con.connect/con.close()` with `with sqlite3.connect(...) as con:` in both waitlist endpoints.
- **P11** (2026-02-26) — Added visually-hidden `<label htmlFor="waitlist-email">` and `id="waitlist-email"` on input; `role="alert"` on error `<p>` (WCAG 1.3.1).
- **P12** (2026-02-26) — Added migration `016_waitlist_index.sql`: `CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON waitlist(created_at DESC)`.
- **P13** (2026-02-26) — Added `logger.info("Waitlist duplicate", email=email)` in `except IntegrityError` block before re-raising 409.

### Blockers
{none}
