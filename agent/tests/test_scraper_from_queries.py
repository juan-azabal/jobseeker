"""Tests for scraper.run_scraper_from_queries() — Phase 1.3."""

import pandas as pd
import pytest
from unittest.mock import patch, call

from models import RawJob


def _empty_df():
    return pd.DataFrame(
        columns=[
            "title",
            "company",
            "site",
            "job_url",
            "location",
            "description",
            "job_type",
            "date_posted",
            "is_remote",
            "salary_source",
            "interval",
            "min_amount",
            "max_amount",
            "currency",
            "job_level",
            "job_function",
            "emails",
            "company_industry",
            "company_url",
            "company_logo",
            "company_num_employees",
            "company_revenue",
        ]
    )


def _make_df(title="Senior PM", company="Acme", site="indeed"):
    return pd.DataFrame(
        [
            {
                "title": title,
                "company": company,
                "site": site,
                "job_url": "https://example.com/1",
                "location": "Barcelona",
                "description": "Great job",
                "job_type": "fulltime",
                "date_posted": "2024-01-01",
                "is_remote": False,
                "salary_source": None,
                "interval": None,
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "job_level": None,
                "job_function": None,
                "emails": None,
                "company_industry": None,
                "company_url": None,
                "company_logo": None,
                "company_num_employees": None,
                "company_revenue": None,
            }
        ]
    )


class TestRunScraperFromQueries:
    def test_empty_list_returns_empty(self):
        from scraper import run_scraper_from_queries

        result = run_scraper_from_queries([])
        assert result == []

    def test_returns_list_of_raw_job(self):
        from scraper import run_scraper_from_queries

        query = {
            "term": "Product Manager",
            "location": "barcelona",
            "site": "indeed",
            "results_wanted": 25,
            "hours_old": 72,
            "country_indeed": "Spain",
            "description_format": "markdown",
        }
        with patch("scraper.scrape_jobs", return_value=_make_df(site="indeed")):
            result = run_scraper_from_queries([query])
        assert len(result) == 1
        assert isinstance(result[0], RawJob)

    def test_indeed_query_mapping(self):
        """Indeed query dict maps to correct scrape_jobs kwargs."""
        from scraper import run_scraper_from_queries

        query = {
            "term": "Product Manager",
            "location": "barcelona",
            "site": "indeed",
            "results_wanted": 25,
            "hours_old": 72,
            "country_indeed": "Spain",
            "description_format": "markdown",
        }
        with patch("scraper.scrape_jobs", return_value=_empty_df()) as mock_scrape:
            run_scraper_from_queries([query])
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == "indeed"
        assert call_kwargs["search_term"] == "Product Manager"
        assert call_kwargs["location"] == "barcelona"
        assert call_kwargs["results_wanted"] == 25
        assert call_kwargs["hours_old"] == 72
        assert call_kwargs["country_indeed"] == "Spain"
        assert call_kwargs["description_format"] == "markdown"
        assert "is_remote" not in call_kwargs
        assert "linkedin_fetch_description" not in call_kwargs

    def test_linkedin_query_mapping(self):
        """LinkedIn query dict maps to correct scrape_jobs kwargs."""
        from scraper import run_scraper_from_queries

        query = {
            "term": "Product Manager",
            "location": "barcelona",
            "site": "linkedin",
            "results_wanted": 15,
            "hours_old": 72,
            "is_remote": False,
            "linkedin_fetch_description": True,
            "description_format": "markdown",
        }
        with patch("scraper.scrape_jobs", return_value=_empty_df()) as mock_scrape, patch("scraper.time") as mock_time:
            run_scraper_from_queries([query])
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == "linkedin"
        assert call_kwargs["search_term"] == "Product Manager"
        assert call_kwargs["results_wanted"] == 15
        assert call_kwargs["is_remote"] is False
        assert call_kwargs["linkedin_fetch_description"] is True
        assert "country_indeed" not in call_kwargs

    def test_linkedin_delay_applied(self):
        """time.sleep called after each LinkedIn query."""
        from scraper import run_scraper_from_queries
        from search_generator import LINKEDIN_DELAY_SECS

        query = {
            "term": "PM",
            "location": "barcelona",
            "site": "linkedin",
            "results_wanted": 15,
            "hours_old": 72,
            "is_remote": False,
            "linkedin_fetch_description": True,
            "description_format": "markdown",
        }
        with patch("scraper.scrape_jobs", return_value=_empty_df()), patch("scraper.time") as mock_time:
            run_scraper_from_queries([query])
        mock_time.sleep.assert_called_once_with(LINKEDIN_DELAY_SECS)

    def test_indeed_no_delay(self):
        """time.sleep NOT called after Indeed queries."""
        from scraper import run_scraper_from_queries

        query = {
            "term": "PM",
            "location": "barcelona",
            "site": "indeed",
            "results_wanted": 25,
            "hours_old": 72,
            "country_indeed": "Spain",
            "description_format": "markdown",
        }
        with patch("scraper.scrape_jobs", return_value=_empty_df()), patch("scraper.time") as mock_time:
            run_scraper_from_queries([query])
        mock_time.sleep.assert_not_called()

    def test_dedup_across_queries(self):
        """Same job returned from two queries → deduplicated to one RawJob."""
        from scraper import run_scraper_from_queries

        queries = [
            {
                "term": "PM",
                "location": "barcelona",
                "site": "indeed",
                "results_wanted": 25,
                "hours_old": 72,
                "country_indeed": "Spain",
                "description_format": "markdown",
            },
            {
                "term": "Product Manager",
                "location": "barcelona",
                "site": "indeed",
                "results_wanted": 25,
                "hours_old": 72,
                "country_indeed": "Spain",
                "description_format": "markdown",
            },
        ]
        # Both return same title+company → should deduplicate
        with patch("scraper.scrape_jobs", return_value=_make_df()):
            result = run_scraper_from_queries(queries)
        assert len(result) == 1

    def test_two_linkedin_queries_each_delayed(self):
        """Two LinkedIn queries → two sleep calls."""
        from scraper import run_scraper_from_queries
        from search_generator import LINKEDIN_DELAY_SECS

        queries = [
            {
                "term": "PM",
                "location": "barcelona",
                "site": "linkedin",
                "results_wanted": 15,
                "hours_old": 72,
                "is_remote": False,
                "linkedin_fetch_description": True,
                "description_format": "markdown",
            },
            {
                "term": "Senior PM",
                "location": "barcelona",
                "site": "linkedin",
                "results_wanted": 15,
                "hours_old": 72,
                "is_remote": False,
                "linkedin_fetch_description": True,
                "description_format": "markdown",
            },
        ]
        with patch("scraper.scrape_jobs", return_value=_empty_df()), patch("scraper.time") as mock_time:
            run_scraper_from_queries(queries)
        assert mock_time.sleep.call_count == 2
