"""Geographic region utilities powered by country-converter, pytz, babel, geonamescache.

Auto-derives region terms (EU, EMEA, Europe, …) from a user's home_locations
so that relocation detection works for any country without manual config.
Also provides timezone abbreviation detection and location→language mapping.
And city-to-country resolution via geonamescache for accurate geo filtering.
"""

import logging
import re
from datetime import datetime

import country_converter as coco
import geonamescache
import pytz

# Suppress "X not found in regex" noise from country_converter — these are
# expected for city names (e.g. "Barcelona") and multi-part strings.
logging.getLogger("country_converter").setLevel(logging.ERROR)

_cc = coco.CountryConverter()
_gc = geonamescache.GeonamesCache()

# US state abbreviations (2-letter) as they appear at end of location strings
_US_STATE_ABBREVS = frozenset(
    [
        "al",
        "ak",
        "az",
        "ar",
        "ca",
        "co",
        "ct",
        "de",
        "fl",
        "ga",
        "hi",
        "id",
        "il",
        "in",
        "ia",
        "ks",
        "ky",
        "la",
        "me",
        "md",
        "ma",
        "mi",
        "mn",
        "ms",
        "mo",
        "mt",
        "ne",
        "nv",
        "nh",
        "nj",
        "nm",
        "ny",
        "nc",
        "nd",
        "oh",
        "ok",
        "or",
        "pa",
        "ri",
        "sc",
        "sd",
        "tn",
        "tx",
        "ut",
        "vt",
        "va",
        "wa",
        "wv",
        "wi",
        "wy",
        "dc",
    ]
)

# Terms that mean "open to everyone" regardless of where you live
UNIVERSAL_TERMS = ["worldwide", "global", "anywhere"]

# Map continent → common business region terms used in job postings
_EMEA_CONTINENTS = {"Europe", "Africa"}
_EMEA_UN_REGIONS = {"Western Asia"}  # Middle East portion of EMEA
_APAC_CONTINENTS = {"Asia", "Oceania"}


def resolve_location_country(location: str | None) -> str | None:
    """Resolve a location string to an ISO2 country code, or None if unresolvable.

    Resolution chain (first match wins):
    1. country-converter on the full string (catches "Spain", "United States", etc.)
    2. geonamescache.search_cities() on each comma-separated token — picks the city
       with the highest population to disambiguate ("Portland" → US not UK,
       "Barcelona" → ES not VE).
    3. US state abbreviation detection: ", CA" ", NY" etc. at end of string → "US"
    4. Returns None if unresolved (conservative — job passes through)

    Args:
        location: Raw location string from job posting (e.g. "San Francisco, CA",
            "Barcelona, Spain", "Remote", "").

    Returns:
        ISO2 country code (e.g. "US", "ES", "DE") or None.
    """
    if not location or not location.strip():
        return None

    loc = location.strip()
    loc_lower = loc.lower()

    # Pass-through: generic remote terms and sentinel non-locations → no country
    if loc_lower in ("remote", "worldwide", "global", "anywhere", "distributed", "nan"):
        return None

    # Layer 1: country-converter on full string
    iso2 = _cc.convert(loc, to="ISO2")
    if iso2 and iso2 != "not found":
        return str(iso2)

    # Handle semicolon-separated lists (e.g. "Alberta; British Columbia; Calgary")
    # Try each segment and return the first resolvable country.
    if ";" in loc:
        for segment in loc.split(";"):
            result = resolve_location_country(segment.strip())
            if result:
                return result
        return None

    # Layer 2: geonamescache city search on each comma-separated token
    tokens = [t.strip() for t in loc.split(",") if t.strip()]
    best_match: tuple[int, str] | None = None  # (population, country_code)
    for i, token in enumerate(tokens):
        # US state abbreviation check — but only when no later token is a country code.
        # This prevents "CT" (Catalonia region) in "Barcelona, CT, ES" from being
        # misclassified as Connecticut when "ES" (Spain) follows.
        if token.lower() in _US_STATE_ABBREVS:
            has_country_ahead = any(
                _cc.convert(tokens[j], to="ISO2") not in ("not found", None) for j in range(i + 1, len(tokens))
            )
            if not has_country_ahead:
                return "US"
            # Region code, not a US state — skip this token
            continue

        # Also try country-converter on each token (catches "France" in "Paris, France")
        iso2 = _cc.convert(token, to="ISO2")
        if iso2 and iso2 != "not found":
            return str(iso2)

        # geonamescache city search — pick highest-population match
        cities = _gc.search_cities(token, case_sensitive=False)
        if cities:
            top = max(cities, key=lambda c: c.get("population", 0))
            pop = top.get("population", 0)
            cc = top.get("countrycode", "")
            if cc and (best_match is None or pop > best_match[0]):
                best_match = (pop, cc)

    if best_match:
        return best_match[1]

    return None


def derive_target_countries(home_locations: list[str]) -> list[str]:
    """Resolve user's home_locations to unique ISO2 country codes.

    Uses the same resolution chain as resolve_location_country(). Duplicates
    are removed; order is preserved (first occurrence wins for each country).

    Args:
        home_locations: e.g. ["barcelona", "spain"] or ["new york", "us"]

    Returns:
        Deduplicated list of ISO2 codes, e.g. ["ES"] or ["US"].
    """
    seen: set[str] = set()
    result: list[str] = []
    for loc in home_locations:
        code = resolve_location_country(loc)
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def derive_home_regions(home_locations: list[str]) -> list[str]:
    """Return a list of broad region terms that include the user's home country.

    Given home_locations like ["barcelona", "madrid", "spain", "españa"],
    resolves country-level entries via country-converter and returns terms
    like ["europe", "european", "eu", "eea", "emea", "schengen"].

    Cities and unrecognised entries are silently skipped (they're still
    used for direct text-matching in home_locations).
    """
    regions: set[str] = set()

    for loc in home_locations:
        iso = _cc.convert(loc, to="ISO3")
        if iso == "not found":
            continue

        # Add the resolved country name (e.g. "us" → "united states")
        short_name = str(_cc.convert(loc, to="name_short")).lower()
        if short_name != "not found" and short_name != loc:
            regions.add(short_name)

        continent = _cc.convert(loc, to="continent")

        # Continent-level
        if continent == "Europe":
            regions.update(["europe", "european"])
        elif continent == "America":
            regions.add("americas")
            un_region = str(_cc.convert(loc, to="UNregion"))
            if "Northern America" in un_region:
                regions.update(["north america", "north american"])
            else:
                regions.update(["latin america", "latam"])
        elif continent == "Asia":
            regions.update(["asia", "asian"])
        elif continent == "Oceania":
            regions.add("oceania")
        elif continent == "Africa":
            regions.add("africa")

        # EU membership (EU27 = post-Brexit)
        if _cc.convert(loc, to="EU27") == "EU27":
            regions.update(["eu", "eu only", "eu-based"])

        # EEA
        if _cc.convert(loc, to="EEA") == "EEA":
            regions.add("eea")

        # Schengen
        if _cc.convert(loc, to="Schengen") == "Schengen":
            regions.add("schengen")

        # EMEA (Europe + Middle East + Africa)
        un_region = str(_cc.convert(loc, to="UNregion"))
        if continent in _EMEA_CONTINENTS or un_region in _EMEA_UN_REGIONS:
            regions.add("emea")

        # APAC (Asia-Pacific)
        if continent in _APAC_CONTINENTS:
            regions.update(["apac", "asia pacific", "asia-pacific"])

    return sorted(regions)


def build_region_pattern(regions: list[str]) -> re.Pattern | None:
    """Build a compiled regex that matches any region term with word boundaries.

    Uses \\b word boundaries to avoid false positives like "eu" matching
    inside "reuters" or "neural".  Returns None if regions is empty.
    """
    if not regions:
        return None
    # Sort longest-first so "eu only" matches before "eu"
    sorted_regions = sorted(regions, key=len, reverse=True)
    pattern = r"\b(?:" + "|".join(re.escape(r) for r in sorted_regions) + r")\b"
    return re.compile(pattern)


def matches_region(text: str, region_pattern: re.Pattern | None) -> bool:
    """Return True if text contains any region term (word-boundary safe)."""
    if region_pattern is None:
        return False
    return region_pattern.search(text) is not None


# ---------------------------------------------------------------------------
# Timezone abbreviations (derived from pytz at import time)
# ---------------------------------------------------------------------------


def _build_tz_abbreviations() -> frozenset[str]:
    """Extract all timezone abbreviations from pytz (winter + summer variants)."""
    abbrevs: set[str] = set()
    for tz_name in pytz.all_timezones:
        try:
            tz = pytz.timezone(tz_name)
            abbrevs.add(tz.localize(datetime(2024, 1, 15)).strftime("%Z").lower())
            abbrevs.add(tz.localize(datetime(2024, 7, 15)).strftime("%Z").lower())
        except Exception:
            pass
    # Remove numeric offsets (+03, -05) and single-char entries
    abbrevs = {a for a in abbrevs if not a.startswith(("+", "-")) and len(a) >= 2}
    # Add common non-standard terms used in job postings
    abbrevs.update(["timezone", "time zone", "hours", "time-zone", "tz"])
    return frozenset(abbrevs)


TZ_TERMS: frozenset[str] = _build_tz_abbreviations()


def is_pure_timezone(restriction: str) -> bool:
    """Return True if every comma-separated token in restriction is a timezone term.

    Used to distinguish 'CET timezone hours' (not reloc) from 'Germany' (reloc).
    """
    if not restriction:
        return False
    for tok in restriction.split(","):
        tok = tok.strip().lower()
        if not tok:
            continue
        if not any(tz in tok for tz in TZ_TERMS):
            return False
    return True


# ---------------------------------------------------------------------------
# Location → language mapping (powered by babel + country-converter)
# ---------------------------------------------------------------------------


def location_to_languages(location_text: str) -> list[str]:
    """Return official language names for a job location string.

    Resolves country names via country-converter, then looks up official
    languages via babel. Returns English-language names like ["French", "German"].
    Falls back to empty list for unrecognised locations.
    """
    from babel.languages import get_official_languages
    from babel import Locale

    if not location_text:
        return []

    # Try to resolve the location to a country ISO2 code
    iso2 = _cc.convert(location_text.strip(), to="ISO2")
    if iso2 == "not found":
        # Try extracting the last word (often the country in "Berlin, Germany")
        parts = [p.strip() for p in re.split(r"[,;/()]", location_text) if p.strip()]
        for part in reversed(parts):
            iso2 = _cc.convert(part, to="ISO2")
            if iso2 != "not found":
                break
    if iso2 == "not found":
        return []

    try:
        lang_codes = get_official_languages(iso2, de_facto=True)
        return [Locale(lc).get_language_name("en") for lc in lang_codes]
    except Exception:
        return []
