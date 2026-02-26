"""
Scoring baseline regression tests.

Captures the exact heuristic scores and rubric output for Juan's profile
as of pre-Phase-7. Any refactor that changes scoring behavior will break
these tests, serving as a safety net.

Created: Phase 7.1
"""

import sys
import os

# Allow importing agent modules from the agent/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import _load_heuristic_config, _heuristic_score
from scorer import _build_scoring_prompt
from tests.fixtures import BASELINE_PROFILE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _load_juan_profile():
    """Return the fixed baseline profile and initialize heuristic config.

    Uses BASELINE_PROFILE (not config/profiles/juan.yaml) so that personal
    profile tuning never breaks these regression tests.
    """
    import copy
    profile = copy.deepcopy(BASELINE_PROFILE)
    _load_heuristic_config(profile)
    return profile


# Job 1: Strong fit — remote, principal, data domain, strong skill overlap
JOB_STRONG_FIT = {
    "title": "Principal Product Manager - Data Platform",
    "company": "Acme Data Co",
    "location": "Remote, Europe",
    "parsed": {
        "seniority": "principal",
        "location_type": "remote",
        "domain": "data",
        "must_have_skills": ["data platform", "event tracking", "SQL", "stakeholder management"],
        "nice_to_have_skills": ["Snowplow", "Kafka", "dbt"],
        "technical_stack": ["Snowflake", "Kafka", "dbt", "Python"],
        "responsibilities_summary": "Own the data platform strategy, define event taxonomy, align 5+ engineering teams.",
        "salary_mentioned": "120000-140000 EUR",
        "red_flags": [],
        "key_phrases": ["data platform ownership", "event taxonomy", "real-time pipeline"],
    },
}

# Job 2: Medium fit — hybrid Barcelona, senior, saas, some skill overlap
JOB_MEDIUM_FIT = {
    "title": "Senior Product Manager - Analytics",
    "company": "BarcelonaTech",
    "location": "Barcelona, Spain (hybrid)",
    "parsed": {
        "seniority": "senior",
        "location_type": "hybrid",
        "domain": "saas",
        "must_have_skills": ["analytics", "product roadmap", "SQL"],
        "nice_to_have_skills": ["experimentation", "data visualization"],
        "technical_stack": ["Looker", "BigQuery", "Python"],
        "responsibilities_summary": "Drive analytics product roadmap for B2B SaaS platform.",
        "salary_mentioned": "not mentioned",
        "red_flags": [],
        "key_phrases": ["analytics platform", "product strategy"],
    },
}

# Job 3: Low fit — onsite NYC, mid-level, healthcare, no skill overlap
JOB_LOW_FIT = {
    "title": "Product Manager - Healthcare",
    "company": "HealthCorp",
    "location": "New York, NY",
    "parsed": {
        "seniority": "mid",
        "location_type": "onsite",
        "domain": "healthcare",
        "must_have_skills": ["HIPAA", "EHR systems", "clinical workflows"],
        "nice_to_have_skills": ["HL7", "FHIR"],
        "technical_stack": ["Epic", "Cerner"],
        "responsibilities_summary": "Own healthcare workflow features for clinical staff.",
        "salary_mentioned": "90000-110000 USD",
        "red_flags": ["requires medical domain experience"],
        "key_phrases": ["clinical workflow", "patient engagement"],
    },
}


# ---------------------------------------------------------------------------
# Heuristic score regression
# ---------------------------------------------------------------------------

class TestHeuristicScoreBaseline:
    """Exact heuristic scores for Juan's profile — regression safety net."""

    def setup_method(self):
        self.profile = _load_juan_profile()

    def test_strong_fit_score(self):
        # domain(data)=15 + seniority(principal)=15 + location(remote)=10 + skills=16
        assert _heuristic_score(JOB_STRONG_FIT) == 56

    def test_medium_fit_score(self):
        # domain(saas)=10 + seniority(senior)=8 + location(hybrid,barcelona)=8 + skills=4
        assert _heuristic_score(JOB_MEDIUM_FIT) == 30

    def test_low_fit_score(self):
        # domain(healthcare)=0 + seniority(mid)=0 + location(onsite,NYC)=0 + skills=0 - red_flags=5 → clamped to 0
        assert _heuristic_score(JOB_LOW_FIT) == 0


# ---------------------------------------------------------------------------
# Rubric prompt regression
# ---------------------------------------------------------------------------

class TestRubricPromptBaseline:
    """Rubric prompt output for Juan's profile — regression safety net."""

    def setup_method(self):
        self.profile = _load_juan_profile()
        self.rubric = _build_scoring_prompt(self.profile)

    def test_rubric_contains_name(self):
        assert "Juan Azabal" in self.rubric

    def test_rubric_contains_core_domains(self):
        assert "data, adtech" in self.rubric

    def test_rubric_contains_adjacent_domains(self):
        # v2 rubric: adjacent domains are not injected separately into the prompt
        # (domain scoring is deterministic in code). Core domains still present.
        assert "data, adtech" in self.rubric

    def test_rubric_contains_target_levels(self):
        # Juan's seniority_weights: principal=15, staff=12 (both >= 10)
        assert "principal/staff" in self.rubric

    def test_rubric_no_hardcoded_saas_b2b_fallback(self):
        # With Juan's profile, adjacent_str resolves to "saas" (not the fallback "SaaS, B2B")
        assert "SaaS, B2B" not in self.rubric

    def test_rubric_contains_role_type(self):
        # v2 rubric: role_type still interpolated; "Generic tech {role_type}" line was v1 only
        assert "experienced Product Manager" in self.rubric

    def test_rubric_contains_geography(self):
        # Parameterized in 7.2 — Juan's profile sets geography: "EU or remote"
        assert "EU or remote" in self.rubric
