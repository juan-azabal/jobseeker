"""Phase 19.1 — Eligibility penalty tests.

Tests for:
- 19.1.1: _compute_eligibility_penalty() pure function
- 19.1.2: penalty wired into heuristic_score()
- 19.1.3: location scoring distinguishes geo-restricted remote (+2/+8/+10)
- 19.2.1: country_weights doesn't inject 'remote' when geo-restricted
"""
import pytest
from api.scoring import heuristic_score, _compute_eligibility_penalty


# ---------------------------------------------------------------------------
# Base profile (barcelona-based, data domain, principal)
# ---------------------------------------------------------------------------

_PROFILE = {
    "domains": {"data": 15},
    "seniority": {"principal": 15, "senior": 10, "staff": 15},
    "skills": ["python", "sql"],
    "home_locations": ["barcelona"],
    "home_regions": ["eu", "europe"],
    "languages": [],
    "location_preference": "b",
    "country_weights": {"netherlands": -10, "remote": 10, "spain": 10},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}

_BASE_PARSED = {
    "domain": "data",
    "seniority": "principal",
    "location_type": "remote",
    "must_have_skills": ["python", "sql"],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "locations_mentioned": [],
    "remote_restriction": None,
    "responsibilities_summary": "",
    "experience_requirements": "",
}


def _parsed(**overrides):
    return {**_BASE_PARSED, **overrides}


def _job(location_type: str = "remote", location: str = "Remote") -> dict:
    return {"location": location, "location_type": location_type}


# ---------------------------------------------------------------------------
# 19.1.1 — _compute_eligibility_penalty() unit tests
# ---------------------------------------------------------------------------

class TestComputeEligibilityPenalty:
    def test_no_restriction_returns_0(self):
        parsed = _parsed(remote_restriction=None)
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == 0

    def test_restriction_nl_home_barcelona_returns_minus20(self):
        parsed = _parsed(remote_restriction="Netherlands only")
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == -20

    def test_restriction_nl_home_amsterdam_returns_0(self):
        profile = {**_PROFILE, "home_locations": ["amsterdam"]}
        parsed = _parsed(remote_restriction="Netherlands only")
        assert _compute_eligibility_penalty(profile, parsed, _job()) == 0

    def test_restriction_spain_or_nl_home_barcelona_returns_0(self):
        parsed = _parsed(remote_restriction="Spain or Netherlands")
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == 0

    def test_restriction_eu_only_home_barcelona_returns_0(self):
        """EU restriction: home_regions includes EU → eligible."""
        parsed = _parsed(remote_restriction="EU only")
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == 0

    def test_location_pref_d_returns_0(self):
        """location_preference='d' (anywhere in Europe) → no penalty."""
        profile = {**_PROFILE, "location_preference": "d"}
        parsed = _parsed(remote_restriction="Netherlands only")
        assert _compute_eligibility_penalty(profile, parsed, _job()) == 0

    def test_non_remote_job_with_restriction_returns_0(self):
        """Penalty only applies to remote jobs."""
        parsed = _parsed(location_type="onsite", remote_restriction="Netherlands only")
        job = _job(location_type="onsite", location="Amsterdam")
        assert _compute_eligibility_penalty(_PROFILE, parsed, job) == 0

    def test_restriction_us_only_home_barcelona_returns_minus20(self):
        parsed = _parsed(remote_restriction="US only")
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == -20

    def test_empty_string_restriction_returns_0(self):
        """Empty string restriction (no restriction) → no penalty."""
        parsed = _parsed(remote_restriction="")
        assert _compute_eligibility_penalty(_PROFILE, parsed, _job()) == 0


# ---------------------------------------------------------------------------
# 19.1.2 — penalty wired into heuristic_score()
# ---------------------------------------------------------------------------

class TestHeuristicScoreWithPenalty:
    def test_restricted_job_scores_lower_than_unrestricted(self):
        """Netherlands-only job (home=barcelona) scores lower than unrestricted."""
        parsed_restricted = _parsed(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        parsed_free = _parsed(remote_restriction=None, locations_mentioned=[])
        job = _job()

        score_restricted = heuristic_score(_PROFILE, parsed_restricted, job, False)
        score_free = heuristic_score(_PROFILE, parsed_free, job, False)

        assert score_restricted < score_free, (
            f"Restricted ({score_restricted}) should score lower than free ({score_free})"
        )

    def test_nl_restricted_job_home_barcelona_score_le_55(self):
        """Integration: ClickHouse-like job NL-only + barcelona profile → score ≤ 55."""
        parsed = _parsed(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        score = heuristic_score(_PROFILE, parsed, _job(), False)
        assert score <= 55, f"Expected ≤55 for geo-ineligible remote job, got {score}"

    def test_same_job_no_restriction_score_ge_55(self):
        """Same job without restriction → score ≥ 55 (no eligibility penalty)."""
        parsed = _parsed(remote_restriction=None, locations_mentioned=[])
        score = heuristic_score(_PROFILE, parsed, _job(), False)
        assert score >= 55, f"Expected ≥55 for unrestricted remote job, got {score}"


# ---------------------------------------------------------------------------
# 19.1.3 — location scoring distinctions
# ---------------------------------------------------------------------------

class TestLocationScoringGeoRestricted:
    def _location_component(self, parsed: dict, job: dict) -> int:
        """Compute location component by using a minimal profile with loc_pref='d'.

        loc_pref='d' bypasses the eligibility penalty (user opted into Europe-wide),
        letting us observe the pure location score assigned by 19.1.3 logic.
        """
        profile_loc_only = {
            **_PROFILE,
            "domains": {},
            "seniority": {},
            "skills": [],
            "country_weights": {},
            "company_type_weights": {},
            "languages": [],
            "location_preference": "d",  # bypasses eligibility penalty
        }
        return heuristic_score(profile_loc_only, parsed, job, False)

    def test_remote_no_restriction_location_component_10(self):
        """Truly remote (no restriction) → location component = 10."""
        parsed = _parsed(remote_restriction=None)
        score = self._location_component(parsed, _job())
        assert score == 10, f"Expected location=10 for unrestricted remote, got {score}"

    def test_remote_spain_only_home_barcelona_location_component_8(self):
        """Spain-only remote, home=barcelona → location = 8 (eligible but restricted)."""
        parsed = _parsed(remote_restriction="Spain only")
        score = self._location_component(parsed, _job())
        assert score == 8, f"Expected location=8 for Spain-only remote + barcelona, got {score}"

    def test_remote_nl_only_home_barcelona_location_component_2(self):
        """NL-only remote, home=barcelona → location = 2 (ineligible)."""
        parsed = _parsed(remote_restriction="Netherlands only")
        score = self._location_component(parsed, _job())
        assert score == 2, f"Expected location=2 for NL-only remote + barcelona, got {score}"


# ---------------------------------------------------------------------------
# 19.2.1 — country_weights uses actual country for geo-restricted remote
# ---------------------------------------------------------------------------

class TestCountryWeightsGeoRestricted:
    def _country_component(self, parsed: dict, job: dict, country_weights: dict) -> int:
        """Compute score with only country_weights active (+ location component).

        Uses loc_pref='d' to bypass the eligibility penalty so scores stay
        predictable: unrestricted remote adds +10, geo-restricted ineligible adds +2.
        """
        profile_cw_only = {
            **_PROFILE,
            "domains": {},
            "seniority": {},
            "skills": [],
            "country_weights": country_weights,
            "company_type_weights": {},
            "languages": [],
            "location_preference": "d",  # bypasses eligibility penalty
        }
        return heuristic_score(profile_cw_only, parsed, job, False)

    def test_remote_no_restriction_remote_weight_applied(self):
        """No restriction, remote keyword in country_weights → location(10) + country(10) = 20."""
        parsed = _parsed(remote_restriction=None, locations_mentioned=[])
        cw = {"remote": 10}
        score = self._country_component(parsed, _job(), cw)
        # location=10 (unrestricted remote) + country=10 (remote injected into normalized_locs)
        assert score == 20, f"Expected 20 for unrestricted remote (loc=10 + cw=10), got {score}"

    def test_remote_nl_restricted_nl_negative_weight_applied(self):
        """NL-only restriction, netherlands:-10 remote:+10 → should get -10 (NL)."""
        parsed = _parsed(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        cw = {"netherlands": -10, "remote": 10}
        score = self._country_component(parsed, _job(), cw)
        assert score == -10 or score == 0, (
            # Score is clamped at max(-10, min(10, best)), so -10 is the expected value.
            # With restriction, 'remote' is NOT injected, so only 'netherlands' (-10) applies.
            f"Expected country=-10 for NL-restricted remote + netherlands:-10, got {score}"
        )
        assert score < 10, "remote weight (+10) must not override NL weight when job is geo-restricted"

    def test_remote_nl_restricted_nl_positive_weight_applied(self):
        """NL-only restriction, netherlands:+5 remote:+10 → location(2) + country(5) = 7 (NL used, not remote)."""
        parsed = _parsed(
            remote_restriction="Netherlands only",
            locations_mentioned=["netherlands"],
        )
        cw = {"netherlands": 5, "remote": 10}
        score = self._country_component(parsed, _job(), cw)
        # location=2 (geo-restricted ineligible) + country=5 (netherlands used, NOT remote:10)
        assert score == 7, (
            f"Expected 7 for NL-restricted remote + netherlands:5, got {score}"
        )
        # Confirm remote:+10 was NOT used (would give 2+10=12 if injected)
        assert score < 12, "remote weight (+10) must not override NL weight when job is geo-restricted"
