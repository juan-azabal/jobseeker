"""Tests for Phase 2.4: onboard generates search_titles, drops searches key."""

import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from onboard import _build_profile_yaml, _build_search_titles

_BASE_EXTRACTED = {
    "name": "Test User",
    "target_level": "senior",
    "track": "ic",
    "role_type": "Product Manager",
    "role_function": "product",
    "domains": {"data": 15},
    "skills": ["python"],
    "languages": ["en"],
}


class TestBuildSearchTitles:
    def test_level_and_role_type_produces_two_titles(self):
        titles = _build_search_titles({"role_type": "Product Manager", "target_level": "senior"})
        assert titles == ["Senior Product Manager", "Product Manager"]

    def test_level_capitalized(self):
        titles = _build_search_titles({"role_type": "Software Engineer", "target_level": "principal"})
        assert titles[0] == "Principal Software Engineer"

    def test_no_level_produces_one_title(self):
        titles = _build_search_titles({"role_type": "Product Manager", "target_level": ""})
        assert titles == ["Product Manager"]

    def test_missing_level_key_produces_one_title(self):
        titles = _build_search_titles({"role_type": "Product Manager"})
        assert titles == ["Product Manager"]

    def test_no_role_type_returns_empty(self):
        titles = _build_search_titles({"role_type": "", "target_level": "senior"})
        assert titles == []

    def test_missing_role_type_returns_empty(self):
        titles = _build_search_titles({"target_level": "senior"})
        assert titles == []

    def test_none_role_type_returns_empty(self):
        titles = _build_search_titles({"role_type": None, "target_level": "senior"})
        assert titles == []


class TestBuildProfileYaml:
    def _parse(self, extracted=None, **kwargs):
        ext = {**_BASE_EXTRACTED, **(extracted or {})}
        raw = _build_profile_yaml(
            extracted=ext,
            profile_id="testuser",
            email="test@example.com",
            salary_min=60000,
            location_choice="b",
            home_locations=["barcelona", "spain"],
        )
        return yaml.safe_load(raw)

    def test_search_titles_in_target_block(self):
        profile = self._parse()
        assert "search_titles" in profile["target"]
        assert profile["target"]["search_titles"] == ["Senior Product Manager", "Product Manager"]

    def test_no_searches_key_in_output(self):
        profile = self._parse()
        assert "searches" not in profile

    def test_search_titles_empty_when_no_role_type(self):
        profile = self._parse({"role_type": None})
        assert profile["target"]["search_titles"] == []
