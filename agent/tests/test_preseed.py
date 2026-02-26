"""
Unit tests for Step 3.1:
preseed_parsed(job: dict) -> dict maps structured RawJob fields to parser schema.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _job(**kwargs) -> dict:
    base = dict(
        id="abc123",
        title="Senior PM",
        company="Acme",
        source="indeed",
        description="A job description here.",
    )
    base.update(kwargs)
    return base


class TestSeniority:

    def test_mid_senior_maps_to_senior(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Mid-Senior Level"))
        assert result.get("seniority") == "senior"

    def test_senior_maps_to_senior(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Senior"))
        assert result.get("seniority") == "senior"

    def test_director_maps_to_director(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Director"))
        assert result.get("seniority") == "director"

    def test_vp_executive_maps_to_vp(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Executive"))
        assert result.get("seniority") == "vp"

    def test_entry_level_maps_to_junior(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Entry Level"))
        assert result.get("seniority") == "junior"

    def test_associate_maps_to_mid(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Associate"))
        assert result.get("seniority") == "mid"

    def test_not_applicable_skipped(self):
        """'Not Applicable' job_level → seniority not pre-seeded."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Not Applicable"))
        assert "seniority" not in result

    def test_none_job_level_skipped(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level=None))
        assert "seniority" not in result

    def test_empty_job_level_skipped(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level=""))
        assert "seniority" not in result

    def test_staff_maps_to_staff(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Staff"))
        assert result.get("seniority") == "staff"

    def test_principal_maps_to_principal(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(job_level="Principal"))
        assert result.get("seniority") == "principal"


class TestLocationType:

    def test_fulltime_maps_to_remote(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(remote_type="fulltime"))
        assert result.get("location_type") == "remote"

    def test_partial_maps_to_hybrid(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(remote_type="partial"))
        assert result.get("location_type") == "hybrid"

    def test_no_maps_to_onsite(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(remote_type="no"))
        assert result.get("location_type") == "onsite"

    def test_none_remote_type_skipped(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(remote_type=None))
        assert "location_type" not in result


class TestSalary:

    def test_salary_formatted_from_min_max(self):
        """Both min and max → 'min - max currency/interval'."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            min_amount=80000.0, max_amount=100000.0,
            currency="EUR", interval="yearly",
            salary_source="direct_data",
        ))
        sal = result.get("salary_mentioned", "")
        assert "80" in sal
        assert "100" in sal
        assert "EUR" in sal or "€" in sal

    def test_salary_min_only(self):
        """Only min → formatted with min only."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            min_amount=90000.0, max_amount=None,
            currency="USD", interval="yearly",
            salary_source="direct_data",
        ))
        assert result.get("salary_mentioned") is not None
        assert "90" in result.get("salary_mentioned", "")

    def test_salary_not_seeded_when_source_not_direct(self):
        """salary_source != 'direct_data' → salary not pre-seeded."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            min_amount=80000.0, max_amount=100000.0,
            currency="EUR", interval="yearly",
            salary_source="description",
        ))
        assert "salary_mentioned" not in result

    def test_salary_not_seeded_when_no_amount(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            min_amount=None, max_amount=None,
            salary_source="direct_data",
        ))
        assert "salary_mentioned" not in result

    def test_salary_not_seeded_when_no_salary_source(self):
        """No salary_source → salary not pre-seeded (conservative)."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            min_amount=80000.0,
        ))
        assert "salary_mentioned" not in result


class TestDomain:

    def test_fintech_from_company_industry(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(company_industry="Financial Services"))
        assert result.get("domain") == "fintech"

    def test_healthtech_from_company_industry(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(company_industry="Hospital & Health Care"))
        assert result.get("domain") == "healthtech"

    def test_gaming_from_company_industry(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(company_industry="Computer Games"))
        assert result.get("domain") == "gaming"

    def test_domain_from_source_category(self):
        """source_category used when company_industry is absent."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(source_category="data-analytics-wNjYw"))
        assert result.get("domain") == "data"

    def test_domain_skipped_when_unmappable(self):
        """Unmappable industry → domain not pre-seeded (don't guess)."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(company_industry="Some Obscure Industry"))
        assert "domain" not in result

    def test_domain_skipped_when_both_absent(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job())
        assert "domain" not in result


class TestExperience:

    def test_experience_min_max_both_seeded(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(experience_min=5, experience_max=8))
        assert result.get("years_experience_min") == 5
        assert result.get("years_experience_max") == 8

    def test_experience_min_only(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(experience_min=3))
        assert result.get("years_experience_min") == 3
        assert "years_experience_max" not in result

    def test_experience_none_skipped(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job(experience_min=None, experience_max=None))
        assert "years_experience_min" not in result
        assert "years_experience_max" not in result


class TestLocations:

    def test_locations_from_structured(self):
        """locations_structured → flat list of city/country strings."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            locations_structured=[
                {"city": "Barcelona", "country_code": "ES"},
                {"city": "Madrid", "country_code": "ES"},
            ]
        ))
        locs = result.get("locations_mentioned", [])
        assert "Barcelona" in locs
        assert "Madrid" in locs

    def test_locations_from_city_country_fallback(self):
        """city/country used when locations_structured absent."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(city="Amsterdam", country="NL"))
        locs = result.get("locations_mentioned", [])
        assert "Amsterdam" in locs

    def test_no_locations_skipped(self):
        from preseed import preseed_parsed

        result = preseed_parsed(_job())
        assert "locations_mentioned" not in result

    def test_locations_deduplicated(self):
        """Duplicate location strings removed."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(
            locations_structured=[
                {"city": "Barcelona", "country_code": "ES"},
                {"city": "Barcelona", "country_code": "ES"},
            ]
        ))
        locs = result.get("locations_mentioned", [])
        assert locs.count("Barcelona") == 1


class TestEmpty:

    def test_no_structured_fields_returns_empty(self):
        """Job with no structured data → empty preseed dict."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job())
        assert result == {}

    def test_returns_only_non_null_fields(self):
        """Only fields with actual values are returned."""
        from preseed import preseed_parsed

        result = preseed_parsed(_job(remote_type="fulltime", job_level=None))
        assert "location_type" in result
        assert "seniority" not in result
        for v in result.values():
            assert v is not None
