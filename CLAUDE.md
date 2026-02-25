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
- Lint: `ruff check .`
- Format: `ruff format .`

## Structure
- Backend: `api/`
  - `api/main.py` — FastAPI app
  - `api/routes/` — one file per resource
  - `api/db/` — SQLite init, migrations, queries
  - `api/ingest.py` — pipeline output → SQLite
  - `api/scoring.py` — per-user heuristic scoring (ported from agent)
  - `api/geo.py` — geographic region utilities (API-side copy of agent/geo.py)
  - `api/onboard_utils.py` — CV parsing + profile YAML generation (extracted from agent/onboard.py)
  - `api/prompts/` — LLM prompts for API-side features (onboard-extraction.md)
  - `api/cv/` — CV generation pipeline
- Frontend: `web/`
  - `web/src/components/` — React components
  - `web/src/pages/` — route-level pages
  - `web/src/context/` — React Context providers
  - `web/src/types/` — TypeScript types
- Agent: `agent/`
  - `agent/main.py` — pipeline orchestrator (scrape → parse → score → notify)
  - `agent/api_cache.py` — cross-user parsed-job cache via Railway DB
  - `agent/config/profiles/*.yaml` — per-user profiles
  - `agent/knowledge/` — CV knowledge base (per user)
  - `agent/output/` — job results JSON (gitignored)
  - `agent/prompts/` — LLM prompts (parser, scoring rubric)
  - `agent/scripts/` — utility scripts (reparse, rescore)
- Tests: `tests/` (backend), `web/src/__tests__/` (frontend)
- DB: `data/jobseeker.db` (gitignored)
- Static build: `web/dist/` (gitignored)

## Conventions
- Commits: conventional (`type: description`)
- Backend has zero import dependency on agent/ (api/geo.py + api/onboard_utils.py are self-contained copies)
- API routes: one file per resource in `api/routes/`
- SQL: raw sqlite3, migrations in `api/db/migrations/` as numbered .sql files
- Frontend: functional components, React Context for global state, TypeScript strict
- All secrets via env vars, never committed
- Test naming: `test_*.py` (backend), `*.test.tsx` (frontend)

## Project State

### Completed
- Phase 0 — Scaffold
- Phase 1 — MVP: Ingest + browse jobs with period/tier filters
- Phase 2 — Auth: Google OAuth (authlib + SessionMiddleware, HTTP-only cookie, protected API, frontend guards)
- Phase 3 — Onboarding: CV upload (.docx) → generate-profile → edit → save-profile → jobagent files written
- Phase 4 — UI overhaul + job tracking + profile page
  - Design: dark theme (zinc-950), violet-500 primary accent, semantic tier colors (emerald/amber/zinc)
  - Job tracking: `user_job_status` table (migration 003), per-user `applied_at`, `POST /jobs/{id}/apply`
  - CV generation: single-job "Generate CV" button (copies prompt to clipboard); bulk selection + floating action bar
  - Profile page `/profile`: view/edit current profile, "Replace CV" flow to re-upload and regenerate
  - Header: sticky frosted-glass, logo links to `/jobs`, hamburger menu (Jobs / My Profile / Sign out)
  - Profile editing: add/remove domains (with weight slider), add/remove skills inline
  - Data safety: `save_profile` with existing `profile_id` only updates `cv.md` — never overwrites YAML
  - Tier C hidden by default in listing filters
- Phase 5 — CV Generation (in-app tailored CV download)
  - LLM provider configurable via CV_LLM_PROVIDER (anthropic|openai), model via CV_LLM_MODEL
  - .docx built with python-docx for ATS compliance (pandoc rejected: generates tables and unicode bullets in XML)
  - CV reference files gitignored (contain personal data), loaded from CV_REFERENCES_DIR
  - ATS audit runs post-build as safety net, result in X-ATS-Audit response header
  - LLM output follows strict structured markdown contract, docx_builder parses deterministically
  - Post-processing auto-fixes em dashes, Oxford commas, unicode bullets as last line of defense
  - "Generate CV" button replaces clipboard-copy: POSTs to /api/jobs/{id}/generate-cv, triggers browser download
- Phase 6 — CV Output Quality
  - docx_builder rewritten for skill-quality formatting: correct font sizes (18/11/10/9pt), colors
    (#1F4E79 blue for name+headers, #444444 title, #555555 dates/context), real bullet numPr XML,
    tab-stop right-aligned dates, italic context lines — matches skill-generated CV spec exactly
  - Plan-driven architecture: deterministic build_cv_plan() (api/cv/plan.py) extracts jd_context
    (company_type, location_language_hints, key_tools), score_summary with per-dimension guidance,
    bullet_allocation (relevance-weighted budget per company, capped at 12), source_facts (title,
    years_experience, languages, core_skills_themes) from scored data + reference files
  - Plan-aware prompts: build_cv_prompts(job, cv_md, plan) adds source fidelity rules (never downgrade
    title/years), bullet allocation instruction, JD-aware tailoring (consultancy sentence, language hints),
    extended anti-slop blacklist, and chain-of-thought <analysis> block requirement to system prompt
  - Analysis stripping: generate_cv() auto-strips <analysis>...</analysis> so callers always get clean markdown
  - Programmatic CV validator: validate_cv(markdown, plan) checks title_downgraded, years_downgraded,
    slop_detected (errors) and missing_language, missing_theme, bullet_budget_violation,
    no_consulting_mention, gerund_start (warnings); build_fix_prompt() for one-shot targeted fix call
  - Full pipeline in endpoint: plan → plan-aware prompts → LLM → validate → fix (if errors) → re-validate
    → docx → ATS audit. New response headers: X-CV-Validation, X-CV-Fix-Applied, X-ATS-Audit
  - Content volume controls: 3-page hard cap, 2-page soft cap, max 12 WE bullets total with recency budget
  - Company names / Core Skills themes / project names use COLOR_ACCENT (#1F4E79) instead of bold
- Phase 7 — Deparameterize Scoring (rubric role_type/geography, adjacent domains, home locations)
- Phase 8 — Per-Profile Pipeline (searches, watchlist, prefilter per-user)
- Phase 9 — Per-User Scoring + New-User Bootstrap
  - DB: `jobs` table is shared (no score/tier/scored columns), `user_job_scores` table holds per-user RAG scores
  - `api/scoring.py`: heuristic scorer (domain 0-15, seniority 0-15, location 0-10, skills 0-30, red_flags -15) runs at query time for jobs without RAG scores — no LLM, instant, free
  - Ingest: `ingest_from_list()` accepts optional `profile_id`; common job data → `jobs`, per-user RAG scores → `user_job_scores`
  - Jobs route: `_score_and_tier_jobs()` prefers RAG score, falls back to heuristic; tier filtering post-scoring; `total_in_db` in response
  - Onboarding pipeline: `save_profile()` pushes profile YAML + cv.md + seen_ids.txt to GitHub via Contents API, triggers `workflow_dispatch` (fire-and-forget). Env: `GH_ACTIONS_TOKEN`, `GH_REPO`, `GH_REF`
  - GHA: single-profile dispatch via `inputs.profile`, ingest syncs with `profile_id` in payload
  - Frontend: empty state with "Scanning job boards" + 60s auto-poll when `totalInDb === 0`; "No matching filters" state with reset button
- Phase 10 — Ops: Persistence, Health Monitoring, Admin
  - Railway volume (`/data`) holds SQLite; `cv_md` + `profile_yaml` persisted in `users` table (migrations 006, 007) so they survive ephemeral filesystem resets on redeploy
  - Auto-prune: `cleanup_old_jobs()` deletes jobs + dependent rows older than 90 days on every ingest; called in `ingest_from_list()`
  - `GET /api/ingest/status` (X-Ingest-Key protected): returns total_jobs, last_ingested_at, scored_profiles, total_scored, jobs_older_than_90d
  - GHA "Verify ingest health" step prints status after every run
  - `GET /api/onboard/profile`: opportunistic cv_md save — if DB is NULL but file exists on disk, persists to DB immediately
  - Admin system: `is_admin INTEGER DEFAULT 0` on users (migration 008); `ADMIN_EMAILS` env var auto-promotes on login; `get_current_admin` dependency (403 if not admin); `api/routes/admin.py` with `GET /api/admin/users` + `POST /api/admin/trigger-pipeline`; React `/admin` page with pipeline trigger + users table (visible only to admins in hamburger menu)

### Current
Phase 10 — Completed

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
- `juan.yaml` was accidentally overwritten by onboarding flow; profile YAML lives at `agent/config/profiles/juan.yaml`
- Hamburger menu (`HamburgerMenu` component in `App.tsx`) replaces inline nav links; dropdown closes on outside click via `mousedown` listener + `useRef`
- ProfileEditor: `addDomain` adds with weight 10; `removeDomain` deletes key from state; `addSkill`/`removeSkill` mutate array. Enter key supported on both inputs.
- OnboardPage must pass `isNew` to ProfileEditor so first-time save uses POST `/save-profile` (creates YAML) instead of PATCH `/profile` (requires existing profile_id).

- jobagent parser v1.1 (2026-02-23): `must_have_skills` in parsed JSON is now technical-only (SQL, Python, dbt…). Soft skills / years of experience / education requirements moved to new `experience_requirements` field. `key_tools` extraction in `api/cv/plan.py` benefits automatically — no jobseeker code change needed. `experience_requirements` available in `row["parsed"]["experience_requirements"]` for future use (scoring improvements, CV generation context).
- Per-user scoring: `jobs` table stores shared data only (no score/tier/scored). Per-user RAG scores in `user_job_scores(user_id, job_id, score, tier, scored, scored_at)`. Heuristic scores computed at query time from profile YAML + parsed JSON — never stored. Migration `005_user_scores.sql` recreates jobs table without those columns.
- Ingest stores per-user scores only when `profile_id` is provided AND the job has a `rag_score` with a non-null `score` value. Jobs without RAG scores rely on heuristic at query time.
- Onboarding triggers pipeline: `save_profile()` (first-time only) pushes files to GitHub repo via Contents API and fires `workflow_dispatch`. Requires `GH_ACTIONS_TOKEN` (PAT with contents:write + actions:write), `GH_REPO`, `GH_REF`.
- Frontend empty state: when `total_in_db === 0` (no jobs scraped yet), shows "Scanning job boards" with 60s auto-poll. When jobs exist but filters exclude all, shows "No matching jobs" with reset button.
- cv_md persistence: saved in `users.cv_md` (migration 006) on `POST /save-profile` and opportunistically on `GET /profile` (if file on disk but DB NULL). Guard in `save_profile`: empty cv_markdown is never written to DB (prevents accidental overwrite).
- profile_yaml persistence: saved in `users.profile_yaml` (migration 007) on first-time save and on every `PATCH /profile`. Restored from DB to disk on `GET /profile` and `PATCH /profile` if filesystem was wiped.
- Admin access: `is_admin` column on users (migration 008, default 0). Set `ADMIN_EMAILS=email@example.com` env var in Railway; users matching that email are auto-promoted to admin on next login. `get_current_admin` dependency in `api/middleware/auth.py`. Admin link in hamburger menu only visible to admins.
- `POST /api/admin/trigger-pipeline`: dispatches `jobagent_daily.yml` workflow via GitHub API. Optional `{"profile": "id"}` body to target a specific profile. Requires same GH_ACTIONS_TOKEN/GH_REPO/GH_REF as onboarding.
- Job cleanup: `cleanup_old_jobs(db_path, days=90)` deletes from user_job_scores + user_job_status + jobs where last_seen < cutoff. Called automatically at end of every ingest.
- Cross-user parsed job dedup: `agent/api_cache.py` calls `POST /api/ingest/batch-lookup` (X-Ingest-Key auth, 500 id cap) to fetch already-parsed jobs from Railway DB before parsing. Injected as Step 3b in `agent/main.py` between local cache split and parse. Graceful fallback: returns `{}` if RAILWAY_URL/INGEST_API_KEY not set or API unreachable. Uses `urllib.request` (no extra deps).
- GHA sequential pipeline: workflow rewritten from parallel matrix to sequential loop in a single `digest` job. Each profile syncs parsed data to Railway before the next starts, so subsequent profiles skip re-parsing overlapping jobs. Jobs: `list-profiles` → `digest` (sequential loop) → `persist-seen-ids` → `verify-health`. `timeout-minutes: 60`.

### Blockers
{none}
