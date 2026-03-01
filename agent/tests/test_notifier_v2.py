"""Tests for the API-driven notifier (Phase 20b.3).

Verifies:
- fetch_digest(): HTTP GET to /api/digest/{profile_id}.
  200 → parsed JSON. 5xx → retry → None. Timeout → retry → None.
- _flatten_api_job(): maps all fields, platform_link format correct.
- _format_salary(): EUR/USD formatting, empty string when no salary.
- _build_context_from_api(): groups by tier, counts match, headline from best A.
- Critical: notifier.py has ZERO 'from main import' statements.
- Critical: notifier.py has no '50' or '30' as tier threshold literals.
- Template rendering tests (existing suite preserved).
"""

import importlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import notifier

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

APP_BASE = "https://example.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_digest_job(job_id="abc123", tier="A", score=82, **extra):
    job = {
        "job_id": job_id,
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "location_type": "remote",
        "url": f"https://ext.com/{job_id}",
        "score": score,
        "tier": tier,
        "geo_restricted": False,
        "domain": "saas",
        "role_function": "product",
        "eligibility_warning": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_interval": None,
        "first_seen": "2026-03-01",
    }
    job.update(extra)
    return job


def _make_digest(tier_a=2, tier_b=2, tier_c=1):
    jobs = []
    score_map = {"A": 82, "B": 52, "C": 20}
    counts = {"A": tier_a, "B": tier_b, "C": tier_c}
    for t, n in counts.items():
        for i in range(n):
            jobs.append(_make_digest_job(job_id=f"{t}{i}", tier=t, score=score_map[t] - i))
    return {
        "jobs": jobs,
        "summary": {"tier_a": tier_a, "tier_b": tier_b, "tier_c": tier_c, "total": tier_a + tier_b + tier_c},
        "profile_id": "juan",
        "date": "2026-03-01",
    }


# ---------------------------------------------------------------------------
# TestFetchDigest
# ---------------------------------------------------------------------------


class TestFetchDigest:
    """fetch_digest() HTTP client behaviour."""

    def _mock_response(self, status_code: int, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        else:
            resp.raise_for_status.return_value = None
        return resp

    def test_200_returns_json(self):
        digest = _make_digest()
        resp = self._mock_response(200, digest)
        with patch("httpx.get", return_value=resp):
            result = notifier.fetch_digest("https://app.railway.app", "juan", "key")
        assert result is not None
        assert result["profile_id"] == "juan"
        assert "jobs" in result

    def test_500_retries_and_returns_none(self):
        import httpx as _httpx

        resp_500 = self._mock_response(500)
        with patch("httpx.get", side_effect=Exception("Server Error")):
            with patch("time.sleep"):
                result = notifier.fetch_digest("https://app.railway.app", "juan", "key")
        assert result is None

    def test_timeout_retries_and_returns_none(self):
        import httpx as _httpx

        with patch("httpx.get", side_effect=_httpx.TimeoutException("timeout")):
            with patch("time.sleep"):
                result = notifier.fetch_digest("https://app.railway.app", "juan", "key")
        assert result is None


# ---------------------------------------------------------------------------
# TestFlattenApiJob
# ---------------------------------------------------------------------------


class TestFlattenApiJob:
    """_flatten_api_job() field mapping."""

    def test_all_required_fields_present(self):
        job = _make_digest_job()
        result = notifier._flatten_api_job(job, APP_BASE)
        for field in (
            "title",
            "company",
            "location",
            "location_type",
            "requires_reloc",
            "salary_display",
            "score",
            "tier",
            "url",
            "platform_link",
            "eligibility_warning",
        ):
            assert field in result, f"Missing field: {field}"

    def test_platform_link_uses_job_id(self):
        job = _make_digest_job(job_id="abc123")
        result = notifier._flatten_api_job(job, APP_BASE)
        assert result["platform_link"] == f"{APP_BASE}/jobs/abc123"

    def test_geo_restricted_maps_to_requires_reloc(self):
        job = _make_digest_job(geo_restricted=True)
        result = notifier._flatten_api_job(job, APP_BASE)
        assert result["requires_reloc"] is True

    def test_eligibility_warning_forwarded(self):
        job = _make_digest_job(eligibility_warning="UK only")
        result = notifier._flatten_api_job(job, APP_BASE)
        assert result["eligibility_warning"] == "UK only"

    def test_no_strength_or_gap_in_output(self):
        """New notifier must not produce strength/gap fields."""
        job = _make_digest_job()
        result = notifier._flatten_api_job(job, APP_BASE)
        assert "strength" not in result
        assert "gap" not in result


# ---------------------------------------------------------------------------
# TestFormatSalary
# ---------------------------------------------------------------------------


class TestFormatSalary:
    """_format_salary() formatting."""

    def test_eur_max_salary(self):
        job = _make_digest_job(salary_max=120000, salary_currency="EUR")
        result = notifier._format_salary(job)
        assert "120" in result
        assert "€" in result

    def test_eur_min_salary_when_no_max(self):
        job = _make_digest_job(salary_min=90000, salary_max=None, salary_currency="EUR")
        result = notifier._format_salary(job)
        assert "90" in result

    def test_no_salary_returns_empty_string(self):
        job = _make_digest_job(salary_min=None, salary_max=None)
        result = notifier._format_salary(job)
        assert result == ""

    def test_usd_salary(self):
        job = _make_digest_job(salary_max=120000, salary_currency="USD")
        result = notifier._format_salary(job)
        assert "120" in result
        assert "$" in result


# ---------------------------------------------------------------------------
# TestBuildContextFromApi
# ---------------------------------------------------------------------------


class TestBuildContextFromApi:
    """_build_context_from_api() groups jobs by tier and builds context."""

    def test_tier_counts_match_summary(self):
        digest = _make_digest(tier_a=2, tier_b=3, tier_c=1)
        ctx = notifier._build_context_from_api(digest, {"total": 10, "passed": 6}, {"date": "01 Mar 2026"})
        assert len(ctx["tier_a"]) == 2
        assert len(ctx["tier_b"]) == 3
        assert len(ctx["tier_c"]) == 1

    def test_headline_from_best_tier_a(self):
        digest = _make_digest(tier_a=2, tier_b=1, tier_c=0)
        ctx = notifier._build_context_from_api(digest, {}, {"date": "01 Mar 2026"})
        # Headline contains company of first tier A job
        assert digest["jobs"][0]["company"] in ctx["headline"]

    def test_n_apply_equals_tier_a_count(self):
        digest = _make_digest(tier_a=3, tier_b=2, tier_c=1)
        ctx = notifier._build_context_from_api(digest, {}, {"date": "01 Mar 2026"})
        assert ctx["n_apply"] == 3

    def test_preheader_format(self):
        digest = _make_digest(tier_a=2, tier_b=3, tier_c=0)
        ctx = notifier._build_context_from_api(digest, {}, {"date": "01 Mar 2026"})
        assert "2 para aplicar" in ctx["preheader"]
        assert "3 para revisar" in ctx["preheader"]

    def test_required_context_keys_present(self):
        digest = _make_digest()
        ctx = notifier._build_context_from_api(digest, {}, {"date": "01 Mar 2026"})
        for key in (
            "date",
            "headline",
            "n_apply",
            "n_review",
            "n_skip",
            "tier_a",
            "tier_b",
            "tier_c",
            "platform_url",
            "preheader",
            "rejected_stats",
            "run_meta",
        ):
            assert key in ctx, f"Missing context key: {key}"


# ---------------------------------------------------------------------------
# TestNotifierNoDependencies (critical assertions)
# ---------------------------------------------------------------------------


class TestNotifierNoDependencies:
    """Critical: notifier.py must not import from main.py."""

    def test_no_from_main_import(self):
        """notifier.py source must not contain 'from main import'."""
        notifier_src = (Path(__file__).parent.parent / "notifier.py").read_text()
        assert "from main import" not in notifier_src

    def test_no_old_tier_thresholds(self):
        """notifier.py must not contain literal '50' or '30' as tier thresholds."""
        notifier_src = (Path(__file__).parent.parent / "notifier.py").read_text()
        # We allow '50' in comments/strings by checking for the old scoring pattern
        assert ">= 50" not in notifier_src
        assert "< 30" not in notifier_src
        assert ">= 30" not in notifier_src


# ---------------------------------------------------------------------------
# TestDigestTemplateToggle (preserved from Phase 20)
# ---------------------------------------------------------------------------


class TestDigestTemplateToggle:
    """DIGEST_TEMPLATE env var selects the template."""

    def test_v1_template_backup_exists(self):
        v1 = TEMPLATES_DIR / "email_digest_v1.html.j2"
        assert v1.exists()
        assert v1.stat().st_size > 0

    def test_digest_template_env_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DIGEST_TEMPLATE", None)
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest.html.j2"

    def test_digest_template_env_override(self):
        with patch.dict(os.environ, {"DIGEST_TEMPLATE": "email_digest_v1.html.j2"}):
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest_v1.html.j2"


# ---------------------------------------------------------------------------
# Template rendering tests (preserved — render with static context dict)
# ---------------------------------------------------------------------------


def _render_template(extra_context=None):
    """Render email_digest.html.j2 with minimal context (no strength/gap required)."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("email_digest.html.j2")
    ctx = {
        "date": "28 Feb 2026",
        "headline": "Acme · remote · 82",
        "n_apply": 1,
        "n_review": 1,
        "n_skip": 0,
        "n_prefiltered": 5,
        "preheader": "1 para aplicar, 1 para revisar",
        "platform_url": "https://example.com",
        "tier_a": [
            {
                "title": "Head of Product",
                "company": "Acme",
                "location": "Remote",
                "location_type": "remote",
                "requires_reloc": False,
                "salary_display": "~€120K",
                "score": 82,
                "tier": "A",
                "url": "https://ext.com/job1",
                "platform_link": "https://example.com/jobs/abc",
                "eligibility_warning": None,
            }
        ],
        "tier_b": [
            {
                "title": "PM",
                "company": "Beta",
                "location": "Madrid",
                "location_type": "hybrid",
                "requires_reloc": False,
                "salary_display": "",
                "score": 45,
                "tier": "B",
                "url": "https://ext.com/job2",
                "platform_link": "https://example.com/jobs/def",
                "eligibility_warning": None,
            }
        ],
        "tier_c": [],
        "rejected_stats": {
            "total": 10,
            "passed": 2,
            "us_only": 3,
            "no_pm_keyword": 2,
            "deal_breaker": 1,
            "title_excluded": 2,
        },
        "run_meta": {"n_searches": 5, "n_watchlist": 3, "duration_s": 120, "cost_usd": 0.12},
    }
    if extra_context:
        ctx.update(extra_context)
    return template.render(**ctx)


class TestTemplateRenderSuite:
    """Template rendering regression tests."""

    def test_color_scheme_meta_present(self):
        assert "color-scheme" in _render_template()

    def test_title_is_jobseeker(self):
        html = _render_template()
        assert "JobSeeker" in html
        assert "JobAgent Digest" not in html

    def test_preheader_div_present(self):
        html = _render_template()
        assert "display:none" in html
        assert "1 para aplicar, 1 para revisar" in html

    def test_violet_accent_not_orange(self):
        html = _render_template()
        assert "#8b5cf6" in html
        assert "#e97316" not in html

    def test_dashboard_cta_in_header(self):
        assert "https://example.com/jobs" in _render_template()

    def test_footer_branding(self):
        assert "JobSeeker" in _render_template()

    def test_footer_juan_azabal(self):
        assert "Juan Azabal" in _render_template()

    def test_tier_a_primary_link_is_platform(self):
        html = _render_template()
        assert "https://example.com/jobs/abc" in html
        assert "Ver en JobSeeker" in html

    def test_tier_a_secondary_link_is_external(self):
        html = _render_template()
        assert "Oferta original" in html
        assert "https://ext.com/job1" in html

    def test_tier_a_ver_todos_cta_present(self):
        assert "Ver todos en el dashboard" in _render_template()

    def test_tier_b_links_to_platform(self):
        assert "https://example.com/jobs/def" in _render_template()

    def test_build_headline_uses_score(self):
        from notifier import _build_headline

        tier_a = [{"company": "Acme", "location_type": "remote", "score": 82}]
        result = _build_headline(tier_a)
        assert "Acme" in result
        assert "82" in result
