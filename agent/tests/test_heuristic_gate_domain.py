"""
Tests for Phase 13.4: Heuristic gate respects negative domain weights.

Verifies:
(a) Negative-weight domain → 0 gate credit (not +20).
(b) Positive-weight domain → +20 gate credit (regression).
(c) Missing domain (not in target) → 0 gate credit (unchanged).
(d) 'other' domain → +10 partial credit (unchanged).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import _heuristic_gate


def _make_profile(domains: dict, threshold: int = 10, skills: list = None):
    return {
        "scoring": {"rag_threshold": threshold},
        "target": {
            "domains": domains,
            "level": "senior",
        },
        "skills": skills or [],
    }


def _make_job(domain: str, seniority: str = "senior") -> dict:
    return {
        "id": "test001",
        "title": "PM",
        "company": "Acme",
        "parsed": {
            "domain": domain,
            "seniority": seniority,
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "salary_mentioned": None,
        },
    }


class TestGateNegativeDomain:
    """Negative-weight domain gets 0 credit in the gate (not +20)."""

    def test_negative_domain_gets_zero_gate_credit(self):
        # domain weight -25 → gate should give 0 domain credit
        profile = _make_profile({"game": -25}, threshold=30)
        job = _make_job("game")
        # With threshold=30, a game job with 0 domain credit + partial seniority (20)
        # = 20 < 30, so it should be skipped
        to_score, skipped = _heuristic_gate([job], profile)
        assert job in skipped, "Negative-weight domain job should be skipped by gate"
        assert job not in to_score

    def test_positive_domain_gets_full_gate_credit(self):
        # domain weight +15 → gate should give +20 credit
        profile = _make_profile({"data": 15}, threshold=30)
        job = _make_job("data")
        # domain(20) + seniority(20) = 40 >= 30 → to_score
        to_score, skipped = _heuristic_gate([job], profile)
        assert job in to_score, "Positive-weight domain job should pass the gate"
        assert job not in skipped

    def test_absent_domain_gets_zero_gate_credit(self):
        # domain not in target_domains → 0 credit (unchanged behavior)
        profile = _make_profile({"data": 15}, threshold=50)
        job = _make_job("healthcare")  # not in target_domains
        # domain(0) + seniority(20) = 20 < 50 → skipped
        to_score, skipped = _heuristic_gate([job], profile)
        assert job in skipped

    def test_other_domain_gets_partial_credit(self):
        # domain='other' → +10 partial credit (unchanged behavior)
        profile = _make_profile({"data": 15}, threshold=25)
        job = _make_job("other")
        # domain(10) + seniority(20) = 30 >= 25 → to_score
        to_score, skipped = _heuristic_gate([job], profile)
        assert job in to_score, "'other' domain should still get partial credit"

    def test_zero_threshold_skips_gate_entirely(self):
        # threshold=0 → gate is disabled, all jobs pass
        profile = _make_profile({"game": -25}, threshold=0)
        job = _make_job("game")
        to_score, skipped = _heuristic_gate([job], profile)
        assert job in to_score
        assert len(skipped) == 0
