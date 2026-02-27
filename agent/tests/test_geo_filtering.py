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

    def _run(self, jobs, prefs_file, empty_applied, empty_seen):
        job_dicts = [dict(j) for j in jobs]
        passed, rejected, stats = prefilter_jobs(
            job_dicts, prefs_file, empty_applied, empty_seen,
            home_locations=["barcelona", "spain"],
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

    def test_baseline_stats_printed(self, geo_prefs_file, empty_applied, empty_seen, capsys):
        """Full baseline run prints stats."""
        job_dicts = [dict(j) for j in GEO_TEST_JOBS]
        passed, rejected, stats = prefilter_jobs(
            job_dicts, geo_prefs_file, empty_applied, empty_seen,
            home_locations=["barcelona", "spain"],
        )
        out = capsys.readouterr().out
        assert "Pre-filter" in out
        print(f"\nBaseline stats: {stats}")
        print(f"Passed: {[j['id'] for j in passed]}")
        print(f"Rejected: {[(j['id'], j.get('reject_reason', '')) for j in rejected]}")
