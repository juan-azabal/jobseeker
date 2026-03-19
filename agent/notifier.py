"""
Email digest notifier using Gmail SMTP + Jinja2.

Fetches today's scored jobs from GET /api/digest/{user_id} (Railway API)
and renders them into the HTML email template. Zero local scoring logic —
all tiers and scores come from the same code path used by the web app.

Usage (called from pipeline.py with --notify):
    from notifier import send_digest
    sent = send_digest(railway_url, user_id, profile_id, ingest_key,
                       rejected_stats, run_meta, profile)

Template variables populated by _build_context_from_api():

  Header:
    date          str  — "04 Mar 2026"
    headline      str  — e.g. "Acme · remote · 82"
    n_apply       int  — Tier A count
    n_review      int  — Tier B count
    n_skip        int  — Tier C count
    n_prefiltered int  — total jobs rejected by prefilter

  Tiers (lists of flattened job dicts):
    tier_a  — score > 60  (full card)
    tier_b  — score > 40  (compact row)
    tier_c  — score ≤ 40  (single line)

  Each job dict in a tier has:
    title         str
    company       str
    location      str  — raw location string, may be empty
    location_type str  — "remote" | "hybrid" | "onsite" | "unknown"
    requires_reloc bool — geo_restricted OR eligibility_warning present
    salary_display str  — "~€120K" or "" if unknown
    score         int  — from API (same as web app)
    strength      str  — always "" (not returned by digest API)
    gap           str  — always "" (not returned by digest API)
    url           str  — external job URL
    platform_link str  — /jobs/{job_id} on the platform

  Footer:
    rejected_stats  dict — {total, us_only, no_pm_keyword, deal_breaker, ...}
    run_meta        dict — {n_searches, n_watchlist, duration_s, cost_usd}
"""

import os
from datetime import date
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = os.getenv("DIGEST_TEMPLATE", "email_digest.html.j2")

_APP_BASE_URL_DEFAULT = "https://jobseeker-production.up.railway.app"


def fetch_digest(railway_url: str, user_id: int, ingest_key: str) -> dict | None:
    """GET /api/digest/{user_id} from the Railway API.

    Returns the parsed JSON response dict, or None on any failure.
    Upgrades http:// to https:// automatically.
    """
    url = railway_url.rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    endpoint = f"{url}/api/digest/{user_id}"
    try:
        resp = httpx.get(
            endpoint,
            headers={"X-Ingest-Key": ingest_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"⚠  fetch_digest failed ({exc})")
        return None


def _format_salary(min_amount, max_amount, currency) -> str:
    """Format salary range for display. Returns '' if no data."""
    amount = max_amount or min_amount
    if not amount:
        return ""
    if currency and currency.upper() == "EUR":
        return f"~€{int(amount / 1000)}K"
    if currency and currency.upper() == "USD":
        return f"~${int(amount / 1000)}K"
    return f"~{int(amount / 1000)}K"


def _flatten_api_job(job: dict) -> dict:
    """Map a digest API job dict to the flat schema the email template expects."""
    app_base_url = os.getenv("APP_BASE_URL", _APP_BASE_URL_DEFAULT)
    job_id = job.get("job_id") or ""
    platform_link = f"{app_base_url}/jobs/{job_id}" if job_id else job.get("url", "#")

    return {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location") or "",
        "location_type": job.get("location_type") or "unknown",
        "requires_reloc": bool(job.get("geo_restricted") or job.get("eligibility_warning")),
        "salary_display": _format_salary(job.get("salary_min"), job.get("salary_max"), job.get("salary_currency")),
        "score": job.get("score", 0),
        "strength": "",  # not returned by digest API
        "gap": "",  # not returned by digest API
        "url": job.get("url", "#"),
        "platform_link": platform_link,
    }


def _build_headline(tier_a: list) -> str:
    """Generate headline from best Tier A job. Falls back gracefully."""
    if not tier_a:
        return "No top roles today"
    best = tier_a[0]
    company = best["company"]
    loc_type = best["location_type"]
    score = best.get("score", 0)
    return f"{company} · {loc_type} · {score}"


def _build_context_from_api(data: dict, rejected_stats: dict, run_meta: dict) -> dict:
    """Build Jinja2 template context from the /api/digest response."""
    jobs = data.get("jobs") or []
    tier_a = [_flatten_api_job(j) for j in jobs if j.get("tier") == "A"]
    tier_b = [_flatten_api_job(j) for j in jobs if j.get("tier") == "B"]
    tier_c = [_flatten_api_job(j) for j in jobs if j.get("tier") == "C"]

    n_apply = len(tier_a)
    n_review = len(tier_b)
    n_prefiltered = rejected_stats.get("total", 0) - rejected_stats.get("passed", 0)
    platform_url = os.getenv("APP_BASE_URL", _APP_BASE_URL_DEFAULT)

    return {
        "date": run_meta.get("date", date.today().strftime("%d %b %Y")),
        "headline": _build_headline(tier_a),
        "n_apply": n_apply,
        "n_review": n_review,
        "n_skip": len(tier_c),
        "n_prefiltered": n_prefiltered,
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_c": tier_c,
        "rejected_stats": rejected_stats,
        "run_meta": run_meta,
        "platform_url": platform_url,
        "preheader": f"{n_apply} para aplicar, {n_review} para revisar",
    }


def send_smtp(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via Gmail SMTP. Returns True on success, False on failure. Never raises.

    Reads GMAIL_ADDRESS and GMAIL_APP_PASSWORD from env.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_password:
        print("⚠  GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"JobSeeker <{gmail_address}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, to, msg.as_string())
        print(f"\n📧 Email sent → {to}")
        return True
    except Exception as e:
        print(f"⚠  Gmail SMTP error: {e}")
        return False


def send_digest(
    railway_url: str,
    user_id: int,
    profile_id: str,
    ingest_key: str,
    rejected_stats: dict,
    run_meta: dict,
    profile: dict | None = None,
) -> bool:
    """Fetch digest from API and send HTML email via Gmail SMTP.

    Args:
        railway_url:    Base URL of the Railway API.
        user_id:        Integer user ID — used in GET /api/digest/{user_id}.
        profile_id:     String profile ID — used for logging only.
        ingest_key:     Value for X-Ingest-Key header.
        rejected_stats: Counts by rejection reason from prefilter_jobs().
        run_meta:       {"duration_s", "cost_usd", "n_searches", "n_watchlist", "date"}.
        profile:        User profile dict. Recipient from profile["user"]["email"],
                        falls back to NOTIFY_EMAIL env var.

    Returns:
        True if email sent, False on any failure. Never raises.
    """
    to_email = None
    if profile:
        to_email = (profile.get("user") or {}).get("email")
    if not to_email:
        to_email = os.getenv("NOTIFY_EMAIL")

    if not os.getenv("GMAIL_ADDRESS") or not os.getenv("GMAIL_APP_PASSWORD"):
        print("⚠  GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email notification")
        return False
    if not to_email:
        print("⚠  No recipient email (set user.email in profile or NOTIFY_EMAIL) — skipping")
        return False

    data = fetch_digest(railway_url, user_id, ingest_key)
    if data is None:
        print("⚠  Could not fetch digest from API — skipping email")
        return False

    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
        template = env.get_template(TEMPLATE_NAME)
        context = _build_context_from_api(data, rejected_stats, run_meta)
        html_body = template.render(**context)
    except Exception as e:
        print(f"⚠  Email template render failed: {e}")
        return False

    n_apply = context["n_apply"]
    run_date = context["date"]
    headline = context["headline"]
    subject = f"JobSeeker · {n_apply} nuevos roles · {headline} — {run_date}"

    return send_smtp(to_email, subject, html_body)
