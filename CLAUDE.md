# JobSearch (Monorepo)

## Description
Job search platform: web CRM (browse, filter, manage scored jobs) + autonomous scraping/scoring engine. Daily email digest links to the web for full detail. Users self-onboard via CV upload.

## Monorepo Layout
- `api/` — FastAPI backend
- `web/` — React frontend
- `agent/` — scraping/scoring engine (formerly standalone `jobagent` repo)
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
  - `api/routes/` — one file per resource (auth, jobs, onboard, ingest, admin)
  - `api/middleware/auth.py` — session auth + admin guards (`get_current_user`, `get_current_admin`)
  - `api/db/` — SQLite init, migrations (001–016), queries
  - `api/ingest.py` — pipeline output → SQLite
  - `api/scoring.py` — per-user heuristic scoring (ported from agent)
  - `api/embeddings.py` — OpenAI embedding service with SQLite cache (text-embedding-3-small)
  - `api/skill_matcher.py` — semantic skill matching (cosine similarity ≥0.80=match, ≥0.68=partial, fallback to substring)
  - `api/geo.py` — geographic region utilities (API-side copy of agent/geo.py)
  - `api/onboard_utils.py` — CV parsing + profile YAML generation (extracted from agent/onboard.py)
  - `api/prompts/` — LLM prompts for API-side features (onboard-extraction.md)
  - `api/cv/` — CV generation pipeline (plan, prompt, llm, validator, docx_builder, ats_audit)
  - `api/analytics.py` — PostHog Python client (init, capture, identify_user, capture_exception)
  - `api/logging_config.py` — structlog configuration (JSON in CI, ConsoleRenderer locally)
- Frontend: `web/`
  - `web/src/components/` — FilterBar, JobCard, ProfileEditor, ScoreBreakdown, FileUpload, UserMenu, DomainSelector, WaitlistForm, MockDashboard, MockJobDetail, MockCVButton
  - `web/src/pages/` — Landing, Login, Onboard, Jobs, JobDetail, Profile, Admin
  - `web/src/context/AuthContext.tsx` — auth state provider
  - `web/src/types/job.ts` — TypeScript types
  - `web/src/constants/domains.ts` — 30-domain canonical enum, display labels, grouped categories
  - `web/src/analytics.ts` — posthog-js wrapper (initPostHog, identifyUser, resetPostHog)
- Agent: `agent/`
  - `agent/main.py` — pipeline orchestrator (scrape → parse → score → notify)
  - `agent/logging_setup.py` — structlog configuration for the agent
  - `agent/api_cache.py` — cross-user parsed-job cache via Railway DB
  - `agent/scraper.py` — JobSpy wrapper + `make_job_id()` dedup
  - `agent/ats_scraper.py` — Greenhouse/Lever/Ashby API poller
  - `agent/wttj_scraper.py` — Welcome to the Jungle (Algolia API)
  - `agent/prefilter.py` — keyword filter + US-only detection (no API calls)
  - `agent/parser.py` — gpt-4o-mini: structured JSON extraction from JD
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
- Tests: `tests/` (backend, 449 tests), `web/src/*.test.tsx` (frontend), `agent/tests/` (agent, 195 tests)
  - `agent/tests/fixtures.py` — shared BASELINE_PROFILE fixture (fixed dict, not from juan.yaml)
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

## Conventions
- Commits: conventional (`type: description`)
- Backend has zero import dependency on agent/ (api/geo.py + api/onboard_utils.py are self-contained copies)
- API routes: one file per resource in `api/routes/`
- SQL: raw sqlite3, migrations in `api/db/migrations/` as numbered .sql files
- Frontend: functional components, React Context for global state, TypeScript strict
- All secrets via env vars, never committed
- Test naming: `test_*.py` (backend), `*.test.tsx` (frontend)

## Architecture

### Agent Pipeline (12 steps)
```
Step 1a-c: Scrape (JobSpy + ATS watchlist + WTTJ) → dedup via make_job_id()
Step 2:    Prefilter (keywords, US-only, deal breakers, seen_ids — no API calls)
Step 3:    Local cache split (cached vs new jobs)
Step 3b:   Cross-user DB cache (fetch already-parsed from Railway DB via api_cache.py)
Step 4:    Parse new jobs (gpt-4o-mini, ~$0.001/job)
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

### Current
Phase 17 — Decomposed Hybrid Scoring (in progress: 17.1 complete)
- Phase 17.1 — Parser + DB + Ingest: role_function enum
  - Parser prompt v1.4: emits role_function (product|engineering|design|data|marketing|sales|ops|support|other)
  - DB migration 017: role_function column on jobs table, backfilled from parsed JSON
  - Ingest: extracts role_function from parsed, writes to jobs.role_function; upsert_job handles missing key defensively
  - Note: plan referenced migration 016 for role_function but 016 was already taken by waitlist index; used 017 instead; scoring grades will use 018

### Pending
- Phase N — Onboarding UX for new profile fields (role_type, geography, searches, preferences)
- Phase R — Refactor & Test Coverage
- Phase F — Ship: Dockerfile, README, deploy

### Decisions
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

### Known Bugs

{none}

### Resolved
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
