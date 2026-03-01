"""
Profile loader for multi-user support.

Each user has a profile YAML at config/profiles/<id>.yaml.
Sub-configs (searches, preferences, applied) live alongside as
config/profiles/<id>-<type>.yaml — they are NOT treated as profiles.

Use load_profile(id) to get the profile dict. Results are cached.
Use resolve_profile_paths(id, raw) to get all derived file paths in one place.

Usage:
    from user_config import load_profile, list_profiles, resolve_profile_paths
    profile = load_profile("juanAza")
    paths = resolve_profile_paths("juanAza", profile)
"""

import os
import functools
import yaml


PROFILES_DIR = "config/profiles"

# Seniority levels ordered from most junior to most senior
_SENIORITY_LEVELS = ["junior", "mid", "senior", "staff", "principal", "director", "vp"]
_LEVEL_IDX = {lvl: i for i, lvl in enumerate(_SENIORITY_LEVELS)}


def compute_seniority_weights(level: str, track: str) -> dict[str, int]:
    """Compute seniority match weights from target.level + target.track.

    Mirrors api/scoring.py:_compute_seniority_weights() — agent-side single
    source of truth.  Per CLAUDE.md: seniority weights are computed at load
    time from level+track, never stored in YAML.

    Scoring:
      - Exact match: 15
      - 1 level off: 10
      - 2 levels off: 6
      - 3+ levels off: 0
      - director/vp capped at 4 for IC track (different career path)
    """
    level = (level or "senior").lower()
    track = (track or "ic").lower()
    target_idx = _LEVEL_IDX.get(level, 2)  # default to "senior" if unknown

    weights: dict[str, int] = {}
    for seniority, idx in _LEVEL_IDX.items():
        delta = abs(idx - target_idx)
        weights[seniority] = {0: 15, 1: 10, 2: 6}.get(delta, 0)

    # Management roles score poorly for IC track
    if track == "ic":
        weights["director"] = min(weights.get("director", 0), 4)
        weights["vp"] = min(weights.get("vp", 0), 4)

    return weights


@functools.lru_cache(maxsize=None)
def load_profile(profile_id: str, profiles_dir: str = PROFILES_DIR) -> dict:
    """Load and cache a user profile by ID. Raises FileNotFoundError if missing."""
    path = os.path.join(profiles_dir, f"{profile_id}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Profile not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def list_profiles(profiles_dir: str = PROFILES_DIR, active_only: bool = False) -> list:
    """Return sorted list of profile IDs (yaml filenames without extension).

    Only returns main profile files — sub-configs like '<id>-preferences.yaml',
    '<id>-searches.yaml', '<id>-applied.yaml' are excluded (they contain a hyphen).

    active_only=True skips profiles where user.active is explicitly set to false.
    """
    if not os.path.isdir(profiles_dir):
        return []
    ids = sorted(
        f[:-5] for f in os.listdir(profiles_dir) if f.endswith(".yaml") and not f.startswith("_") and "-" not in f[:-5]
    )
    if not active_only:
        return ids
    return [pid for pid in ids if _is_active(pid, profiles_dir)]


def resolve_profile_paths(profile_id: str, raw: dict) -> dict:
    """Resolve all per-profile resource paths from the loaded YAML.

    Explicit keys in the YAML always take precedence; sensible per-user
    defaults are used otherwise. This is the single source of truth for
    path derivation — callers should not build paths themselves.

    Returns:
        dict with keys: preferences, watchlist, applied, seen_ids
    """
    per_user_prefs = f"config/profiles/{profile_id}-preferences.yaml"
    return {
        "preferences": raw.get("preferences")
        or (per_user_prefs if os.path.exists(per_user_prefs) else "config/preferences.yaml"),
        "watchlist": raw.get("watchlist") or "config/watchlist.yaml",
        "applied": raw.get("applied") or f"config/profiles/{profile_id}-applied.yaml",
        "seen_ids": raw.get("seen_ids") or f"config/seen_ids/{profile_id}.txt",
    }


def _is_active(profile_id: str, profiles_dir: str = PROFILES_DIR) -> bool:
    """Return True if the profile is active (default: True if field not set)."""
    try:
        profile = load_profile(profile_id, profiles_dir)
        return profile.get("user", {}).get("active", True)
    except Exception:
        return False


def is_profile_active(profile: dict) -> bool:
    """Return True if a loaded profile dict is active."""
    return profile.get("user", {}).get("active", True)
