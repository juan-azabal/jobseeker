# JobSearch (Monorepo)

Job search platform: web CRM + autonomous scraping/scoring engine + email digests. Users self-onboard via CV upload.

## Commands
- Dev both: `bash dev.sh`
- Dev backend: `venv/bin/uvicorn api.main:app --reload --port 8000`
- Dev frontend: `cd web && npm run dev`
- Run agent: `cd agent && ../venv/bin/python main.py --profile juan --notify`
- Test backend: `pytest tests/`
- Test agent: `cd agent && pytest tests/`
- Test frontend: `cd web && npm test`
- Lint: `ruff check . && ruff format .`

## Structure
- `api/` — FastAPI backend (routes/, db/, middleware/, cv/, prompts/)
- `web/` — React frontend (components/, pages/, context/)
- `agent/` — Scraping/scoring engine (scrapers, parser, scorer, notifier, pipeline)
- `shared/` — Scoring core (pure logic, imported by api/ and agent/)
- `tests/` — Backend tests (683+)
- `agent/tests/` — Agent tests (625+)
- `data/` — SQLite DB (gitignored)
- `scripts/` — Utility scripts
- `plans/` — Implementation specs

## Trigger Table
| If you touch... | Read FIRST... |
|-----------------|---------------|
| shared/* | INVARIANTS.md §Scoring + §Boundaries |
| api/scoring.py | INVARIANTS.md §Scoring + §Dual-Copy (shared/scoring_core.py) |
| agent/main.py scoring | INVARIANTS.md §Scoring + §Dual-Copy (api/scoring.py) |
| api/cv/* | INVARIANTS.md §CV Pipeline |
| api/geo.py OR agent/geo.py | INVARIANTS.md §Dual-Copy |
| requirements*.txt | INVARIANTS.md §Deploy (BOTH files) |
| api/prompts/* OR agent/prompts/* | INVARIANTS.md §Dual-Copy |
| .github/workflows/* | NEVER modify. Ask user. |
| Dockerfile, railway.toml, startup.sh | INVARIANTS.md §Deploy |
| api/db/migrations/* | Next number is 026. Check INVARIANTS.md §Data. |

## Conventions
- Commits: conventional (`type: description`)
- SQL: raw sqlite3, numbered migrations in api/db/migrations/
- API routes: one file per resource in api/routes/
- Frontend: functional components, React Context, TypeScript strict
- All secrets via env vars, never committed
- See @INVARIANTS.md for module boundaries, scoring rules, deploy rules, dual-copy sync

## Deployment
- Railway auto-deploys on push to main (parallel with GHA tests, NOT gated)
- Deploy flow: PR → staging auto-deploy → validate → merge → production + GHA redeploy
- See @INVARIANTS.md §Deploy for hard rules

## Project State

### Completed
Phases 0-20 + QC + UID + Staging + Master CV + Parser Enrichment + Career History UX + Ingestion Overhaul + Scraper Health Monitoring. See @docs/project-state.md for full history.

### Current
- Phase N — Onboarding UX (role_type, geography, searches, preferences)
- Phase R — Refactor & Test Coverage
- Phase F — Ship

### Decisions
See @INVARIANTS.md §Decisions Log

### Known Issues
See @BUGS.md

### Blockers
None
