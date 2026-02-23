# JobSeeker — Refactor & Test Coverage Plan

> **Execute. Do not plan.** If you enter plan mode, call ExitPlanMode immediately.
> If any step is ambiguous, STOP and ask. Do not assume.

## Context

### Goal
Reduce technical debt and increase test coverage across the jobseeker backend. Centralize configuration, eliminate the fragile sys.path import hack, and add unit tests to the untested CV pipeline (plan, validator, docx_builder) and API integration tests — so future changes are safe.

### Architecture
- Stack: Python 3.11+ / FastAPI / SQLite (backend), React 19 / TypeScript / Vite (frontend)
- Libraries: pytest + pytest-asyncio (testing), httpx (test client), python-docx, anthropic/openai (LLM)
- Patterns: one route file per resource, raw sqlite3 queries, functional React components
- Avoid: ORMs, mock avalanche (prefer fixtures/hardcoded returns over elaborate mocks), premature abstraction, modifying jobagent code

### Existing project notes
- Project at Phase 6 — Completed. This plan continues as Phase 7–9.
- CLAUDE.md already exists — update Project State at every GATE.
- jobagent is a sibling repo imported as local dependency. Currently loaded via `_load_jobagent()` sys.path hack. `pip install -e ../jobagent` is the correct approach (already in README).
- CV pipeline: `api/cv/plan.py` (build_cv_plan), `api/cv/prompt.py` (build_cv_prompts), `api/cv/validator.py` (validate_cv), `api/cv/docx_builder.py` (build_docx), `api/cv/llm.py` (generate_cv, strip_analysis)
- DB migrations in `api/db/migrations/` as numbered .sql files. Queries in `api/db/queries.py`.
- Tests: `pytest tests/` (backend), `cd web && npm test` (frontend). Coverage tool NOT currently installed.

---

## Tasks

- [ ] Phase 7 — Foundation: Config & Imports (7.1–7.4)
- [ ] Phase 8 — Test Coverage: CV Pipeline (8.1–8.5)
- [ ] Phase 9 — Test Coverage: API & DB (9.1–9.4)

---

## Execution rules

These override your defaults. Follow them exactly.

1. **Test-first**: For every step that adds tests, write the test FIRST → run → must FAIL → implement minimum to pass → run ALL tests → must PASS. For refactor steps, run ALL existing tests before AND after to confirm no regressions.
2. **One step, one commit**: Commit after every step. Never accumulate changes across steps.
3. **Stuck protocol**: If a test fails after 3 fix attempts → STOP. Add a TodoWrite item: `"BLOCKER [step]: [error + what you tried]"`. Do NOT proceed.
4. **Checkpoint**: At every GATE, update CLAUDE.md Project State (move phase to Completed, advance Current, log any decisions or blockers). Mark `[x]` on the phase checkbox above. Commit: `docs: checkpoint`.
5. **Phase transitions**: After each checkpoint, `/clear` context, then re-read this plan file + CLAUDE.md before continuing.
6. **Stay in your lane**: Implement ONLY what the current step describes. No "while I'm here" additions.
7. **No jobagent modifications**: Never modify files inside the jobagent repo. Only change jobseeker code.

---

## Phase 7 — Foundation: Config & Imports

### 7.1 · Centralize configuration into settings module
**Action**: Create `api/config.py` that loads all env vars in one place using a dataclass or simple class: `DB_PATH`, `JOBAGENT_DIR`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`, `CV_LLM_PROVIDER`, `CV_LLM_MODEL`, `CV_REFERENCES_DIR`. Provide sensible defaults where they already exist (e.g., `DB_PATH=data/jobseeker.db`). Export a singleton `settings` instance.
**Files**: `api/config.py`
**Verify** (unit): Write a test in `tests/test_config.py` that imports `settings`, asserts all expected attributes exist, and verifies defaults load when env vars are unset. `pytest tests/test_config.py` → green.
**Commit**: `refactor: centralize env config into api/config.py`

### 7.2 · Migrate all env var reads to settings
**Action**: Find every `os.getenv()` / `os.environ` / `dotenv` usage across `api/` and replace with `from api.config import settings`. Remove scattered `load_dotenv()` calls except the one in config.py. Run full test suite before AND after to confirm no regressions.
**Files**: all files in `api/` that read env vars (likely `main.py`, `routes/auth.py`, `routes/onboard.py`, `cv/llm.py`, `db/init.py`)
**Verify** (output): `grep -rn "os.getenv\|os.environ\|load_dotenv" api/ --include="*.py"` returns ONLY `api/config.py`. `pytest tests/` → all green.
**Commit**: `refactor: migrate all env var reads to centralized settings`

### 7.3 · Replace sys.path hack with proper import guard
**Action**: Remove the `_load_jobagent()` function that manipulates `sys.path` at module load. Replace with a guard in `api/config.py` that checks if `jobagent` is importable, and if not, raises a clear error message: `"jobagent not installed. Run: pip install -e ./agent"`. Update any adapter files in `api/adapters/` to import jobagent normally. Run full test suite.
**Files**: `api/config.py`, `api/adapters/*.py` (whichever files contain the sys.path hack)
**Verify** (output): `grep -rn "sys.path" api/ --include="*.py"` returns nothing. `pytest tests/` → all green.
**Commit**: `refactor: remove sys.path hack, require jobagent as installed package`

### 7.4 · Add pytest-cov and measure baseline
**Action**: Add `pytest-cov` to `requirements.txt`. Run `pytest tests/ --cov=api --cov-report=term-missing` and record the baseline coverage percentage in CLAUDE.md Decisions. Create a `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` section with `addopts = --cov=api --cov-report=term-missing` so coverage runs by default.
**Files**: `requirements.txt`, `pytest.ini` or `pyproject.toml`
**Verify** (output): `pytest tests/` now shows coverage table. Baseline number logged.
**Commit**: `chore: add pytest-cov, establish coverage baseline`

**GATE**: Config centralized. sys.path hack removed. Coverage baseline measured. All existing tests green. Run **Checkpoint**.

---

## Phase 8 — Test Coverage: CV Pipeline

### 8.1 · Create CV pipeline test fixtures
**Action**: Create `tests/fixtures/` directory with sample data needed to test the CV pipeline in isolation: (a) a minimal `sample_job` dict matching the shape that `build_cv_plan()` expects (with `parsed` field containing `must_have_skills`, `experience_requirements`, etc.), (b) a minimal `sample_cv_md` string (a short realistic CV in markdown), (c) a `sample_plan` dict matching the output shape of `build_cv_plan()`. Examine the actual functions to understand the exact data shapes. Use a `conftest.py` in `tests/` to expose these as pytest fixtures.
**Files**: `tests/conftest.py`, `tests/fixtures/` (sample data files if needed)
**Verify** (unit): Write a trivial test in `tests/test_fixtures.py` that imports each fixture and asserts it's not None. `pytest tests/test_fixtures.py` → green.
**Commit**: `test: add CV pipeline test fixtures`

### 8.2 · Unit tests for build_cv_plan
**Action**: Test `api/cv/plan.py :: build_cv_plan()`. Cover: (a) happy path — returns plan with expected keys (`jd_context`, `score_summary`, `bullet_allocation`, `source_facts`), (b) consultancy detection — job with consultancy signals → `company_type == "consultancy"`, (c) location→language mapping — Paris job → includes French in language hints, (d) bullet budget — total bullets ≤ 12 cap.
**Files**: `tests/test_cv_plan.py`
**Verify** (unit): `pytest tests/test_cv_plan.py -v` → all tests green.
**Commit**: `test: unit tests for build_cv_plan`

### 8.3 · Unit tests for validate_cv
**Action**: Test `api/cv/validator.py :: validate_cv()`. Cover: (a) clean CV → no errors, (b) CV with slop phrase ("proven ability...") → `slop_detected` error, (c) title downgrade → `title_downgraded` error, (d) years downgrade → `years_downgraded` error, (e) gerund-starting bullet → `gerund_start` warning. Also test `build_fix_prompt()` returns non-empty string when validation has errors.
**Files**: `tests/test_cv_validator.py`
**Verify** (unit): `pytest tests/test_cv_validator.py -v` → all tests green.
**Commit**: `test: unit tests for validate_cv`

### 8.4 · Unit tests for docx_builder
**Action**: Test `api/cv/docx_builder.py`. Cover: (a) given valid structured markdown → produces a `.docx` bytes object (or file), (b) output contains expected sections (name, experience entries), (c) font sizes match spec (18pt name, 11pt body). Use `python-docx` to inspect the output document programmatically.
**Files**: `tests/test_docx_builder.py`
**Verify** (unit): `pytest tests/test_docx_builder.py -v` → all tests green.
**Commit**: `test: unit tests for docx_builder`

### 8.5 · Unit test for strip_analysis and LLM integration point
**Action**: Test `api/cv/llm.py :: strip_analysis()`. Cover: (a) text with `<analysis>...</analysis>` → stripped cleanly, (b) text without analysis tags → unchanged, (c) multiline analysis block. Do NOT test actual LLM calls — only the pure functions. If `generate_cv()` has mockable boundaries, add one test with a patched LLM client that returns a fixture response, verifying the full pipeline (plan → prompt → "LLM" → validate → docx) runs end-to-end.
**Files**: `tests/test_cv_llm.py`
**Verify** (unit): `pytest tests/test_cv_llm.py -v` → all tests green.
**Commit**: `test: unit tests for strip_analysis and mocked CV generation`

**GATE**: CV pipeline has unit tests for plan, validator, docx_builder, and LLM utilities. All tests green. Coverage improved from baseline. Run **Checkpoint**.

---

## Phase 9 — Test Coverage: API & DB

### 9.1 · Create test database fixture
**Action**: Create a test fixture that provisions a fresh in-memory SQLite database (or temp file) with all migrations applied. Use FastAPI's `TestClient` from `httpx` with dependency override for the DB connection. Add a fixture for an authenticated test session (mock user with `profile_id` set). Place in `tests/conftest.py` (extend from Phase 8).
**Files**: `tests/conftest.py`
**Verify** (unit): Write a trivial test that uses the `test_client` fixture to call `GET /api/health` (or any public endpoint) and gets a response. `pytest tests/test_api_fixtures.py` → green.
**Commit**: `test: add API test client and DB fixtures`

### 9.2 · Integration tests for jobs routes
**Action**: Test `api/routes/jobs.py` via TestClient. Cover: (a) `GET /api/jobs` returns 200 with list (may be empty), (b) `GET /api/jobs` with tier filter, (c) `GET /api/jobs/{id}` returns job detail or 404, (d) `POST /api/jobs/{id}/apply` sets applied status (requires auth fixture). Insert test data directly into the test DB via the fixture.
**Files**: `tests/test_routes_jobs.py`
**Verify** (integration): `pytest tests/test_routes_jobs.py -v` → all tests green.
**Commit**: `test: integration tests for jobs API routes`

### 9.3 · Integration tests for auth routes
**Action**: Test `api/routes/auth.py` via TestClient. Cover: (a) `GET /api/auth/login` redirects (302) to Google, (b) `GET /api/auth/me` without session → 401, (c) `GET /api/auth/me` with valid session cookie → returns user data, (d) `POST /api/auth/logout` clears session. Mock the Google OAuth callback — do NOT make real OAuth calls.
**Files**: `tests/test_routes_auth.py`
**Verify** (integration): `pytest tests/test_routes_auth.py -v` → all tests green.
**Commit**: `test: integration tests for auth routes`

### 9.4 · DB queries coverage
**Action**: Test key functions in `api/db/queries.py` directly against the test DB fixture. Cover: (a) insert and retrieve a job, (b) insert and retrieve a user, (c) `user_job_status` insert and query. Focus on the queries used by routes — not exhaustive coverage of every query.
**Files**: `tests/test_db_queries.py`
**Verify** (integration): `pytest tests/test_db_queries.py -v` → all tests green.
**Commit**: `test: integration tests for DB queries`

**GATE**: API routes and DB queries have integration tests. Full `pytest tests/` green. Coverage meaningfully above baseline. Run **Checkpoint** — update CLAUDE.md with final coverage number.

---

## CLAUDE.md Project State update (for Checkpoint reference)

After all phases, Project State should read:

```
### Completed
- Phase 0–6 (existing)
- Phase 7 — Foundation: Config centralization, sys.path removal, coverage baseline
- Phase 8 — Test Coverage: CV Pipeline (plan, validator, docx_builder, llm)
- Phase 9 — Test Coverage: API & DB (jobs routes, auth routes, DB queries)

### Current
Phase 9 — Completed

### Pending
- Phase F — Ship: Dockerfile, deploy
```
