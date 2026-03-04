"""Tests for notifier.py — API-based email digest (Phase 20b rewrite).

Covers:
  - fetch_digest(): GET /api/digest/{profile_id}
  - _flatten_api_job(): maps API fields to template schema
  - _build_context_from_api(): builds Jinja2 context from digest response
  - _build_headline(): unchanged helper
  - Template toggle (DIGEST_TEMPLATE env var)
  - Template rendering (visual regression, unchanged from Phase 20/20b)
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ── Fixtures ──────────────────────────────────────────────────────────────────

_DIGEST_JOB = {
    "job_id": "abc123",
    "title": "Head of Product",
    "company": "Acme",
    "location": "Remote",
    "location_type": "remote",
    "url": "https://ext.com/job/1",
    "score": 82,
    "tier": "A",
    "geo_restricted": False,
    "eligibility_warning": None,
    "salary_min": 80000.0,
    "salary_max": 120000.0,
    "salary_currency": "EUR",
    "salary_interval": "yearly",
    "first_seen": "2026-03-04",
}

_DIGEST_RESPONSE = {
    "jobs": [_DIGEST_JOB],
    "summary": {"tier_a": 1, "tier_b": 0, "tier_c": 0, "total": 1},
    "profile_id": "juan",
    "date": "2026-03-04",
}

_RUN_META = {"date": "04 Mar 2026", "duration_s": 120, "cost_usd": 0.12, "n_searches": 5, "n_watchlist": 3}
_REJECTED_STATS = {"total": 10, "passed": 1}


def _make_mock_response(data: dict):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = data
    return mock


def _make_digest_jobs(tier_a=1, tier_b=1, tier_c=0):
    jobs = []
    for i in range(tier_a):
        jobs.append({**_DIGEST_JOB, "job_id": f"a{i}", "company": f"CoA{i}", "score": 75, "tier": "A"})
    for i in range(tier_b):
        jobs.append(
            {
                **_DIGEST_JOB,
                "job_id": f"b{i}",
                "company": f"CoB{i}",
                "score": 45,
                "tier": "B",
                "location_type": "hybrid",
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
            }
        )
    for i in range(tier_c):
        jobs.append(
            {
                **_DIGEST_JOB,
                "job_id": f"c{i}",
                "company": f"CoC{i}",
                "score": 25,
                "tier": "C",
                "location_type": "onsite",
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
            }
        )
    return {
        "jobs": jobs,
        "summary": {"tier_a": tier_a, "tier_b": tier_b, "tier_c": tier_c, "total": tier_a + tier_b + tier_c},
        "profile_id": "juan",
        "date": "2026-03-04",
    }


# ── TestFetchDigest ───────────────────────────────────────────────────────────


class TestFetchDigest:
    """fetch_digest(): GET /api/digest/{profile_id} via httpx."""

    def test_returns_json_on_success(self):
        from notifier import fetch_digest

        with patch("httpx.get", return_value=_make_mock_response(_DIGEST_RESPONSE)):
            result = fetch_digest("https://example.com", "juan", "secret")
        assert result == _DIGEST_RESPONSE

    def test_returns_none_on_connection_error(self):
        from notifier import fetch_digest

        with patch("httpx.get", side_effect=httpx.ConnectError("boom")):
            result = fetch_digest("https://example.com", "juan", "secret")
        assert result is None

    def test_returns_none_on_http_error(self):
        from notifier import fetch_digest

        mock = MagicMock()
        mock.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
        with patch("httpx.get", return_value=mock):
            result = fetch_digest("https://example.com", "juan", "secret")
        assert result is None

    def test_uses_ingest_key_header(self):
        from notifier import fetch_digest

        with patch("httpx.get", return_value=_make_mock_response(_DIGEST_RESPONSE)) as mock_get:
            fetch_digest("https://example.com", "juan", "mykey")
        headers = mock_get.call_args[1]["headers"]
        assert headers["X-Ingest-Key"] == "mykey"

    def test_upgrades_http_to_https(self):
        from notifier import fetch_digest

        with patch("httpx.get", return_value=_make_mock_response(_DIGEST_RESPONSE)) as mock_get:
            fetch_digest("http://example.com", "juan", "key")
        url_called = mock_get.call_args[0][0]
        assert url_called.startswith("https://")

    def test_calls_correct_endpoint(self):
        from notifier import fetch_digest

        with patch("httpx.get", return_value=_make_mock_response(_DIGEST_RESPONSE)) as mock_get:
            fetch_digest("https://example.com", "juan", "key")
        url_called = mock_get.call_args[0][0]
        assert url_called == "https://example.com/api/digest/juan"


# ── TestFlattenApiJob ─────────────────────────────────────────────────────────


class TestFlattenApiJob:
    """_flatten_api_job(): maps API digest fields to template flat schema."""

    def test_platform_link_uses_job_id(self):
        from notifier import _flatten_api_job

        with patch.dict(os.environ, {"APP_BASE_URL": "https://example.com"}):
            result = _flatten_api_job({**_DIGEST_JOB, "job_id": "abc123"})
        assert result["platform_link"] == "https://example.com/jobs/abc123"

    def test_platform_link_fallback_no_job_id(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "job_id": None, "url": "https://ext.com/job"})
        assert result["platform_link"] == "https://ext.com/job"

    def test_salary_display_eur(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "salary_max": 120000.0, "salary_currency": "EUR"})
        assert result["salary_display"] == "~€120K"

    def test_salary_display_empty_when_no_salary(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "salary_min": None, "salary_max": None, "salary_currency": None})
        assert result["salary_display"] == ""

    def test_requires_reloc_from_geo_restricted(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "geo_restricted": True, "eligibility_warning": None})
        assert result["requires_reloc"] is True

    def test_requires_reloc_from_eligibility_warning(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "geo_restricted": False, "eligibility_warning": "UK only"})
        assert result["requires_reloc"] is True

    def test_not_reloc_when_both_false(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "geo_restricted": False, "eligibility_warning": None})
        assert result["requires_reloc"] is False

    def test_strength_and_gap_are_empty(self):
        """strength/gap not returned by digest API — always empty strings."""
        from notifier import _flatten_api_job

        result = _flatten_api_job(_DIGEST_JOB)
        assert result["strength"] == ""
        assert result["gap"] == ""

    def test_score_passed_through(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job({**_DIGEST_JOB, "score": 75})
        assert result["score"] == 75

    def test_required_keys_present(self):
        from notifier import _flatten_api_job

        result = _flatten_api_job(_DIGEST_JOB)
        required = {
            "title",
            "company",
            "location",
            "location_type",
            "requires_reloc",
            "salary_display",
            "score",
            "strength",
            "gap",
            "url",
            "platform_link",
        }
        assert required.issubset(result.keys())


# ── TestBuildContextFromApi ───────────────────────────────────────────────────


class TestBuildContextFromApi:
    """_build_context_from_api(): builds Jinja2 template context from digest response."""

    def test_tiers_split_correctly(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=2, tier_b=3, tier_c=1)
        ctx = _build_context_from_api(data, _REJECTED_STATS, _RUN_META)
        assert len(ctx["tier_a"]) == 2
        assert len(ctx["tier_b"]) == 3
        assert len(ctx["tier_c"]) == 1

    def test_n_apply_n_review_n_skip(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=2, tier_b=1, tier_c=3)
        ctx = _build_context_from_api(data, _REJECTED_STATS, _RUN_META)
        assert ctx["n_apply"] == 2
        assert ctx["n_review"] == 1
        assert ctx["n_skip"] == 3

    def test_preheader_format(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=2, tier_b=1, tier_c=0)
        ctx = _build_context_from_api(data, _REJECTED_STATS, _RUN_META)
        assert ctx["preheader"] == "2 para aplicar, 1 para revisar"

    def test_n_prefiltered_computed_from_rejected_stats(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=1, tier_b=1, tier_c=0)
        ctx = _build_context_from_api(data, {"total": 10, "passed": 2}, _RUN_META)
        assert ctx["n_prefiltered"] == 8

    def test_platform_url_env(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=1, tier_b=0, tier_c=0)
        with patch.dict(os.environ, {"APP_BASE_URL": "https://custom.app"}):
            ctx = _build_context_from_api(data, _REJECTED_STATS, _RUN_META)
        assert ctx["platform_url"] == "https://custom.app"

    def test_required_template_keys_present(self):
        from notifier import _build_context_from_api

        data = _make_digest_jobs(tier_a=1, tier_b=0, tier_c=0)
        ctx = _build_context_from_api(data, _REJECTED_STATS, _RUN_META)
        required = {
            "date",
            "headline",
            "n_apply",
            "n_review",
            "n_skip",
            "n_prefiltered",
            "tier_a",
            "tier_b",
            "tier_c",
            "rejected_stats",
            "run_meta",
            "platform_url",
            "preheader",
        }
        assert required.issubset(ctx.keys())


# ── TestBuildHeadline ─────────────────────────────────────────────────────────


class TestBuildHeadline:
    """_build_headline(): unchanged helper."""

    def test_build_headline_uses_score(self):
        from notifier import _build_headline

        tier_a = [{"company": "Acme", "location_type": "remote", "score": 82}]
        result = _build_headline(tier_a)
        assert "Acme" in result
        assert "remote" in result
        assert "82" in result

    def test_build_headline_empty_tier_a(self):
        from notifier import _build_headline

        result = _build_headline([])
        assert "No top" in result


# ── TestDigestTemplateToggle ──────────────────────────────────────────────────


class TestDigestTemplateToggle:
    """DIGEST_TEMPLATE env var selects the template file."""

    def test_v1_template_backup_exists(self):
        v1 = TEMPLATES_DIR / "email_digest_v1.html.j2"
        assert v1.exists(), "email_digest_v1.html.j2 backup not found"
        assert v1.stat().st_size > 0

    def test_digest_template_env_default(self):
        import importlib
        import notifier

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DIGEST_TEMPLATE", None)
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest.html.j2"

    def test_digest_template_env_override(self):
        import importlib
        import notifier

        with patch.dict(os.environ, {"DIGEST_TEMPLATE": "email_digest_v1.html.j2"}):
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest_v1.html.j2"


# ── Template rendering helpers + tests (unchanged from Phase 20/20b) ──────────


def _render_template(extra_context=None):
    """Helper: render email_digest.html.j2 with minimal well-formed context."""
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
                "strength": "Led data teams",
                "gap": "No fintech",
                "url": "https://ext.com/job1",
                "platform_link": "https://example.com/jobs/abc",
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
                "strength": "",
                "gap": "",
                "url": "https://ext.com/job2",
                "platform_link": "https://example.com/jobs/def",
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


class TestTemplateRender20_3a:
    """Step 20.3a: head, preheader, header, footer template changes."""

    def test_color_scheme_meta_present(self):
        assert "color-scheme" in _render_template()

    def test_supported_color_schemes_meta_present(self):
        assert "supported-color-schemes" in _render_template()

    def test_title_is_jobseeker(self):
        html = _render_template()
        assert "JobSeeker" in html
        assert "JobAgent Digest" not in html

    def test_preheader_div_present(self):
        html = _render_template()
        assert "display:none" in html
        assert "1 para aplicar, 1 para revisar" in html

    def test_violet_accent_in_header(self):
        html = _render_template()
        assert "#8b5cf6" in html
        assert "#e97316" not in html

    def test_dashboard_cta_in_header(self):
        assert "https://example.com/jobs" in _render_template()

    def test_footer_branding(self):
        assert "JobSeeker" in _render_template()

    def test_footer_juan_azabal(self):
        assert "Juan Azabal" in _render_template()


class TestTemplateRender20_3b:
    """Step 20.3b: Tier A cards use platform links."""

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

    def test_tier_a_ver_todos_links_to_platform(self):
        assert "https://example.com/jobs" in _render_template()


class TestTemplateRender20_3c:
    """Step 20.3c: Tier B and C platform links."""

    def test_tier_b_links_to_platform(self):
        assert "https://example.com/jobs/def" in _render_template()

    def test_tier_b_ver_mas_link_present(self):
        assert "Ver más en el dashboard" in _render_template()

    def test_tier_c_links_to_platform(self):
        ctx_override = {
            "tier_b": [],
            "tier_c": [
                {
                    "title": "PM",
                    "company": "Gamma",
                    "location": "",
                    "location_type": "remote",
                    "requires_reloc": False,
                    "salary_display": "",
                    "score": 30,
                    "url": "https://ext.com/job3",
                    "platform_link": "https://example.com/jobs/ghi",
                    "strength": "",
                    "gap": "",
                }
            ],
        }
        assert "https://example.com/jobs/ghi" in _render_template(ctx_override)
