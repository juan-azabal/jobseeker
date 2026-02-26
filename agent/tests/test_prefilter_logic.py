"""Tests for prefilter.py: US-only detection, title relevance, applied loading, full prefilter flow."""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prefilter import _is_relevant_title, _is_us_only, load_applied, load_seen_ids, prefilter_jobs


# ---------------------------------------------------------------------------
# _is_us_only
# ---------------------------------------------------------------------------


class TestIsUsOnly:
    def test_us_city_in_location(self):
        assert _is_us_only({"location": "San Francisco, CA", "description": ""}) is True

    def test_us_state_abbreviation(self):
        assert _is_us_only({"location": "Remote, NY", "description": ""}) is True

    def test_european_city_not_us(self):
        assert _is_us_only({"location": "Barcelona, Spain", "description": ""}) is False

    def test_remote_europe_not_us(self):
        assert _is_us_only({"location": "Remote, Europe", "description": ""}) is False

    def test_remote_only_not_us(self):
        assert _is_us_only({"location": "Remote", "description": ""}) is False

    def test_us_work_auth_in_description(self):
        assert (
            _is_us_only(
                {
                    "location": "Remote",
                    "description": "Must be authorized to work in the United States",
                }
            )
            is True
        )

    def test_unable_to_sponsor_with_us_context(self):
        assert (
            _is_us_only(
                {
                    "location": "Remote",
                    "description": "We are unable to sponsor visa sponsorship at this time",
                }
            )
            is True
        )

    def test_unable_to_sponsor_without_us_context(self):
        # "unable to sponsor" alone without US signals → not US-only
        assert (
            _is_us_only(
                {
                    "location": "Remote, Europe",
                    "description": "We are unable to sponsor at this time",
                }
            )
            is False
        )

    def test_nationwide(self):
        assert _is_us_only({"location": "Nationwide", "description": ""}) is True

    def test_empty_location_not_us(self):
        assert _is_us_only({"location": "", "description": ""}) is False

    def test_e_verify_in_description(self):
        assert (
            _is_us_only(
                {
                    "location": "Remote",
                    "description": "All candidates must pass E-Verify upon hire",
                }
            )
            is True
        )


# ---------------------------------------------------------------------------
# _is_relevant_title
# ---------------------------------------------------------------------------


class TestIsRelevantTitle:
    def test_pm_keyword_passes(self):
        ok, reason = _is_relevant_title("senior product manager", ["product manager"], [])
        assert ok is True
        assert reason is None

    def test_no_pm_keyword_fails(self):
        ok, reason = _is_relevant_title("data engineer", ["product manager"], [])
        assert ok is False
        assert "no PM keyword" in reason

    def test_excluded_term_fails(self):
        ok, reason = _is_relevant_title("project manager", ["manager"], ["project manager"])
        assert ok is False
        assert "excluded" in reason

    def test_product_owner_passes(self):
        ok, _ = _is_relevant_title("product owner - data", ["product manager", "product owner"], [])
        assert ok is True


# ---------------------------------------------------------------------------
# load_applied
# ---------------------------------------------------------------------------


class TestLoadApplied:
    def test_missing_file_returns_defaults(self):
        result = load_applied("/nonexistent/file.yaml")
        assert result["applied_companies"] == []
        assert result["applied_ids"] == set()
        assert result["skip_ids"] == set()
        assert result["skip_titles"] == []

    def test_loads_dict_and_string_companies(self, tmp_path):
        data = {
            "applied": {
                "companies": [
                    {"name": "Acme", "date": "2026-02-01"},
                    "LegacyCo",
                ],
                "ids": [{"id": "job001", "note": "test"}],
            },
            "not_interested": {
                "ids": [{"id": "skip001"}],
                "titles": ["sales manager"],
            },
        }
        f = tmp_path / "applied.yaml"
        f.write_text(yaml.dump(data))
        result = load_applied(str(f))
        assert "acme" in result["applied_companies"]
        assert "legacyco" in result["applied_companies"]
        assert "job001" in result["applied_ids"]
        assert "skip001" in result["skip_ids"]
        assert "sales manager" in result["skip_titles"]

    def test_expired_companies_excluded(self, tmp_path):
        data = {
            "applied": {
                "companies": [
                    {"name": "OldCo", "date": "2024-01-01"},  # >90 days
                ],
            },
        }
        f = tmp_path / "applied.yaml"
        f.write_text(yaml.dump(data))
        result = load_applied(str(f))
        assert "oldco" not in result["applied_companies"]

    def test_empty_yaml(self, tmp_path):
        f = tmp_path / "applied.yaml"
        f.write_text("")
        result = load_applied(str(f))
        assert result["applied_companies"] == []


# ---------------------------------------------------------------------------
# load_seen_ids
# ---------------------------------------------------------------------------


class TestLoadSeenIds:
    def test_missing_file_returns_empty(self):
        assert load_seen_ids("/nonexistent/seen.txt") == set()

    def test_loads_ids(self, tmp_path):
        f = tmp_path / "seen.txt"
        f.write_text("id1\nid2\n\nid3\n")
        ids = load_seen_ids(str(f))
        assert ids == {"id1", "id2", "id3"}

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "seen.txt"
        f.write_text("  id1  \nid2\n")
        ids = load_seen_ids(str(f))
        assert ids == {"id1", "id2"}


# ---------------------------------------------------------------------------
# prefilter_jobs (integration)
# ---------------------------------------------------------------------------


class TestPrefilterJobs:
    @pytest.fixture
    def prefs_file(self, tmp_path):
        prefs = {
            "prefilter": {
                "deal_breakers": ["intern"],
                "title_must_contain_one_of": ["product manager", "product owner"],
                "title_exclude": ["project manager"],
                "exclude_companies": ["badco"],
                "location": {"accept_onsite_cities": ["Barcelona"]},
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

    def _make_job(self, **overrides):
        base = {
            "id": "j1",
            "title": "Senior Product Manager",
            "company": "GoodCo",
            "location": "Remote",
            "description": "",
        }
        base.update(overrides)
        return base

    def test_passes_good_pm_job(self, prefs_file, empty_applied, empty_seen):
        jobs = [self._make_job()]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert len(passed) == 1

    def test_rejects_non_pm_title(self, prefs_file, empty_applied, empty_seen):
        jobs = [self._make_job(title="Data Engineer")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert len(passed) == 0
        assert stats["no_pm_keyword"] == 1

    def test_rejects_excluded_company(self, prefs_file, empty_applied, empty_seen):
        jobs = [self._make_job(company="BadCo")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert len(passed) == 0
        assert stats["excluded_company"] == 1

    def test_rejects_deal_breaker(self, prefs_file, empty_applied, empty_seen):
        jobs = [self._make_job(title="Intern Product Manager")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert len(passed) == 0
        assert stats["deal_breaker"] == 1

    def test_rejects_us_only(self, prefs_file, empty_applied, empty_seen):
        jobs = [self._make_job(location="San Francisco, CA")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert len(passed) == 0
        assert stats["us_only"] == 1

    def test_seen_ids_filtered(self, prefs_file, empty_applied, tmp_path):
        seen_file = tmp_path / "seen.txt"
        seen_file.write_text("j1\n")
        jobs = [self._make_job()]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, str(seen_file))
        assert len(passed) == 0
        assert stats["already_seen"] == 1

    def test_home_location_rescues_us_flagged(self, prefs_file, empty_applied, empty_seen):
        # Job in New York (US-flagged), but if user lives there it should pass
        jobs = [self._make_job(location="New York, NY")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            empty_seen,
            home_locations=["new york"],
        )
        assert len(passed) == 1

    def test_stats_totals(self, prefs_file, empty_applied, empty_seen):
        jobs = [
            self._make_job(id="j1"),
            self._make_job(id="j2", title="Data Engineer"),
        ]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, empty_seen)
        assert stats["total"] == 2
        assert stats["passed"] == 1
