"""
Unit tests for Step 0.1 — WTTJ geographic filter.
Tests verify that run_wttj_scraper() builds the correct Algolia filter
based on target_countries, including remote passthrough.
"""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Ensure agent/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_mock_post(captured_bodies: list):
    """Return a mock requests.post that captures request bodies and returns empty hits."""

    def mock_post(url, json=None, headers=None, timeout=None):
        captured_bodies.append(json or {})
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"hits": [], "nbHits": 0}
        return mock

    return mock_post


class TestWTTJGeographicFilter:
    def test_filter_includes_all_target_country_codes(self):
        """Filter string must include each country in target_countries."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper(target_countries=["ES", "NL", "DE", "GB", "IE"])

        assert captured, "No Algolia requests made"
        for body in captured:
            f = body.get("filters", "")
            assert "offices.country_code:ES" in f, f"ES missing from filter: {f}"
            assert "offices.country_code:NL" in f, f"NL missing from filter: {f}"
            assert "offices.country_code:DE" in f, f"DE missing from filter: {f}"
            assert "offices.country_code:GB" in f, f"GB missing from filter: {f}"
            assert "offices.country_code:IE" in f, f"IE missing from filter: {f}"

    def test_filter_includes_remote_regardless_of_country(self):
        """Filter must include remote:fulltime and remote:partial so remote jobs from any country pass."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper(target_countries=["ES"])

        assert captured
        for body in captured:
            f = body.get("filters", "")
            assert "remote:fulltime" in f, f"remote:fulltime missing from filter: {f}"
            assert "remote:partial" in f, f"remote:partial missing from filter: {f}"

    def test_france_onsite_excluded_when_fr_not_in_target(self):
        """When FR not in target_countries, filter must not include offices.country_code:FR."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper(target_countries=["ES", "NL", "DE"])

        assert captured
        for body in captured:
            f = body.get("filters", "")
            assert "country_code:FR" not in f, f"FR unexpectedly in filter: {f}"

    def test_default_target_countries_includes_es_and_remote(self):
        """When called without target_countries, defaults to ES + remote only."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper()  # no argument

        assert captured
        for body in captured:
            f = body.get("filters", "")
            assert "offices.country_code:ES" in f
            assert "remote:fulltime" in f
            assert "remote:partial" in f

    def test_pm_filter_preserved_alongside_geo_filter(self):
        """Existing PM profession filter must still be present in every query."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper(target_countries=["ES"])

        assert captured
        _PM = "new_profession.sub_category_reference:product-management-wNjYw"
        for body in captured:
            f = body.get("filters", "")
            assert _PM in f, f"PM category filter missing from: {f}"

    def test_geo_filter_combined_with_or_not_and(self):
        """Country codes must be OR'd together (not AND'd) inside the geo group."""
        from wttj_scraper import run_wttj_scraper

        captured = []
        with patch("wttj_scraper.requests.post", side_effect=_make_mock_post(captured)):
            run_wttj_scraper(target_countries=["ES", "NL"])

        assert captured
        for body in captured:
            f = body.get("filters", "")
            # Both ES and NL must appear in the same OR group
            # e.g. "(offices.country_code:ES OR offices.country_code:NL OR remote:fulltime ...)"
            es_pos = f.find("offices.country_code:ES")
            nl_pos = f.find("offices.country_code:NL")
            assert es_pos >= 0 and nl_pos >= 0
            # OR should appear between them (not AND)
            between = f[min(es_pos, nl_pos) : max(es_pos, nl_pos)]
            assert " OR " in between, f"Expected OR between country codes, got: {between}"
