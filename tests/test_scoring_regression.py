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
            self._PROFILE_HATES_GAMING,
            _PARSED_GAMING,
            _JOB,
            False,
            technical_grade="A",
            profile_grade="A",
        )
        assert score < 55, f"Expected score < 55 but got {score} (gaming=-20 ignored)"

    def test_positive_gaming_weight_rewards_score(self):
        """gaming=+10 profile + gaming job → score > 70 with A/A grades."""
        score = hybrid_score(
            self._PROFILE_LIKES_GAMING,
            _PARSED_GAMING,
            _JOB,
            False,
            technical_grade="A",
            profile_grade="A",
        )
        assert score > 70, f"Expected score > 70 but got {score}"

    def test_negative_beats_positive_always(self):
        """Profile that hates gaming always scores lower than one that likes it."""
        hate_score = hybrid_score(
            self._PROFILE_HATES_GAMING, _PARSED_GAMING, _JOB, False, technical_grade="A", profile_grade="A"
        )
        like_score = hybrid_score(
            self._PROFILE_LIKES_GAMING, _PARSED_GAMING, _JOB, False, technical_grade="A", profile_grade="A"
        )
        assert hate_score < like_score


# ---------------------------------------------------------------------------
# 17.7.2 — PMM≠PM: role_function gate fires for marketing vs product
# ---------------------------------------------------------------------------


class TestPMMismatchRegression:
    """role_function gate must subtract 15 when profile=product meets a marketing job."""

    _PROFILE_PRODUCT = {
        "domains": {"saas": 10},
        "seniority": {"senior": 15},
        "skills": ["python"],
        "location_preference": "a",
        "home_locations": ["london"],
        "home_regions": [],
        "role_function": "product",
    }

    _JOB_PMM = {"title": "Senior PMM", "company": "SaaSCo", "location": "Remote"}

    def test_marketing_job_penalised_vs_product_job(self):
        """product profile + marketing job scores 15 less than product profile + product job."""
        score_mismatch = hybrid_score(
            self._PROFILE_PRODUCT,
            _PARSED_MARKETING,
            self._JOB_PMM,
            False,
            technical_grade="A",
            profile_grade="A",
        )
        score_match = hybrid_score(
            self._PROFILE_PRODUCT,
            _PARSED_PRODUCT,
            self._JOB_PMM,
            False,
            technical_grade="A",
            profile_grade="A",
        )
        assert score_match - score_mismatch == 15, (
            f"Expected 15-point gap; got match={score_match}, mismatch={score_mismatch}"
        )

    def test_mismatch_score_below_match(self):
        """Marketing job always scores lower than product job for a product profile."""
        score_mismatch = hybrid_score(
            self._PROFILE_PRODUCT, _PARSED_MARKETING, self._JOB_PMM, False, technical_grade="B", profile_grade="B"
        )
        score_match = hybrid_score(
            self._PROFILE_PRODUCT, _PARSED_PRODUCT, self._JOB_PMM, False, technical_grade="B", profile_grade="B"
        )
        assert score_mismatch < score_match

    def test_no_penalty_when_profile_has_no_role_function(self):
        """Profile without role_function gets no penalty regardless of job role_function."""
        profile_no_rf = {k: v for k, v in self._PROFILE_PRODUCT.items() if k != "role_function"}
        score_no_rf = hybrid_score(
            profile_no_rf, _PARSED_MARKETING, self._JOB_PMM, False, technical_grade="A", profile_grade="A"
        )
        score_rf = hybrid_score(
            self._PROFILE_PRODUCT, _PARSED_MARKETING, self._JOB_PMM, False, technical_grade="A", profile_grade="A"
        )
        assert score_no_rf > score_rf, "No-RF profile should not be penalised"


# ---------------------------------------------------------------------------
# 17.7.3 — Cross-user differentiation
# ---------------------------------------------------------------------------


class TestCrossUserDifferentiation:
    """Same job must score differently for two distinct profiles."""

    # Juan: strong data background, kafka/flink skills
    _PROFILE_JUAN = {
        "domains": {"data": 15, "saas": 8},
        "seniority": {"senior": 15},
        "skills": ["kafka", "flink", "python", "sql"],
        "location_preference": "a",
        "home_locations": ["london"],
        "home_regions": [],
        "role_function": "product",
    }

    # Noura: saas-focused, no data stack
    _PROFILE_NOURA = {
        "domains": {"saas": 15, "ecommerce": 8},
        "seniority": {"senior": 15},
        "skills": ["roadmapping", "stakeholder-management", "agile"],
        "location_preference": "a",
        "home_locations": ["london"],
        "home_regions": [],
        "role_function": "product",
    }

    def test_data_profile_beats_saas_profile_on_data_job(self):
        """Juan (data=15, kafka/flink) scores higher than Noura (saas=15) on a data PM role."""
        juan_score = hybrid_score(
            self._PROFILE_JUAN,
            _PARSED_DATA_JOB,
            _JOB_DATA,
            False,
            technical_grade="B",
            profile_grade="B",
        )
        noura_score = hybrid_score(
            self._PROFILE_NOURA,
            _PARSED_DATA_JOB,
            _JOB_DATA,
            False,
            technical_grade="B",
            profile_grade="B",
        )
        assert juan_score > noura_score, f"Expected Juan ({juan_score}) > Noura ({noura_score}) on data job"

    def test_scores_differ_meaningfully(self):
        """Score gap between data-specialist and generalist must be at least 10 pts."""
        juan_score = hybrid_score(
            self._PROFILE_JUAN, _PARSED_DATA_JOB, _JOB_DATA, False, technical_grade="B", profile_grade="B"
        )
        noura_score = hybrid_score(
            self._PROFILE_NOURA, _PARSED_DATA_JOB, _JOB_DATA, False, technical_grade="B", profile_grade="B"
        )
        assert juan_score - noura_score >= 10, (
            f"Gap too small: Juan={juan_score}, Noura={noura_score}, diff={juan_score - noura_score}"
        )

    def test_same_grades_same_job_different_scores(self):
        """With identical grades, profile content alone drives score divergence."""
        score_a = hybrid_score(
            self._PROFILE_JUAN, _PARSED_DATA_JOB, _JOB_DATA, False, technical_grade="A", profile_grade="A"
        )
        score_b = hybrid_score(
            self._PROFILE_NOURA, _PARSED_DATA_JOB, _JOB_DATA, False, technical_grade="A", profile_grade="A"
        )
        assert score_a != score_b
