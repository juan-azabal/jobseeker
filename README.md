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
- **Self-service onboarding** — upload CV, review extracted profile, save → pipeline fires automatically
- **Cross-user dedup** — jobs parsed by one user are reused by subsequent users (saves LLM costs)
- **Semantic skill matching** — cosine similarity matching between profile skills and job requirements; skill chips colored by match status in job detail
- **Domain scoring** — 30-domain canonical system with per-user weights (positive/negative); editable per-job with grouped dropdown; keyword reparse and correction analytics in admin
- **Enriched job data** — scrapers capture structured salary, company metadata (industry, size, URL, logo), seniority level, remote type; merged across sources with field-priority rules; pre-seeds LLM parser to reduce token cost and hallucination
- **Admin panel** — trigger pipeline, view users, keyword reparse, domain corrections, manage system

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLite |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 |
| Auth | Google OAuth via Authlib |
| Agent | Python · JobSpy · ChromaDB · OpenAI (gpt-4o/mini) |
| CV Gen | Anthropic Claude / OpenAI · python-docx |
| Infra | Railway (backend) · GitHub Actions (agent pipeline) |

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
cd web && npm install && cd ..
cp .env.example .env   # fill in credentials
```

### Run

```bash
bash dev.sh            # starts backend (:8000) + frontend (:5173)
```

---

## Environment variables

### Core
| Variable | Description | Default |
|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | — |
| `SESSION_SECRET` | Session signing key | `dev-secret-change-in-prod` |
| `DB_PATH` | SQLite database path | `data/jobseeker.db` |
| `JOBAGENT_DIR` | Path to agent engine | `agent` |
| `ADMIN_EMAILS` | Comma-separated admin emails | — |

### API Keys
| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (agent parsing + scoring) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (CV generation) | — |
| `INGEST_API_KEY` | Shared secret for ingest/batch-lookup endpoints | — |

### CV Generation
| Variable | Description | Default |
|---|---|---|
| `CV_LLM_PROVIDER` | LLM provider (anthropic\|openai) | `anthropic` |
| `CV_LLM_MODEL` | Model override | provider default |
| `CV_REFERENCES_DIR` | CV reference files directory | `api/cv/references/` |

### GitHub Actions Integration
| Variable | Description | Default |
|---|---|---|
| `GH_ACTIONS_TOKEN` | GitHub PAT (contents:write + actions:write) | — |
| `GH_REPO` | GitHub repo `owner/repo` | — |
| `GH_REF` | Git branch for dispatch | `main` |

### Agent Email
| Variable | Description | Default |
|---|---|---|
| `GMAIL_ADDRESS` | Gmail sender for digests | — |
| `GMAIL_APP_PASSWORD` | Gmail app password | — |

### Railway
| Variable | Description | Default |
|---|---|---|
| `RAILWAY_URL` | Railway API base URL | — |

---

## Project structure

```
jobsearch/
├── api/                    # FastAPI backend
│   ├── main.py
│   ├── routes/             # auth, jobs, onboard, ingest, admin
│   ├── middleware/          # session auth, admin guards
│   ├── cv/                 # CV generation pipeline (plan → prompt → LLM → validate → docx)
│   ├── db/                 # SQLite init, migrations (001–019), queries
│   ├── ingest.py           # agent output → SQLite
│   ├── scoring.py          # per-user heuristic scoring (no LLM)
│   ├── embeddings.py       # OpenAI embedding service with SQLite cache
│   ├── skill_matcher.py    # semantic skill matching (cosine similarity)
│   ├── geo.py              # geographic utilities
│   └── onboard_utils.py    # CV parsing + profile generation
├── web/                    # React frontend
│   └── src/
│       ├── pages/          # Landing, Login, Onboard, Jobs, JobDetail, Profile, Admin
│       ├── components/     # FilterBar, JobCard, ProfileEditor, ScoreBreakdown, DomainSelector, WaitlistForm, MockDashboard, MockJobDetail, MockCVButton, etc.
│       ├── context/        # AuthContext
│       └── types/          # TypeScript types
├── agent/                  # Scraping/scoring engine
│   ├── main.py             # Pipeline orchestrator (scrape → merge → pre-seed → parse → score → notify)
│   ├── models.py           # RawJob Pydantic model (source-agnostic intermediate representation)
│   ├── merger.py           # Merge duplicate RawJobs across sources (field-priority rules)
│   ├── preseed.py          # Map structured fields to parser schema (pre-seeds before LLM call)
│   ├── api_cache.py        # Cross-user parsed-job cache via Railway DB
│   ├── search_generator.py # generate_queries/generate_unified_queries from search_titles
│   ├── scraper.py          # run_scraper_from_queries() + make_job_id() → list[RawJob]
│   ├── ats_scraper.py      # Greenhouse/Lever/Ashby APIs → list[RawJob]
│   ├── wttj_scraper.py     # Welcome to the Jungle (Algolia) → list[RawJob]
│   ├── prefilter.py        # Keyword filtering (no API calls)
│   ├── parser.py           # gpt-4o-mini structured extraction (pre-seeded)
│   ├── scorer.py           # gpt-4o RAG scoring via ChromaDB
│   ├── notifier.py         # Gmail SMTP digest
│   ├── config/profiles/    # Per-user YAML profiles
│   ├── config/seen_ids/    # Per-user seen job ID lists
│   ├── knowledge/          # Per-user CV knowledge base
│   ├── prompts/            # LLM prompts (parser, scoring rubric)
│   ├── scripts/            # reparse, rescore, ingest payload builder
│   ├── schemas/            # JSON output contracts
│   └── patterns/           # Module interface contracts
├── tests/                  # Backend tests (562), frontend tests (56), agent tests (400)
├── data/                   # jobseeker.db (gitignored)
├── scripts/                # seed_dev.py, backfill_embeddings.py, audit_domain_scoring.py
└── requirements.txt        # Merged deps
```

---

## Development notes

- **Dev backend**: `venv/bin/uvicorn api.main:app --reload --port 8000`
- **Dev frontend**: `cd web && npm run dev`
- **Dev both**: `bash dev.sh`
- **Ingest jobs**: `python -m api.ingest`
- **Run agent**: `cd agent && ../venv/bin/python main.py --profile juan --notify`
- **Backend tests**: `pytest tests/` (run from repo root)
- **Frontend tests**: `cd web && npm test`
- **Agent tests**: `cd agent && pytest tests/`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Dev session cookie** (no OAuth): `document.cookie = "jsk=dev-jsk-juan; path=/"`

---

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Scaffold | ✅ |
| 1 | MVP: Ingest + browse jobs | ✅ |
| 2 | Auth: Google OAuth | ✅ |
| 3 | Onboarding: CV upload → profile | ✅ |
| 4 | UI overhaul + job tracking + profile page | ✅ |
| 5 | CV generation (in-app tailored .docx) | ✅ |
| 6 | CV output quality (plan-driven, validated) | ✅ |
| 7 | Deparameterize scoring (multi-user rubric) | ✅ |
| 8 | Per-profile pipeline (searches, watchlist) | ✅ |
| 9 | Per-user scoring + new-user bootstrap | ✅ |
| 10 | Ops: persistence, health, admin | ✅ |
| 11 | Cross-user dedup + sequential pipeline | ✅ |
| 12 | Semantic skill matching | ✅ |
| 13 | Domain scoring fix (30-domain enum, per-user overrides, admin reparse) | ✅ |
| 14 | Instrumentation + observability (structlog, PostHog, LLM telemetry) | ✅ |
| 15 | Landing page + waitlist (public landing, WaitlistForm, MockDashboard, branding) | ✅ |
| 16 | Landing iteration: MockJobDetail, MockCVButton, CV callout, 4-step How it works | ✅ |
| 17 | Decomposed hybrid scoring: role_function gate, LLM grade rubric (A/B/C), hybrid_score() | ✅ |
| Ingestion Overhaul | RawJob schema, source-group merge, pre-seed parser, enriched DB (14 fields) + API | ✅ |
| Auto-search | search_titles in profile drives queries; unified scraping across profiles; LinkedIn + Indeed | ✅ |
| N | Onboarding UX for new profile fields | 🔜 |
| R | Refactor & test coverage | 🔜 |
| F | Ship: Dockerfile, README, deploy | 🔜 |
