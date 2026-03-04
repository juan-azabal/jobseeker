# Pattern: Notifier Module

## Contract

```python
send_digest(
    railway_url: str,         # Railway API base URL (e.g. https://jobseeker-production.up.railway.app)
    profile_id: str,          # user profile ID — used in GET /api/digest/{profile_id}
    ingest_key: str,          # value for X-Ingest-Key header
    rejected_stats: dict,     # from prefilter_jobs() stats return value
    run_meta: dict,           # {"duration_s", "cost_usd", "n_searches", "n_watchlist", "date"}
    profile: dict | None = None,
) -> bool                     # True if sent, False if failed — never raises
```

**Never raises exceptions. Returns `False` on any error (SMTP, template, missing env vars).**

## Data Flow

```
1. fetch_digest(railway_url, profile_id, ingest_key)
   → GET /api/digest/{profile_id} (X-Ingest-Key auth)
   → returns dict with "jobs": [{tier, title, company, score, ...}]

2. _build_context_from_api(data, rejected_stats, run_meta)
   → splits jobs by tier field ("A" | "B" | "C")
   → flattens each via _flatten_api_job()
   → returns Jinja2 template context dict

3. template.render(**context)
   → HTML email body

4. Gmail SMTP send
```

## fetch_digest

```python
fetch_digest(railway_url: str, profile_id: str, ingest_key: str) -> dict | None
```

- Calls `GET {railway_url}/api/digest/{profile_id}` with `X-Ingest-Key` header
- Upgrades `http://` to `https://` automatically
- Returns parsed JSON dict or `None` on any failure (network, HTTP error, JSON parse)
- Never raises

## Job Flattening

Raw API job dicts are never passed directly to the template. `_flatten_api_job(job: dict) -> dict`
converts them to the flat template schema:

```python
{
    "title":          str,
    "company":        str,
    "location":       str,       # raw location string, may be empty
    "location_type":  str,       # "remote" | "hybrid" | "onsite" | "unknown"
    "requires_reloc": bool,      # True if geo_restricted OR eligibility_warning present
    "salary_display": str,       # "~€120K" or "" if unknown
    "score":          int,       # from API (same as web app)
    "strength":       str,       # always "" (not returned by digest API)
    "gap":            str,       # always "" (not returned by digest API)
    "url":            str,       # external job URL
    "platform_link":  str,       # APP_BASE_URL/jobs/{job_id}; falls back to url if job_id missing
}
```

**Template variables only come from `_flatten_api_job()` output — never from raw API fields.**

## Tier Split

Tiers are assigned by the API (same scoring path as `list_jobs(period="today")`):

```python
tier_a = [jobs where tier == "A"]   # score > 60
tier_b = [jobs where tier == "B"]   # score > 40
tier_c = [jobs where tier == "C"]   # score ≤ 40
```

No local score computation. Thresholds are enforced by the API — see `patterns/scorer.md`.

## Template

Templates: `templates/email_digest.html.j2` (v2, default) · `templates/email_digest_v1.html.j2`
(v1 reference only — requires `strength`/`gap`/local scores that this notifier doesn't produce;
full rollback = git revert of Phase 20b commits).

**v2 design**: Dark-first zinc palette (zinc-950 bg), violet-500 (#8b5cf6) accent. Table-based
layout for Outlook compatibility. Dark mode: `color-scheme` meta tags + `@media prefers-color-scheme`
for Apple Mail/iOS.

Template variables are documented in `schemas/digest_context.json`.

## Email Credentials

Read from environment (`.env`):
- `GMAIL_ADDRESS` — sender
- `GMAIL_APP_PASSWORD` — Gmail App Password (not account password)
- `NOTIFY_EMAIL` — fallback recipient if `profile["user"]["email"]` not set
- `APP_BASE_URL` — platform base URL for digest links (default: `https://jobseeker-production.up.railway.app`)
- `DIGEST_TEMPLATE` — template filename override (default: `email_digest.html.j2`)

## Subject Format

```
"JobSeeker · {n_apply} nuevos roles · {headline} — {date}"
```

Where `headline` is `"{company} · {location_type} · {score}"` from the best Tier A job.

Sender `From` header: `"JobSeeker <{gmail_address}>"`.

## Invariants

- `send_digest()` never raises — all exceptions are caught and logged
- Returns `False` if credentials missing, `fetch_digest` fails, template fails, or SMTP errors
- All tier logic lives in `_build_context_from_api()`, not in the template
- `_flatten_api_job()` is the only translation layer between API response and template
- Zero local scoring — all scores and tiers come from the API
