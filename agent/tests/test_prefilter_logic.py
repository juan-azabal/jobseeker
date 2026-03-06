"""Tests for prefilter.py: geo filtering, title relevance, applied loading, full prefilter flow."""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prefilter import _is_non_target_geo, _is_relevant_title, load_applied, load_seen_ids, prefilter_jobs


# ---------------------------------------------------------------------------
# _is_non_target_geo
# ---------------------------------------------------------------------------


def _geo_job(**kwargs) -> dict:
    base = {
        "id": "test",
        "title": "Product Manager",
        "company": "Corp",
        "source": "linkedin",
        "location": None,
        "description": "",
        "remote_type": "no",
    }
    base.update(kwargs)
    return base


class TestIsNonTargetGeo:
    def test_us_city_rejected_for_es(self):
        rejected, country, _ = _is_non_target_geo(_geo_job(location="San Francisco, CA"), ["ES"])
        assert rejected is True
        assert country == "US"

    def test_us_state_abbreviation_rejected_for_es(self):
        # "Remote, NY" — NY token resolves to US
        rejected, country, _ = _is_non_target_geo(_geo_job(location="Remote, NY"), ["ES"])
        assert rejected is True
        assert country == "US"

    def test_es_city_passes_for_es(self):
        rejected, _, _ = _is_non_target_geo(_geo_job(location="Barcelona, Spain"), ["ES"])
        assert rejected is False

    def test_unresolvable_location_passes_conservative(self):
        # "Remote, Europe" — no country resolved → conservative pass
        rejected, _, _ = _is_non_target_geo(_geo_job(location="Remote, Europe"), ["ES"])
        assert rejected is False

    def test_remote_only_passes(self):
        # "Remote" → None (sentinel) → pass
        rejected, _, _ = _is_non_target_geo(_geo_job(location="Remote"), ["ES"])
        assert rejected is False

    def test_us_work_auth_in_description_rejected_for_es(self):
        rejected, country, _ = _is_non_target_geo(
            _geo_job(
                location=None,
                description="Must be authorized to work in the United States",
            ),
            ["ES"],
        )
        assert rejected is True
        assert country == "US"

    def test_unable_to_sponsor_with_us_context_rejected_for_es(self):
        rejected, country, _ = _is_non_target_geo(
            _geo_job(
                location=None,
                description="We are unable to sponsor visa sponsorship at this time",
            ),
            ["ES"],
        )
        assert rejected is True
        assert country == "US"

    def test_unable_to_sponsor_without_us_context_passes(self):
        # "unable to sponsor" alone without US signals → conservative pass
        rejected, _, _ = _is_non_target_geo(
            _geo_job(
                location=None,
                description="We are unable to sponsor at this time",
            ),
            ["ES"],
        )
        assert rejected is False

    def test_unresolvable_nationwide_passes_conservative(self):
        # "Nationwide" cannot be resolved to a country → conservative pass
        rejected, _, _ = _is_non_target_geo(_geo_job(location="Nationwide"), ["ES"])
        assert rejected is False

    def test_empty_location_passes(self):
        rejected, _, _ = _is_non_target_geo(_geo_job(location=""), ["ES"])
        assert rejected is False

    def test_e_verify_in_description_rejected_for_es(self):
        rejected, country, _ = _is_non_target_geo(
            _geo_job(
                location=None,
                description="All candidates must pass E-Verify upon hire",
            ),
            ["ES"],
        )
        assert rejected is True
        assert country == "US"


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

    def test_passes_good_pm_job(self, prefs_file, empty_applied):
        jobs = [self._make_job()]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied)
        assert len(passed) == 1

    def test_rejects_non_pm_title(self, prefs_file, empty_applied):
        jobs = [self._make_job(title="Data Engineer")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied)
        assert len(passed) == 0
        assert stats["no_pm_keyword"] == 1

    def test_rejects_excluded_company(self, prefs_file, empty_applied):
        jobs = [self._make_job(company="BadCo")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied)
        assert len(passed) == 0
        assert stats["excluded_company"] == 1

    def test_rejects_deal_breaker(self, prefs_file, empty_applied):
        jobs = [self._make_job(title="Intern Product Manager")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied)
        assert len(passed) == 0
        assert stats["deal_breaker"] == 1

    def test_rejects_non_target_geo(self, prefs_file, empty_applied):
        jobs = [self._make_job(location="San Francisco, CA")]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, target_countries=["ES"])
        assert len(passed) == 0
        assert stats["non_target_geo"] == 1

    def test_seen_ids_filtered(self, prefs_file, empty_applied):
        jobs = [self._make_job()]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied, seen_ids={"j1"})
        assert len(passed) == 0
        assert stats["already_seen"] == 1

    def test_us_target_accepts_ny_job(self, prefs_file, empty_applied):
        # When target_countries includes US, a New York job passes geo filter
        jobs = [self._make_job(location="New York, NY")]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            prefs_file,
            empty_applied,
            target_countries=["US"],
        )
        assert len(passed) == 1

    def test_stats_totals(self, prefs_file, empty_applied):
        jobs = [
            self._make_job(id="j1"),
            self._make_job(id="j2", title="Data Engineer"),
        ]
        passed, rejected, stats = prefilter_jobs(jobs, prefs_file, empty_applied)
        assert stats["total"] == 2
        assert stats["passed"] == 1
