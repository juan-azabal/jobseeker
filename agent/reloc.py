"""Relocation detection functions for agent pipeline.

Uses module globals from scoring.py (populated by scoring.load_heuristic_config).
Reads scoring._HOME_LOCATIONS and scoring._HOME_REGION_RE at call time so
updates from load_heuristic_config() are always reflected.

Exports:
  is_remote_requiring_reloc(job, ...)  — True if remote job is geo-restricted
  is_reloc(job)                        — True if job requires relocating
"""

import re

import scoring as _scoring_mod


def is_remote_requiring_reloc(job, home_locations=None, home_regions=None, region_pattern=None):
    """Return True if a remote job pins the worker to a place outside home.

    Checks three signals (title, location, restriction) against the user's
    home_locations and home_regions (auto-derived via country-converter).
    A remote job is reloc-free only if:
      1. The user's home location explicitly appears in the combined text, OR
      2. The user's home region appears (word-boundary safe via regex), OR
      3. A universal term appears (worldwide, global, anywhere), OR
      4. There is NO country/city pinning at all (truly global remote).
    Everything else counts as relocation.
    """
    from geo import matches_region, UNIVERSAL_TERMS, build_region_pattern  # noqa: PLC0415

    home_locs = home_locations if home_locations is not None else _scoring_mod._HOME_LOCATIONS
    re_pattern = region_pattern if region_pattern is not None else _scoring_mod._HOME_REGION_RE
    # Build pattern on the fly if caller passed regions list but no compiled pattern
    if re_pattern is None and home_regions:
        re_pattern = build_region_pattern(home_regions)

    p = job.get("parsed") or {}
    title_lower = (job.get("title") or "").lower()
    job_loc = (job.get("location") or "").lower()
    restriction = (p.get("remote_restriction") or "").lower()
    if restriction in ("null", "none"):
        restriction = ""

    combined = f"{title_lower} {job_loc} {restriction}"

    # 1. User's home is mentioned → accessible, not reloc
    if home_locs and any(home in combined for home in home_locs):
        return False

    # 2. User's home region is mentioned (word-boundary regex) → not reloc
    if matches_region(combined, re_pattern):
        return False

    # 3. Universally inclusive → not reloc
    if any(term in combined for term in UNIVERSAL_TERMS):
        return False

    # 4. "Remote from X" pattern in title → country-pinned → reloc
    if re.search(r"remote from \w", title_lower):
        return True

    # 5. Location is "SomePlace (remote)" → country-pinned → reloc
    if "(remote)" in job_loc and job_loc.replace("(remote)", "").strip():
        return True

    # 6. Restriction names a specific place (not just a timezone)
    if restriction:
        from geo import is_pure_timezone  # noqa: PLC0415

        if not is_pure_timezone(restriction):
            return True

    # 7. No signals → truly global remote → not reloc
    return False


def is_reloc(job):
    """Return True if role requires relocating.

    Remote jobs: checks restriction/title/location for country pinning.
    Non-remote: checks if the job location matches user's home locations.
    """
    p = job.get("parsed") or {}
    loc_type = p.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    if loc_type == "remote":
        return is_remote_requiring_reloc(job)
    if any(c in job_loc for c in _scoring_mod._HOME_LOCATIONS):
        return False
    return True
