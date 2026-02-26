"""
Unit tests for Step 1.3:
run_wttj_scraper() returns list[RawJob] with all structured WTTJ fields.
"""

import sys
import os

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob


def _make_wttj_hit(**overrides):
    """Minimal valid Algolia hit representing a WTTJ job posting."""
    base = {
        "name": "Senior Product Manager - Data",
        "organization": {"name": "Acme Corp", "slug": "acme-corp"},
        "slug": "senior-pm-data-123",
        "reference": "ref-123",
        "offices": [
            {"city": "Barcelona", "country_code": "ES", "zip": "08001", "name": "Barcelona HQ"}
        ],
        "remote": "partial",
        "contract_type": "fulltime",
        "published_at": "2024-01-15",
        "summary": "Lead data products.",
        "profile": "You are a strategic PM.",
        "key_missions": ["Define roadmap", "Own OKRs"],
        "salary_yearly_minimum": 60000,
        "salary_maximum": 90000,
        "salary_currency": "EUR",
        "salary_period": "yearly",
        "new_profession": {"sub_category_reference": "product-management-wNjYw"},
        "experience_level_minimum": 5,
        "experience_level_maximum": 8,
        "language": "en",
        "source_category": "product-management-wNjYw",
    }
    base.update(overrides)
    return base


def _run_wttj_with_mock(hit, extra_hits=None):
    """Run _search_wttj_algolia with a mocked Algolia response."""
    from wttj_scraper import _search_wttj_algolia

    hits = [hit] + (extra_hits or [])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"hits": hits}
    mock_resp.raise_for_status.return_value = None

    queries = [{"term": "data", "filters": "", "results_wanted": 25}]
    with patch("wttj_scraper.requests.post", return_value=mock_resp):
        return _search_wttj_algolia(queries)


class TestWttjReturnsRawJob:
    """_search_wttj_algolia() must return list[RawJob]."""

    def test_returns_list_of_raw_job(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        assert len(jobs) == 1
        assert isinstance(jobs[0], RawJob)

    def test_required_fields_populated(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert j.title == "Senior Product Manager - Data"
        assert j.company == "Acme Corp"
        assert j.source == "wttj"
        assert j.id is not None

    def test_remote_type_captured(self):
        """remote field from Algolia → remote_type on RawJob."""
        jobs = _run_wttj_with_mock(_make_wttj_hit(remote="fulltime"))
        assert jobs[0].remote_type == "fulltime"
        assert jobs[0].is_remote is True

    def test_partial_remote(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit(remote="partial"))
        assert jobs[0].remote_type == "partial"
        assert jobs[0].is_remote is True

    def test_no_remote(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit(remote="no"))
        assert jobs[0].remote_type == "no"
        assert jobs[0].is_remote is False

    def test_locations_structured_captured(self):
        """offices[] stored as locations_structured list[dict]."""
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert isinstance(j.locations_structured, list)
        assert len(j.locations_structured) == 1
        assert j.locations_structured[0]["city"] == "Barcelona"
        assert j.locations_structured[0]["country_code"] == "ES"

    def test_country_city_from_first_office(self):
        """country and city extracted from first office entry."""
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert j.country == "ES"
        assert j.city == "Barcelona"

    def test_salary_fields_captured(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert j.min_amount == 60000
        assert j.max_amount == 90000
        assert j.currency == "EUR"
        assert j.interval == "yearly"

    def test_experience_range_captured(self):
        """experience_level_minimum/maximum → experience_min/max."""
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert j.experience_min == 5
        assert j.experience_max == 8

    def test_language_captured(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        assert jobs[0].language == "en"

    def test_source_category_captured(self):
        """source_category populated from new_profession.sub_category_reference."""
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        assert jobs[0].source_category == "product-management-wNjYw"

    def test_description_assembled_from_parts(self):
        """Description combines summary + profile + key_missions."""
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert "Lead data products" in j.description
        assert "strategic PM" in j.description
        assert "Define roadmap" in j.description

    def test_job_url_built_from_slugs(self):
        jobs = _run_wttj_with_mock(_make_wttj_hit())
        j = jobs[0]
        assert "welcometothejungle.com" in j.job_url
        assert "acme-corp" in j.job_url

    def test_no_offices_gives_empty_structured(self):
        """When offices is empty, locations_structured is None or []."""
        jobs = _run_wttj_with_mock(_make_wttj_hit(offices=[]))
        j = jobs[0]
        assert j.locations_structured is None or j.locations_structured == []
        assert j.country is None
        assert j.city is None

    def test_dedup_across_queries(self):
        """Same job from two Algolia queries → single RawJob."""
        hit = _make_wttj_hit()
        from wttj_scraper import _search_wttj_algolia

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": [hit]}
        mock_resp.raise_for_status.return_value = None

        # Two queries returning same job
        queries = [
            {"term": "data", "filters": "", "results_wanted": 25},
            {"term": "platform", "filters": "", "results_wanted": 25},
        ]
        with patch("wttj_scraper.requests.post", return_value=mock_resp):
            jobs = _search_wttj_algolia(queries)

        assert len(jobs) == 1
