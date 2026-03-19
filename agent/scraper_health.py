"""Scraper health monitoring — per-source metrics and health evaluation.

Collects structured metadata from a scrape run, evaluates against fixed
thresholds, and surfaces issues via PostHog, GHA annotations, and email.

Pure collection and evaluation functions. Side-effect functions (email,
PostHog) are best-effort: they catch all exceptions and return bool/None.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Thresholds ────────────────────────────────────────────────────────────────

THRESHOLDS: dict[str, dict] = {
    "indeed": {"min_jobs": 3, "min_desc_pct": 0.5, "min_desc_len": 100},
    "linkedin": {"min_jobs": 3, "min_desc_pct": 0.5, "min_desc_len": 100},
    "wttj": {"min_jobs": 3, "min_desc_pct": 0.7, "min_desc_len": 100},
    "greenhouse": {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
    "lever": {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
    "ashby": {"min_jobs": 1, "min_desc_pct": 0.8, "min_desc_len": 200},
}
_DEFAULT_THRESHOLD = {"min_jobs": 1, "min_desc_pct": 0.5, "min_desc_len": 100}

# Verdict constants
OK = "ok"
WARNING = "warning"
CRITICAL = "critical"

_VERDICT_RANK = {OK: 0, WARNING: 1, CRITICAL: 2}


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class ScraperMeta:
    """Raw per-source metrics measured after a scrape run."""

    source: str
    job_count: int
    error: str | None  # exception message if scraper failed entirely
    has_description_pct: float  # fraction of jobs with non-empty description
    median_desc_length: int  # median len(description) among non-empty
    has_location_pct: float  # fraction with non-empty location
    has_company_pct: float  # fraction with non-empty company


@dataclass
class SourceHealth:
    """Evaluated health verdict for a single source."""

    source: str
    verdict: str  # OK | WARNING | CRITICAL
    job_count: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class HealthReport:
    """Aggregated health report across all sources."""

    sources: list[SourceHealth]
    overall: str  # worst verdict across all sources
    timestamp: str  # ISO UTC


# ── Collection ────────────────────────────────────────────────────────────────


def collect_source_meta(
    raw_jobs: list,
    errors: dict[str, str],
) -> list[ScraperMeta]:
    """Compute per-source metrics from a raw job list.

    Args:
        raw_jobs: list[RawJob] — jobs as returned by scrapers before merge.
        errors:   {source: error_message} for scrapers that raised exceptions.

    Returns:
        One ScraperMeta per source found in raw_jobs or errors.
    """
    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)
    for job in raw_jobs:
        src = job.get("source") if isinstance(job, dict) else getattr(job, "source", None)
        if src:
            groups[src].append(job)

    # Add error-only sources (scraper failed before returning any jobs)
    for src in errors:
        if src not in groups:
            groups[src] = []

    metas = []
    for source, jobs in groups.items():
        metas.append(_compute_meta_for_source(source, jobs, errors.get(source)))
    return metas


def _compute_meta_for_source(
    source: str,
    jobs: list,
    error: str | None,
) -> ScraperMeta:
    """Compute metrics for a single source."""
    n = len(jobs)
    if n == 0:
        return ScraperMeta(
            source=source,
            job_count=0,
            error=error,
            has_description_pct=0.0,
            median_desc_length=0,
            has_location_pct=0.0,
            has_company_pct=0.0,
        )

    def _get(job, attr):
        return job.get(attr) if isinstance(job, dict) else getattr(job, attr, None)

    desc_lengths = [len(_get(j, "description")) for j in jobs if _get(j, "description")]
    has_location = sum(1 for j in jobs if _get(j, "location"))
    has_company = sum(1 for j in jobs if _get(j, "company"))

    return ScraperMeta(
        source=source,
        job_count=n,
        error=error,
        has_description_pct=round(len(desc_lengths) / n, 3),
        median_desc_length=int(statistics.median(desc_lengths)) if desc_lengths else 0,
        has_location_pct=round(has_location / n, 3),
        has_company_pct=round(has_company / n, 3),
    )


# ── Evaluation ────────────────────────────────────────────────────────────────


def evaluate_health(metas: list[ScraperMeta]) -> HealthReport:
    """Evaluate each source against thresholds. Returns HealthReport."""
    sources = [_evaluate_source(m) for m in metas]
    overall = max((s.verdict for s in sources), key=lambda v: _VERDICT_RANK[v], default=OK)
    return HealthReport(
        sources=sources,
        overall=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _evaluate_source(meta: ScraperMeta) -> SourceHealth:
    """Apply threshold rules to produce a SourceHealth verdict."""
    thresh = THRESHOLDS.get(meta.source, _DEFAULT_THRESHOLD)
    reasons: list[str] = []

    if meta.error is not None:
        return SourceHealth(
            source=meta.source,
            verdict=CRITICAL,
            job_count=meta.job_count,
            reasons=[f"scraper_error: {meta.error}"],
        )

    if meta.job_count == 0:
        return SourceHealth(
            source=meta.source,
            verdict=CRITICAL,
            job_count=0,
            reasons=["zero_results"],
        )

    if meta.job_count < thresh["min_jobs"]:
        reasons.append(f"low_count: {meta.job_count} (min {thresh['min_jobs']})")

    if meta.has_description_pct < thresh["min_desc_pct"]:
        reasons.append(f"schema_drift: description {meta.has_description_pct:.0%} (min {thresh['min_desc_pct']:.0%})")

    if meta.median_desc_length < thresh["min_desc_len"]:
        reasons.append(f"schema_drift: median_desc_len {meta.median_desc_length} (min {thresh['min_desc_len']})")

    if len(reasons) >= 2:
        verdict = CRITICAL
    elif reasons:
        verdict = WARNING
    else:
        verdict = OK

    return SourceHealth(
        source=meta.source,
        verdict=verdict,
        job_count=meta.job_count,
        reasons=reasons,
    )


# ── GHA annotations ───────────────────────────────────────────────────────────


def format_gha_annotations(report: HealthReport) -> list[str]:
    """Format health report as GHA workflow command strings.

    Returns lines that GitHub Actions interprets as annotations when printed
    to stdout. OK sources produce no lines.
    """
    lines = []
    for sh in report.sources:
        if sh.verdict == OK:
            continue
        level = "error" if sh.verdict == CRITICAL else "warning"
        reasons_str = "; ".join(sh.reasons) if sh.reasons else sh.verdict
        lines.append(f"::{level}::Scraper health [{sh.source}]: {reasons_str}")
    return lines


# ── Serialisation ─────────────────────────────────────────────────────────────


def health_report_to_dict(report: HealthReport) -> dict:
    """Serialize HealthReport to a flat dict for PostHog/structlog."""
    return {
        "overall": report.overall,
        "timestamp": report.timestamp,
        "sources": [
            {
                "source": s.source,
                "verdict": s.verdict,
                "job_count": s.job_count,
                "reasons": s.reasons,
            }
            for s in report.sources
        ],
        "n_ok": sum(1 for s in report.sources if s.verdict == OK),
        "n_warning": sum(1 for s in report.sources if s.verdict == WARNING),
        "n_critical": sum(1 for s in report.sources if s.verdict == CRITICAL),
    }


# ── Alert email ───────────────────────────────────────────────────────────────


def send_health_alert(report: HealthReport) -> bool:
    """Send health alert email if any source is warning or critical.

    Recipient: ADMIN_EMAIL env var, falls back to NOTIFY_EMAIL.
    Returns True if sent, False if skipped or failed. Never raises.
    """
    import os

    if report.overall == OK:
        return False

    to_email = os.getenv("ADMIN_EMAIL") or os.getenv("NOTIFY_EMAIL")
    if not to_email:
        return False

    try:
        from notifier import send_smtp
    except ImportError:
        return False

    try:
        html_body = _render_alert_template(report)
    except Exception:
        return False

    d = health_report_to_dict(report)
    n_critical = d["n_critical"]
    n_warning = d["n_warning"]
    subject = f"Scraper Health Alert: {n_critical} critical, {n_warning} warning"
    return send_smtp(to_email, subject, html_body)


def _render_alert_template(report: HealthReport) -> str:
    """Render the health alert HTML via Jinja2."""
    import pathlib

    from jinja2 import Environment, FileSystemLoader

    template_dir = pathlib.Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("scraper_health_alert.html.j2")
    return template.render(report=report, data=health_report_to_dict(report))
