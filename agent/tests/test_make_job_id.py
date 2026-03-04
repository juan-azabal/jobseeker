"""
Unit tests for Step 0.2 — make_job_id normalization.
Verifies deduplication across cross-source title/company variants.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMakeJobIdNormalization:
    def test_gender_suffix_stripped(self):
        """(f/m/d) and similar suffixes must be stripped before hashing."""
        from scraper import make_job_id

        assert make_job_id("Senior PM (f/m/d)", "Elastic GmbH") == make_job_id("Senior PM", "Elastic")

    def test_leading_trailing_spaces(self):
        """Leading/trailing spaces in title must not produce different IDs."""
        from scraper import make_job_id

        assert make_job_id(" Senior PM, Platform", "Elastic") == make_job_id("Senior PM - Platform", "Elastic")

    def test_double_spaces_collapsed(self):
        """Double spaces collapsed to single before hashing."""
        from scraper import make_job_id

        assert make_job_id("AI PM  - Denmark", "Factbird") == make_job_id("AI PM - Denmark", "Factbird")

    def test_company_legal_suffix_stripped(self):
        """Legal suffixes like ', Inc.' stripped from company."""
        from scraper import make_job_id

        assert make_job_id("PM", "Stripe, Inc.") == make_job_id("PM", "Stripe")

    def test_idempotent(self):
        """Same inputs always produce same ID."""
        from scraper import make_job_id

        assert make_job_id("PM", "X") == make_job_id("PM", "X")

    def test_gmbh_stripped(self):
        """GmbH suffix stripped from company."""
        from scraper import make_job_id

        assert make_job_id("PM", "Elastic GmbH") == make_job_id("PM", "Elastic")

    def test_ltd_stripped(self):
        """Ltd suffix stripped from company."""
        from scraper import make_job_id

        assert make_job_id("PM", "Acme Ltd") == make_job_id("PM", "Acme")

    def test_all_genders_stripped(self):
        """(all genders) suffix stripped."""
        from scraper import make_job_id

        assert make_job_id("Senior PM (all genders)", "Acme") == make_job_id("Senior PM", "Acme")

    def test_hfm_slash_suffix_stripped(self):
        """(h/f) suffix stripped."""
        from scraper import make_job_id

        assert make_job_id("PM (h/f)", "Acme") == make_job_id("PM", "Acme")

    def test_punctuation_normalized(self):
        """Punctuation differences between comma and dash don't produce different IDs."""
        from scraper import make_job_id

        # Both normalize punctuation to spaces then collapse
        id1 = make_job_id("Senior PM, Platform", "Acme")
        id2 = make_job_id("Senior PM - Platform", "Acme")
        id3 = make_job_id("Senior PM  Platform", "Acme")
        assert id1 == id2 == id3

    def test_two_arg_signature(self):
        """make_job_id must accept exactly 2 positional args (no location)."""
        from scraper import make_job_id
        import inspect

        sig = inspect.signature(make_job_id)
        params = list(sig.parameters.keys())
        assert "location" not in params, f"'location' param should be removed, got: {params}"
        assert len(params) == 2, f"Expected 2 params (title, company), got: {params}"

    def test_different_titles_produce_different_ids(self):
        """Sanity: distinct titles still produce distinct IDs."""
        from scraper import make_job_id

        assert make_job_id("Senior PM", "Acme") != make_job_id("Junior PM", "Acme")

    def test_different_companies_produce_different_ids(self):
        """Sanity: distinct companies still produce distinct IDs."""
        from scraper import make_job_id

        assert make_job_id("PM", "Acme") != make_job_id("PM", "Other Corp")


class TestGeoSuffixNormalization:
    """Greenhouse-style titles like 'Senior PM | Canada | Remote' must dedup
    with the same role in a different geo before hashing."""

    def test_cross_geo_same_id(self):
        """Same role at same company in different geos → identical job_id."""
        from scraper import make_job_id

        assert make_job_id("Senior PM | Canada | Remote", "Grafana Labs") == make_job_id(
            "Senior PM | Spain | Remote", "Grafana Labs"
        )

    def test_geo_suffix_remote_stripped(self):
        """'| Country | Remote' suffix stripped before hashing."""
        from scraper import make_job_id

        assert make_job_id("Senior PM | Canada | Remote", "Acme") == make_job_id("Senior PM", "Acme")

    def test_geo_suffix_hybrid_stripped(self):
        """'| Region | Hybrid' suffix stripped."""
        from scraper import make_job_id

        assert make_job_id("Staff Engineer | EMEA | Hybrid", "Acme") == make_job_id("Staff Engineer", "Acme")

    def test_geo_suffix_onsite_stripped(self):
        """'| Region | On-site' suffix stripped."""
        from scraper import make_job_id

        assert make_job_id("Senior PM | EMEA | On-site", "Acme") == make_job_id("Senior PM", "Acme")

    def test_geo_suffix_office_stripped(self):
        """'| Country | Office' suffix stripped."""
        from scraper import make_job_id

        assert make_job_id("PM | Germany | Office", "Acme") == make_job_id("PM", "Acme")

    def test_single_pipe_not_stripped(self):
        """Only one pipe segment → not a geo suffix → unchanged."""
        from scraper import make_job_id

        # "PM | Canada" with no workmode should NOT be stripped
        assert make_job_id("PM | Canada", "Acme") != make_job_id("PM", "Acme")

    def test_unknown_workmode_not_stripped(self):
        """'| Country | Full-time' is not in workmode whitelist → not stripped."""
        from scraper import make_job_id

        assert make_job_id("PM | Canada | Full-time", "Acme") != make_job_id("PM", "Acme")

    def test_multiword_region_stripped(self):
        """Multi-word region like 'United States' is stripped correctly."""
        from scraper import make_job_id

        assert make_job_id("Senior PM | United States | Remote", "Acme") == make_job_id("Senior PM", "Acme")
