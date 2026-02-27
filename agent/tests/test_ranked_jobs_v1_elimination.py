"""Phase 19.0.2 — Agent v1 RAG path elimination tests.

Verifies that ranked_jobs() and _auto_skip_reloc() do NOT use stored v1
scores directly — they must always compute from _heuristic_score() + grades.
"""
import sys
import os

# Add the agent directory to the path (consistent with other agent tests)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def _make_job(job_id: str, rag_score: dict | None = None) -> dict:
    """Create a non-reloc remote job (no remote_restriction, no foreign pinning)."""
    return {
        "id": job_id,
        "title": "Staff Data Engineer",
        "company": "Acme Data",
        "location": "Remote",
        "location_type": "remote",
        "parsed": {
            "domain": "data",
            "seniority": "principal",
            "location_type": "remote",
            "must_have_skills": ["python", "sql"],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "red_flags": [],
            "locations_mentioned": [],
            "remote_restriction": None,
        },
        "rag_score": rag_score,
    }


class TestRankedJobsV1Elimination:
    """ranked_jobs() must not use v1 stored numeric scores directly."""

    def setup_method(self):
        """Load heuristic config with a minimal profile."""
        import main as m
        m._PROFILE_SKILLS = ["python", "sql"]
        m._DOMAIN_SCORES = {"data": 15}
        m._SENIORITY_SCORES = {"principal": 15, "senior": 10, "staff": 15}
        m._HOME_LOCATIONS = ["barcelona"]
        m._HOME_REGIONS = ["eu", "europe"]
        from geo import build_region_pattern
        m._HOME_REGION_RE = build_region_pattern(m._HOME_REGIONS)

    def test_v1_stored_score_not_used_directly(self):
        """Job with v1 rag_score (has 'score' key) must NOT return that stored score."""
        import main as m

        job = _make_job("job-v1", rag_score={"score": 99, "tier": "A"})
        tier_a, tier_b, tier_c = m.ranked_jobs([job])
        all_jobs = tier_a + tier_b + tier_c

        # Find our job
        matched = [j for j in all_jobs if j.get("id") == "job-v1"]
        assert matched, "Job should appear in ranked output"
        display_score = matched[0]["_display_score"]
        # Must NOT be 99 (the stored v1 score)
        assert display_score != 99, (
            f"v1 stored score 99 should not be used directly in ranked_jobs(); got {display_score}"
        )

    def test_v2_job_uses_hybrid_score(self):
        """v2 job uses heuristic + grade points (not a stored numeric score)."""
        import main as m

        job = _make_job("job-v2", rag_score={"technical_depth": "A", "profile_evidence": "B"})
        tier_a, tier_b, tier_c = m.ranked_jobs([job])
        all_jobs = tier_a + tier_b + tier_c

        matched = [j for j in all_jobs if j.get("id") == "job-v2"]
        assert matched
        display_score = matched[0]["_display_score"]
        fit_score = matched[0]["_fit_score"]
        # v2: display = fit + grade_points(A=20) + grade_points(B=12) = fit + 32
        expected = min(100, max(0, fit_score + 20 + 12))
        assert display_score == expected, (
            f"v2 display_score should be {expected} (fit={fit_score}+32), got {display_score}"
        )

    def test_no_rag_uses_heuristic(self):
        """Job with no rag_score uses heuristic fit score only."""
        import main as m

        job = _make_job("job-unscored", rag_score=None)
        tier_a, tier_b, tier_c = m.ranked_jobs([job])
        all_jobs = tier_a + tier_b + tier_c

        matched = [j for j in all_jobs if j.get("id") == "job-unscored"]
        assert matched
        assert matched[0]["_display_score"] == matched[0]["_fit_score"]
