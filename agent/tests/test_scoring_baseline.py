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
        # domain(data)=15 + seniority(principal)=15 + location(remote)=10
        # + country_weights(remote=10) + skills=16
        assert _heuristic_score(JOB_STRONG_FIT) == 66

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


# ---------------------------------------------------------------------------
# 19.2.2 — country_weights geo-restriction guard
# ---------------------------------------------------------------------------


class TestCountryWeightsGeoRestriction:
    """19.2.2: 'remote' is NOT injected into normalized_locs when geo-restricted."""

    def _make_job(self, loc_type="remote", remote_restriction=None, locations_mentioned=None):
        return {
            "location": "Remote",
            "parsed": {
                "location_type": loc_type,
                "domain": "data",
                "seniority": "principal",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
                "remote_restriction": remote_restriction,
                "locations_mentioned": locations_mentioned or [],
            },
        }

    def setup_method(self):
        from tests.fixtures import BASELINE_PROFILE
        import copy

        _load_heuristic_config(copy.deepcopy(BASELINE_PROFILE))
        # Baseline profile: country_weights = {"spain": 10, "remote": 10}

    def test_unrestricted_remote_injects_remote_key(self):
        """No restriction → 'remote' injected → country_weights['remote']=+10 applied."""
        job = self._make_job(remote_restriction=None)
        score = _heuristic_score(job)
        # domain(15) + seniority(15) + location(10) + country(remote=10) + skills(0) = 50
        assert score == 50

    def test_geo_restricted_remote_no_remote_injection(self):
        """NL-only restriction → 'remote' NOT injected; 'netherlands' used instead.

        Baseline profile has no 'netherlands' weight, so country delta = 0.
        """
        job = self._make_job(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        score = _heuristic_score(job)
        # domain(15) + seniority(15) + location(0, is_reloc→no bonus) + country(0, nl not in cw) + skills(0) = 30
        # Note: remote weight (+10) must NOT be applied for geo-restricted job
        assert score < 50, "remote weight must not be injected for geo-restricted remote"

    def test_geo_restricted_remote_negative_country_weight_applied(self):
        """NL-only restriction + netherlands:-10 in cw → -10 applied (not remote:+10)."""
        from tests.fixtures import BASELINE_PROFILE
        import copy

        profile = copy.deepcopy(BASELINE_PROFILE)
        profile["target"]["country_weights"] = {"netherlands": -10, "remote": 10}
        _load_heuristic_config(profile)

        job = self._make_job(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        score_with_negative = _heuristic_score(job)
        score_with_no_weight = _heuristic_score(self._make_job(remote_restriction="Netherlands only"))
        assert score_with_negative <= score_with_no_weight, (
            "netherlands:-10 must reduce score vs no weight; remote:+10 must not override"
        )


class TestEligibilityPenaltyAgent:
    """19.5.1 + 19.5.2 — Eligibility penalty + graduated location scoring in agent."""

    def _make_job(self, remote_restriction: str | None, location_type: str = "remote") -> dict:
        return {
            "title": "PM",
            "company": "Acme",
            "location": "Remote",
            "parsed": {
                "seniority": "principal",
                "location_type": location_type,
                "domain": "data",
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "technical_stack": [],
                "responsibilities_summary": "",
                "red_flags": [],
                "remote_restriction": remote_restriction,
                "locations_mentioned": [],
            },
        }

    def setup_method(self):
        """Use minimal profile: barcelona home, no country_weights (isolates eligibility)."""
        from tests.fixtures import BASELINE_PROFILE
        import copy

        profile = copy.deepcopy(BASELINE_PROFILE)
        # Remove country_weights to isolate eligibility and location scoring
        profile["target"]["country_weights"] = {}
        _load_heuristic_config(profile)

    def test_us_only_restriction_applies_penalty_and_reduced_location(self):
        """Remote job restricted to US → -20 penalty + location drops from +10 to +2 (-8).

        Total diff = -28 (penalty -20 + location -8).
        baseline: domain(15) + seniority(15) + location(10) = 40
        restricted: domain(15) + seniority(15) + location(2) + penalty(-20) = 12
        """
        unrestricted = self._make_job(remote_restriction=None)
        us_only = self._make_job(remote_restriction="Must be based in the United States")
        score_unr = _heuristic_score(unrestricted)
        score_us = _heuristic_score(us_only)
        # penalty(-20) + location(-8) = -28 total
        assert score_us == score_unr - 28, (
            f"Expected -28 total (penalty -20 + location -8); got unrestricted={score_unr}, restricted={score_us}"
        )

    def test_spain_restriction_eligible_user_no_penalty(self):
        """Remote job restricted to Spain → user in Barcelona is eligible → no -20 penalty.

        Only location penalty: +10 → +8 = -2.
        """
        spain_only = self._make_job(remote_restriction="Must be based in Spain")
        unrestricted = self._make_job(remote_restriction=None)
        score_es = _heuristic_score(spain_only)
        score_unr = _heuristic_score(unrestricted)
        # No -20 penalty; location: +8 (eligible restricted) vs +10 (unrestricted) → diff = -2
        assert score_es == score_unr - 2, (
            f"Spain-eligible: expected diff=-2 (location only); unrestricted={score_unr}, spain={score_es}"
        )

    def test_ineligible_scores_lower_than_eligible_restriction(self):
        """Ineligible (US-only) scores 26 less than eligible (Spain-only).

        Penalty diff: 20 (penalty fires for US, not Spain).
        Location diff: 6 (eligible gets +8, ineligible gets +2).
        Total: 26.
        """
        us_only = self._make_job(remote_restriction="Must be based in the United States")
        spain_only = self._make_job(remote_restriction="Must be based in Spain")
        score_us = _heuristic_score(us_only)
        score_es = _heuristic_score(spain_only)
        assert score_us == score_es - 26, (
            f"Ineligible must score 26 less than eligible (penalty -20 + location -6); us={score_us}, spain={score_es}"
        )
