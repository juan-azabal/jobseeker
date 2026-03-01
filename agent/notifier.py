"""Email digest notifier using Gmail SMTP + Jinja2.

Architecture (Phase 20b):
  Fetches scored/tiered jobs from GET /api/digest/{profile_id} on Railway,
  so the email uses the exact same scoring as the web app. Zero local scoring.

Usage (called from main.py with --notify):
    from notifier import send_digest
    sent = send_digest(
        railway_url=..., profile_id=..., ingest_key=...,
        rejected_stats=..., run_meta=..., profile=...,
    )

Template context built by _build_context_from_api():
  date          str  — "01 Mar 2026"
  headline      str  — e.g. "ClickHouse · remote · 82"
  n_apply       int  — Tier A count
  n_review      int  — Tier B count
  n_skip        int  — Tier C count
  n_prefiltered int  — jobs rejected by prefilter
  preheader     str  — hidden inbox preview text
  platform_url  str  — base platform URL for dashboard links
  tier_a        list[dict] — full cards (no strength/gap)
  tier_b        list[dict] — compact rows
  tier_c        list[dict] — single lines
  rejected_stats dict
  run_meta       dict

Each job dict in a tier:
  title, company, location, location_type, requires_reloc,
  salary_display, score, tier, url, platform_link, eligibility_warning
"""

import os
import time
from datetime import date
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = os.getenv("DIGEST_TEMPLATE", "email_digest.html.j2")

_APP_BASE_URL_DEFAULT = "https://jobseeker-production.up.railway.app"


# ---------------------------------------------------------------------------
# Digest API client
# ---------------------------------------------------------------------------


def fetch_digest(railway_url: str, profile_id: str, ingest_key: str) -> dict | None:
    """Fetch today's scored jobs from GET /api/digest/{profile_id}.

    Retries once on timeout or 5xx with 5s backoff.
    Returns parsed JSON dict or None on failure.
    """
    url = railway_url.rstrip("/")
    endpoint = f"{url}/api/digest/{profile_id}"
    headers = {"X-Ingest-Key": ingest_key}

    for attempt in range(2):
        try:
            resp = httpx.get(endpoint, headers=headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as exc:
            if attempt == 0:
                print("⚠  Digest fetch timeout (attempt 1), retrying in 5s…")
                time.sleep(5)
            else:
                print(f"⚠  Digest fetch timeout after retry: {exc}")
                return None
        except Exception as exc:
            if attempt == 0:
                print(f"⚠  Digest fetch error (attempt 1): {exc}, retrying in 5s…")
                time.sleep(5)
            else:
                print(f"⚠  Digest fetch failed after retry: {exc}")
                return None

    return None


# ---------------------------------------------------------------------------
# Job flattening
# ---------------------------------------------------------------------------


def _format_salary(job: dict) -> str:
    """Format salary_max (or salary_min) + currency for display.

    Returns "~€120K", "~$90K", or "" if no salary data.
    """
    amount = job.get("salary_max") or job.get("salary_min")
    currency = job.get("salary_currency") or ""

    if not amount or amount <= 0:
        return ""

    symbol_map = {"EUR": "€", "USD": "$", "GBP": "£"}
    symbol = symbol_map.get(currency.upper(), currency or "€")
    return f"~{symbol}{int(amount / 1000)}K"


def _flatten_api_job(job: dict, app_base_url: str) -> dict:
    """Map an API digest job dict to the flat schema the template expects."""
    job_id = job.get("job_id") or ""
    platform_link = f"{app_base_url}/jobs/{job_id}" if job_id else job.get("url", "#")

    return {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location") or "",
        "location_type": job.get("location_type") or "unknown",
        "requires_reloc": job.get("geo_restricted", False),
        "salary_display": _format_salary(job),
        "score": job.get("score", 0),
        "tier": job.get("tier", "C"),
        "url": job.get("url", "#"),
        "platform_link": platform_link,
        "eligibility_warning": job.get("eligibility_warning"),
    }


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_headline(tier_a: list) -> str:
    """Generate headline from best Tier A job. Falls back gracefully."""
    if not tier_a:
        return "No top roles today"
    best = tier_a[0]
    company = best["company"]
    loc_type = best["location_type"]
    score = best.get("score", 0)
    return f"{company} · {loc_type} · {score}"


def _build_context_from_api(digest: dict, rejected_stats: dict, run_meta: dict) -> dict:
    """Build Jinja2 template context from the API digest response.

    Groups jobs by tier field (no local threshold logic).
    """
    app_base_url = os.getenv("APP_BASE_URL", _APP_BASE_URL_DEFAULT)
    jobs = digest.get("jobs", [])

    tier_a = [_flatten_api_job(j, app_base_url) for j in jobs if j.get("tier") == "A"]
    tier_b = [_flatten_api_job(j, app_base_url) for j in jobs if j.get("tier") == "B"]
    tier_c = [_flatten_api_job(j, app_base_url) for j in jobs if j.get("tier") == "C"]

    headline = _build_headline(tier_a)
    n_apply = len(tier_a)
    n_review = len(tier_b)
    n_prefiltered = rejected_stats.get("total", 0) - rejected_stats.get("passed", 0)
    run_date = run_meta.get("date", date.today().strftime("%d %b %Y"))

    return {
        "date": run_date,
        "headline": headline,
        "n_apply": n_apply,
        "n_review": n_review,
        "n_skip": len(tier_c),
        "n_prefiltered": n_prefiltered,
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_c": tier_c,
        "rejected_stats": rejected_stats,
        "run_meta": run_meta,
        "platform_url": app_base_url,
        "preheader": f"{n_apply} para aplicar, {n_review} para revisar",
    }


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


def send_digest(
    railway_url: str,
    profile_id: str,
    ingest_key: str,
    rejected_stats: dict,
    run_meta: dict,
    profile: dict = None,
) -> bool:
    """Fetch today's jobs from API and send the HTML email digest.

    Args:
        railway_url:    Railway base URL (e.g. https://jobseeker.railway.app).
        profile_id:     Profile identifier used for GET /api/digest/{profile_id}.
        ingest_key:     X-Ingest-Key value for API auth.
        rejected_stats: Counts by rejection reason from prefilter_jobs().
        run_meta:       {"duration_s", "cost_usd", "n_searches", "n_watchlist", "date"}.
        profile:        User profile dict. Email recipient read from profile["user"]["email"].
                        Falls back to NOTIFY_EMAIL env var.

    Returns:
        True if sent successfully, False otherwise. Never raises.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    to_email = None
    if profile:
        to_email = (profile.get("user") or {}).get("email")
    if not to_email:
        to_email = os.getenv("NOTIFY_EMAIL")

    if not gmail_address or not gmail_password:
        print("⚠  GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email")
        return False
    if not to_email:
        print("⚠  No recipient email — skipping email")
        return False

    # Fetch jobs from API
    digest = fetch_digest(railway_url, profile_id, ingest_key)
    if digest is None:
        print("⚠  Digest fetch failed — skipping email")
        return False

    summary = digest.get("summary", {})
    if summary.get("total", 0) == 0:
        print("⚠  No jobs in digest today — skipping email")
        return False

    # Render template
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
        template = env.get_template(TEMPLATE_NAME)
        context = _build_context_from_api(digest, rejected_stats, run_meta)
        html_body = template.render(**context)
    except Exception as e:
        print(f"⚠  Email template render failed: {e}")
        return False

    # Build subject
    n_apply = context["n_apply"]
    run_date = context["date"]
    headline = context["headline"]
    subject = f"JobSeeker · {n_apply} nuevos roles · {headline} — {run_date}"

    # Send via Gmail SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"JobSeeker <{gmail_address}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, to_email, msg.as_string())

        print(f"\n📧 Email sent → {to_email}")
        return True
    except Exception as e:
        print(f"⚠  Gmail SMTP error: {e}")
        return False
