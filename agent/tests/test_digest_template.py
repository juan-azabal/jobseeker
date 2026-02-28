"""Regression tests for the email digest template (Phase 20).

Renders email_digest.html.j2 with controlled test data and asserts presence/
absence of key elements. Tests are independent of send_digest() — they call
Jinja2 directly so no SMTP credentials are needed.
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
PLATFORM_URL = "https://jobseeker-production.up.railway.app"


def _make_tier_a_job(job_id: str, title: str = "Head of Product", company: str = "Acme") -> dict:
    return {
        "title": title,
        "company": company,
        "location": "Remote",
        "location_type": "remote",
        "requires_reloc": False,
        "salary_display": "~€120K",
        "score": 82,
        "strength": "Led cross-functional teams",
        "gap": "No fintech experience",
        "url": f"https://ext.com/{job_id}",
        "platform_link": f"{PLATFORM_URL}/jobs/{job_id}",
    }


def _make_tier_b_job(job_id: str) -> dict:
    return {
        "title": "Product Manager",
        "company": "Beta Corp",
        "location": "Madrid",
        "location_type": "hybrid",
        "requires_reloc": False,
        "salary_display": "",
        "score": 50,
        "strength": "",
        "gap": "",
        "url": f"https://ext.com/{job_id}",
        "platform_link": f"{PLATFORM_URL}/jobs/{job_id}",
    }


def _make_tier_c_job(job_id: str) -> dict:
    return {
        "title": "Associate PM",
        "company": "Gamma",
        "location": "",
        "location_type": "onsite",
        "requires_reloc": True,
        "salary_display": "",
        "score": 35,
        "strength": "",
        "gap": "",
        "url": f"https://ext.com/{job_id}",
        "platform_link": f"{PLATFORM_URL}/jobs/{job_id}",
    }


def _build_context() -> dict:
    return {
        "date": "28 Feb 2026",
        "headline": "Acme · remote · 82",
        "n_apply": 2,
        "n_review": 2,
        "n_skip": 1,
        "n_prefiltered": 10,
        "preheader": "2 para aplicar, 2 para revisar",
        "platform_url": PLATFORM_URL,
        "tier_a": [
            _make_tier_a_job("hash_a1", "Head of Product", "Acme"),
            _make_tier_a_job("hash_a2", "Director of Product", "Betaworks"),
        ],
        "tier_b": [
            _make_tier_b_job("hash_b1"),
            _make_tier_b_job("hash_b2"),
        ],
        "tier_c": [
            _make_tier_c_job("hash_c1"),
        ],
        "rejected_stats": {
            "total": 20, "passed": 5, "us_only": 5, "no_pm_keyword": 3,
            "deal_breaker": 2, "title_excluded": 2,
        },
        "run_meta": {
            "n_searches": 5, "n_watchlist": 3, "duration_s": 90, "cost_usd": 0.15,
        },
    }


def _render() -> str:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("email_digest.html.j2")
    return template.render(**_build_context())


class TestPresence:
    """Elements that MUST appear in the rendered template."""

    def test_jobseeker_appears(self):
        assert "JobSeeker" in _render()

    def test_platform_url_in_html(self):
        assert PLATFORM_URL in _render()

    def test_preheader_div_display_none(self):
        html = _render()
        assert "display:none" in html
        assert "2 para aplicar, 2 para revisar" in html

    def test_violet_accent_present(self):
        assert "#8b5cf6" in _render()

    def test_built_by_juan_azabal(self):
        assert "Juan Azabal" in _render()

    def test_color_scheme_meta(self):
        assert 'color-scheme' in _render()

    def test_supported_color_schemes_meta(self):
        assert 'supported-color-schemes' in _render()

    def test_tier_a_platform_links(self):
        """All Tier A job links must use /jobs/ platform path."""
        html = _render()
        assert f"{PLATFORM_URL}/jobs/hash_a1" in html
        assert f"{PLATFORM_URL}/jobs/hash_a2" in html

    def test_tier_a_oferta_original_links(self):
        """Tier A must have secondary 'Oferta original' external links."""
        html = _render()
        assert "Oferta original" in html
        assert "https://ext.com/hash_a1" in html

    def test_ver_tu_dashboard_cta(self):
        """Header must have 'Ver tu dashboard' CTA."""
        html = _render()
        assert "Ver tu dashboard" in html

    def test_ver_todos_dashboard_cta(self):
        """'Ver todos en el dashboard' CTA must appear after Tier A."""
        html = _render()
        assert "Ver todos en el dashboard" in html

    def test_tier_b_platform_links(self):
        html = _render()
        assert f"{PLATFORM_URL}/jobs/hash_b1" in html

    def test_tier_c_platform_links(self):
        html = _render()
        assert f"{PLATFORM_URL}/jobs/hash_c1" in html

    def test_ver_mas_dashboard_link(self):
        """'Ver más en el dashboard' text link must appear after Tier B."""
        assert "Ver más en el dashboard" in _render()


class TestAbsence:
    """Elements that must NOT appear in the rendered template."""

    def test_no_jobagent(self):
        """'JobAgent' must not appear anywhere in the rendered output."""
        assert "JobAgent" not in _render()

    def test_no_orange_accent(self):
        """Old orange accent #e97316 must not appear."""
        assert "#e97316" not in _render()

    def test_no_gestionar_notificaciones(self):
        """No unsubscribe/notification management link (none configured yet)."""
        assert "Gestionar notificaciones" not in _render()

    def test_no_jobagent_in_title(self):
        """<title> must not contain 'JobAgent'."""
        html = _render()
        assert "<title>JobAgent" not in html


class TestTemplateRendersWithoutError:
    """Template must render without Jinja2 errors with various inputs."""

    def test_empty_tiers(self):
        """Template must render even when all tiers are empty."""
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
        template = env.get_template("email_digest.html.j2")
        ctx = _build_context()
        ctx["tier_a"] = []
        ctx["tier_b"] = []
        ctx["tier_c"] = []
        html = template.render(**ctx)
        assert "JobSeeker" in html

    def test_missing_salary(self):
        """Jobs without salary_display must render without errors."""
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
        template = env.get_template("email_digest.html.j2")
        ctx = _build_context()
        ctx["tier_a"][0]["salary_display"] = ""
        html = template.render(**ctx)
        assert "Head of Product" in html

    def test_reloc_warning_pill(self):
        """Jobs with requires_reloc=True must show 'reloc' warning pill."""
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
        template = env.get_template("email_digest.html.j2")
        ctx = _build_context()
        ctx["tier_a"][0]["requires_reloc"] = True
        html = template.render(**ctx)
        assert "reloc" in html
        assert "#fef3c7" in html  # amber warning pill bg
