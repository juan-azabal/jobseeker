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

### Current
Phase 4 — Email integration: Dual links in digest

### Pending
- Phase 5 — Harden: Errors, mobile, security, multi-user isolation
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

### Blockers
{none}
