"""Tests for 17.6.2 — role_function and role_type inferred from CV in onboard_utils.

The extraction prompt must request role_function (enum) and role_type (free text).
onboard_utils.build_profile_yaml() must include them in the target block.
"""

import pytest

from api.onboard_utils import _build_profile_yaml as build_profile_yaml


def _call_build(extracted: dict) -> str:
    return build_profile_yaml(
        extracted=extracted,
        profile_id="testuser",
        email="test@example.com",
        salary_min=60000,
        location_choice="b",
        home_locations=["london"],
    )


class TestOnboardRoleFields:
    def test_role_function_in_yaml_product(self):
        """Extracted role_function=product ends up in target block of YAML."""
        extracted = {
            "name": "Test User",
            "track": "ic",
            "target_level": "principal",
            "domains": {"saas": 12},
            "skills": ["python"],
            "exclude_companies": [],
            "role_function": "product",
            "role_type": "Product Manager",
        }
        yaml_str = _call_build(extracted)
        assert "role_function: product" in yaml_str

    def test_role_type_in_yaml(self):
        """Extracted role_type ends up in target block of YAML."""
        extracted = {
            "name": "Test User",
            "track": "ic",
            "target_level": "principal",
            "domains": {"saas": 12},
            "skills": ["python"],
            "exclude_companies": [],
            "role_function": "product",
            "role_type": "Head of Product",
        }
        yaml_str = _call_build(extracted)
        assert "Head of Product" in yaml_str

    def test_missing_role_fields_gracefully_omitted(self):
        """_build_profile_yaml handles missing role fields without error."""
        extracted = {
            "name": "Test User",
            "track": "ic",
            "target_level": "principal",
            "domains": {"saas": 12},
            "skills": ["python"],
            "exclude_companies": [],
            # No role_function, no role_type
        }
        yaml_str = _call_build(extracted)
        assert yaml_str  # just must not error
