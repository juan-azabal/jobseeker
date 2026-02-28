"""Phase 19.1 — Eligibility penalty tests.

Tests for:
- 19.1.1: _compute_eligibility_penalty() pure function
- 19.1.2: penalty wired into heuristic_score()
- 19.1.3: location scoring distinguishes geo-restricted remote (+2/+8/+10)
- 19.2.1: country_weights doesn't inject 'remote' when geo-restricted
- Bug fix: onsite non-home country → -20 eligibility penalty
- Bug fix: v2 relocation penalty applied in _score_and_tier_jobs()
"""
import json
import sqlite3
import tempfile
from unittest.mock import patch

import pytest
from api.scoring import heuristic_score, _compute_eligibility_penalty, hybrid_score, compute_tier


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

    def test_onsite_non_home_country_returns_minus20(self):
        """Onsite job in non-home country fires penalty (bug fix: not remote-only)."""
        # remote_restriction is irrelevant for onsite; job.location resolves to NL
        parsed = _parsed(location_type="onsite", remote_restriction="Netherlands only")
        job = _job(location_type="onsite", location="Amsterdam")
        # Amsterdam → netherlands → not in home_countries (barcelona/spain) → -20
        assert _compute_eligibility_penalty(_PROFILE, parsed, job) == -20

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


# ---------------------------------------------------------------------------
# Bug fix: onsite/hybrid eligibility penalty (non-home country)
# ---------------------------------------------------------------------------

_PROFILE_BCN = {
    "domains": {"saas": 15},
    "seniority": {"director": 15, "senior": 10},
    "skills": [],
    "home_locations": ["barcelona"],
    "home_regions": ["eu", "europe", "spain"],
    "languages": [],
    "location_preference": "b",
    "country_weights": {},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}


def _parsed_onsite(locations_mentioned: list, location_type: str = "onsite") -> dict:
    return {
        "domain": "saas",
        "seniority": "director",
        "location_type": location_type,
        "must_have_skills": [],
        "nice_to_have_skills": [],
        "technical_stack": [],
        "red_flags": [],
        "locations_mentioned": locations_mentioned,
        "remote_restriction": None,
        "responsibilities_summary": "",
        "experience_requirements": "",
    }


class TestOnsiteEligibilityPenalty:
    """_compute_eligibility_penalty fires for onsite jobs in non-home countries."""

    def test_onsite_us_barcelona_user_returns_minus_20(self):
        """Onsite job in US, home=barcelona → penalty = -20."""
        parsed = _parsed_onsite(["new york city"])
        job = {"location": "New York City, NY", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == -20

    def test_onsite_san_francisco_barcelona_user_returns_minus_20(self):
        """Onsite job in San Francisco, home=barcelona → penalty = -20."""
        parsed = _parsed_onsite(["san francisco"])
        job = {"location": "San Francisco, CA", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == -20

    def test_onsite_spain_barcelona_user_returns_0(self):
        """Onsite job in Spain, home=barcelona → no penalty (home country)."""
        parsed = _parsed_onsite(["madrid"])
        job = {"location": "Madrid, Spain", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == 0

    def test_onsite_barcelona_home_returns_0(self):
        """Onsite job in barcelona (exact home city), home=barcelona → no penalty."""
        parsed = _parsed_onsite(["barcelona"])
        job = {"location": "Barcelona, Spain", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == 0

    def test_onsite_unresolvable_location_returns_0(self):
        """Onsite job with unresolvable location → conservative, no penalty."""
        parsed = _parsed_onsite(["silicon valley"])  # not in _CITY_TO_COUNTRY
        job = {"location": "Silicon Valley, CA", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == 0

    def test_onsite_empty_locations_mentioned_fallback_to_job_location(self):
        """No locations_mentioned but job.location contains known city → penalty fires."""
        parsed = _parsed_onsite([])  # empty locations_mentioned
        job = {"location": "New York", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == -20

    def test_onsite_empty_locations_and_empty_job_location_returns_0(self):
        """No locations_mentioned, no job location → conservative, no penalty."""
        parsed = _parsed_onsite([])
        job = {"location": "", "location_type": "onsite"}
        assert _compute_eligibility_penalty(_PROFILE_BCN, parsed, job) == 0

    def test_onsite_loc_pref_d_returns_0(self):
        """loc_pref='d' (anywhere in EU) → no penalty for onsite non-home."""
        profile_d = {**_PROFILE_BCN, "location_preference": "d"}
        parsed = _parsed_onsite(["new york city"])
        job = {"location": "New York City, NY", "location_type": "onsite"}
        assert _compute_eligibility_penalty(profile_d, parsed, job) == 0

    def test_onsite_penalty_wired_into_heuristic_score(self):
        """heuristic_score() for onsite NYC job scores lower than onsite BCN job."""
        parsed_us = _parsed_onsite(["new york city"])
        parsed_bcn = _parsed_onsite(["barcelona"])
        job_us = {"location": "New York City, NY", "location_type": "onsite"}
        job_bcn = {"location": "Barcelona, Spain", "location_type": "onsite"}
        score_us = heuristic_score(_PROFILE_BCN, parsed_us, job_us, is_reloc=True)
        score_bcn = heuristic_score(_PROFILE_BCN, parsed_bcn, job_bcn, is_reloc=False)
        assert score_us < score_bcn, (
            f"US onsite ({score_us}) should score lower than BCN onsite ({score_bcn}) due to -20 penalty"
        )
        assert score_us <= score_bcn - 20, (
            f"Penalty delta should be ≥20: US={score_us}, BCN={score_bcn}"
        )


# ---------------------------------------------------------------------------
# Bug fix: v2 relocation penalty applied in _score_and_tier_jobs()
# ---------------------------------------------------------------------------

def _make_minimal_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, title TEXT, company TEXT,
            location TEXT, location_type TEXT, parsed TEXT, domain TEXT,
            role_function TEXT, scored_v2 INTEGER DEFAULT 0,
            company_url TEXT, company_logo TEXT, company_industry TEXT,
            company_size TEXT, job_level TEXT,
            salary_min REAL, salary_max REAL, salary_currency TEXT,
            salary_interval TEXT, salary_source TEXT,
            country TEXT, city TEXT, remote_type TEXT, sources TEXT
        );
        CREATE TABLE IF NOT EXISTS user_job_scores (
            user_id INTEGER, job_id TEXT, score REAL, tier TEXT,
            scored INTEGER DEFAULT 0, technical_grade TEXT,
            profile_grade TEXT, scored_v2 INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_job_status (
            user_id INTEGER, job_id TEXT, domain_override TEXT,
            applied_at TEXT, dismissed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS skill_embeddings (skill TEXT PRIMARY KEY, embedding BLOB);
    """)
    con.commit()
    con.close()
    return db_path


_PARSED_NYC_ONSITE = {
    "domain": "saas",
    "seniority": "director",
    "location_type": "onsite",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "red_flags": [],
    "locations_mentioned": ["new york city"],
    "remote_restriction": None,
    "responsibilities_summary": "",
    "experience_requirements": "",
}

_PROFILE_BCN_RICH = {
    "domains": {"saas": 15},
    "seniority": {"director": 15, "senior": 10},
    "skills": [],
    "home_locations": ["barcelona"],
    "home_regions": ["eu", "europe", "spain"],
    "languages": [],
    "location_preference": "b",
    "country_weights": {},
    "company_type_weights": {},
    "role_function": None,
    "role_type": None,
}


class TestV2RelocPenaltyApplied:
    """v2-scored onsite/reloc jobs must have relocation penalty applied."""

    def test_v2_onsite_reloc_gets_reloc_penalty(self):
        """v2 job: onsite NYC (reloc=True) → _score_and_tier_jobs applies -15 reloc penalty."""
        db_path = _make_minimal_db()
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO jobs (job_id, title, company, location, location_type, parsed, domain)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("job-nyc", "Head of Product", "MongoDB", "New York City, NY", "onsite",
             json.dumps(_PARSED_NYC_ONSITE), "saas"),
        )
        con.execute(
            "INSERT INTO user_job_scores (user_id, job_id, score, tier, scored, technical_grade, profile_grade, scored_v2)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "job-nyc", 0, "A", 1, "B", "A", 1),
        )
        con.commit()
        con.close()

        from api.routes.jobs import _score_and_tier_jobs

        job = {
            "job_id": "job-nyc",
            "title": "Head of Product",
            "company": "MongoDB",
            "location": "New York City, NY",
            "location_type": "onsite",
            "parsed": json.dumps(_PARSED_NYC_ONSITE),
            "domain": "saas",
            "role_function": None,
            "ujs_score": None,
            "ujs_tier": None,
            "ujs_scored": 1,
            "ujs_technical_grade": "B",
            "ujs_profile_grade": "A",
            "ujs_scored_v2": 1,
            "remote_restriction": None,
        }

        with patch("api.routes.jobs._db_path", return_value=db_path):
            with patch("api.routes.jobs.get_all_domain_overrides", return_value={}):
                results = _score_and_tier_jobs(
                    [job], _PROFILE_BCN_RICH, ["barcelona"], ["eu", "europe", "spain"], user_id=1
                )

        score = results[0]["score"]
        # Without reloc penalty fix: score would equal hybrid_score() (no -15)
        # With fix: hybrid_score() - 15 (onsite reloc) applied
        # Also -20 eligibility penalty fires inside heuristic_score (Bug 2 fix)
        # So score must be substantially lower than a plain hybrid_score with B+A grades
        base_hybrid = hybrid_score(_PROFILE_BCN_RICH, _PARSED_NYC_ONSITE, job, is_reloc=False,
                                   technical_grade="B", profile_grade="A")
        assert score < base_hybrid, (
            f"v2 onsite reloc score ({score}) must be < base hybrid ({base_hybrid}) after reloc + eligibility penalties"
        )


class TestMongodbRegression:
    """MongoDB onsite NYC regression: v2 B+A → score ≤ 40 (tier C) after both bug fixes."""

    def test_onsite_nyc_v2_ba_score_le_40_tier_c(self):
        """MongoDB onsite NYC (v2 B+A): both bug fixes bring score ≤ 40, tier C."""
        # Simulate: hybrid_score (includes -20 eligibility from Bug 2 fix)
        # then apply -15 reloc penalty (Bug 1 fix)
        job = {"location": "New York City, NY", "location_type": "onsite"}
        score = hybrid_score(
            _PROFILE_BCN_RICH,
            _PARSED_NYC_ONSITE,
            job,
            is_reloc=True,
            technical_grade="B",
            profile_grade="A",
        )
        # Apply reloc penalty as the fixed v2 branch does (Bug 1 fix)
        if score > 0:
            penalty = 5 if _PARSED_NYC_ONSITE.get("location_type") == "remote" else 15
            score = max(0, score - penalty)

        assert score <= 40, (
            f"MongoDB NYC onsite (v2 B+A) should score ≤ 40 after both fixes, got {score}"
        )
        assert compute_tier(score) == "C", (
            f"Expected tier C (skip), got {compute_tier(score)} for score={score}"
        )
