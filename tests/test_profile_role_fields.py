"""Tests for 17.6.1 — role_type and role_function returned by load_profile_data.

load_profile_data() must include:
  - role_function: from target.role_function (enum string or None)
  - role_type: from target.role_type (free text string or None)
"""

import tempfile
import os
from pathlib import Path

import pytest
import yaml

from api.scoring import load_profile_data


@pytest.fixture()
def profile_dir(tmp_path, monkeypatch):
    """Create a temp profiles dir and point JOBAGENT_DIR at it."""
    profiles = tmp_path / "config" / "profiles"
    profiles.mkdir(parents=True)
    monkeypatch.setenv("JOBAGENT_DIR", str(tmp_path))
    return profiles


def _write_profile(profiles_dir: Path, profile_id: str, role_function=None, role_type=None):
    data = {
        "user": {"home_locations": ["london"], "location_preference": "a"},
        "target": {
            "domains": {"saas": 15},
            "level": "senior",
            "track": "ic",
        },
        "skills": ["Python"],
    }
    if role_function is not None:
        data["target"]["role_function"] = role_function
    if role_type is not None:
        data["target"]["role_type"] = role_type

    path = profiles_dir / f"{profile_id}.yaml"
    path.write_text(yaml.dump(data))
    return profile_id


class TestProfileRoleFields:
    def test_role_function_returned(self, profile_dir):
        """load_profile_data returns role_function from target block."""
        pid = _write_profile(profile_dir, "testuser", role_function="product")
        profile = load_profile_data(pid)
        assert profile is not None
        assert profile.get("role_function") == "product"

    def test_role_type_returned(self, profile_dir):
        """load_profile_data returns role_type from target block."""
        pid = _write_profile(profile_dir, "testuser2", role_type="Head of Product")
        profile = load_profile_data(pid)
        assert profile is not None
        assert profile.get("role_type") == "Head of Product"

    def test_both_fields_returned(self, profile_dir):
        """load_profile_data returns both role_function and role_type."""
        pid = _write_profile(profile_dir, "testuser3", role_function="product", role_type="CPO")
        profile = load_profile_data(pid)
        assert profile is not None
        assert profile["role_function"] == "product"
        assert profile["role_type"] == "CPO"

    def test_missing_fields_return_none(self, profile_dir):
        """Profile without role fields returns None for both."""
        pid = _write_profile(profile_dir, "testuser4")
        profile = load_profile_data(pid)
        assert profile is not None
        assert profile.get("role_function") is None
        assert profile.get("role_type") is None
