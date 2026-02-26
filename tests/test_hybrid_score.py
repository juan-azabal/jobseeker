"""Tests for 17.4.1 — hybrid_score() function.

hybrid_score = deterministic_dims (same as heuristic) + grade_to_points(technical_grade)
              + grade_to_points(profile_grade), clamped [0, 100].

Grade points: A→20, B→12, C→5, None→10 (default midpoint).
"""

import pytest

from api.scoring import hybrid_score


# Minimal profile for deterministic scoring
_PROFILE = {
    "domains": {"saas": 15, "data": 12},
    "seniority": {"senior": 15},
    "skills": ["Python", "SQL"],
    "location_preference": "a",  # remote-only
    "home_locations": ["london"],
    "home_regions": [],
}

_PARSED = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": ["Python"],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
}

_JOB = {
    "title": "Senior PM",
    "company": "Acme",
    "location": "Remote",
}


class TestHybridScoreGradeImpact:
    """Grade A/B/C/None produces different scores."""

    def test_grade_a_a_higher_than_c_c(self):
        score_aa = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="A", profile_grade="A")
        score_cc = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="C", profile_grade="C")
        assert score_aa > score_cc

    def test_grade_a_b_higher_than_b_c(self):
        score_ab = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="A", profile_grade="B")
        score_bc = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="B", profile_grade="C")
        assert score_ab > score_bc

    def test_grade_a_a_adds_40_vs_no_grades(self):
        """A+A adds 20+20=40 vs no-grade default 10+10=20 → +20 difference."""
        base = hybrid_score(_PROFILE, _PARSED, _JOB, False)
        with_aa = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="A", profile_grade="A")
        # A+A adds 40; default adds 20; diff should be 20 (unless clamped)
        assert with_aa - base == 20 or with_aa == 100

    def test_grade_c_c_adds_10_vs_no_grades(self):
        """C+C adds 5+5=10 vs no-grade default 10+10=20 → -10 difference."""
        base = hybrid_score(_PROFILE, _PARSED, _JOB, False)
        with_cc = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="C", profile_grade="C")
        assert base - with_cc == 10 or with_cc == 0

    def test_none_grades_are_neutral_midpoint(self):
        """None grades → grade_to_points() returns 10 each."""
        score_none = hybrid_score(_PROFILE, _PARSED, _JOB, False)
        score_none_explicit = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade=None, profile_grade=None)
        assert score_none == score_none_explicit


class TestHybridScoreReturnBounds:
    """hybrid_score always returns 0 ≤ score ≤ 100."""

    def test_score_not_exceeds_100(self):
        profile_maxed = {**_PROFILE, "domains": {"saas": 100}}  # inflated
        score = hybrid_score(profile_maxed, _PARSED, _JOB, False, technical_grade="A", profile_grade="A")
        assert score <= 100

    def test_score_not_below_zero(self):
        parsed_with_flags = {**_PARSED, "red_flags": ["x"] * 5}
        score = hybrid_score(_PROFILE, parsed_with_flags, _JOB, False, technical_grade="C", profile_grade="C")
        assert score >= 0

    def test_empty_parsed_returns_grade_defaults(self):
        """Empty parsed → no deterministic signal; default grades add 10+10=20."""
        score = hybrid_score(_PROFILE, {}, _JOB, False)
        assert score == 20  # grade_to_points(None) + grade_to_points(None)


class TestHybridScoreSignature:
    """hybrid_score has correct signature and backward-compat defaults."""

    def test_accepts_domain_override(self):
        """domain_override kwarg must be accepted."""
        score = hybrid_score(
            _PROFILE, _PARSED, _JOB, False, domain_override="saas", technical_grade="B", profile_grade="B"
        )
        assert isinstance(score, int)

    def test_accepts_db_path_none(self):
        """db_path=None must not crash."""
        score = hybrid_score(_PROFILE, _PARSED, _JOB, False, db_path=None)
        assert isinstance(score, int)

    def test_lowercase_grades_accepted(self):
        """grade_to_points is case-insensitive."""
        score_upper = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="A", profile_grade="B")
        score_lower = hybrid_score(_PROFILE, _PARSED, _JOB, False, technical_grade="a", profile_grade="b")
        assert score_upper == score_lower
