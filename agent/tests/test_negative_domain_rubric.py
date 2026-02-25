"""
Tests for Phase 13.1: Graduated negative domain penalty injection into RAG scoring rubric.

Verifies:
(a) Strong penalty (weight ≤ -15) → cap domain_fit at 3.
(b) Mild penalty (-15 < weight < 0) → cap domain_fit at 10.
(c) Both tiers present when profile has domains in each tier.
(d) No penalty clause when no negative domains.
(e) Positive domains appear in core/adjacent, NOT in penalty.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import _build_scoring_prompt
import scorer


def _reset_rubric_cache():
    scorer._SCORING_RUBRIC_CACHE = None


class TestStrongPenalty:
    """Weight ≤ -15 → strong penalty tier (cap 3)."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"gaming": -25, "data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_penalty_clause_present(self):
        assert "PENALTY" in self.rubric

    def test_strong_tier_names_domain(self):
        penalty_start = self.rubric.find("PENALTY")
        assert penalty_start != -1
        penalty_section = self.rubric[penalty_start:penalty_start + 500]
        assert "gaming" in penalty_section.lower()

    def test_strong_tier_caps_at_3(self):
        assert "cap domain_fit at 3" in self.rubric

    def test_strong_tier_does_not_say_cap_at_10(self):
        assert "cap domain_fit at 10" not in self.rubric

    def test_positive_domain_in_core(self):
        assert "data" in self.rubric

    def test_cap_4_language_gone(self):
        assert "cap domain_fit at 4" not in self.rubric


class TestMildPenalty:
    """Weight between -1 and -14 → mild penalty tier (cap 10)."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"media": -5, "data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_penalty_clause_present(self):
        assert "PENALTY" in self.rubric

    def test_mild_tier_names_domain(self):
        penalty_start = self.rubric.find("PENALTY")
        penalty_section = self.rubric[penalty_start:penalty_start + 500]
        assert "media" in penalty_section.lower()

    def test_mild_tier_caps_at_10(self):
        assert "cap domain_fit at 10" in self.rubric

    def test_mild_tier_does_not_say_cap_at_3(self):
        assert "cap domain_fit at 3" not in self.rubric

    def test_cap_4_language_gone(self):
        assert "cap domain_fit at 4" not in self.rubric


class TestBothTiers:
    """Profile has domains in both strong (≤-15) and mild (<0, >-15) tiers."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"gaming": -25, "media": -5, "data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_both_tiers_present(self):
        assert "cap domain_fit at 3" in self.rubric
        assert "cap domain_fit at 10" in self.rubric

    def test_strong_domain_in_strong_tier(self):
        idx_cap3 = self.rubric.find("cap domain_fit at 3")
        assert idx_cap3 != -1
        context = self.rubric[max(0, idx_cap3 - 200):idx_cap3 + 50]
        assert "gaming" in context.lower()

    def test_mild_domain_in_mild_tier(self):
        idx_cap10 = self.rubric.find("cap domain_fit at 10")
        assert idx_cap10 != -1
        context = self.rubric[max(0, idx_cap10 - 200):idx_cap10 + 50]
        assert "media" in context.lower()

    def test_positive_domain_not_in_penalty(self):
        penalty_start = self.rubric.find("PENALTY")
        penalty_section = self.rubric[penalty_start:penalty_start + 600]
        assert "data" not in penalty_section.lower()

    def test_cap_4_language_gone(self):
        assert "cap domain_fit at 4" not in self.rubric


class TestNoPenaltyWhenNoNegative:
    """No negative domains → no penalty clause."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"data": 15, "saas": 10},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_no_penalty_clause(self):
        assert "PENALTY" not in self.rubric

    def test_no_cap_language(self):
        assert "cap domain_fit at 3" not in self.rubric
        assert "cap domain_fit at 10" not in self.rubric
        assert "cap domain_fit at 4" not in self.rubric


class TestBoundaryAtMinus15:
    """Exact boundary: -15 is strong, -14 is mild."""

    def _rubric_for(self, domains):
        scorer._SCORING_RUBRIC_CACHE = None
        profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "PM",
                "geography": "Remote",
                "domains": domains,
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        return _build_scoring_prompt(profile)

    def test_minus_15_is_strong(self):
        rubric = self._rubric_for({"gaming": -15, "data": 10})
        assert "cap domain_fit at 3" in rubric
        assert "cap domain_fit at 10" not in rubric

    def test_minus_14_is_mild(self):
        rubric = self._rubric_for({"gaming": -14, "data": 10})
        assert "cap domain_fit at 10" in rubric
        assert "cap domain_fit at 3" not in rubric
