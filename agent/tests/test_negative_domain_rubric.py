"""
Tests for Phase 13.1: Negative domain penalty injection into RAG scoring rubric.

Verifies:
(a) Profile with negative-weight domains → rubric contains penalty clause with those domains.
(b) Profile with no negative domains → rubric contains NO penalty clause.
(c) Profile with mixed positive/negative → penalty clause only names negative domains,
    and positive domains appear in core/adjacent sections as expected.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import _build_scoring_prompt
import scorer


def _reset_rubric_cache():
    scorer._SCORING_RUBRIC_CACHE = None


class TestNegativeDomainInjected:
    """(a) Profile with negative domains → penalty clause appears in rubric."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"game": -25, "data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_penalty_clause_present(self):
        assert "PENALTY" in self.rubric

    def test_penalty_clause_names_negative_domain(self):
        assert "game" in self.rubric.lower()
        # The penalty clause must reference the negative domain specifically
        penalty_section = self.rubric[self.rubric.find("PENALTY"):]
        assert "game" in penalty_section.lower()

    def test_positive_domain_in_core(self):
        # data (weight 15, >= 12) should appear in core domains
        assert "data" in self.rubric

    def test_cap_language_present(self):
        # The penalty clause should mention capping domain_fit at 4
        assert "cap domain_fit at 4" in self.rubric or "domain_fit at 4" in self.rubric

    def test_explicitly_deprioritized_language(self):
        assert "explicitly deprioritized" in self.rubric


class TestNoPenaltyClauseWhenNoNegative:
    """(b) Profile with only positive domains → no penalty clause."""

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
        assert "cap domain_fit at 4" not in self.rubric


class TestMultipleNegativeDomains:
    """Multiple negative domains all appear in penalty clause."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = {
            "user": {"name": "Test User"},
            "target": {
                "role_type": "Product Manager",
                "geography": "Remote",
                "domains": {"game": -25, "media": -10, "data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        self.rubric = _build_scoring_prompt(self.profile)

    def test_both_negative_domains_in_penalty(self):
        penalty_start = self.rubric.find("PENALTY")
        assert penalty_start != -1
        penalty_section = self.rubric[penalty_start:penalty_start + 300]
        assert "game" in penalty_section.lower()
        assert "media" in penalty_section.lower()

    def test_positive_domain_not_in_penalty(self):
        penalty_start = self.rubric.find("PENALTY")
        penalty_section = self.rubric[penalty_start:penalty_start + 300]
        # "data" is positive — must not be named in the penalty clause
        assert "data" not in penalty_section.lower()
