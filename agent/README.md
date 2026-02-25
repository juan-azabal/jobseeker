# JobAgent

AI-powered job search agent that scores listings against your CV, detects skill gaps over time, and delivers daily email digests. Built for developers who'd rather configure YAML than click through job boards.

**Time to First Digest: < 5 minutes** from clone to email in your inbox.

## How it works

```
Job Sources          Intelligence                    Output
─────────────        ────────────                    ──────
Indeed  ─┐
Google  ─┤                        ┌─ Language detection   ┌─ Email digest
LinkedIn ┼─→ Dedup → Prefilter ─┤  US-only detection  ─→ │  (daily, tiered)
Greenhouse└─  Deal breaker scan  │
Lever   ──┘                       │  ┌─ Heuristic gate      │
                          LLM Parse ─┤  (cost control)  ─→ ├─ Gap history
                                     └─ LLM Score vs CV     │  (JSONL, 90 days)
                                        (full CV in context, │
                                        not RAG — see ADR-001)└─ JSON output
```

73 listings scraped → 16 pass prefilter → 16 parsed → scored and ranked → email with apply/review/skip tiers. Runs in ~90 seconds. Costs ~$0.11/run.

## Quickstart

```bash
git clone https://github.com/yourusername/jobagent.git
cd jobagent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env        # Add OPENAI_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFY_EMAIL
nano config/profiles/juan.yaml  # Edit profile to match your background

# Run
python main.py --notify
```

Check your email. You should have a digest with scored job listings, strengths, gaps, and direct apply links per role.

## Scoring

Each job is evaluated across 5 dimensions against your full CV:

| Dimension | Weight | Source |
|---|---|---|
| Domain fit | 0–25 | Work history domains × recency × duration |
| Seniority fit | 0–20 | Auto-computed from target level + career track |
| Technical depth | 0–20 | Role requirements vs candidate foundation |
| Profile evidence | 0–20 | How well CV excerpts support JD requirements |
| Strategic impact | 0–15 | Trajectory advance vs lateral move |

Jobs scoring ≥50 land in **Tier A** (apply), 30–49 in **Tier B** (review), <30 in **Tier C** (skip).

A post-parse heuristic gate ([ADR-006](docs/decisions/006-post-parse-heuristic-gate.md)) skips expensive LLM scoring for jobs the heuristic already identifies as poor fits. They still appear in your digest — they're just not scored with the full rubric.

### Relocation detection

Remote jobs pinned to specific countries ("Remote from Portugal", "EU only", "EMEA") are automatically detected. Region membership (EU, EEA, Schengen, EMEA, APAC, Americas) is auto-derived from the user's `home_locations` via [country-converter](https://github.com/konstantinstadler/country_converter) — no manual region config needed. A Spain-based user sees "EU only" as accessible; a US-based user sees it as relocation. Salary normalization uses ECB reference rates via CurrencyConverter ([ADR-007](docs/decisions/007-library-backed-geo-currency-lang.md)).

## Gap tracking

Every scored job's strengths and gaps are persisted to `data/gap_history/`. Over time this reveals:

- **Skill gaps** that recur across high-fit roles (actionable: take a course, build a project)
- **Storytelling gaps** where you have the experience but your CV doesn't surface it (actionable: rewrite bullets)
- **Scoring bugs** where the system flags a gap that contradicts your CV (actionable: adjust the scoring prompt)

Gap analysis across rolling windows is planned. The data accumulates from day one.

## Built with Claude Code

This project was built using Claude Code as a development accelerator. The architecture, trade-off decisions, prompt design, and product direction are mine — Claude Code handles implementation under constraints I define and maintain.

This is a deliberate design choice, not a shortcut. A senior PM in 2026 who can't leverage AI coding tools is leaving significant velocity on the table. The question isn't whether to use them, but how to maintain quality and ownership when you do.

**How I maintain ownership and quality:**

The repo is structured so that the high-leverage decisions live in human-readable files that Claude Code reads as context — not scattered through Python strings:

- `CLAUDE.md` — architecture, invariants, and constraints Claude must follow
- `prompts/` — scoring rubric and parser logic, versioned as source of truth
- `patterns/` — interface contracts per module, updated before Claude touches related code
- `.claude/rules/` — session-level conventions (coding style, doc-sync protocol)

When I change the scoring model or remove a feature, I update the relevant `patterns/` file first. Claude Code reads it and implements accordingly. When it doesn't — I catch it in review and tighten the rules. That feedback loop is itself a product decision.

**What this means in practice:**

Every architectural decision in this repo has an ADR explaining the trade-off. Every module has an interface contract in `patterns/`. Prompts are treated as code — versioned, externalised, never inlined. The result is a codebase I can reason about, modify, and hand off — even if most of the Python was generated.

See [ADR-002](docs/decisions/002-llm-friendly-dx.md) for the full rationale on LLM-friendly DX as a design principle.

## Architecture decisions

Every significant trade-off is documented as an ADR in [`docs/decisions/`](docs/decisions/):

| ADR | Decision | Key trade-off |
|---|---|---|
| [001](docs/decisions/001-full-cv-over-rag.md) | Full CV in context over RAG | Eliminated ChromaDB. CV is 5K tokens — RAG retrieval caused information loss without cost savings |
| [002](docs/decisions/002-llm-friendly-dx.md) | LLM-friendly DX as design principle | Repo designed for LLM consumption: patterns, schemas, versioned prompts |
| [003](docs/decisions/003-mini-over-4o-scoring.md) | gpt-4o-mini for parsing, gpt-4o for scoring | Parsing is extraction (mini sufficient); scoring needs nuanced judgment (4o) |
| [004](docs/decisions/004-email-digest-over-webapp.md) | Email digest over web app | 90% of value at 10% of effort. Push beats pull for job search consistency |
| [005](docs/decisions/005-monochrome-palette.md) | Monochrome zinc + orange accent | Accessibility (deuteranopia-safe), graceful email client degradation |
| [006](docs/decisions/006-post-parse-heuristic-gate.md) | Post-parse heuristic gate | Cost control: skip LLM scoring for obvious non-fits. Jobs still visible in digest |
| [007](docs/decisions/007-library-backed-geo-currency-lang.md) | Library-backed geo, currency, and language | Replace hardcoded maps with country-converter, CurrencyConverter (ECB), babel, pytz |

## Configuration

All configuration is YAML. Profile drives scoring weights, search config drives sources.

```
config/
├── profiles/juan.yaml    # Your background, target role, skills, salary floor
├── preferences.yaml      # Deal breakers, title rules, excluded companies
├── searches.yaml         # Job board search terms and locations
└── watchlist.yaml        # Company ATS boards to poll (Greenhouse/Lever slugs)
```

Seniority weights are auto-computed from `target.level` + `target.track` in your profile. You declare intent ("I want principal IC roles"), the system calculates the weights. See the seniority weight generation section in `CLAUDE.md`.

## Scheduling

GitHub Actions runs the pipeline daily at 07:00 CET on weekdays:

```yaml
# .github/workflows/jobagent_daily.yml
on:
  schedule:
    - cron: '0 6 * * 1-5'  # 06:00 UTC = 07:00 CET
  workflow_dispatch:         # Manual trigger (optional profile input)
```

Pipeline runs profiles sequentially — each syncs parsed data to Railway before the next starts, enabling cross-user dedup. Requires repo secrets: `OPENAI_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RAILWAY_URL`, `INGEST_API_KEY`.

## Project structure

```
├── main.py              # Pipeline orchestrator (12-step pipeline)
├── api_cache.py         # Cross-user parsed-job cache via Railway DB
├── scraper.py           # Indeed/Google/LinkedIn via python-jobspy
├── ats_scraper.py       # Greenhouse/Lever/Ashby API poller
├── wttj_scraper.py      # Welcome to the Jungle (Algolia API)
├── prefilter.py         # Fast keyword filtering (no API calls)
├── parser.py            # LLM extraction (gpt-4o-mini)
├── scorer.py            # LLM scoring (gpt-4o, full CV context via ChromaDB)
├── vectorstore.py       # ChromaDB knowledge base builder/loader
├── gap_tracker.py       # Persists strengths/gaps to JSONL
├── notifier.py          # Email digest via Gmail SMTP
├── geo.py               # Geographic utilities (country-converter, pytz, babel)
├── user_config.py       # Profile loading, seniority weight computation
├── config/              # YAML configuration (profiles, searches, preferences, seen_ids)
├── knowledge/           # Per-user CV/knowledge base for scoring (read-only)
├── prompts/             # Versioned business logic prompts (source of truth)
├── patterns/            # Interface contracts for LLM developers
├── schemas/             # Output format contracts (JSON Schema)
├── scripts/             # reparse, rescore, ingest payload, list active profiles
├── docs/decisions/      # Architecture Decision Records (001-007)
├── templates/           # Jinja2 email templates
├── tests/               # 113 tests
├── data/                # Runtime data (gap history, gitignored)
└── output/              # JSON results per run (gitignored)
```

## Tech stack

- Python 3.12
- OpenAI API (gpt-4o-mini for parsing, gpt-4o for scoring)
- python-jobspy + Greenhouse/Lever/Ashby APIs + WTTJ Algolia for job sourcing
- country-converter + babel + pytz for geographic region detection, language mapping, and timezone classification
- CurrencyConverter (ECB reference rates) for salary normalization to EUR
- Gmail SMTP for email delivery
- Jinja2 for email templates
- GitHub Actions for daily scheduling

Part of the jobsearch monorepo — the agent is the scraping/scoring engine, while the web app and API live in the parent directory. See the ADRs for architectural decisions.

## Cost

~$0.11/run. ~$2.42/month at 22 weekday runs. Parsing uses gpt-4o-mini (~$0.001/job), scoring uses gpt-4o (~$0.04/job). The heuristic gate keeps scored jobs to a minimum.

## Status

| Phase | Status |
|---|---|
| Scrape + prefilter + parse + heuristic rank | ✅ Complete |
| LLM scoring with full CV context | ✅ Complete |
| Email digest + GitHub Actions | ✅ Complete |
| Gap persistence | ✅ Complete |
| DX layer (ADRs, patterns, schemas, prompts) | ✅ Complete |
| Onboarding from CV (onboard.py) | ✅ Complete |
| Multi-user scoring + geo/currency/lang libs | ✅ Complete |
| Cross-user dedup + sequential pipeline | ✅ Complete |
| Gap analysis + recommendations | 🔜 Planned |
| CV tailoring per application | 📋 Future |

## License

MIT
