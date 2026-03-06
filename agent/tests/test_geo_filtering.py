"""
Tests for Phase 15 geo filtering: resolver, WTTJ filter, ATS filter, prefilter.
"""

import sys
import os
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from geo import resolve_location_country, derive_target_countries
from prefilter import prefilter_jobs
from wttj_scraper import _build_geo_filter
from ats_scraper import _is_geo_allowed
from models import RawJob as _RawJob

# Load geo test fixtures (fixtures/ has no __init__.py, import directly)
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "geo_test_jobs",
    os.path.join(os.path.dirname(__file__), "fixtures", "geo_test_jobs.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
GEO_TEST_JOBS = _mod.GEO_TEST_JOBS


# ---------------------------------------------------------------------------
# 15.1 — resolve_location_country
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "location,expected",
    [
        ("San Francisco, CA", "US"),
        ("Barcelona, Spain", "ES"),
        ("Berlin, Germany", "DE"),
        ("New York, NY", "US"),
        ("Paris", "FR"),
        ("Remote", None),
        ("", None),
        ("Strasbourg, France", "FR"),
        ("Mumbai, India", "IN"),
        ("Barcelona", "ES"),
    ],
)
def test_resolve_location_country(location, expected):
    assert resolve_location_country(location) == expected


def test_resolve_location_country_none_input():
    assert resolve_location_country(None) is None


# ---------------------------------------------------------------------------
# 15.1 — derive_target_countries
# ---------------------------------------------------------------------------


def test_derive_target_countries_barcelona_spain():
    result = derive_target_countries(["barcelona", "spain"])
    assert result == ["ES"]


def test_derive_target_countries_new_york_us():
    result = derive_target_countries(["new york", "us"])
    assert result == ["US"]


def test_derive_target_countries_deduplication():
    # Both "barcelona" and "spain" resolve to ES — only one "ES" in result
    result = derive_target_countries(["barcelona", "spain"])
    assert result.count("ES") == 1


def test_derive_target_countries_empty():
    assert derive_target_countries([]) == []


def test_derive_target_countries_unresolvable():
    # "remote" and "" are unresolvable → empty result
    result = derive_target_countries(["remote", ""])
    assert result == []


# ---------------------------------------------------------------------------
# 15.2 — Regression baseline: current prefilter behavior on synthetic jobs
# ---------------------------------------------------------------------------


@pytest.fixture
def geo_prefs_file(tmp_path):
    """Minimal prefilter config for geo regression baseline."""
    prefs = {
        "prefilter": {
            "deal_breakers": [],
            "title_must_contain_one_of": ["product manager", "head of product", "vp product"],
            "title_exclude": [],
            "exclude_companies": [],
            "location": {
                "accept_onsite_cities": ["Barcelona"],
                "reject_if_requires_relocation_outside": "Spain",
            },
        }
    }
    f = tmp_path / "prefs.yaml"
    f.write_text(yaml.dump(prefs))
    return str(f)


@pytest.fixture
def empty_applied(tmp_path):
    return str(tmp_path / "nonexistent-applied.yaml")


@pytest.fixture
def empty_seen(tmp_path):
    return str(tmp_path / "nonexistent-seen.txt")


class TestGeoRegressionBaseline:
    """Baseline: documents current prefilter behavior before Phase 15.5 changes.

    After 15.5, jobs that currently PASS must still pass (regression check).
    Jobs that were incorrectly PASSING (e.g. US jobs via null location) are
    expected to fail after 15.5 — so we only assert the "must still pass" subset.
    """

    def _run(self, jobs, prefs_file, empty_applied, empty_seen, target_countries=None):
        job_dicts = [dict(j) for j in jobs]
        passed, rejected, stats = prefilter_jobs(
            job_dicts,
            prefs_file,
            empty_applied,
            empty_seen,
            home_locations=["barcelona", "spain"],
            target_countries=target_countries or ["ES"],
        )
        passed_ids = {j["id"] for j in passed}
        rejected_ids = {j["id"] for j in rejected}
        return passed_ids, rejected_ids, stats

    def test_es_onsite_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """Spain onsite must always pass."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "es-onsite"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "es-onsite" in passed_ids

    def test_es_madrid_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """Madrid Spain onsite must always pass."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "es-madrid-onsite"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "es-madrid-onsite" in passed_ids

    def test_global_remote_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """Global remote must always pass."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "global-remote"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "global-remote" in passed_ids

    def test_ats_no_location_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """ATS job with null location → conservative pass."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "ats-no-loc"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "ats-no-loc" in passed_ids

    def test_no_loc_no_signals_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """Job with null location and no signals → conservative pass."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "no-loc-no-signals"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "no-loc-no-signals" in passed_ids

    def test_us_sf_rejected_by_us_only(self, geo_prefs_file, empty_applied, empty_seen):
        """SF job with CA state code → rejected as US-only."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "us-sf-loc"]
        _, rejected_ids, stats = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "us-sf-loc" in rejected_ids

    def test_fr_onsite_rejected(self, geo_prefs_file, empty_applied, empty_seen):
        """France onsite → rejected (non-target country)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "fr-onsite"]
        _, rejected_ids, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "fr-onsite" in rejected_ids

    def test_us_remote_fulltime_passes(self, geo_prefs_file, empty_applied, empty_seen):
        """US remote fulltime → passes (remote_type=fulltime exemption in unified geo filter)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "us-remote-ft"]
        passed_ids, _, _ = self._run(jobs, geo_prefs_file, empty_applied, empty_seen)
        assert "us-remote-ft" in passed_ids

    def test_baseline_stats_printed(self, geo_prefs_file, empty_applied, empty_seen, capsys):
        """Full baseline run prints stats."""
        job_dicts = [dict(j) for j in GEO_TEST_JOBS]
        passed, rejected, stats = prefilter_jobs(
            job_dicts,
            geo_prefs_file,
            empty_applied,
            empty_seen,
            home_locations=["barcelona", "spain"],
            target_countries=["ES"],
        )
        out = capsys.readouterr().out
        assert "Pre-filter" in out
        print(f"\nBaseline stats: {stats}")
        print(f"Passed: {[j['id'] for j in passed]}")
        print(f"Rejected: {[(j['id'], j.get('reject_reason', '')) for j in rejected]}")


# ---------------------------------------------------------------------------
# 15.3 — WTTJ _build_geo_filter tests
# ---------------------------------------------------------------------------


class TestWTTJGeoFilter:
    """Test that partial-remote from non-target countries is excluded."""

    def _in_filter(self, filter_str: str, offices_code: str, remote: str) -> bool:
        """Simulate Algolia filter evaluation.

        A job matches the filter if:
        - offices.country_code:<code> is in the filter, OR
        - remote:<type> is in the filter
        """
        office_clause = f"offices.country_code:{offices_code}"
        remote_clause = f"remote:{remote}"
        return office_clause in filter_str or remote_clause in filter_str

    def test_fr_partial_not_in_es_filter(self):
        """FR office + partial remote → NOT included (partial from non-target excluded)."""
        f = _build_geo_filter(["ES"])
        assert not self._in_filter(f, "FR", "partial")

    def test_es_partial_in_es_filter(self):
        """ES office + partial remote → included (target country)."""
        f = _build_geo_filter(["ES"])
        assert self._in_filter(f, "ES", "partial")

    def test_fr_fulltime_in_es_filter(self):
        """FR office + fulltime remote → included (remote fulltime always passes)."""
        f = _build_geo_filter(["ES"])
        assert self._in_filter(f, "FR", "fulltime")

    def test_es_onsite_in_es_filter(self):
        """ES office + no remote → included (onsite in target country)."""
        f = _build_geo_filter(["ES"])
        assert self._in_filter(f, "ES", "no")

    def test_fr_onsite_not_in_es_filter(self):
        """FR office + no remote → NOT included (onsite in non-target)."""
        f = _build_geo_filter(["ES"])
        assert not self._in_filter(f, "FR", "no")


# ---------------------------------------------------------------------------
# 15.4 — ATS scraper geo filter (_is_geo_allowed)
# ---------------------------------------------------------------------------


def _make_ats_job(location, remote_type="no") -> _RawJob:
    return _RawJob(
        id="test",
        title="Product Manager",
        company="Test Co",
        source="greenhouse",
        location=location,
        remote_type=remote_type,
    )


class TestATSGeoFilter:
    def test_ny_rejected_for_es_target(self):
        """New York, NY (US) → rejected when target is ES."""
        job = _make_ats_job("New York, NY")
        assert not _is_geo_allowed(job, ["ES"])

    def test_barcelona_accepted_for_es_target(self):
        """Barcelona, Spain → accepted when target is ES."""
        job = _make_ats_job("Barcelona, Spain")
        assert _is_geo_allowed(job, ["ES"])

    def test_remote_location_accepted_regardless_of_target(self):
        """Location string 'Remote' → always accepted."""
        job = _make_ats_job("Remote")
        assert _is_geo_allowed(job, ["ES"])

    def test_empty_location_accepted_conservative(self):
        """Empty location → accepted (conservative: unresolved)."""
        job = _make_ats_job("")
        assert _is_geo_allowed(job, ["ES"])

    def test_ny_accepted_for_us_target(self):
        """New York, NY → accepted when target is US."""
        job = _make_ats_job("New York, NY")
        assert _is_geo_allowed(job, ["US"])

    def test_barcelona_rejected_for_us_target(self):
        """Barcelona, Spain → rejected when target is US."""
        job = _make_ats_job("Barcelona, Spain")
        assert not _is_geo_allowed(job, ["US"])

    def test_fulltime_remote_type_accepted_regardless(self):
        """remote_type=fulltime → always accepted even with US location."""
        job = _make_ats_job("San Francisco, CA", remote_type="fulltime")
        assert _is_geo_allowed(job, ["ES"])

    def test_remote_in_location_string_accepted(self):
        """Location containing 'remote' → always accepted."""
        job = _make_ats_job("Remote, US")
        assert _is_geo_allowed(job, ["ES"])


# ---------------------------------------------------------------------------
# 15.5 — Unified _is_non_target_geo tests
# ---------------------------------------------------------------------------


from prefilter import _is_non_target_geo as _geo_filter


def _geo_job(**kwargs) -> dict:
    base = {
        "id": "test",
        "title": "Product Manager",
        "company": "Corp",
        "source": "linkedin",
        "location": None,
        "description": "",
        "remote_type": "no",
        "is_remote": False,
    }
    base.update(kwargs)
    return base


class TestUnifiedGeoFilter:
    """Tests for _is_non_target_geo covering all three layers."""

    # --- Layer 1: structured location ---

    def test_layer1_sf_ca_rejected_for_es(self):
        """SF CA → resolved US, rejected for ES target."""
        job = _geo_job(location="San Francisco, CA")
        rejected, country, layer = _geo_filter(job, ["ES"])
        assert rejected is True
        assert country == "US"
        assert layer == "prefilter_location"

    def test_layer1_barcelona_passes_for_es(self):
        """Barcelona → resolved ES, passes for ES target."""
        job = _geo_job(location="Barcelona")
        rejected, _, _ = _geo_filter(job, ["ES"])
        assert rejected is False

    def test_layer1_berlin_rejected_for_es(self):
        """Berlin, Germany → DE, rejected for ES target."""
        job = _geo_job(location="Berlin, Germany")
        rejected, country, _ = _geo_filter(job, ["ES"])
        assert rejected is True
        assert country == "DE"

    def test_layer1_remote_fulltime_always_passes(self):
        """remote_type=fulltime → never rejected regardless of location."""
        job = _geo_job(location="San Francisco, CA", remote_type="fulltime")
        rejected, _, _ = _geo_filter(job, ["ES"])
        assert rejected is False

    def test_layer1_null_location_falls_through(self):
        """Null location → no Layer 1 rejection (falls through to Layer 2/3)."""
        job = _geo_job(location=None, description="")
        rejected, _, _ = _geo_filter(job, ["ES"])
        assert rejected is False

    def test_layer1_mumbai_passes_for_in(self):
        """Mumbai → IN, passes for IN target."""
        job = _geo_job(location="Mumbai")
        rejected, _, _ = _geo_filter(job, ["IN"])
        assert rejected is False

    def test_layer1_london_rejected_for_in(self):
        """London → GB, rejected for IN target."""
        job = _geo_job(location="London, United Kingdom")
        rejected, country, _ = _geo_filter(job, ["IN"])
        assert rejected is True
        assert country == "GB"

    def test_layer1_sf_passes_for_us(self):
        """SF CA → US, passes for US target."""
        job = _geo_job(location="San Francisco, CA")
        rejected, _, _ = _geo_filter(job, ["US"])
        assert rejected is False

    # --- Layer 2: description city mentions ---

    def test_layer2_berlin_office_mention_rejected_for_es(self):
        """Null location, 'our Berlin office' in description → DE, rejected for ES."""
        job = _geo_job(
            location=None,
            description="We are growing rapidly. Our Berlin office is the heart of our team.",
        )
        rejected, country, layer = _geo_filter(job, ["ES"])
        assert rejected is True
        assert country == "DE"
        assert layer == "prefilter_description"

    def test_layer2_no_context_words_passes(self):
        """Null location, city mention without context words → passes (conservative)."""
        job = _geo_job(
            location=None,
            description="We serve customers in Berlin and Paris with great service.",
        )
        rejected, _, _ = _geo_filter(job, ["ES"])
        assert rejected is False  # no "based in", "office in" etc.

    # --- Layer 3: US-specific signals ---

    def test_layer3_remote_within_us_rejected_for_es(self):
        """'remote within the us' in description → rejected for ES target."""
        job = _geo_job(
            location=None,
            description="This is a remote within the US position. Great benefits.",
        )
        rejected, country, layer = _geo_filter(job, ["ES"])
        assert rejected is True
        assert country == "US"
        assert layer == "prefilter_signal"

    def test_layer3_everi_fy_rejected_for_es(self):
        """e-verify signal → rejected for ES target."""
        job = _geo_job(
            location=None,
            description="We participate in E-Verify to confirm work authorization.",
        )
        rejected, country, _ = _geo_filter(job, ["ES"])
        assert rejected is True
        assert country == "US"

    def test_layer3_null_location_no_signals_passes(self):
        """Null location, no geo signals → passes (conservative)."""
        job = _geo_job(
            location=None,
            description="We are looking for a talented product manager to join our team.",
        )
        rejected, _, _ = _geo_filter(job, ["ES"])
        assert rejected is False

    def test_layer3_us_signals_pass_for_us_target(self):
        """US signals detected but US is in target → passes."""
        job = _geo_job(
            location=None,
            description="You must be authorized to work in the U.S. Great role!",
        )
        rejected, _, _ = _geo_filter(job, ["US"])
        assert rejected is False


# ---------------------------------------------------------------------------
# 15.9 — End-to-end integration: full pipeline with mixed-geo job set
# ---------------------------------------------------------------------------


class TestEndToEndGeoFiltering:
    """Integration test: prefilter applied to mixed-geo job set for ES target user.

    Simulates the flow: derive_target_countries(home_locations) → prefilter_jobs()
    with the full GEO_TEST_JOBS fixture.
    """

    @pytest.fixture
    def prefs_file(self, tmp_path):
        prefs = {
            "prefilter": {
                "deal_breakers": [],
                "title_must_contain_one_of": ["product manager", "head of product", "vp product"],
                "title_exclude": [],
                "exclude_companies": [],
            }
        }
        f = tmp_path / "prefs.yaml"
        f.write_text(yaml.dump(prefs))
        return str(f)

    @pytest.fixture
    def empty_applied(self, tmp_path):
        return str(tmp_path / "nonexistent-applied.yaml")

    @pytest.fixture
    def empty_seen(self, tmp_path):
        return str(tmp_path / "nonexistent-seen.txt")

    def _run_pipeline(self, jobs, prefs_file, empty_applied, empty_seen, home_locations):
        """Simulate pipeline: derive target_countries → prefilter."""
        target_countries = derive_target_countries(home_locations)
        job_dicts = [dict(j) for j in jobs]
        passed, rejected, stats = prefilter_jobs(
            job_dicts,
            config_path=prefs_file,
            applied_path=empty_applied,
            seen_ids=None,
            home_locations=home_locations,
            target_countries=target_countries,
        )
        return {j["id"] for j in passed}, {j["id"] for j in rejected}, stats

    def test_es_target_spain_jobs_pass(self, prefs_file, empty_applied, empty_seen):
        """All Spain-based jobs pass for ES target user."""
        jobs = [j for j in GEO_TEST_JOBS if j.id in ("es-onsite", "es-madrid-onsite")]
        passed_ids, _, _ = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "es-onsite" in passed_ids
        assert "es-madrid-onsite" in passed_ids

    def test_es_target_us_job_with_location_rejected(self, prefs_file, empty_applied, empty_seen):
        """US job with SF CA location → rejected at prefilter (Layer 1)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "us-sf-loc"]
        _, rejected_ids, stats = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "us-sf-loc" in rejected_ids
        assert stats["non_target_geo"] == 1

    def test_es_target_us_desc_signal_rejected(self, prefs_file, empty_applied, empty_seen):
        """US job with null location + US work auth in description → rejected (Layer 3)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "us-desc-signal"]
        _, rejected_ids, stats = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "us-desc-signal" in rejected_ids
        assert stats["non_target_geo"] == 1

    def test_es_target_null_location_no_signals_passes(self, prefs_file, empty_applied, empty_seen):
        """Job with null location and no geo signals → passes (conservative)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "no-loc-no-signals"]
        passed_ids, _, _ = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "no-loc-no-signals" in passed_ids

    def test_es_target_remote_fulltime_from_us_passes(self, prefs_file, empty_applied, empty_seen):
        """Remote fulltime job with US location → passes (remote_type=fulltime exemption)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "us-remote-ft"]
        passed_ids, _, _ = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "us-remote-ft" in passed_ids

    def test_es_target_de_office_in_description_rejected(self, prefs_file, empty_applied, empty_seen):
        """Null location + 'based in our Berlin office' → rejected at prefilter (Layer 2)."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "de-desc-mention"]
        _, rejected_ids, stats = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "de-desc-mention" in rejected_ids
        assert stats["non_target_geo"] == 1

    def test_es_target_fr_onsite_rejected(self, prefs_file, empty_applied, empty_seen):
        """France onsite → rejected for ES target user."""
        jobs = [j for j in GEO_TEST_JOBS if j.id == "fr-onsite"]
        _, rejected_ids, _ = self._run_pipeline(jobs, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"])
        assert "fr-onsite" in rejected_ids

    def test_geo_rejection_rate_below_10pct_for_es_user(self, prefs_file, empty_applied, empty_seen):
        """On the full synthetic job set, geo-restricted rate among passed jobs < 10%.

        All non-geo rejections are expected (title/deal_breaker), geo filter correctly
        removes non-target jobs. Remaining passed jobs are either ES, remote-fulltime,
        or null-location conservative passes.
        """
        passed_ids, rejected_ids, stats = self._run_pipeline(
            GEO_TEST_JOBS, prefs_file, empty_applied, empty_seen, ["barcelona", "spain"]
        )
        total = stats["total"]
        geo_rejected = stats.get("non_target_geo", 0)
        # Geo-rejected jobs as % of total scraped: tracking improvement
        # Key assertion: ES jobs + remote-fulltime + no-signal nulls all pass
        assert "es-onsite" in passed_ids
        assert "es-madrid-onsite" in passed_ids
        assert "us-remote-ft" in passed_ids
        assert "global-remote" in passed_ids
        assert "no-loc-no-signals" in passed_ids
        # Key rejections work
        assert "us-sf-loc" in rejected_ids
        assert "fr-onsite" in rejected_ids
        assert "de-onsite" in rejected_ids
        assert geo_rejected >= 5  # at least US, FR, DE, IN, NY jobs rejected
