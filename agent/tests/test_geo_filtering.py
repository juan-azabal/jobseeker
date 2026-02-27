"""
Tests for Phase 15 geo filtering: resolver, WTTJ filter, ATS filter, prefilter.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from geo import resolve_location_country, derive_target_countries


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
