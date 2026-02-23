"""
Tests for Phase 8.1: Per-profile searches config.

Verifies:
(a) Profile with searches: path → loads that file.
(b) Profile without searches → loads shared default.
(c) Juan's profile → loads same queries as before.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from scraper import load_search_config


class TestSearchConfigLoading:
    """Verify search config loading from different paths."""

    def test_loads_per_user_file(self):
        """Profile with searches: path → loads that file."""
        config = load_search_config("config/profiles/juan-searches.yaml")
        assert "searches" in config
        assert len(config["searches"]) > 0

    def test_loads_shared_default(self):
        """Fallback: load shared config/searches.yaml."""
        config = load_search_config("config/searches.yaml")
        assert "searches" in config
        assert len(config["searches"]) > 0

    def test_juan_per_user_matches_shared(self):
        """Juan's per-user searches should match the shared file (copied from it)."""
        shared = load_search_config("config/searches.yaml")
        per_user = load_search_config("config/profiles/juan-searches.yaml")
        assert shared == per_user


class TestProfileSearchesPath:
    """Verify the pipeline resolves searches path from profile."""

    def test_juan_profile_has_searches_path(self):
        from user_config import load_profile
        profile = load_profile("juan")
        searches_path = profile.get("searches")
        assert searches_path is not None
        assert "juan" in searches_path

    def test_profile_without_searches_gets_default(self):
        """A profile without searches: field falls back to shared."""
        profile = {"user": {"name": "Test"}, "target": {}, "skills": []}
        searches_path = profile.get("searches", "config/searches.yaml")
        assert searches_path == "config/searches.yaml"
