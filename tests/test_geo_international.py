"""
Tests for api/geo.py resolve_location_country — international location formats.

Mirrors agent/tests/test_geo_international.py (dual copy, sync rule).
"""

import pytest
from api.geo import resolve_location_country


@pytest.mark.parametrize(
    "location,expected",
    [
        ("Barcelona, CT, ES", "ES"),
        ("Plegamans, CT, ES", "ES"),
        ("Paris, FR", "FR"),
        ("Sant Cugat del Vallès, Catalonia, Spain", "ES"),
        ("Courbevoie, FR", "FR"),
        # US regression
        ("New York, New York, USA", "US"),
        ("San Francisco, CA", "US"),
        ("New York, NY", "US"),
        # Graceful
        ("Dublin", "IE"),
    ],
)
def test_resolve_location_country_international(location, expected):
    assert resolve_location_country(location) == expected


def test_semicolon_list_no_crash():
    result = resolve_location_country("Alberta; British Columbia; Calgary; Edmonton")
    assert result is None or isinstance(result, str)
