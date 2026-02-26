"""
Tests for Phase 7.2: Parameterized rubric (role_type, geography, adjacent fallback).

Verifies:
(a) Juan's profile → rubric contains "Product Manager", "EU or remote", his core domains.
(b) Synthetic Data Engineer profile → rubric says those, no "PM" or "EU".
(c) Profile with NO role_type/geography → rubric uses fallbacks, never "PM" or "EU or remote".
(d) Profile with no adjacent domains → rubric doesn't contain "SaaS, B2B" and reads cleanly.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import _build_scoring_prompt, _SCORING_RUBRIC_CACHE
import scorer
from tests.fixtures import BASELINE_PROFILE


def _reset_rubric_cache():
    """Reset the module-level rubric cache so template changes take effect."""
    scorer._SCORING_RUBRIC_CACHE = None


class TestJuanProfile:
    """(a) Fixed baseline profile → rubric contains correct parameterized values.

    Uses BASELINE_PROFILE (not config/profiles/juan.yaml) so that personal
    profile tuning never breaks these regression tests.
    """

    def setup_method(self):
        _reset_rubric_cache()
        import copy

        self.profile = copy.deepcopy(BASELINE_PROFILE)
        self.rubric = _build_scoring_prompt(self.profile)

    def test_contains_product_manager(self):
        assert "Product Manager" in self.rubric

    def test_contains_eu_or_remote(self):
        assert "EU or remote" in self.rubric

    def test_contains_core_domains(self):
        assert "data, adtech" in self.rubric

    def test_contains_adjacent_domains(self):
        # v2: adjacent domains not injected into prompt (domain scoring is code-side)
        # Core domains still present
        assert "data, adtech" in self.rubric

    def test_no_hardcoded_pm_abbreviation(self):
        # The rubric should say "Product Manager", not just "PM" as a role type
        # (Note: "PM" may appear in other contexts like example text, but not as role)
        assert "experienced PM," not in self.rubric
        assert "tech PM," not in self.rubric


class TestDataEngineerProfile:
    """(b) Synthetic Data Engineer profile → rubric says those, no PM or EU."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {
                "name": "Alice Chen",
                "home_locations": ["new york", "us"],
            },
            "target": {
                "role_type": "Data Engineer",
                "geography": "US, remote-preferred",
                "domains": {"data": 15, "ml": 12},
                "seniority": {"senior": 15, "staff": 12},
            },
            "skills": ["SQL", "Python", "Spark", "dbt", "Airflow"],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_contains_data_engineer(self):
        assert "Data Engineer" in self.rubric

    def test_contains_us_geography(self):
        assert "US, remote-preferred" in self.rubric

    def test_no_pm(self):
        assert "experienced PM" not in self.rubric
        assert "tech PM" not in self.rubric

    def test_no_eu(self):
        assert "EU or remote" not in self.rubric

    def test_contains_correct_domains(self):
        assert "data, ml" in self.rubric

    def test_no_adjacent_fallback(self):
        # v2: adjacent_clause not in prompt at all (domain scoring is code-side)
        assert "SaaS, B2B" not in self.rubric
        assert "Tangentially related domains" not in self.rubric


class TestNoRoleTypeNoGeography:
    """(c) Profile with NO role_type/geography → uses fallbacks."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {
                "name": "Test User",
                "home_locations": ["london", "uk"],
            },
            "target": {
                "domains": {"fintech": 15, "saas": 10},
                "seniority": {"senior": 15},
            },
            "skills": ["Python"],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_fallback_role_type(self):
        assert "experienced professional" in self.rubric

    def test_fallback_geography(self):
        # Fallback: derived from home_locations
        assert "london, uk or remote" in self.rubric

    def test_no_hardcoded_pm(self):
        assert "experienced PM" not in self.rubric
        assert "tech PM" not in self.rubric

    def test_no_hardcoded_eu(self):
        assert "EU or remote" not in self.rubric


class TestNoHomeLocationsNoGeography:
    """Profile with no geography AND no home_locations → "flexible location"."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Nomad User"},
            "target": {
                "domains": {"saas": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_flexible_location(self):
        assert "flexible location" in self.rubric


class TestNoAdjacentDomains:
    """(d) Profile with no adjacent domains → rubric reads cleanly."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Focused Dev"},
            "target": {
                "role_type": "Software Engineer",
                "geography": "Global, remote",
                "domains": {"data": 15, "ml": 14},  # both core, no adjacent
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_no_saas_b2b(self):
        assert "SaaS, B2B" not in self.rubric

    def test_tangentially_related(self):
        # v2: adjacent_clause not injected into prompt (domain scoring is code-side)
        assert "Tangentially related domains" not in self.rubric

    def test_reads_cleanly(self):
        # v2: no numeric scoring tiers in prompt (deterministic code-side)
        assert "12-19:" not in self.rubric
