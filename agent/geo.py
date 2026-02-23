"""Geographic region utilities powered by country-converter.

Auto-derives region terms (EU, EMEA, Europe, …) from a user's home_locations
so that relocation detection works for any country without manual config.
"""

import re
import country_converter as coco

_cc = coco.CountryConverter()

# Terms that mean "open to everyone" regardless of where you live
UNIVERSAL_TERMS = ["worldwide", "global", "anywhere"]

# Map continent → common business region terms used in job postings
_EMEA_CONTINENTS = {"Europe", "Africa"}
_EMEA_UN_REGIONS = {"Western Asia"}  # Middle East portion of EMEA
_APAC_CONTINENTS = {"Asia", "Oceania"}


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
