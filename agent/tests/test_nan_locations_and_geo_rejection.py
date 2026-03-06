"""
Unit tests for Step 0.3:
A. Sanitize nan locations at scrape time (scraper.py, ats_scraper.py, wttj_scraper.py)
B. reject_if_requires_relocation_outside in prefilter.py
"""

import sys
import os
import math
import tempfile
from unittest.mock import patch, MagicMock

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from geo import derive_target_countries


# ---------------------------------------------------------------------------
# A. Nan location sanitization (scraper.py)
# ---------------------------------------------------------------------------


class TestNanSanitizationScraper:
    """run_scraper() must never emit 'nan' string for location or other string fields."""

    def test_nan_location_becomes_empty_string(self):
        """Pandas NaN in 'location' column must be sanitized to ''."""
        import pandas as pd
        from scraper import run_scraper

        mock_df = pd.DataFrame(
            [
                {
                    "title": "Senior PM",
                    "company": "Acme",
                    "location": float("nan"),  # pandas NaN
                    "description": "A great role",
                    "job_url": "https://example.com",
                    "date_posted": "",
                    "job_type": "",
                    "is_remote": False,
                    "min_amount": None,
                    "max_amount": None,
                    "currency": "",
                    "interval": "",
                    "site": "indeed",
                }
            ]
        )

        with (
            patch("scraper.scrape_jobs", return_value=mock_df),
            patch(
                "scraper.load_search_config",
                return_value={
                    "country_indeed": "Spain",
                    "is_remote": False,
                    "searches": [{"term": "PM", "sites": ["indeed"]}],
                },
            ),
        ):
            jobs = run_scraper()

        assert len(jobs) == 1
        assert jobs[0].location != "nan"
        assert jobs[0].location is None or jobs[0].location == ""

    def test_nan_string_location_becomes_empty_string(self):
        """String literal 'nan' (from pandas str conversion) must also be sanitized."""
        import pandas as pd
        from scraper import run_scraper

        mock_df = pd.DataFrame(
            [
                {
                    "title": "PM",
                    "company": "Corp",
                    "location": "nan",  # string "nan" (str(float('nan')))
                    "description": "desc",
                    "job_url": "",
                    "date_posted": "",
                    "job_type": "",
                    "is_remote": False,
                    "min_amount": None,
                    "max_amount": None,
                    "currency": "nan",
                    "interval": "nan",
                    "site": "indeed",
                }
            ]
        )

        with (
            patch("scraper.scrape_jobs", return_value=mock_df),
            patch(
                "scraper.load_search_config",
                return_value={
                    "country_indeed": "Spain",
                    "is_remote": False,
                    "searches": [{"term": "PM", "sites": ["indeed"]}],
                },
            ),
        ):
            jobs = run_scraper()

        assert len(jobs) == 1
        assert jobs[0].location is None or jobs[0].location == ""
        assert jobs[0].currency is None or jobs[0].currency == ""
        assert jobs[0].interval is None or jobs[0].interval == ""

    def test_valid_location_preserved(self):
        """Non-nan location string is preserved unchanged."""
        import pandas as pd
        from scraper import run_scraper

        mock_df = pd.DataFrame(
            [
                {
                    "title": "PM",
                    "company": "Corp",
                    "location": "Barcelona, Spain",
                    "description": "desc",
                    "job_url": "",
                    "date_posted": "",
                    "job_type": "",
                    "is_remote": False,
                    "min_amount": None,
                    "max_amount": None,
                    "currency": "EUR",
                    "interval": "yearly",
                    "site": "indeed",
                }
            ]
        )

        with (
            patch("scraper.scrape_jobs", return_value=mock_df),
            patch(
                "scraper.load_search_config",
                return_value={
                    "country_indeed": "Spain",
                    "is_remote": False,
                    "searches": [{"term": "PM", "sites": ["indeed"]}],
                },
            ),
        ):
            jobs = run_scraper()

        assert len(jobs) == 1
        assert jobs[0].location == "Barcelona, Spain"


# ---------------------------------------------------------------------------
# B. reject_if_requires_relocation_outside in prefilter
# ---------------------------------------------------------------------------


def _make_prefs_file(reject_outside="Spain", accept_onsite_cities=None, tmp_dir=None):
    """Write a minimal preferences YAML and return its path."""
    prefs = {
        "prefilter": {
            "deal_breakers": [],
            "title_must_contain_one_of": ["product manager", "pm"],
            "title_exclude": [],
            "exclude_companies": [],
            "location": {
                "accept_remote": True,
                "accept_hybrid": True,
                "accept_onsite_cities": accept_onsite_cities or ["Spain", "Barcelona"],
                "reject_if_requires_relocation_outside": reject_outside,
            },
        }
    }
    path = os.path.join(tmp_dir, "prefs.yaml")
    with open(path, "w") as f:
        yaml.dump(prefs, f)
    return path


def _make_applied_file(tmp_dir):
    path = os.path.join(tmp_dir, "applied.yaml")
    with open(path, "w") as f:
        yaml.dump({}, f)
    return path


def _make_seen_file(tmp_dir):
    path = os.path.join(tmp_dir, "seen.txt")
    open(path, "w").close()
    return path


def _run_prefilter(jobs, reject_outside="Spain", accept_onsite_cities=None):
    with tempfile.TemporaryDirectory() as tmp:
        prefs_path = _make_prefs_file(reject_outside, accept_onsite_cities, tmp)
        applied_path = _make_applied_file(tmp)
        from prefilter import prefilter_jobs

        home_locations = ["Spain", "Barcelona"]
        # Derive target_countries from home_locations when geo config is active
        target_countries = derive_target_countries(home_locations) if reject_outside else None

        return prefilter_jobs(
            jobs,
            config_path=prefs_path,
            applied_path=applied_path,
            home_locations=home_locations,
            target_countries=target_countries,
        )


def _pm_job(title="Senior Product Manager", company="Acme", location="", is_remote=False):
    return {
        "id": f"id_{location}_{is_remote}",
        "title": title,
        "company": company,
        "location": location,
        "description": "Great role for a PM.",
        "is_remote": is_remote,
        "remote_type": "fulltime" if is_remote else "no",
        "job_url": "https://example.com",
        "site": "linkedin",
    }


class TestGeoRejection:
    def test_france_onsite_rejected(self):
        """Paris, France onsite job → rejected when France is not target."""
        job = _pm_job(location="Paris, France", is_remote=False)
        passed, rejected, stats = _run_prefilter([job])
        assert len(passed) == 0, "France onsite job should be rejected"
        assert len(rejected) == 1

    def test_france_remote_passes(self):
        """Paris, France remote job → passes (remote is always accepted)."""
        job = _pm_job(location="Paris, France", is_remote=True)
        passed, rejected, stats = _run_prefilter([job])
        assert len(passed) == 1, "France remote job should pass"

    def test_spain_onsite_passes(self):
        """Barcelona, Spain onsite job → passes (Spain is target)."""
        job = _pm_job(location="Barcelona, Spain", is_remote=False)
        passed, rejected, stats = _run_prefilter([job])
        assert len(passed) == 1, "Spain onsite job should pass"

    def test_empty_location_passes(self):
        """Empty location → passes (conservative; let scoring handle ambiguity)."""
        job = _pm_job(location="", is_remote=False)
        passed, rejected, stats = _run_prefilter([job])
        assert len(passed) == 1, "Empty location job should pass"

    def test_nan_location_never_seen(self):
        """Location 'nan' must not appear (sanitized upstream). Verify it would pass
        if it somehow arrived (conservative fallback — empty/unknown → pass)."""
        # After sanitization, 'nan' becomes ''. But if it somehow slips through,
        # it should NOT trigger a false rejection.
        job = _pm_job(location="nan", is_remote=False)
        passed, rejected, stats = _run_prefilter([job])
        # 'nan' contains no recognized country → passes (conservative)
        assert len(passed) == 1, "'nan' location should not trigger geo rejection"

    def test_germany_onsite_rejected(self):
        """Munich, Germany onsite job → rejected when Germany not in target."""
        job = _pm_job(location="Munich, Germany", is_remote=False)
        passed, rejected, stats = _run_prefilter([job])
        assert len(passed) == 0, "Germany onsite job should be rejected"

    def test_no_config_means_no_rejection(self):
        """When reject_if_requires_relocation_outside not in prefs → no geo rejection."""
        job = _pm_job(location="Paris, France", is_remote=False)
        passed, rejected, stats = _run_prefilter([job], reject_outside=None)
        assert len(passed) == 1, "Without config, France onsite should pass"
