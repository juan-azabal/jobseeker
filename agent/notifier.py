"""
Email digest notifier using Gmail SMTP + Jinja2.

Usage (called from main.py with --notify):
    from notifier import send_digest
    sent = send_digest(jobs, rejected_stats, run_meta)

Template variables populated by _build_context():

  Header:
    date          str  — "20 Feb 2026"
    headline      str  — e.g. "ClickHouse · remote data platform"
    n_apply       int  — Tier A count (score >= 50)
    n_review      int  — Tier B count (score 30-49)
    n_skip        int  — Tier C count (score < 30)
    n_prefiltered int  — total jobs rejected by prefilter

  Tiers (lists of flattened job dicts):
    tier_a  — score >= 50  (full card: strength, gap)
    tier_b  — score 30-49  (compact row)
    tier_c  — score < 30   (single line)

  Each job dict in a tier has:
    title         str
    company       str
    location      str  — raw location string, may be empty
    location_type str  — "remote" | "hybrid" | "onsite" | "unknown"
    requires_reloc bool
    salary_display str  — "~€120K" or "" if unknown
    score         int  — display score (RAG if available, else heuristic)
    strength      str  — first RAG strength claim, or top matched skill
    gap           str  — first RAG gap, or "–" if none
    url           str

  Footer:
    rejected_stats  dict — {total, us_only, no_pm_keyword, deal_breaker, title_excluded, ...}
    run_meta        dict — {n_searches, n_watchlist, duration_s, cost_usd}

DO NOT regenerate the template — design is final.
"""

import os
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = os.getenv("DIGEST_TEMPLATE", "email_digest.html.j2")


def _is_reloc(job, home_locations=None, home_regions=None) -> bool:
    """Return True if role requires relocating.

    Remote jobs: checks restriction/title/location for country pinning.
    Non-remote: checks if job location matches user's home locations.
    """
    from reloc import is_remote_requiring_reloc as _is_remote_requiring_reloc

    parsed = job.get("parsed") or {}
    loc_type = parsed.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    _home = [loc.lower() for loc in (home_locations or [])]
    _regions = [r.lower() for r in (home_regions or [])]
    if loc_type == "remote":
        return _is_remote_requiring_reloc(job, home_locations=_home, home_regions=_regions)
    if any(c in job_loc for c in _home):
        return False
    return True


def _salary_display(salary_eur: float) -> str:
    """Format salary for display. Returns empty string if unknown."""
    if salary_eur and salary_eur > 0:
        return f"~€{int(salary_eur / 1000)}K"
    return ""


_APP_BASE_URL_DEFAULT = "https://jobseeker-production.up.railway.app"


def _flatten_job(job, home_locations=None, home_regions=None) -> dict:
    """Convert a raw pipeline job dict into the flat schema the template expects."""
    parsed = job.get("parsed") or {}
    rag = job.get("rag_score") or {}

    # Strength: first RAG strength claim, or top matched skill as fallback
    strength = ""
    rag_strengths = rag.get("strengths") or []
    if rag_strengths:
        strength = rag_strengths[0].get("claim", "")
    if not strength:
        skills = parsed.get("truly_required") or parsed.get("must_have_skills") or []
        strength = skills[0] if skills else ""

    # Gap: first RAG gap, or empty
    gap = ""
    rag_gaps = rag.get("gaps") or []
    if rag_gaps:
        gap = rag_gaps[0].get("gap", "")

    salary_eur = job.get("_salary_eur", 0) or 0

    # Platform link: prefer /jobs/{job_id} hash, fall back to external URL
    app_base_url = os.getenv("APP_BASE_URL", _APP_BASE_URL_DEFAULT)
    job_id = job.get("job_id") or ""
    if job_id:
        platform_link = f"{app_base_url}/jobs/{job_id}"
    else:
        platform_link = job.get("job_url", "#")

    return {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location") or "",
        "location_type": parsed.get("location_type") or "unknown",
        "requires_reloc": _is_reloc(job, home_locations, home_regions),
        "salary_display": _salary_display(salary_eur),
        "score": job.get("_display_score", 0),
        "strength": strength,
        "gap": gap,
        "url": job.get("job_url", "#"),
        "platform_link": platform_link,
    }


def _sort_key(job_flat: dict):
    """Sort: no-reloc first, then score desc, then salary desc (parsed from display)."""
    reloc = 1 if job_flat["requires_reloc"] else 0
    score = -job_flat["score"]
    # Extract numeric salary from display string for tie-breaking
    sal_str = job_flat["salary_display"]
    sal = 0
    if sal_str:
        import re

        m = re.search(r"(\d+)", sal_str)
        if m:
            sal = -int(m.group(1))
    return (reloc, score, sal)


def _build_headline(tier_a: list) -> str:
    """Generate headline from best Tier A job. Falls back gracefully."""
    if not tier_a:
        return "No top roles today"
    best = tier_a[0]
    company = best["company"]
    loc_type = best["location_type"]
    score = best.get("score", 0)
    return f"{company} · {loc_type} · {score}"


def _build_context(jobs, rejected_stats, run_meta, profile=None):
    """Build Jinja2 template context from pipeline data."""
    from salary import extract_max_salary_eur as _extract_max_salary_eur
    from scoring import heuristic_score as _heuristic_score

    home_locations = None
    home_regions = None
    if profile:
        from geo import derive_home_regions

        home_locations = profile.get("user", {}).get("home_locations")
        home_regions = derive_home_regions([loc.lower() for loc in (home_locations or [])])

    parsed_jobs = [j for j in jobs if j.get("parsed")]

    # Ensure scoring fields exist
    for j in parsed_jobs:
        if "_salary_eur" not in j:
            j["_salary_eur"] = _extract_max_salary_eur(j)
        if "_display_score" not in j:
            from shared.scoring_core import grade_to_points as _grade_to_points

            j["_fit_score"] = _heuristic_score(j)
            rag = j.get("rag_score")
            if rag is None:
                j["_display_score"] = j["_fit_score"]
            elif "score" in rag:
                j["_display_score"] = rag["score"]
            else:
                tech_pts = _grade_to_points(rag.get("technical_depth"))
                prof_pts = _grade_to_points(rag.get("profile_evidence"))
                j["_display_score"] = min(100, max(0, j["_fit_score"] + tech_pts + prof_pts))

    # Split tiers and flatten
    tier_a_raw = sorted(
        [j for j in parsed_jobs if j["_display_score"] >= 50],
        key=lambda j: (
            1 if _is_reloc(j, home_locations, home_regions) else 0,
            -j["_display_score"],
            -j.get("_salary_eur", 0),
        ),
    )
    tier_b_raw = sorted(
        [j for j in parsed_jobs if 30 <= j["_display_score"] < 50],
        key=lambda j: (
            1 if _is_reloc(j, home_locations, home_regions) else 0,
            -j["_display_score"],
            -j.get("_salary_eur", 0),
        ),
    )
    tier_c_raw = sorted([j for j in parsed_jobs if j["_display_score"] < 30], key=lambda j: -j["_display_score"])

    tier_a = [_flatten_job(j, home_locations, home_regions) for j in tier_a_raw]
    tier_b = [_flatten_job(j, home_locations, home_regions) for j in tier_b_raw]
    tier_c = [_flatten_job(j, home_locations, home_regions) for j in tier_c_raw]

    headline = _build_headline(tier_a)
    n_prefiltered = rejected_stats.get("total", 0) - rejected_stats.get("passed", 0)
    platform_url = os.getenv("APP_BASE_URL", _APP_BASE_URL_DEFAULT)
    n_apply = len(tier_a)
    n_review = len(tier_b)

    return {
        "date": run_meta.get("date", date.today().strftime("%d %b %Y")),
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
        "platform_url": platform_url,
        "preheader": f"{n_apply} para aplicar, {n_review} para revisar",
    }


def send_digest(
    jobs: list,
    rejected_stats: dict,
    run_meta: dict,
    profile: dict = None,
) -> bool:
    """Render and send the HTML email digest via Gmail SMTP.

    Args:
        jobs:           All parsed jobs from the pipeline (_salary_eur and
                        _display_score should already be set by print_summary).
        rejected_stats: Counts by rejection reason from prefilter_jobs().
        run_meta:       {"duration_s", "cost_usd", "n_searches", "n_watchlist", "date"}.
        profile:        User profile dict. Email recipient is read from profile["user"]["email"].
                        Falls back to NOTIFY_EMAIL env var if not set in profile.

    Returns:
        True if sent successfully, False otherwise. Never raises.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    # Prefer email from profile; fall back to NOTIFY_EMAIL env var for backward compat
    to_email = None
    if profile:
        to_email = (profile.get("user") or {}).get("email")
    if not to_email:
        to_email = os.getenv("NOTIFY_EMAIL")

    if not gmail_address or not gmail_password:
        print("⚠  GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email notification")
        return False
    if not to_email:
        print("⚠  No recipient email (set user.email in profile or NOTIFY_EMAIL env var) — skipping")
        return False

    # Render template
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
        template = env.get_template(TEMPLATE_NAME)
        context = _build_context(jobs, rejected_stats, run_meta, profile=profile)
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
