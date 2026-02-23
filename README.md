# JobSeeker

A personal job search CRM. Scored job matches land in a browsable web UI — filter by tier, track applications, and generate tailored CV prompts in one click.

Powered by [jobagent](../jobagent) for scoring and profile management.

---

## Features

- **Job listing** — browse matches grouped by tier (Apply / Review / Skip), filterable by period
- **Score breakdown** — per-job AI scoring across domain fit, seniority, technical depth, profile evidence, strategic impact
- **Applied tracking** — mark jobs as applied; applied state persists per user
- **CV generation** — copy a tailored prompt to clipboard (single job or bulk selection) for use with the career-helper Claude skill
- **Profile page** — view and edit your job-matching preferences (domain weights, skills, locations); replace your CV to re-generate the full profile
- **Google OAuth** — sign in with Google; HTTP-only session cookie

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLite |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 |
| Auth | Google OAuth via Authlib |
| Profile/scoring | jobagent (local dependency) |

---

## Setup

### Prerequisites

- Python 3.11+
- Node 20+
- jobagent repo at `../jobagent` (or set `JOBAGENT_DIR`)
- Google OAuth credentials

### Backend

```bash
cd jobseeker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ../jobagent
cp .env.example .env   # fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd web
npm install
npm run dev            # proxies /api/* to :8000
```

### Both at once

```bash
docker compose up
```

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | — |
| `SESSION_SECRET` | Session signing key | `dev-secret-change-in-prod` |
| `DB_PATH` | SQLite database path | `data/jobseeker.db` |
| `JOBAGENT_DIR` | Path to jobagent repo | `../jobagent` |

---

## Project structure

```
jobseeker/
├── api/
│   ├── main.py              # FastAPI app, middleware, routers
│   ├── routes/
│   │   ├── auth.py          # Google OAuth login/callback/logout/me
│   │   ├── jobs.py          # List, detail, apply endpoints
│   │   └── onboard.py       # CV upload, profile generation, profile read
│   ├── middleware/
│   │   └── auth.py          # get_current_user FastAPI dependency
│   └── db/
│       ├── init.py          # Run migrations on startup
│       ├── queries.py       # SQL wrappers
│       └── migrations/      # 001_jobs · 002_users · 003_job_status
├── web/
│   └── src/
│       ├── pages/           # LoginPage · OnboardPage · JobsPage · JobDetailPage · ProfilePage
│       ├── components/      # FilterBar · JobCard · ScoreBreakdown · ProfileEditor · FileUpload · UserMenu
│       ├── context/         # AuthContext
│       └── types/           # job.ts
├── data/                    # jobseeker.db (gitignored)
├── requirements.txt
└── docker-compose.yml
```

---

## User flow

```
Sign in with Google
  └─ profile_id == null → /onboard
       Upload .docx CV → extract markdown → generate profile → edit → activate
       └─ profile_id set → /jobs

/jobs  browse · filter · select · mark applied
/jobs/:id  detail · score breakdown · strengths · gaps · generate CV prompt · mark applied
/profile  view/edit preferences · replace CV
```

---

## Development notes

- **Ingest jobs**: `python -m api.ingest --jobagent-dir ../jobagent`
- **Backend tests**: `pytest tests/` (run from repo root)
- **Frontend tests**: `cd web && npm test`
- **Lint/format**: `ruff check .` / `ruff format .`
- **Dev session cookie** (no OAuth): insert a row in `sessions` table with token `dev-jsk-juan`, then `document.cookie = "jsk=dev-jsk-juan; path=/"` in the browser console
