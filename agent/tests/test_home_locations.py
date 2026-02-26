"""
Tests for Phase 7.3: Remove hardcoded home locations.

Verifies:
(a) With home_locations=[], location scoring returns 0 (no crash).
(b) With Juan's profile, location scoring unchanged from baseline.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import _load_heuristic_config, _heuristic_score
from tests.fixtures import BASELINE_PROFILE


class TestEmptyHomeLocations:
    """With no home locations, location-dependent scoring gives 0 points, no crash."""

    def setup_method(self):
        profile = {
            "user": {"name": "No Home User", "home_locations": []},
            "target": {
                "domains": {"data": 15},
                "seniority": {"senior": 15},
            },
            "skills": [],
        }
        _load_heuristic_config(profile)

    def test_remote_job_still_scores(self):
        job = {
            "title": "PM",
            "location": "Remote",
            "parsed": {
                "seniority": "senior",
                "location_type": "remote",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # Domain 15 + seniority 15 + remote 10 = 40
        assert score == 40

    def test_hybrid_job_no_home_match(self):
        job = {
            "title": "PM",
            "location": "Barcelona, Spain (hybrid)",
            "parsed": {
                "seniority": "senior",
                "location_type": "hybrid",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # Domain 15 + seniority 15 + hybrid with no home match = 0
        assert score == 30

    def test_onsite_job_no_home_match(self):
        job = {
            "title": "PM",
            "location": "London, UK",
            "parsed": {
                "seniority": "senior",
                "location_type": "onsite",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # Domain 15 + seniority 15 + onsite no match = 0
        assert score == 30


class TestJuanHomeLocations:
    """Fixed baseline profile — location scoring unchanged from baseline.

    Uses BASELINE_PROFILE (not config/profiles/juan.yaml) so personal profile
    tuning never breaks these regression tests.
    """

    def setup_method(self):
        import copy
        profile = copy.deepcopy(BASELINE_PROFILE)
        _load_heuristic_config(profile)

    def test_remote_scores_10(self):
        job = {
            "title": "PM",
            "location": "Remote, Europe",
            "parsed": {
                "seniority": "principal",
                "location_type": "remote",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # domain 15 + seniority 15 + remote 10 = 40
        assert score == 40

    def test_hybrid_barcelona_scores_8(self):
        job = {
            "title": "PM",
            "location": "Barcelona, Spain (hybrid)",
            "parsed": {
                "seniority": "principal",
                "location_type": "hybrid",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # domain 15 + seniority 15 + hybrid barcelona 8 = 38
        assert score == 38

    def test_onsite_madrid_scores_6(self):
        job = {
            "title": "PM",
            "location": "Madrid, Spain",
            "parsed": {
                "seniority": "principal",
                "location_type": "onsite",
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
            },
        }
        score = _heuristic_score(job)
        # domain 15 + seniority 15 + onsite madrid 6 = 36
        assert score == 36

    def test_baseline_regression_strong_fit(self):
        """Same job as baseline test — must still score 56 (after seniority fix)."""
        from tests.test_scoring_baseline import JOB_STRONG_FIT
        assert _heuristic_score(JOB_STRONG_FIT) == 56
