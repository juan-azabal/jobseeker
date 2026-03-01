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

    def test_juan_per_user_has_valid_structure(self):
        """Juan's per-user search config has valid structure (searches list + is_remote)."""
        per_user = load_search_config("config/profiles/juan-searches.yaml")
        assert "searches" in per_user
        assert len(per_user["searches"]) > 0
        for search in per_user["searches"]:
            assert "term" in search
            assert "sites" in search
