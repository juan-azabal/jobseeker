"""
Profile loader for multi-user support.

Each user has a profile YAML at config/profiles/<id>.yaml.
Use load_profile(id) to get the profile dict. Results are cached.

Usage:
    from user_config import load_profile, list_profiles
    profile = load_profile("juan")
"""

import os
import functools
import yaml


PROFILES_DIR = "config/profiles"


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

    active_only=True skips profiles where user.active is explicitly set to false.
    """
    if not os.path.isdir(profiles_dir):
        return []
    ids = sorted(
        f[:-5] for f in os.listdir(profiles_dir)
        if f.endswith(".yaml") and not f.startswith("_")
    )
    if not active_only:
        return ids
    return [pid for pid in ids if _is_active(pid, profiles_dir)]


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
