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

### Current
Phase 1 — MVP: Ingest + browse jobs with period/tier filters

### Pending
- Phase 2 — Auth: Google OAuth
- Phase 3 — Onboarding: Web CV upload + profile creation
- Phase 4 — Email integration: Dual links (web + original) in digest
- Phase 5 — Harden: Errors, mobile, security, multi-user isolation
- Phase F — Ship: Dockerfile, README, deploy

### Decisions
{none yet}

### Blockers
{none}
