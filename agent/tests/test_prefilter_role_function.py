"""Tests for 17.5.3 — role_function soft gate in prefilter_jobs.

Soft gate rules:
  - Both profile AND job have role_function → mismatch → filtered
  - Match → kept
  - Job has no role_function → kept
  - Profile has no role_function → kept (gate disabled)
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prefilter import prefilter_jobs


@pytest.fixture()
def prefs_file(tmp_path):
    prefs = {
        "prefilter": {
            "deal_breakers": [],
            "title_must_contain_one_of": ["product manager", "head of product", "product owner"],
            "title_exclude": [],
            "exclude_companies": [],
            "location": {"accept_onsite_cities": []},
        }
    }
    f = tmp_path / "prefs.yaml"
    f.write_text(yaml.dump(prefs))
    return str(f)


@pytest.fixture()
def empty_applied(tmp_path):
    return str(tmp_path / "nonexistent-applied.yaml")


def _make_job(role_function=None, **overrides):
    base = {
        "id": "j1",
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "description": "",
    }
    if role_function is not None:
        base["role_function"] = role_function
    base.update(overrides)
    return base


class TestRoleFunctionPrefilter:
    def test_mismatch_is_filtered(self, prefs_file, empty_applied):
        """PM profile + Engineering job → filtered out."""
        jobs = [_make_job(role_function="engineering")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            profile_role_function="product",
        )
        assert len(passed) == 0
        assert len(rejected) == 1
        assert "role_function" in rejected[0]["reject_reason"]

    def test_match_is_kept(self, prefs_file, empty_applied):
        """PM profile + PM job → kept."""
        jobs = [_make_job(role_function="product")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            profile_role_function="product",
        )
        assert len(passed) == 1

    def test_no_job_role_function_kept(self, prefs_file, empty_applied):
        """Job without role_function → gate disabled → kept."""
        jobs = [_make_job()]  # no role_function
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            profile_role_function="product",
        )
        assert len(passed) == 1

    def test_no_profile_role_function_kept(self, prefs_file, empty_applied):
        """Profile without role_function → gate disabled → kept."""
        jobs = [_make_job(role_function="engineering")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            # profile_role_function not passed (None)
        )
        assert len(passed) == 1

    def test_case_insensitive_match(self, prefs_file, empty_applied):
        """role_function match is case-insensitive."""
        jobs = [_make_job(role_function="Product")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            profile_role_function="product",
        )
        assert len(passed) == 1

    def test_mismatch_counted_in_stats(self, prefs_file, empty_applied):
        """Mismatch increments role_function_mismatch in stats."""
        jobs = [_make_job(role_function="marketing")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            profile_role_function="product",
        )
        assert stats.get("role_function_mismatch", 0) == 1
