"""Tests for user_config.py: profile loading, path resolution, seniority weights."""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_config import (
    compute_seniority_weights,
    is_profile_active,
    list_profiles,
    load_profile,
    resolve_profile_paths,
)


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    """list_profiles() returns main profiles, excludes sub-configs."""

    def test_returns_sorted_profile_ids(self, tmp_path):
        (tmp_path / "bob.yaml").write_text("user:\n  name: Bob\n")
        (tmp_path / "alice.yaml").write_text("user:\n  name: Alice\n")
        ids = list_profiles(str(tmp_path))
        assert ids == ["alice", "bob"]

    def test_excludes_sub_configs(self, tmp_path):
        (tmp_path / "alice.yaml").write_text("user:\n  name: Alice\n")
        (tmp_path / "alice-searches.yaml").write_text("searches: []\n")
        (tmp_path / "alice-preferences.yaml").write_text("prefilter: {}\n")
        (tmp_path / "alice-applied.yaml").write_text("applied: {}\n")
        ids = list_profiles(str(tmp_path))
        assert ids == ["alice"]

    def test_excludes_underscore_prefixed(self, tmp_path):
        (tmp_path / "alice.yaml").write_text("user:\n  name: Alice\n")
        (tmp_path / "_template.yaml").write_text("template: true\n")
        ids = list_profiles(str(tmp_path))
        assert ids == ["alice"]

    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert list_profiles(str(tmp_path)) == []

    def test_nonexistent_dir_returns_empty_list(self):
        assert list_profiles("/nonexistent/path") == []

    def test_active_only_filters_inactive(self, tmp_path):
        (tmp_path / "alice.yaml").write_text("user:\n  name: Alice\n  active: true\n")
        (tmp_path / "bob.yaml").write_text("user:\n  name: Bob\n  active: false\n")
        load_profile.cache_clear()
        active = list_profiles(str(tmp_path), active_only=True)
        assert active == ["alice"]

    def test_hex_ids_included(self, tmp_path):
        """Profile IDs like 028354c3 (hex UUIDs) should be included."""
        (tmp_path / "028354c3.yaml").write_text("user:\n  name: Test\n")
        ids = list_profiles(str(tmp_path))
        assert ids == ["028354c3"]


# ---------------------------------------------------------------------------
# load_profile
# ---------------------------------------------------------------------------


class TestLoadProfile:
    def test_loads_valid_profile(self, tmp_path):
        (tmp_path / "test.yaml").write_text("user:\n  name: Test\nskills:\n  - python\n")
        load_profile.cache_clear()
        profile = load_profile("test", str(tmp_path))
        assert profile["user"]["name"] == "Test"
        assert profile["skills"] == ["python"]

    def test_raises_on_missing_profile(self, tmp_path):
        load_profile.cache_clear()
        with pytest.raises(FileNotFoundError):
            load_profile("nonexistent", str(tmp_path))

    def test_caches_result(self, tmp_path):
        (tmp_path / "cached.yaml").write_text("user:\n  name: Cached\n")
        load_profile.cache_clear()
        p1 = load_profile("cached", str(tmp_path))
        p2 = load_profile("cached", str(tmp_path))
        assert p1 is p2  # same object from cache


# ---------------------------------------------------------------------------
# resolve_profile_paths
# ---------------------------------------------------------------------------


class TestResolveProfilePaths:
    def test_explicit_paths_take_precedence(self):
        raw = {
            "preferences": "custom/prefs.yaml",
            "watchlist": "custom/watchlist.yaml",
            "applied": "custom/applied.yaml",
            "seen_ids": "custom/seen.txt",
        }
        paths = resolve_profile_paths("user1", raw)
        assert paths["preferences"] == "custom/prefs.yaml"
        assert paths["watchlist"] == "custom/watchlist.yaml"
        assert paths["applied"] == "custom/applied.yaml"
        assert paths["seen_ids"] == "custom/seen.txt"

    def test_defaults_when_no_explicit(self):
        paths = resolve_profile_paths("user1", {})
        assert paths["watchlist"] == "config/watchlist.yaml"
        assert paths["applied"] == "config/profiles/user1-applied.yaml"
        assert paths["seen_ids"] == "config/seen_ids/user1.txt"

    def test_all_keys_present(self):
        paths = resolve_profile_paths("x", {})
        assert set(paths.keys()) == {
            "preferences",
            "watchlist",
            "applied",
            "seen_ids",
        }


# ---------------------------------------------------------------------------
# is_profile_active
# ---------------------------------------------------------------------------


class TestIsProfileActive:
    def test_active_by_default(self):
        assert is_profile_active({"user": {"name": "Test"}}) is True

    def test_explicitly_active(self):
        assert is_profile_active({"user": {"active": True}}) is True

    def test_explicitly_inactive(self):
        assert is_profile_active({"user": {"active": False}}) is False

    def test_no_user_block(self):
        assert is_profile_active({}) is True


# ---------------------------------------------------------------------------
# compute_seniority_weights
# ---------------------------------------------------------------------------


class TestComputeSeniorityWeights:
    def test_exact_match_is_15(self):
        w = compute_seniority_weights("senior", "ic")
        assert w["senior"] == 15

    def test_one_off_is_10(self):
        w = compute_seniority_weights("senior", "ic")
        assert w["staff"] == 10
        assert w["mid"] == 10

    def test_two_off_is_6(self):
        w = compute_seniority_weights("senior", "ic")
        assert w["principal"] == 6
        assert w["junior"] == 6

    def test_three_off_is_0(self):
        w = compute_seniority_weights("junior", "ic")
        assert w["principal"] == 0
        assert w["director"] == 0

    def test_ic_caps_director_vp(self):
        w = compute_seniority_weights("principal", "ic")
        assert w["director"] <= 4
        assert w["vp"] <= 4

    def test_management_does_not_cap_director(self):
        w = compute_seniority_weights("director", "management")
        assert w["director"] == 15
        assert w["vp"] == 10

    def test_default_level_is_senior(self):
        w = compute_seniority_weights("", "ic")
        assert w["senior"] == 15

    def test_unknown_level_defaults_to_senior(self):
        w = compute_seniority_weights("nonexistent", "ic")
        assert w["senior"] == 15

    def test_all_levels_present(self):
        w = compute_seniority_weights("senior", "ic")
        expected_keys = {"junior", "mid", "senior", "staff", "principal", "director", "vp"}
        assert set(w.keys()) == expected_keys

    def test_principal_ic_weights(self):
        """Verify weights for Juan's actual profile: principal IC."""
        w = compute_seniority_weights("principal", "ic")
        assert w["principal"] == 15
        assert w["staff"] == 10
        assert w["senior"] == 6
        assert w["director"] == 4  # capped for IC
        assert w["vp"] == 4  # 2 off (6) but capped at 4 for IC
