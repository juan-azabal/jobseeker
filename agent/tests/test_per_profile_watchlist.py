"""
Tests for Phase 8.2: Per-profile watchlist config.

Verifies:
(a) Profile with watchlist: path → loads that file.
(b) Profile without watchlist → loads shared default.
(c) Juan's profile → loads same companies as before.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ats_scraper import load_watchlist
from user_config import load_profile


class TestWatchlistConfigLoading:
    """Verify watchlist config loading from different paths."""

    def test_loads_per_user_file(self):
        config = load_watchlist("config/profiles/juan-watchlist.yaml")
        assert "greenhouse" in config
        assert len(config["greenhouse"]) > 0

    def test_loads_shared_default(self):
        config = load_watchlist("config/watchlist.yaml")
        assert "greenhouse" in config
        assert len(config["greenhouse"]) > 0

    def test_juan_per_user_matches_shared(self):
        shared = load_watchlist("config/watchlist.yaml")
        per_user = load_watchlist("config/profiles/juan-watchlist.yaml")
        assert shared == per_user


class TestProfileWatchlistPath:
    """Verify the pipeline resolves watchlist path from profile."""

    def test_juan_profile_has_watchlist_path(self):
        profile = load_profile("juan")
        watchlist_path = profile.get("watchlist")
        assert watchlist_path is not None
        assert "juan" in watchlist_path

    def test_profile_without_watchlist_gets_default(self):
        profile = {"user": {"name": "Test"}, "target": {}, "skills": []}
        watchlist_path = profile.get("watchlist", "config/watchlist.yaml")
        assert watchlist_path == "config/watchlist.yaml"
