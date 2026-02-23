# Pattern: Notifier Module

## Contract

```python
send_digest(
    jobs: list[dict],           # all parsed jobs from pipeline
    rejected_stats: dict,       # from prefilter_jobs() stats return value
    run_meta: dict,             # {"duration_s", "cost_usd", "n_searches", "n_watchlist", "date"}
    profile: dict | None = None,
) -> bool                       # True if sent, False if failed — never raises
```

**Never raises exceptions. Returns `False` on any error (SMTP, template, missing env vars).**

## Job Flattening

Raw pipeline job dicts are never passed directly to the template. `_flatten_job(job, home_locations=None) -> dict` at `notifier.py:73` converts them to the flat template schema:

```python
{
    "title":          str,
    "company":        str,
    "location":       str,       # raw location string, may be empty
    "location_type":  str,       # "remote" | "hybrid" | "onsite" | "unknown"
    "requires_reloc": bool,      # True if role is not remote and not in home_locations
    "salary_display": str,       # "~€120K" or "" if unknown
    "score":          int,       # _display_score (RAG if available, else heuristic)
    "strength":       str,       # first RAG strength claim, or first must_have_skill
    "gap":            str,       # first RAG gap, or ""
    "url":            str,
}
```

**Template variables only come from `_flatten_job()` output — never from raw pipeline fields.**

## Tier Split and Sort

```python
tier_a = [jobs where _display_score >= 50]  # sorted: no-reloc first, score desc, salary desc
tier_b = [jobs where 30 <= score < 50]       # same sort
tier_c = [jobs where score < 30]             # sorted: score desc only
```

These thresholds mirror `patterns/scorer.md`. If you change tier boundaries, update both.

## Template

Template: `templates/email_digest.html.j2`

**DO NOT regenerate the template — design is final.** Zinc monochrome palette, orange (#e97316) accent on CTAs only. Table-based layout for Outlook compatibility.

Template variables are documented in `schemas/digest_context.json`.

## Email Credentials

Read from environment (`.env`):
- `GMAIL_ADDRESS` — sender
- `GMAIL_APP_PASSWORD` — Gmail App Password (not account password)
- `NOTIFY_EMAIL` — fallback recipient if `profile["user"]["email"]` not set

## Subject Format

```
"JobAgent: {n_apply} roles · {headline} — {date}"
```

Where `headline` is `"{company} · {location_type}"` from the best Tier A job.

## Invariants

- `send_digest()` never raises — all exceptions are caught and logged
- Returns `False` if credentials missing, template fails, or SMTP errors
- All tier logic and sorting lives in `_build_context()`, not in the template
- `_flatten_job()` is the only translation layer between pipeline and template
