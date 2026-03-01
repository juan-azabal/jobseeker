"""Cross-system regression tests for Phase 19 — eligibility penalty + location scoring.

Verifies that api/scoring.py and agent/main.py produce identical heuristic scores
for the same inputs across 5 key scenarios:

  1. Global remote (no restriction) → +10 location, 0 penalty
  2. Eligible restriction (spain in text) → +8 location, 0 penalty
  3. Ineligible restriction (US only, user in Barcelona) → +2 location, -20 penalty
  4. Timezone-only restriction (CET) → treated as unrestricted → +10, 0 penalty
  5. EU restriction → eligible for Barcelona user → +8 location, 0 penalty

Both systems must agree on the score for each scenario.

Profile notes:
- _PROFILE_*_FLAT: flat format for api/scoring.heuristic_score()
- _PROFILE_*_AGENT: nested (user/target) format for agent/_load_heuristic_config()
- RICH variants include domain+seniority so scores don't clamp to 0 under penalty
- MINIMAL variants use empty domains/seniority with explicit zero to ensure equivalence
"""

import copy
import sys
import os

# ---------------------------------------------------------------------------
# Agent path setup (agent/ is not a package, uses sys.path)
# ---------------------------------------------------------------------------

_AGENT_DIR = os.path.join(os.path.dirname(__file__), "..", "agent")

# ---------------------------------------------------------------------------
# API imports
# ---------------------------------------------------------------------------

from api.scoring import heuristic_score as _api_heuristic

# ---------------------------------------------------------------------------
# Profiles: Barcelona-based user, loc_pref "a" (remote-only)
#
# MINIMAL: no domain/seniority score — for absolute parity tests
#   Agent uses seniority_weights: {senior: 0} (explicit zero avoids compute fallback)
#
# RICH: domain=15, seniority=15 — for arithmetic tests (avoids penalty clamping to 0)
# ---------------------------------------------------------------------------

_HOME_REGIONS_BCN = ["eu", "eu only", "eu-based", "europe", "european", "emea", "eea", "schengen", "spain"]

_PROFILE_MINIMAL_FLAT = {
    "domains": {},
    "seniority": {},  # all seniorities = 0
    "skills": [],
    "location_preference": "a",
    "home_locations": ["barcelona", "spain"],
    "home_regions": _HOME_REGIONS_BCN,
    "country_weights": {},
    "languages": [],
}

_PROFILE_MINIMAL_AGENT = {
    "user": {
        "home_locations": ["barcelona", "spain"],
        "location_preference": "a",
    },
    "target": {
        "domains": {},
        "seniority_weights": {"senior": 0},  # explicit 0 avoids compute_seniority_weights fallback
        "country_weights": {},
    },
    "skills": [],
}

_PROFILE_RICH_FLAT = {
    "domains": {"saas": 15},
    "seniority": {"senior": 15},
    "skills": [],
    "location_preference": "a",
    "home_locations": ["barcelona", "spain"],
    "home_regions": _HOME_REGIONS_BCN,
    "country_weights": {},
    "languages": [],
}

_PROFILE_RICH_AGENT = {
    "user": {
        "home_locations": ["barcelona", "spain"],
        "location_preference": "a",
    },
    "target": {
        "domains": {"saas": 15},
        "seniority_weights": {"senior": 15},
        "country_weights": {},
    },
    "skills": [],
}

_JOB_REMOTE = {"title": "Senior PM", "company": "AcmeCo", "location": "Remote"}


def _make_parsed(restriction: str | None, loc_type: str = "remote") -> dict:
    return {
        "seniority": "senior",
        "domain": "saas",
        "location_type": loc_type,
        "remote_restriction": restriction,
        "must_have_skills": [],
        "nice_to_have_skills": [],
        "technical_stack": [],
        "red_flags": [],
        "locations_mentioned": [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _api(profile_flat: dict, parsed: dict) -> int:
    return _api_heuristic(profile_flat, parsed, _JOB_REMOTE, is_reloc=False)


def _agent(profile_agent: dict, parsed: dict) -> int:
    sys.path.insert(0, _AGENT_DIR)
    try:
        import main as agent_main
        import scoring as _agent_scoring
        agent_main._load_heuristic_config(copy.deepcopy(profile_agent))
        job = {"title": "Senior PM", "company": "AcmeCo", "location": "Remote", "parsed": parsed}
        return _agent_scoring.heuristic_score(job)
    finally:
        if _AGENT_DIR in sys.path:
            sys.path.remove(_AGENT_DIR)


# ---------------------------------------------------------------------------
# TestCrossSystemLocationScoring — absolute parity
# Both systems must give the same score for each restriction scenario.
# Uses MINIMAL profile (equivalent in both systems).
# ---------------------------------------------------------------------------


class TestCrossSystemLocationScoring:
    """API and agent produce identical heuristic scores for the same input."""

    def _both(self, restriction: str | None) -> tuple[int, int]:
        parsed = _make_parsed(restriction)
        return (
            _api(_PROFILE_MINIMAL_FLAT, parsed),
            _agent(_PROFILE_MINIMAL_AGENT, parsed),
        )

    def test_global_remote_no_restriction(self):
        """No restriction → +10 location, 0 penalty. Both systems agree."""
        api, agent = self._both(None)
        assert api == agent, f"API={api} vs agent={agent} for unrestricted remote"

    def test_eligible_restriction_spain(self):
        """'Spain only' → user is eligible (+8 location, 0 penalty). Both systems agree."""
        api, agent = self._both("Spain only")
        assert api == agent, f"API={api} vs agent={agent} for Spain restriction"

    def test_ineligible_restriction_us_only(self):
        """'United States only' → ineligible (+2 location, -20 penalty). Both systems agree."""
        api, agent = self._both("United States only")
        assert api == agent, f"API={api} vs agent={agent} for US-only restriction"

    def test_timezone_only_restriction_not_penalised(self):
        """'CET timezone hours' → pure timezone, NOT a country barrier. Both systems agree."""
        api, agent = self._both("CET timezone hours")
        assert api == agent, f"API={api} vs agent={agent} for CET timezone restriction"

    def test_eu_restriction_eligible_for_bcn_user(self):
        """'EU only' → user is in EU → eligible (+8 location, 0 penalty). Both systems agree."""
        api, agent = self._both("EU only")
        assert api == agent, f"API={api} vs agent={agent} for EU-only restriction"


# ---------------------------------------------------------------------------
# TestCrossSystemPenaltyArithmetic — delta tests
# Uses RICH profile (domain=15+seniority=15=30 base) to avoid clamping.
# Both systems must show the same score delta for restricted vs unrestricted.
# ---------------------------------------------------------------------------


class TestCrossSystemPenaltyArithmetic:
    """Score deltas are identical between API and agent."""

    def test_ineligible_score_is_unrestricted_minus_28(self):
        """US-only (ineligible) = unrestricted - 28 (location -8 + penalty -20). Both systems."""
        parsed_global = _make_parsed(None)
        parsed_us = _make_parsed("United States only")

        api_global = _api(_PROFILE_RICH_FLAT, parsed_global)
        api_us = _api(_PROFILE_RICH_FLAT, parsed_us)
        agent_global = _agent(_PROFILE_RICH_AGENT, parsed_global)
        agent_us = _agent(_PROFILE_RICH_AGENT, parsed_us)

        assert api_global - api_us == 28, f"API diff={api_global - api_us} (expected 28)"
        assert agent_global - agent_us == 28, f"Agent diff={agent_global - agent_us} (expected 28)"

    def test_eligible_restriction_score_is_unrestricted_minus_2(self):
        """Spain-only (eligible) = unrestricted - 2 (location +8 vs +10). Both systems."""
        parsed_global = _make_parsed(None)
        parsed_spain = _make_parsed("Spain")

        api_global = _api(_PROFILE_RICH_FLAT, parsed_global)
        api_spain = _api(_PROFILE_RICH_FLAT, parsed_spain)
        agent_global = _agent(_PROFILE_RICH_AGENT, parsed_global)
        agent_spain = _agent(_PROFILE_RICH_AGENT, parsed_spain)

        assert api_global - api_spain == 2, f"API diff={api_global - api_spain} (expected 2)"
        assert agent_global - agent_spain == 2, f"Agent diff={agent_global - agent_spain} (expected 2)"

    def test_timezone_restriction_same_as_no_restriction(self):
        """Timezone-only restriction → same score as unrestricted. Both systems."""
        parsed_global = _make_parsed(None)
        parsed_cet = _make_parsed("CET timezone hours")

        api_global = _api(_PROFILE_RICH_FLAT, parsed_global)
        api_cet = _api(_PROFILE_RICH_FLAT, parsed_cet)
        agent_global = _agent(_PROFILE_RICH_AGENT, parsed_global)
        agent_cet = _agent(_PROFILE_RICH_AGENT, parsed_cet)

        assert api_global == api_cet, f"API: global={api_global} != cet={api_cet} (should be equal)"
        assert agent_global == agent_cet, f"Agent: global={agent_global} != cet={agent_cet} (should be equal)"
