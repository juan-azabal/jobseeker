# JobSeeker

## Description
Job search CRM web product. Browse, filter, and manage scored job matches. Daily email digest links to the web for full detail. Powered by jobagent engine. Users self-onboard via CV upload.

## Commands
- Dev backend: `uvicorn api.main:app --reload --port 8000`
- Dev frontend: `cd web && npm run dev`
- Dev both: `docker compose up`
- Ingest jobs: `python -m api.ingest --jobagent-dir ../jobagent`
- Test backend: `pytest tests/`
- Test frontend: `cd web && npm test`
- Lint: `ruff check .`
- Format: `ruff format .`

## Structure
- Backend: `api/`
  - `api/main.py` — FastAPI app
  - `api/routes/` — one file per resource
  - `api/adapters/` — wrappers around jobagent imports
  - `api/db/` — SQLite init, migrations, queries
  - `api/ingest.py` — pipeline output → SQLite
- Frontend: `web/`
  - `web/src/components/` — React components
  - `web/src/pages/` — route-level pages
  - `web/src/context/` — React Context providers
  - `web/src/types/` — TypeScript types
- Tests: `tests/` (backend), `web/src/__tests__/` (frontend)
- DB: `data/jobseeker.db` (gitignored)
- Static build: `web/dist/` (gitignored)

## Conventions
- Commits: conventional (`type: description`)
- Backend imports jobagent as package — never copy or modify jobagent code
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

### Current
Phase F — Ship

### Pending
- Phase F — Ship: Dockerfile, README, deploy

### Decisions
- react-router v7 uses `react-router` package (not `react-router-dom`)
- `vitest/config` required in vite.config.ts to fix TypeScript `test` key error
- Test files excluded from tsconfig.app.json to avoid TS errors on `global`
- Auth: Google OAuth via authlib, session token in HTTP-only cookie, `get_current_user` FastAPI dependency on jobs router
- LoginPage uses `<a href="/api/auth/login">` (not a button) — tests must use `getByRole('link', ...)`
- jobagent imported via sys.path (no setup.py in jobagent) — `_load_jobagent()` called at module load adds JOBAGENT_DIR to sys.path
- Run backend tests from `/Users/juanazabal/Proyectos/jobseeker/` dir, not from `web/`
- openai added to requirements.txt (needed because jobagent/onboard.py imports it at module level)
- Users with `profile_id: null` are redirected to `/onboard`; test mocks must include `profile_id: 'user'`
- PyYAML available in venv via jobagent dependency — not in requirements.txt but importable as `import yaml`
- YAML profile (jobagent format) is nested: `user.{name,email,home_locations}`, `target.{domains,seniority}`, top-level `skills`. ProfileEditor expects flat format — normalize in `GET /api/onboard/profile`
- Dev session: insert token `dev-jsk-juan` in sessions table; inject cookie via `document.cookie = "jsk=dev-jsk-juan; path=/"`
- CV generation: POST /api/jobs/{id}/generate-cv → LLM (anthropic/openai) → python-docx .docx → FileResponse. ATS audit in X-ATS-Audit header.
- `save_profile` guard: if `user.profile_id` exists → only write `cv.md`, never regenerate YAML. First-time onboarding (no profile_id) still does full YAML generation.
- `juan.yaml` was accidentally overwritten by onboarding flow; restored via `git checkout be89638 -- config/profiles/juan.yaml` from jobagent repo
- Hamburger menu (`HamburgerMenu` component in `App.tsx`) replaces inline nav links; dropdown closes on outside click via `mousedown` listener + `useRef`
- ProfileEditor: `addDomain` adds with weight 10; `removeDomain` deletes key from state; `addSkill`/`removeSkill` mutate array. Enter key supported on both inputs.

### Blockers
{none}
