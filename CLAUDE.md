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
  - `api/cv/` — CV generation pipeline
- Frontend: `web/`
  - `web/src/components/` — React components
  - `web/src/pages/` — route-level pages
  - `web/src/context/` — React Context providers
  - `web/src/types/` — TypeScript types
- Agent: `agent/`
  - `agent/main.py` — pipeline orchestrator (scrape → parse → score → notify)
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
- Backend imports agent modules via sys.path (JOBAGENT_DIR=agent)
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

### Current
Phase 6 — Completed

### Pending
- Phase F — Ship: Dockerfile, README, deploy

### Decisions
- react-router v7 uses `react-router` package (not `react-router-dom`)
- `vitest/config` required in vite.config.ts to fix TypeScript `test` key error
- Test files excluded from tsconfig.app.json to avoid TS errors on `global`
- Auth: Google OAuth via authlib, session token in HTTP-only cookie, `get_current_user` FastAPI dependency on jobs router
- LoginPage uses `<a href="/api/auth/login">` (not a button) — tests must use `getByRole('link', ...)`
- Agent imported via sys.path — `_load_jobagent()` called at module load adds `JOBAGENT_DIR` (default `agent`) to sys.path
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

- jobagent parser v1.1 (2026-02-23): `must_have_skills` in parsed JSON is now technical-only (SQL, Python, dbt…). Soft skills / years of experience / education requirements moved to new `experience_requirements` field. `key_tools` extraction in `api/cv/plan.py` benefits automatically — no jobseeker code change needed. `experience_requirements` available in `row["parsed"]["experience_requirements"]` for future use (scoring improvements, CV generation context).

### Blockers
{none}
