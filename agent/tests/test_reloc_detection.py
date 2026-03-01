"""
Tests for country-specific remote relocation detection.

Verifies that:
- "Remote from Portugal", "Remote from Denmark", etc. are reloc for a Spain user
- "EU only" is NOT reloc for Spain but IS reloc for US
- Region matching is auto-derived via country-converter (no manual config)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_config import load_profile
from geo import derive_home_regions, UNIVERSAL_TERMS
from scoring import (
    load_heuristic_config as _load_heuristic_config,
    heuristic_score as _heuristic_score,
    _HOME_LOCATIONS,
    _HOME_REGIONS,
)
from reloc import is_reloc as _is_reloc, is_remote_requiring_reloc as _is_remote_requiring_reloc


def _setup_juan():
    profile = load_profile("juan")
    _load_heuristic_config(profile)
    return profile


def _make_remote_job(title, location="", restriction=""):
    return {
        "title": title,
        "location": location,
        "parsed": {
            "seniority": "senior",
            "location_type": "remote",
            "domain": "data",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "",
            "red_flags": [],
            "remote_restriction": restriction,
        },
    }


# ---------------------------------------------------------------------------
# Auto-derived regions via country-converter
# ---------------------------------------------------------------------------


class TestDeriveHomeRegions:
    """Region auto-derivation from country-converter."""

    def test_spain_includes_eu(self):
        regions = derive_home_regions(["spain"])
        assert "eu" in regions

    def test_spain_includes_europe(self):
        regions = derive_home_regions(["spain"])
        assert "europe" in regions

    def test_spain_includes_emea(self):
        regions = derive_home_regions(["spain"])
        assert "emea" in regions

    def test_spain_includes_eea(self):
        regions = derive_home_regions(["spain"])
        assert "eea" in regions

    def test_us_does_not_include_eu(self):
        regions = derive_home_regions(["us"])
        assert "eu" not in regions

    def test_us_does_not_include_europe(self):
        regions = derive_home_regions(["us"])
        assert "europe" not in regions

    def test_us_includes_americas(self):
        regions = derive_home_regions(["us"])
        assert "americas" in regions

    def test_uk_not_in_eu(self):
        """Post-Brexit: UK is in Europe but NOT in EU/EEA."""
        regions = derive_home_regions(["uk"])
        assert "eu" not in regions
        assert "eea" not in regions
        assert "europe" in regions

    def test_cities_silently_skipped(self):
        regions = derive_home_regions(["barcelona", "madrid"])
        assert regions == []  # no country-level matches

    def test_mixed_cities_and_countries(self):
        regions = derive_home_regions(["barcelona", "spain"])
        assert "eu" in regions  # spain resolves, barcelona skipped


# ---------------------------------------------------------------------------
# Country-pinned remote: should be reloc for Spain-based user
# ---------------------------------------------------------------------------


class TestCountryPinnedRemoteIsReloc:
    """Jobs pinned to a specific non-Spain country should require relocation."""

    def setup_method(self):
        _setup_juan()

    def test_remote_from_portugal(self):
        job = _make_remote_job(
            "Senior PM (Remote from Portugal)",
            restriction="CET timezone hours",
        )
        assert _is_reloc(job) is True

    def test_remote_from_denmark(self):
        job = _make_remote_job(
            "Senior PM (Remote from Denmark)",
            restriction="CET timezone hours",
        )
        assert _is_reloc(job) is True

    def test_remote_from_netherlands(self):
        job = _make_remote_job(
            "Senior PM (Remote from Netherlands)",
            restriction="CET timezone hours",
        )
        assert _is_reloc(job) is True

    def test_remote_from_uk(self):
        job = _make_remote_job(
            "Senior PM (Remote from United Kingdom)",
        )
        assert _is_reloc(job) is True

    def test_netherlands_only_restriction(self):
        job = _make_remote_job(
            "Senior Technical PM",
            location="Amsterdam (remote)",
            restriction="Netherlands only",
        )
        assert _is_reloc(job) is True

    def test_uk_only_restriction(self):
        job = _make_remote_job(
            "Senior Technical PM",
            location="United Kingdom (remote)",
            restriction="United Kingdom only",
        )
        assert _is_reloc(job) is True

    def test_ireland_restriction(self):
        job = _make_remote_job(
            "Product Manager",
            restriction="Ireland region",
        )
        assert _is_reloc(job) is True

    def test_germany_restriction(self):
        job = _make_remote_job(
            "AI Product Manager",
            restriction="Germany",
        )
        assert _is_reloc(job) is True

    def test_canada_restriction(self):
        job = _make_remote_job(
            "Technical PM",
            restriction="Canada",
        )
        assert _is_reloc(job) is True

    def test_us_only_restriction(self):
        job = _make_remote_job(
            "Principal PM",
            restriction="United States only",
        )
        assert _is_reloc(job) is True

    def test_multi_country_not_home(self):
        job = _make_remote_job(
            "PM Payments",
            restriction="Germany, Netherlands and the United Kingdom",
        )
        assert _is_reloc(job) is True


# ---------------------------------------------------------------------------
# Hybrid/onsite in non-Spain should also be reloc (pre-existing behavior)
# ---------------------------------------------------------------------------


class TestHybridOnsiteNonSpainIsReloc:
    """Hybrid/onsite outside Spain should still be reloc."""

    def setup_method(self):
        _setup_juan()

    def test_hybrid_ukraine(self):
        job = {
            "title": "Senior PM",
            "location": "Kyiv, Ukraine",
            "parsed": {
                "location_type": "hybrid",
                "domain": "data",
                "seniority": "senior",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        assert _is_reloc(job) is True

    def test_hybrid_paris(self):
        job = {
            "title": "Senior PM",
            "location": "Paris, France",
            "parsed": {
                "location_type": "hybrid",
                "domain": "data",
                "seniority": "senior",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        assert _is_reloc(job) is True


# ---------------------------------------------------------------------------
# Non-reloc: jobs accessible from Spain
# ---------------------------------------------------------------------------


class TestAccessibleFromSpainIsNotReloc:
    """Remote jobs accessible from Spain should NOT be reloc."""

    def setup_method(self):
        _setup_juan()

    def test_truly_global_remote(self):
        job = _make_remote_job("Senior PM - Data Platform", restriction="")
        assert _is_reloc(job) is False

    def test_europe_only_restriction(self):
        job = _make_remote_job("Senior PM", restriction="Europe only")
        assert _is_reloc(job) is False

    def test_eu_only_restriction(self):
        job = _make_remote_job("PM Ad Management", restriction="EU only")
        assert _is_reloc(job) is False

    def test_emea_restriction(self):
        job = _make_remote_job("AI PM", restriction="EMEA")
        assert _is_reloc(job) is False

    def test_worldwide_restriction(self):
        job = _make_remote_job("Senior PM Growth", restriction="worldwide")
        assert _is_reloc(job) is False

    def test_spain_restriction(self):
        job = _make_remote_job(
            "Senior PM Payments (Remote from Spain)",
            restriction="Spain",
        )
        assert _is_reloc(job) is False

    def test_remote_from_spain_title(self):
        job = _make_remote_job("Senior PM (Remote from Spain)")
        assert _is_reloc(job) is False

    def test_hybrid_barcelona(self):
        job = {
            "title": "Senior PM",
            "location": "Barcelona, Spain (hybrid)",
            "parsed": {
                "location_type": "hybrid",
                "domain": "data",
                "seniority": "senior",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        assert _is_reloc(job) is False


# ---------------------------------------------------------------------------
# Cross-user: US user should see EU-only as reloc, global as not reloc
# ---------------------------------------------------------------------------


class TestUSUserReloc:
    """A US-based user should see EU-restricted jobs as relocation."""

    def setup_method(self):
        # Load the US-based test profile
        self.profile = load_profile("de-profile", profiles_dir="tests/fixtures")
        _load_heuristic_config(self.profile)

    def test_eu_only_is_reloc_for_us_user(self):
        job = _make_remote_job("PM Ad Management", restriction="EU only")
        assert _is_reloc(job) is True

    def test_europe_only_is_reloc_for_us_user(self):
        job = _make_remote_job("Senior PM", restriction="Europe only")
        assert _is_reloc(job) is True

    def test_emea_is_reloc_for_us_user(self):
        job = _make_remote_job("AI PM", restriction="EMEA")
        assert _is_reloc(job) is True

    def test_us_only_is_not_reloc_for_us_user(self):
        job = _make_remote_job("Principal PM", restriction="United States only")
        assert _is_reloc(job) is False

    def test_global_remote_is_not_reloc_for_us_user(self):
        job = _make_remote_job("Senior PM - Data", restriction="")
        assert _is_reloc(job) is False

    def test_worldwide_is_not_reloc_for_us_user(self):
        job = _make_remote_job("PM Growth", restriction="worldwide")
        assert _is_reloc(job) is False

    def test_americas_is_not_reloc_for_us_user(self):
        job = _make_remote_job("PM Latam", restriction="Americas")
        assert _is_reloc(job) is False


# ---------------------------------------------------------------------------
# Heuristic score: country-pinned remote should get 0 location bonus
# ---------------------------------------------------------------------------


class TestHeuristicScoreRelocPenalty:
    """Country-pinned remote jobs get reduced location score + eligibility penalty."""

    def setup_method(self):
        _setup_juan()

    def test_global_remote_gets_bonus(self):
        job = _make_remote_job("Senior PM - Data Platform", restriction="")
        score = _heuristic_score(job)
        # domain data=15 + seniority senior=8 + remote=10 + country_weights(remote=10) = 43
        assert score == 43

    def test_timezone_only_restriction_not_pinned(self):
        """Timezone-only restriction (CET) is not a country barrier — gets full remote bonus."""
        job = _make_remote_job(
            "Senior PM (Remote from Netherlands)",
            restriction="CET timezone hours",
        )
        score = _heuristic_score(job)
        # CET is pure timezone → NOT geo-restricted → +10 location, +10 country_weights(remote) = 43
        assert score == 43

    def test_country_pinned_remote_gets_reduced_bonus_and_penalty(self):
        """Country restriction (US only) → location +2 + penalty -20 for ineligible user."""
        job = _make_remote_job(
            "Senior PM - Data Platform",
            restriction="Must be based in the United States",
        )
        score = _heuristic_score(job)
        # domain(15) + seniority(8) + location(2, ineligible geo-restricted) + country_weights(0) + penalty(-20) = 5
        assert score == 5

    def test_score_difference_is_38_for_country_pinned(self):
        """Global remote vs US-pinned: diff = 38 (location +8, penalty +20, country_weights +10)."""
        global_job = _make_remote_job("Senior PM - Data", restriction="")
        us_only_job = _make_remote_job(
            "Senior PM - Data",
            restriction="Must be based in the United States",
        )
        diff = _heuristic_score(global_job) - _heuristic_score(us_only_job)
        # 43 - 5 = 38
        assert diff == 38
