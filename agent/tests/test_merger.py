"""
Unit tests for Step 2.1:
merge_jobs(jobs: list[RawJob]) -> list[RawJob]
Source-group priority merging of duplicate jobs.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob
from scraper import make_job_id


def _job(source, title="Senior PM", company="Acme", **kwargs) -> RawJob:
    return RawJob(
        id=make_job_id(title, company),
        title=title,
        company=company,
        source=source,
        **kwargs,
    )


class TestSingleSource:
    def test_single_job_passes_through(self):
        """Single-source job passes through unchanged (except sources populated)."""
        from merger import merge_jobs

        job = _job("indeed", location="Barcelona", min_amount=80000.0)
        result = merge_jobs([job])

        assert len(result) == 1
        r = result[0]
        assert r.location == "Barcelona"
        assert r.min_amount == 80000.0

    def test_single_job_sources_populated(self):
        """sources list contains the single source."""
        from merger import merge_jobs

        job = _job("indeed")
        result = merge_jobs([job])

        assert result[0].sources == ["indeed"]

    def test_empty_list(self):
        from merger import merge_jobs

        assert merge_jobs([]) == []

    def test_unique_jobs_all_returned(self):
        """N jobs with different ids → N results."""
        from merger import merge_jobs

        jobs = [
            _job("indeed", title="PM A", company="Co1"),
            _job("indeed", title="PM B", company="Co2"),
            _job("wttj", title="PM C", company="Co3"),
        ]
        result = merge_jobs(jobs)
        assert len(result) == 3


class TestFieldGroupPriority:
    def test_salary_prefers_wttj_over_indeed(self):
        """WTTJ has salary priority; Indeed fills remaining gaps."""
        from merger import merge_jobs

        indeed_job = _job(
            "indeed",
            min_amount=75000.0,
            max_amount=95000.0,
            currency="USD",
        )
        wttj_job = _job(
            "wttj",
            min_amount=80000.0,
            max_amount=100000.0,
            currency="EUR",
        )
        result = merge_jobs([indeed_job, wttj_job])

        assert len(result) == 1
        r = result[0]
        # WTTJ wins for salary group
        assert r.min_amount == 80000.0
        assert r.max_amount == 100000.0
        assert r.currency == "EUR"

    def test_company_meta_prefers_indeed_over_wttj(self):
        """Indeed wins company_meta group."""
        from merger import merge_jobs

        indeed_job = _job(
            "indeed",
            company_industry="Tech",
            company_employees_label="1001-5000",
        )
        wttj_job = _job(
            "wttj",
            company_industry="Software",
            company_employees_label="201-500",
        )
        result = merge_jobs([indeed_job, wttj_job])

        r = result[0]
        assert r.company_industry == "Tech"
        assert r.company_employees_label == "1001-5000"

    def test_remote_type_prefers_wttj(self):
        """WTTJ wins remote_type group (knows partial remote best)."""
        from merger import merge_jobs

        indeed_job = _job("indeed", remote_type="no")
        wttj_job = _job("wttj", remote_type="partial")
        result = merge_jobs([indeed_job, wttj_job])

        assert result[0].remote_type == "partial"

    def test_job_level_prefers_linkedin(self):
        """LinkedIn wins job_level group."""
        from merger import merge_jobs

        indeed_job = _job("indeed", job_level="Senior")
        linkedin_job = _job("linkedin", job_level="Director")
        result = merge_jobs([indeed_job, linkedin_job])

        assert result[0].job_level == "Director"

    def test_location_prefers_indeed(self):
        """Indeed wins location group (city/country)."""
        from merger import merge_jobs

        wttj_job = _job("wttj", city="Barcelona", country="ES")
        indeed_job = _job("indeed", city="Madrid", country="ES")
        result = merge_jobs([wttj_job, indeed_job])

        assert result[0].city == "Madrid"

    def test_description_prefers_greenhouse(self):
        """Greenhouse wins description group (ATS first)."""
        from merger import merge_jobs

        gh_job = _job("greenhouse", description="GH desc with details about the role.")
        li_job = _job("linkedin", description="LI desc short.")
        result = merge_jobs([gh_job, li_job])

        assert "GH desc" in result[0].description

    def test_org_structure_team_prefers_greenhouse(self):
        """Greenhouse wins org_structure group for non-list fields (team)."""
        from merger import merge_jobs

        gh_job = _job("greenhouse", team="Platform")
        li_job = _job("linkedin", team="Core Product")
        result = merge_jobs([gh_job, li_job])

        # Greenhouse wins org_structure group → its team wins
        assert result[0].team == "Platform"

    def test_gap_filling_across_groups(self):
        """Fields absent in priority source are filled from lower-priority sources."""
        from merger import merge_jobs

        # Indeed has salary, WTTJ has experience_min but no salary
        indeed_job = _job("indeed", min_amount=90000.0, currency="USD")
        wttj_job = _job("wttj", experience_min=5, experience_max=8)
        result = merge_jobs([indeed_job, wttj_job])

        r = result[0]
        # WTTJ wins salary group → but WTTJ has no salary, so Indeed fills in
        assert r.min_amount == 90000.0  # Indeed fills since WTTJ has none
        # WTTJ wins remote group → experience from WTTJ
        assert r.experience_min == 5
        assert r.experience_max == 8


class TestDescriptionMerge:
    def test_description_prefers_longer(self):
        """Within description group, longer text wins even if lower-priority source."""
        from merger import merge_jobs

        short_gh = _job("greenhouse", description="Short GH desc.")
        long_li = _job("linkedin", description="Long LinkedIn description " * 10)
        result = merge_jobs([short_gh, long_li])

        # LinkedIn desc is much longer → should win
        assert "LinkedIn description" in result[0].description

    def test_description_prefers_non_html(self):
        """Plain text preferred over HTML of similar length."""
        from merger import merge_jobs

        html_job = _job("greenhouse", description="<p>Build <b>features</b> and define roadmap.</p>")
        plain_job = _job("linkedin", description="Build features and define roadmap for the team.")
        result = merge_jobs([html_job, plain_job])

        # Plain text wins (no HTML tags)
        assert "<" not in result[0].description

    def test_none_description_falls_back(self):
        """None description in priority source → falls back to next source."""
        from merger import merge_jobs

        gh_job = _job("greenhouse", description=None)
        li_job = _job("linkedin", description="LinkedIn description content.")
        result = merge_jobs([gh_job, li_job])

        assert result[0].description == "LinkedIn description content."


class TestListFieldMerge:
    def test_departments_unioned(self):
        """departments lists merged across sources (deduped)."""
        from merger import merge_jobs

        gh_job = _job("greenhouse", departments=["Product"])
        ashby_job = _job("ashby", departments=["Product", "Platform"])
        result = merge_jobs([gh_job, ashby_job])

        depts = result[0].departments
        assert set(depts) == {"Product", "Platform"}

    def test_locations_structured_unioned(self):
        """locations_structured lists merged (no dedup — raw list union)."""
        from merger import merge_jobs

        wttj1 = _job("wttj", locations_structured=[{"city": "Barcelona", "country_code": "ES"}])
        wttj2 = _job("wttj", locations_structured=[{"city": "Madrid", "country_code": "ES"}])
        # Same id — different run results
        result = merge_jobs([wttj1, wttj2])

        assert len(result[0].locations_structured) == 2

    def test_none_list_field_ignored(self):
        """None list field on one source doesn't wipe the other's data."""
        from merger import merge_jobs

        gh_job = _job("greenhouse", departments=["Product"])
        li_job = _job("linkedin", departments=None)
        result = merge_jobs([gh_job, li_job])

        assert result[0].departments == ["Product"]


class TestSourcesTracking:
    def test_two_sources_tracked(self):
        from merger import merge_jobs

        j1 = _job("indeed")
        j2 = _job("wttj")
        result = merge_jobs([j1, j2])

        assert set(result[0].sources) == {"indeed", "wttj"}

    def test_three_sources_tracked(self):
        from merger import merge_jobs

        j1 = _job("greenhouse")
        j2 = _job("linkedin")
        j3 = _job("indeed")
        result = merge_jobs([j1, j2, j3])

        assert set(result[0].sources) == {"greenhouse", "linkedin", "indeed"}

    def test_single_source_tracked(self):
        from merger import merge_jobs

        j = _job("wttj")
        result = merge_jobs([j])

        assert result[0].sources == ["wttj"]

    def test_non_grouped_field_uses_best_source(self):
        """Fields outside FIELD_TO_GROUP use the best SOURCE_RANK source."""
        from merger import merge_jobs

        # greenhouse rank=1, indeed rank=6
        gh_job = _job("greenhouse", job_url="https://boards.greenhouse.io/acme/1")
        indeed_job = _job("indeed", job_url="https://www.indeed.com/job/1")
        result = merge_jobs([gh_job, indeed_job])

        # greenhouse has highest priority → its job_url wins
        assert "greenhouse" in result[0].job_url


class TestTitleVariants:
    """title_variants captures all original titles when geo-variant jobs merge."""

    def test_single_job_no_title_variants(self):
        """Single job passes through; title_variants stays None."""
        from merger import merge_jobs

        job = _job("greenhouse", title="Senior PM")
        result = merge_jobs([job])

        assert result[0].title_variants is None

    def test_merged_jobs_title_variants_collected(self):
        """Two jobs with same id but different titles → title_variants has both."""
        from merger import merge_jobs
        from scraper import make_job_id

        title_ca = "Senior PM | Canada | Remote"
        title_es = "Senior PM | Spain | Remote"
        company = "Grafana Labs"
        # After geo-suffix stripping, both produce the same id
        shared_id = make_job_id(title_ca, company)

        job_ca = RawJob(id=shared_id, title=title_ca, company=company, source="greenhouse")
        job_es = RawJob(id=shared_id, title=title_es, company=company, source="greenhouse")

        result = merge_jobs([job_ca, job_es])

        assert len(result) == 1
        merged = result[0]
        assert merged.title_variants is not None
        assert title_ca in merged.title_variants
        assert title_es in merged.title_variants

    def test_same_title_no_duplicate_variants(self):
        """Same title from two sources → title_variants deduped."""
        from merger import merge_jobs
        from scraper import make_job_id

        title = "Senior PM"
        company = "Acme"
        shared_id = make_job_id(title, company)

        job_gh = RawJob(id=shared_id, title=title, company=company, source="greenhouse")
        job_li = RawJob(id=shared_id, title=title, company=company, source="linkedin")

        result = merge_jobs([job_gh, job_li])

        assert len(result) == 1
        # Same title from two sources → appears once (or None if deduplicated to single entry)
        variants = result[0].title_variants
        assert variants is not None
        assert variants.count(title) == 1
