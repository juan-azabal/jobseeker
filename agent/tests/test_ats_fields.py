"""
Unit tests for Step 1.4:
_fetch_greenhouse/lever/ashby() return list[RawJob] with ATS metadata.
"""

import sys
import os

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob


# ── Greenhouse ──────────────────────────────────────────────────────────────


def _make_greenhouse_job(**overrides):
    base = {
        "title": "Senior Product Manager",
        "location": {"name": "Barcelona, Spain"},
        "content": "<p>Great role</p>",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
        "updated_at": "2024-01-15",
        "departments": [{"id": 1, "name": "Product", "parent_id": None}],
    }
    base.update(overrides)
    return base


def _run_greenhouse(job_data, company_name="Acme Corp", title_patterns=None):
    from ats_scraper import _fetch_greenhouse

    patterns = title_patterns or ["product manager"]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jobs": [job_data]}
    mock_resp.raise_for_status.return_value = None

    with patch("ats_scraper.requests.get", return_value=mock_resp):
        return _fetch_greenhouse("acme", company_name, patterns)


class TestGreenhouseReturnsRawJob:
    def test_returns_list_of_raw_job(self):
        jobs = _run_greenhouse(_make_greenhouse_job())
        assert len(jobs) == 1
        assert isinstance(jobs[0], RawJob)

    def test_required_fields_populated(self):
        jobs = _run_greenhouse(_make_greenhouse_job())
        j = jobs[0]
        assert j.title == "Senior Product Manager"
        assert j.company == "Acme Corp"
        assert j.source == "greenhouse"

    def test_departments_captured(self):
        """departments[] from Greenhouse job → RawJob.departments list[str]."""
        jobs = _run_greenhouse(_make_greenhouse_job())
        j = jobs[0]
        assert j.departments == ["Product"]

    def test_no_departments_gives_none(self):
        job = _make_greenhouse_job()
        del job["departments"]
        jobs = _run_greenhouse(job)
        assert jobs[0].departments is None

    def test_location_captured(self):
        jobs = _run_greenhouse(_make_greenhouse_job())
        assert jobs[0].location == "Barcelona, Spain"

    def test_remote_detection(self):
        """'Remote' in location → remote_type='fulltime'."""
        jobs = _run_greenhouse(_make_greenhouse_job(location={"name": "Remote"}))
        j = jobs[0]
        assert j.remote_type == "fulltime"
        assert j.is_remote is True

    def test_non_matching_title_filtered(self):
        """Jobs not matching title_patterns are excluded."""
        jobs = _run_greenhouse(
            _make_greenhouse_job(title="Software Engineer"),
            title_patterns=["product manager"],
        )
        assert len(jobs) == 0


# ── Lever ────────────────────────────────────────────────────────────────────


def _make_lever_job(**overrides):
    base = {
        "text": "Head of Product",
        "categories": {
            "location": "Madrid, Spain",
            "commitment": "Full-time",
            "department": "Product",
            "team": "Core Product",
        },
        "descriptionPlain": "Lead the product org.",
        "lists": [{"text": "Responsibilities", "content": ["Define roadmap", "Own KPIs"]}],
        "hostedUrl": "https://jobs.lever.co/acme/abc123",
    }
    base.update(overrides)
    return base


def _run_lever(job_data, company_name="Acme Corp", title_patterns=None):
    from ats_scraper import _fetch_lever

    patterns = title_patterns or ["product", "head of product"]
    mock_resp = MagicMock()
    mock_resp.json.return_value = [job_data]
    mock_resp.raise_for_status.return_value = None

    with patch("ats_scraper.requests.get", return_value=mock_resp):
        return _fetch_lever("acme", company_name, patterns)


class TestLeverReturnsRawJob:
    def test_returns_list_of_raw_job(self):
        jobs = _run_lever(_make_lever_job())
        assert len(jobs) == 1
        assert isinstance(jobs[0], RawJob)

    def test_required_fields_populated(self):
        jobs = _run_lever(_make_lever_job())
        j = jobs[0]
        assert j.title == "Head of Product"
        assert j.company == "Acme Corp"
        assert j.source == "lever"

    def test_team_captured(self):
        """categories.team → RawJob.team."""
        jobs = _run_lever(_make_lever_job())
        assert jobs[0].team == "Core Product"

    def test_departments_from_categories_department(self):
        """categories.department → RawJob.departments as single-element list."""
        jobs = _run_lever(_make_lever_job())
        assert jobs[0].departments == ["Product"]

    def test_no_team_or_department_gives_none(self):
        job = _make_lever_job()
        job["categories"] = {"location": "Madrid", "commitment": "Full-time"}
        jobs = _run_lever(job)
        j = jobs[0]
        assert j.team is None
        assert j.departments is None


# ── Ashby ────────────────────────────────────────────────────────────────────


def _make_ashby_job(**overrides):
    base = {
        "title": "Principal Product Manager",
        "location": "Berlin, Germany",
        "descriptionHtml": "<p>Strategic PM role</p>",
        "jobUrl": "https://jobs.ashbyhq.com/acme/xyz",
        "publishedAt": "2024-01-20",
        "employmentType": "FullTime",
        "department": "Product Management",
        "team": "Platform",
    }
    base.update(overrides)
    return base


def _run_ashby(job_data, company_name="Acme Corp", title_patterns=None):
    from ats_scraper import _fetch_ashby

    patterns = title_patterns or ["product manager", "principal"]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jobs": [job_data]}
    mock_resp.raise_for_status.return_value = None

    with patch("ats_scraper.requests.get", return_value=mock_resp):
        return _fetch_ashby("acme", company_name, patterns)


class TestAshbyReturnsRawJob:
    def test_returns_list_of_raw_job(self):
        jobs = _run_ashby(_make_ashby_job())
        assert len(jobs) == 1
        assert isinstance(jobs[0], RawJob)

    def test_required_fields_populated(self):
        jobs = _run_ashby(_make_ashby_job())
        j = jobs[0]
        assert j.title == "Principal Product Manager"
        assert j.company == "Acme Corp"
        assert j.source == "ashby"

    def test_department_captured(self):
        """department field → RawJob.departments as single-element list."""
        jobs = _run_ashby(_make_ashby_job())
        assert jobs[0].departments == ["Product Management"]

    def test_team_captured(self):
        """team field → RawJob.team."""
        jobs = _run_ashby(_make_ashby_job())
        assert jobs[0].team == "Platform"

    def test_no_department_gives_none(self):
        job = _make_ashby_job()
        del job["department"]
        jobs = _run_ashby(job)
        assert jobs[0].departments is None

    def test_no_team_gives_none(self):
        job = _make_ashby_job()
        del job["team"]
        jobs = _run_ashby(job)
        assert jobs[0].team is None
