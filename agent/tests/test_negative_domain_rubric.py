"""
Tests for domain scoring behavior in the scoring prompt.

Phase 13.1 originally tested penalty clause injection into the LLM rubric.
Phase 17.2: domain_fit is now computed deterministically in code (hybrid_score/heuristic_score).
The LLM rubric v2 no longer asks the LLM to score domain_fit; it asks only for
technical_depth and profile_evidence grades.

These tests verify the v2 prompt behavior:
- No "cap domain_fit" language in generated prompt (domain scoring is code-side)
- Prompt still contains correct profile context values
- No score_breakdown in prompt
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import _build_scoring_prompt
import scorer


def _reset_rubric_cache():
    scorer._SCORING_RUBRIC_CACHE = None


def _profile_with_domains(domains):
    return {
        "user": {"name": "Test User"},
        "target": {
            "role_type": "Product Manager",
            "geography": "Remote",
            "domains": domains,
            "seniority": {"senior": 15},
        },
        "skills": [],
    }


class TestV2DomainPromptBehavior:
    """v2: domain_fit cap language must NOT appear in the LLM prompt (it's code-side now)."""

    def setup_method(self):
        _reset_rubric_cache()

    def test_strong_negative_domain_no_cap_language(self):
        """Profile with gaming=-25 must NOT produce 'cap domain_fit' in prompt."""
        rubric = _build_scoring_prompt(_profile_with_domains({"gaming": -25, "data": 15}))
        assert "cap domain_fit" not in rubric

    def test_mild_negative_domain_no_cap_language(self):
        """Profile with media=-5 must NOT produce 'cap domain_fit' in prompt."""
        rubric = _build_scoring_prompt(_profile_with_domains({"media": -5, "data": 15}))
        assert "cap domain_fit" not in rubric

    def test_no_negative_domains_no_cap_language(self):
        """All-positive domains also produces no domain_fit cap language."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15, "saas": 10}))
        assert "cap domain_fit" not in rubric

    def test_prompt_has_no_score_breakdown(self):
        """v2 prompt must not contain score_breakdown field."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15}))
        assert "score_breakdown" not in rubric

    def test_prompt_has_technical_depth(self):
        """v2 prompt must contain technical_depth grade field."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15}))
        assert "technical_depth" in rubric

    def test_prompt_has_profile_evidence(self):
        """v2 prompt must contain profile_evidence grade field."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15}))
        assert "profile_evidence" in rubric

    def test_prompt_contains_candidate_name(self):
        """Prompt must still interpolate candidate name."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15}))
        assert "Test User" in rubric

    def test_prompt_contains_role_type(self):
        """Prompt must still interpolate role_type."""
        rubric = _build_scoring_prompt(_profile_with_domains({"data": 15}))
        assert "Product Manager" in rubric
