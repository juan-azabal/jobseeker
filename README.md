# JobSearch

A personal job search platform. Web CRM + autonomous scraping/scoring engine in a single monorepo.

---

## Features

- **Job listing** — browse matches grouped by tier (Apply / Review / Skip), filterable by period
- **Score breakdown** — per-job AI scoring across domain fit, seniority, technical depth, profile evidence, strategic impact
- **Applied tracking** — mark jobs as applied; applied state persists per user
- **CV generation** — generate a tailored .docx CV for any job (single or bulk)
- **Profile page** — view and edit job-matching preferences: domains, skills, locations, salary
- **Google OAuth** — sign in with Google; HTTP-only session cookie
- **Daily digest** — automated scraping + email notification (GitHub Actions cron)

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLite |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 |
| Auth | Google OAuth via Authlib |
| Agent | Python · JobSpy · ChromaDB · OpenAI (gpt-4o/mini) |

---

## Setup

### Prerequisites

- Python 3.12+
- Node 20+
- Google OAuth credentials

### Install

```bash
cd jobsearch
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
```

### Run

```bash
bash dev.sh            # starts backend (:8000) + frontend (:5173)
```

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | — |
| `SESSION_SECRET` | Session signing key | `dev-secret-change-in-prod` |
| `DB_PATH` | SQLite database path | `data/jobseeker.db` |
| `JOBAGENT_DIR` | Path to agent engine | `agent` |
| `OPENAI_API_KEY` | OpenAI API key (agent) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (CV gen) | — |

---

## Project structure

```
jobsearch/
├── api/                    # FastAPI backend
│   ├── main.py
│   ├── routes/             # auth, jobs, onboard
│   ├── cv/                 # CV generation pipeline
│   ├── db/                 # SQLite init, migrations, queries
│   └── ingest.py           # agent output → SQLite
├── web/                    # React frontend
│   └── src/
│       ├── pages/          # Login, Onboard, Jobs, JobDetail, Profile
│       ├── components/     # FilterBar, JobCard, ProfileEditor, etc.
│       └── types/          # TypeScript types
├── agent/                  # Scraping/scoring engine
│   ├── main.py             # Pipeline orchestrator
│   ├── config/profiles/    # Per-user YAML profiles
│   ├── knowledge/          # CV knowledge base
│   ├── prompts/            # LLM prompts (parser, scoring)
│   └── scripts/            # reparse, rescore utilities
├── data/                   # jobseeker.db (gitignored)
├── tests/                  # Backend tests
└── requirements.txt        # Merged deps (web + agent)
```

---

## Development notes

- **Ingest jobs**: `python -m api.ingest`
- **Run agent**: `cd agent && ../venv/bin/python main.py --profile juan --notify`
- **Backend tests**: `pytest tests/` (run from repo root)
- **Frontend tests**: `cd web && npm test`
- **Dev session cookie** (no OAuth): `document.cookie = "jsk=dev-jsk-juan; path=/"`
