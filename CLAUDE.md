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
  - `api/db/` — SQLite init, migrations (001–011), queries
  - `api/ingest.py` — pipeline output → SQLite
  - `api/scoring.py` — per-user heuristic scoring (ported from agent)
  - `api/embeddings.py` — OpenAI embedding service with SQLite cache (text-embedding-3-small)
  - `api/skill_matcher.py` — semantic skill matching (cosine similarity ≥0.80=match, ≥0.68=partial, fallback to substring)
  - `api/geo.py` — geographic region utilities (API-side copy of agent/geo.py)
  - `api/onboard_utils.py` — CV parsing + profile YAML generation (extracted from agent/onboard.py)
  - `api/prompts/` — LLM prompts for API-side features (onboard-extraction.md)
  - `api/cv/` — CV generation pipeline (plan, prompt, llm, validator, docx_builder, ats_audit)
- Frontend: `web/`
  - `web/src/components/` — FilterBar, JobCard, ProfileEditor, ScoreBreakdown, FileUpload, UserMenu
  - `web/src/pages/` — Login, Onboard, Jobs, JobDetail, Profile, Admin
  - `web/src/context/AuthContext.tsx` — auth state provider
  - `web/src/types/job.ts` — TypeScript types
- Agent: `agent/`
  - `agent/main.py` — pipeline orchestrator (scrape → parse → score → notify)
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
- Tests: `tests/` (backend, 297 tests), `web/src/*.test.tsx` (frontend), `agent/tests/` (agent, 113 tests)
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
  - Embeddings: OpenAI text-embedding-3-small, cached in SQLite (skill_embeddings table, migration 011)
  - Matching: cosine similarity ≥0.80 = match, ≥0.68 = partial. Fallback to exact substring if no API key.
  - Scoring: heuristic_score() uses semantic matching for skills dimension (partial match = 2pts, full = 5pts)
  - Job detail: GET /api/jobs/{id} returns skill_matches with match status per skill
  - Add skill: POST /api/onboard/profile/skills — one-click add from job detail
  - Frontend: skill chips colored by match status (green/amber/default), click unmatched to add
  - Backfill: scripts/backfill_embeddings.py for existing data; auto-embed on ingest
  - Performance: in-process LRU cache, 500-pair ceiling for semantic matching

### Current
Phase 12 — Completed

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
- Embedding model: text-embedding-3-small (1536 dims). Cache key: lowercase trimmed skill text.
- Embedding storage: JSON-serialized list[float] in BLOB column. No numpy dependency.
- Semantic thresholds: 0.80 match, 0.68 partial. Tuned on skill synonym pairs (analytics↔data analysis, ML↔machine learning).
- Cosine similarity: pure Python (no numpy). Acceptable for ≤500 pairwise comparisons per request.
- POST /api/onboard/profile/skills in onboard router (not separate profile router) — consistent with existing PATCH /profile.

### Blockers
{none}
