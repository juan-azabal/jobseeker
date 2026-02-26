"""Regression tests for Phase 17 — hybrid scoring.

17.7.1: EA Gaming — domain weights respected (gaming=-20 drives score down).
17.7.2: PMM≠PM — role_function gate fires for marketing vs product.
17.7.3: Cross-user differentiation — different profiles score same job differently.
"""

import pytest

from api.scoring import hybrid_score

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_JOB = {"title": "Senior PM", "company": "EA Games", "location": "Remote"}

_PARSED_GAMING = {
    "domain": "gaming",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
}

_PARSED_MARKETING = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "role_function": "marketing",
}

_PARSED_PRODUCT = {**_PARSED_MARKETING, "role_function": "product"}

_PARSED_DATA_JOB = {
    "domain": "data",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": ["kafka", "flink", "dbt"],
    "nice_to_have_skills": [],
    "technical_stack": ["kafka", "flink"],
    "red_flags": [],
}

_JOB_DATA = {"title": "Data Product Manager", "company": "DataCo", "location": "Remote"}


# ---------------------------------------------------------------------------
# 17.7.1 — EA Gaming: domain weights respected
# ---------------------------------------------------------------------------

class TestEAGamingRegression:
    """gaming=-20 domain weight must bring hybrid score well below neutral."""

    _PROFILE_HATES_GAMING = {
        "domains": {"gaming": -20, "saas": 10},
        "seniority": {"senior": 15},
        "skills": ["python"],
        "location_preference": "a",
        "home_locations": ["london"],
        "home_regions": [],
    }

    _PROFILE_LIKES_GAMING = {
        "domains": {"gaming": 10, "saas": 10},
        "seniority": {"senior": 15},
        "skills": ["python"],
        "location_preference": "a",
        "home_locations": ["london"],
        "home_regions": [],
    }

    def test_negative_gaming_weight_caps_score(self):
        """gaming=-20 profile + gaming job → score < 55 even with A/A grades."""
        score = hybrid_score(
            self._PROFILE_HATES_GAMING, _PARSED_GAMING, _JOB, False,
            technical_grade="A", profile_grade="A",
        )
        assert score < 55, f"Expected score < 55 but got {score} (gaming=-20 ignored)"

    def test_positive_gaming_weight_rewards_score(self):
        """gaming=+10 profile + gaming job → score > 70 with A/A grades."""
        score = hybrid_score(
            self._PROFILE_LIKES_GAMING, _PARSED_GAMING, _JOB, False,
            technical_grade="A", profile_grade="A",
        )
        assert score > 70, f"Expected score > 70 but got {score}"

    def test_negative_beats_positive_always(self):
        """Profile that hates gaming always scores lower than one that likes it."""
        hate_score = hybrid_score(self._PROFILE_HATES_GAMING, _PARSED_GAMING, _JOB, False, technical_grade="A", profile_grade="A")
        like_score = hybrid_score(self._PROFILE_LIKES_GAMING, _PARSED_GAMING, _JOB, False, technical_grade="A", profile_grade="A")
        assert hate_score < like_score
