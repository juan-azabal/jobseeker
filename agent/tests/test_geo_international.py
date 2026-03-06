"""
Tests for geo parser handling of international location formats.

Step 1.2: These tests MUST FAIL before the fix in step 1.3.
Covers formats seen in Noura's pipeline logs:
  - "Barcelona, CT, ES"  → country=ES (not US)
  - "Plegamans, CT, ES"  → country=ES
  - "Paris, FR"          → country=FR
  - "Sant Cugat del Vallès, Catalonia, Spain" → country=ES
  - "Courbevoie, FR"     → country=FR
  - "New York, New York, USA" → country=US (regression: must not break)
  - "Dublin" (no country) → country=IE (geonamescache resolves capital)
  - "Alberta; British Columbia; Calgary; Edmonton" → no crash, returns None or CA
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from geo import resolve_location_country


# ---------------------------------------------------------------------------
# Failing formats (bug: CT misclassified as Connecticut)
# ---------------------------------------------------------------------------


def test_barcelona_ct_es_returns_es():
    """'Barcelona, CT, ES' must resolve to ES (Catalonia region code, not Connecticut)."""
    assert resolve_location_country("Barcelona, CT, ES") == "ES"


def test_plegamans_ct_es_returns_es():
    """'Plegamans, CT, ES' must resolve to ES."""
    assert resolve_location_country("Plegamans, CT, ES") == "ES"


# ---------------------------------------------------------------------------
# Formats that should already work (document expected behaviour)
# ---------------------------------------------------------------------------


def test_paris_fr_returns_fr():
    """'Paris, FR' must resolve to FR."""
    assert resolve_location_country("Paris, FR") == "FR"


def test_sant_cugat_catalonia_spain_returns_es():
    """'Sant Cugat del Vallès, Catalonia, Spain' must resolve to ES."""
    assert resolve_location_country("Sant Cugat del Vallès, Catalonia, Spain") == "ES"


def test_courbevoie_fr_returns_fr():
    """'Courbevoie, FR' must resolve to FR."""
    assert resolve_location_country("Courbevoie, FR") == "FR"


# ---------------------------------------------------------------------------
# Regression: US locations must still resolve correctly
# ---------------------------------------------------------------------------


def test_new_york_new_york_usa_returns_us():
    """'New York, New York, USA' must remain US."""
    assert resolve_location_country("New York, New York, USA") == "US"


def test_san_francisco_ca_returns_us():
    """'San Francisco, CA' must remain US (CA = California, not Canada)."""
    assert resolve_location_country("San Francisco, CA") == "US"


def test_new_york_ny_returns_us():
    """'New York, NY' must remain US."""
    assert resolve_location_country("New York, NY") == "US"


# ---------------------------------------------------------------------------
# Graceful handling
# ---------------------------------------------------------------------------


def test_dublin_resolves_to_ie():
    """'Dublin' (no country) should resolve to IE via geonamescache."""
    result = resolve_location_country("Dublin")
    assert result == "IE"


def test_semicolon_list_no_crash():
    """'Alberta; British Columbia; Calgary; Edmonton' must not crash."""
    result = resolve_location_country("Alberta; British Columbia; Calgary; Edmonton")
    # Returns None or a country code — just must not raise
    assert result is None or isinstance(result, str)


def test_semicolon_list_returns_canada():
    """Semicolon-separated list starting with Canadian province returns CA."""
    result = resolve_location_country("Alberta; British Columbia")
    # Alberta → Canada → "CA"
    # Acceptable if it returns CA or None (conservative)
    assert result in ("CA", None)
