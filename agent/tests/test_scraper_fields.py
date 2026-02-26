"""
Unit tests for Step 1.2:
run_scraper() returns list[RawJob] with all available JobSpy fields captured.
"""

import sys
import os
import math

import pytest
import pandas as pd
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob


def _make_mock_df(**overrides):
    """Minimal valid DataFrame row with all JobSpy columns."""
    base = {
        "id": "abc123",
        "title": "Senior Product Manager",
        "company": "Acme Corp",
        "location": "Barcelona, Spain",
        "description": "Great role",
        "job_url": "https://example.com/job/1",
        "job_url_direct": "https://direct.example.com/job/1",
        "date_posted": "2024-01-15",
        "job_type": "fulltime",
        "is_remote": False,
        "salary_source": "direct_data",
        "interval": "yearly",
        "min_amount": 60000.0,
        "max_amount": 90000.0,
        "currency": "EUR",
        "job_level": "Mid-Senior Level",
        "job_function": "Product Management",
        "listing_type": None,
        "emails": None,
        "company_industry": "Software",
        "company_url": "https://acme.example.com",
        "company_logo": "https://acme.example.com/logo.png",
        "company_url_direct": None,
        "company_addresses": None,
        "company_num_employees": "51-200",
        "company_revenue": "$10M-$50M",
        "company_description": None,
        "skills": None,
        "experience_range": None,
        "company_rating": None,
        "company_reviews_count": None,
        "vacancy_count": None,
        "work_from_home_type": None,
        "site": "indeed",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def _run_scraper_with_mock(mock_df, search_config=None):
    from scraper import run_scraper

    config = search_config or {
        "country_indeed": "Spain",
        "is_remote": False,
        "searches": [{"term": "PM", "sites": ["indeed"]}],
    }
    with patch("scraper.scrape_jobs", return_value=mock_df), patch("scraper.load_search_config", return_value=config):
        return run_scraper()


class TestRunScraperReturnsRawJob:
    """run_scraper() must return list[RawJob], not list[dict]."""

    def test_returns_list_of_raw_job(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        assert len(jobs) == 1
        assert isinstance(jobs[0], RawJob)

    def test_required_fields_populated(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.title == "Senior Product Manager"
        assert j.company == "Acme Corp"
        assert j.source == "indeed"
        assert j.id is not None and len(j.id) == 12  # make_job_id hash

    def test_salary_fields_captured(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.min_amount == 60000.0
        assert j.max_amount == 90000.0
        assert j.currency == "EUR"
        assert j.interval == "yearly"
        assert j.salary_source == "direct_data"

    def test_company_metadata_captured(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.company_employees_label == "51-200"
        assert j.company_revenue_label == "$10M-$50M"
        assert j.company_industry == "Software"
        assert j.company_url == "https://acme.example.com"
        assert j.company_logo == "https://acme.example.com/logo.png"

    def test_role_metadata_captured(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.job_level == "Mid-Senior Level"
        assert j.job_function == "Product Management"

    def test_core_fields_captured(self):
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.location == "Barcelona, Spain"
        assert j.description == "Great role"
        assert j.job_url == "https://example.com/job/1"
        assert j.date_posted == "2024-01-15"
        assert j.job_type == "fulltime"

    def test_remote_flag_from_is_remote_column(self):
        """is_remote=True in DataFrame → remote_type='fulltime' → is_remote computed=True."""
        jobs = _run_scraper_with_mock(_make_mock_df(is_remote=True))
        j = jobs[0]
        assert j.is_remote is True
        assert j.remote_type == "fulltime"

    def test_non_remote_job(self):
        """is_remote=False → remote_type='no' → is_remote computed=False."""
        jobs = _run_scraper_with_mock(_make_mock_df(is_remote=False))
        j = jobs[0]
        assert j.is_remote is False
        assert j.remote_type == "no"

    def test_nan_location_becomes_none(self):
        """NaN location → RawJob.location is None (not 'nan')."""
        jobs = _run_scraper_with_mock(_make_mock_df(location=float("nan")))
        j = jobs[0]
        assert j.location is None or j.location == ""

    def test_source_set_from_site_column(self):
        """source field must be set from the 'site' column."""
        jobs = _run_scraper_with_mock(_make_mock_df(site="google"))
        j = jobs[0]
        assert j.source == "google"

    def test_search_term_used_populated(self):
        """search_term_used must be set from the search config term."""
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.search_term_used == "PM"

    def test_dedup_produces_single_job(self):
        """Two rows with same title+company → single RawJob (dedup by id)."""
        df = pd.DataFrame([_make_mock_df().iloc[0], _make_mock_df().iloc[0]])
        jobs = _run_scraper_with_mock(df)
        assert len(jobs) == 1

    def test_sources_list_starts_empty(self):
        """sources list starts empty (filled during merge phase)."""
        jobs = _run_scraper_with_mock(_make_mock_df())
        j = jobs[0]
        assert j.sources == []
