"""
Unit tests for Step 1.1 — RawJob Pydantic model (agent/models.py).
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRawJobModel:

    def test_minimal_required_fields(self):
        """Only id, title, company, source are required."""
        from models import RawJob
        job = RawJob(id="abc123", title="Senior PM", company="Acme", source="indeed")
        assert job.id == "abc123"
        assert job.title == "Senior PM"
        assert job.company == "Acme"
        assert job.source == "indeed"

    def test_glassdoor_is_valid_source(self):
        """glassdoor must be a valid source value."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="glassdoor")
        assert job.source == "glassdoor"

    def test_all_sources_valid(self):
        """All 8 expected source values must be accepted."""
        from models import RawJob
        for src in ("indeed", "linkedin", "google", "glassdoor", "greenhouse", "lever", "ashby", "wttj"):
            job = RawJob(id="x", title="PM", company="Acme", source=src)
            assert job.source == src

    def test_optional_fields_default_to_none(self):
        """Optional fields not provided default to None."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="indeed")
        assert job.company_url is None
        assert job.company_industry is None
        assert job.company_employees_label is None
        assert job.company_revenue_label is None
        assert job.company_logo is None
        assert job.job_level is None
        assert job.salary_source is None
        assert job.country is None
        assert job.city is None
        assert job.state is None
        assert job.emails is None
        assert job.job_function is None
        assert job.remote_type is None
        assert job.experience_min is None
        assert job.experience_max is None
        assert job.language is None
        assert job.departments is None
        assert job.team is None
        assert job.locations_structured is None
        assert job.sources == []  # list field defaults to empty list

    def test_is_remote_true_when_fulltime(self):
        """is_remote computed property returns True when remote_type='fulltime'."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="wttj", remote_type="fulltime")
        assert job.is_remote is True

    def test_is_remote_true_when_partial(self):
        """is_remote returns True when remote_type='partial'."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="wttj", remote_type="partial")
        assert job.is_remote is True

    def test_is_remote_false_when_no(self):
        """is_remote returns False when remote_type='no'."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="wttj", remote_type="no")
        assert job.is_remote is False

    def test_is_remote_false_when_none(self):
        """is_remote returns False when remote_type is None."""
        from models import RawJob
        job = RawJob(id="x", title="PM", company="Acme", source="indeed")
        assert job.is_remote is False

    def test_all_optional_fields_populate(self):
        """All optional fields can be set and retrieved."""
        from models import RawJob
        job = RawJob(
            id="abc",
            title="Head of PM",
            company="Stripe",
            source="linkedin",
            company_url="https://stripe.com",
            company_industry="Fintech",
            company_employees_label="1001-5000",
            company_revenue_label="$500M-$1B",
            company_logo="https://logo.com/stripe.png",
            job_level="Director",
            salary_source="direct_data",
            country="ES",
            city="Barcelona",
            state=None,
            emails=["hr@stripe.com"],
            job_function="Product Management",
            remote_type="partial",
            experience_min=5,
            experience_max=10,
            language="en",
            departments=["Product"],
            team="Platform",
            locations_structured=[{"city": "Barcelona", "country_code": "ES"}],
            sources=["linkedin", "greenhouse"],
        )
        assert job.company_url == "https://stripe.com"
        assert job.company_industry == "Fintech"
        assert job.departments == ["Product"]
        assert job.sources == ["linkedin", "greenhouse"]
        assert job.is_remote is True

    def test_extra_fields_ignored(self):
        """Pydantic model must ignore unknown extra fields."""
        from models import RawJob
        # Pydantic v2 default: ignore extras — should not raise
        job = RawJob(
            id="x", title="PM", company="Acme", source="indeed",
            unknown_field_xyz="should be ignored",
        )
        assert job.id == "x"
