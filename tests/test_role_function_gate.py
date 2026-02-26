"""Tests for 17.5.1 — role_function gate in hybrid_score.

When user profile has target.role_function AND the job has role_function:
  match   →  0 pts
  mismatch → -15 pts
Either absent → 0 pts (neutral, no penalty).
"""

import pytest

from api.scoring import hybrid_score


_PROFILE_WITH_RF = {
    "domains": {"saas": 15},
    "seniority": {"senior": 15},
    "skills": ["Python"],
    "location_preference": "a",
    "home_locations": ["london"],
    "home_regions": [],
    "role_function": "product",  # user targets PM roles
}

_PROFILE_NO_RF = {
    "domains": {"saas": 15},
    "seniority": {"senior": 15},
    "skills": ["Python"],
    "location_preference": "a",
    "home_locations": ["london"],
    "home_regions": [],
    # no role_function key
}

_PARSED_PM = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "role_function": "product",
}

_PARSED_ENG = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "role_function": "engineering",
}

_PARSED_NO_RF = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    # no role_function
}

_JOB = {"title": "PM", "company": "Acme", "location": "Remote"}


class TestRoleFunctionGate:
    """role_function match → no penalty; mismatch → -15 pts."""

    def test_match_no_penalty(self):
        """PM profile + PM job → no role penalty."""
        score_match = hybrid_score(_PROFILE_WITH_RF, _PARSED_PM, _JOB, False)
        score_no_rf = hybrid_score(_PROFILE_NO_RF, _PARSED_PM, _JOB, False)
        # Match: no penalty. No-RF profile: also no penalty. Equal.
        assert score_match == score_no_rf

    def test_mismatch_subtracts_15(self):
        """PM profile + Engineering job → -15 penalty."""
        score_mismatch = hybrid_score(_PROFILE_WITH_RF, _PARSED_ENG, _JOB, False)
        score_no_rf = hybrid_score(_PROFILE_NO_RF, _PARSED_ENG, _JOB, False)
        assert score_no_rf - score_mismatch == 15 or score_mismatch == 0

    def test_no_profile_role_function_no_penalty(self):
        """Profile without role_function → no gate applied."""
        score = hybrid_score(_PROFILE_NO_RF, _PARSED_ENG, _JOB, False)
        score_match = hybrid_score(_PROFILE_NO_RF, _PARSED_PM, _JOB, False)
        # No penalty regardless of job role_function
        assert score == score_match

    def test_no_job_role_function_no_penalty(self):
        """Job without role_function → no gate applied."""
        score_with = hybrid_score(_PROFILE_WITH_RF, _PARSED_NO_RF, _JOB, False)
        score_without = hybrid_score(_PROFILE_NO_RF, _PARSED_NO_RF, _JOB, False)
        assert score_with == score_without

    def test_mismatch_score_not_below_zero(self):
        """Mismatch penalty never drives score below 0."""
        profile_bad = {**_PROFILE_WITH_RF, "domains": {"other": -5}}
        score = hybrid_score(profile_bad, _PARSED_ENG, _JOB, False, technical_grade="C", profile_grade="C")
        assert score >= 0

    def test_case_insensitive_match(self):
        """role_function comparison is case-insensitive."""
        parsed_upper = {**_PARSED_PM, "role_function": "Product"}
        score_upper = hybrid_score(_PROFILE_WITH_RF, parsed_upper, _JOB, False)
        score_lower = hybrid_score(_PROFILE_WITH_RF, _PARSED_PM, _JOB, False)
        assert score_upper == score_lower
