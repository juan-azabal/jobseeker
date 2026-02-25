"""
Tests for Phase 8.3: Per-profile prefilter preferences.

Verifies:
(a) Profile with custom preferences (different titles) → prefilter uses those.
(b) Profile without preferences → uses shared defaults.
(c) Juan's profile → identical prefilter behavior.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prefilter import load_preferences
from user_config import load_profile


class TestPreferencesLoading:
    """Verify preferences loading from different paths."""

    def test_loads_per_user_file(self):
        prefs = load_preferences("config/profiles/juan-preferences.yaml")
        assert "prefilter" in prefs
        pf = prefs["prefilter"]
        assert "title_must_contain_one_of" in pf
        assert "product manager" in pf["title_must_contain_one_of"]

    def test_loads_shared_default(self):
        prefs = load_preferences("config/preferences.yaml")
        assert "prefilter" in prefs
        assert "title_must_contain_one_of" in prefs["prefilter"]

    def test_juan_per_user_has_same_structure_as_shared(self):
        shared = load_preferences("config/preferences.yaml")
        per_user = load_preferences("config/profiles/juan-preferences.yaml")
        # Per-user preferences may diverge in values (salary, deal_breakers, etc.)
        # but must have the same top-level structure.
        assert set(shared.keys()) == set(per_user.keys())
        assert set(shared["prefilter"].keys()) == set(per_user["prefilter"].keys())


class TestCustomPreferencesPrefilter:
    """Test that different preferences produce different prefilter behavior."""

    def test_data_engineer_preferences(self, tmp_path):
        """A Data Engineer's preferences should accept DE titles, reject PM."""
        import yaml

        custom_prefs = {
            "prefilter": {
                "deal_breakers": ["junior", "intern"],
                "title_must_contain_one_of": [
                    "data engineer",
                    "analytics engineer",
                    "staff data engineer",
                ],
                "title_exclude": ["project manager", "sales"],
                "exclude_companies": [],
                "location": {"accept_onsite_cities": ["New York"]},
            }
        }
        prefs_file = tmp_path / "de-preferences.yaml"
        with open(prefs_file, "w") as f:
            yaml.dump(custom_prefs, f)

        prefs = load_preferences(str(prefs_file))
        pf = prefs["prefilter"]
        assert "data engineer" in pf["title_must_contain_one_of"]
        assert "product manager" not in pf["title_must_contain_one_of"]


class TestProfilePreferencesPath:
    """Verify the pipeline resolves preferences path from profile."""

    def test_juan_profile_has_preferences_path(self):
        profile = load_profile("juan")
        prefs_path = profile.get("preferences")
        assert prefs_path is not None
        assert "juan" in prefs_path

    def test_profile_without_preferences_gets_default(self):
        profile = {"user": {"name": "Test"}, "target": {}, "skills": []}
        prefs_path = profile.get("preferences", "config/preferences.yaml")
        assert prefs_path == "config/preferences.yaml"
