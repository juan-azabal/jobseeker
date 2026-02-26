"""List active profile IDs as a JSON array for GHA matrix.

Called by the GitHub Actions list-profiles job to build the matrix
input for parallel digest execution.

Matches the old workflow's profile-selection logic:
  - Excludes sub-configs (names containing a hyphen, e.g. juan-searches)
  - Excludes profiles where user.active is explicitly false
  - Includes all others (named profiles and hash-based search profiles)

Usage (from repo root):
    python agent/scripts/list_active_profiles.py

Output:
    ["alice", "juan", "noura", "test1234"]
"""

import json
import os
import sys

# Locate user_config.py relative to this script's location
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _AGENT_DIR)

from user_config import list_profiles  # noqa: E402

profiles_dir = os.path.join(_AGENT_DIR, "config", "profiles")
all_active = list_profiles(profiles_dir=profiles_dir, active_only=True)

# Exclude sub-configs: names with a hyphen (e.g. juan-searches, juan-preferences)
# This mirrors: case "$profile_id" in *-*) continue ;; esac  in the old workflow
main_profiles = [pid for pid in all_active if "-" not in pid]

print(json.dumps(main_profiles))
