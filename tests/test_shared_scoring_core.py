"""Tests for shared/scoring_core.py — single source of truth for scoring logic.

Each class corresponds to one refactor step (1.1–1.4).
Run with: pytest tests/test_shared_scoring_core.py -x
"""


# ─── Step 1.1 ────────────────────────────────────────────────────────────────


class TestInferDomain:
    """1.1: infer_domain() detects domain from job parsed fields."""

    def test_data_keywords(self):
        from shared.scoring_core import infer_domain

        parsed = {
            "domain": "other",
            "responsibilities_summary": "Build a data platform with event tracking pipelines",
            "must_have_skills": [],
            "technical_stack": [],
        }
        assert infer_domain(parsed) == "data"

    def test_ai_ml_keywords(self):
        from shared.scoring_core import infer_domain

        parsed = {
            "domain": "other",
            "responsibilities_summary": "Train machine learning models and deploy them",
            "must_have_skills": [],
            "technical_stack": [],
        }
        assert infer_domain(parsed) == "ai_ml"

    def test_non_other_domain_passthrough(self):
        from shared.scoring_core import infer_domain

        parsed = {"domain": "fintech", "responsibilities_summary": ""}
        assert infer_domain(parsed) == "fintech"

    def test_no_keywords_returns_other(self):
        from shared.scoring_core import infer_domain

        parsed = {
            "domain": "other",
            "responsibilities_summary": "Manage stakeholders and write PRDs",
            "must_have_skills": [],
            "technical_stack": [],
        }
        assert infer_domain(parsed) == "other"

    def test_domain_constants_exported(self):
        from shared.scoring_core import DOMAIN_KEYWORDS, DOMAIN_ALIASES, VALID_DOMAINS

        assert "data" in DOMAIN_KEYWORDS
        assert "ai_ml" in DOMAIN_KEYWORDS
        assert "ia" in DOMAIN_ALIASES
        assert DOMAIN_ALIASES["ia"] == "ai_ml"
        assert "data" in VALID_DOMAINS
        assert "other" in VALID_DOMAINS
        assert len(VALID_DOMAINS) == 30


# ─── Step 1.2 ────────────────────────────────────────────────────────────────


class TestGradeToPoints:
    """1.2: grade_to_points() maps A/B/C grades to integers."""

    def test_grade_a(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points("A") == 20

    def test_grade_b(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points("B") == 12

    def test_grade_c(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points("C") == 5

    def test_grade_none_returns_default(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points(None) == 10

    def test_grade_none_custom_default(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points(None, default=0) == 0

    def test_grade_case_insensitive(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points("a") == 20
        assert grade_to_points("b") == 12

    def test_grade_unknown_returns_default(self):
        from shared.scoring_core import grade_to_points

        assert grade_to_points("X") == 10

    def test_grade_points_constant(self):
        from shared.scoring_core import GRADE_POINTS

        assert GRADE_POINTS == {"A": 20, "B": 12, "C": 5}


class TestIsPureTimezone:
    """1.2: is_pure_timezone() distinguishes timezone vs country restrictions."""

    def test_cet_is_pure_timezone(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("CET") is True

    def test_utc_offset_is_pure_timezone(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("UTC+2 timezone hours") is True

    def test_emea_hours_is_pure_timezone(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("EMEA hours") is True

    def test_germany_is_not_timezone(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("Germany only") is False

    def test_us_only_is_not_timezone(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("Must be based in the United States") is False

    def test_empty_string_is_false(self):
        from shared.scoring_core import is_pure_timezone

        assert is_pure_timezone("") is False


# ─── Step 1.3 ────────────────────────────────────────────────────────────────


class TestComputeEligibilityPenalty:
    """1.3: compute_eligibility_penalty() returns -20 when user is ineligible."""

    def _make_parsed(self, loc_type="remote", restriction=None, locations_mentioned=None):
        return {
            "location_type": loc_type,
            "remote_restriction": restriction,
            "locations_mentioned": locations_mentioned or [],
        }

    def test_remote_no_restriction_no_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction=None)
        result = compute_eligibility_penalty(["barcelona"], ["eu"], "b", parsed, {})
        assert result == 0

    def test_remote_restricted_user_eligible_no_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction="Spain only")
        result = compute_eligibility_penalty(["barcelona"], ["eu"], "b", parsed, {})
        assert result == 0

    def test_remote_restricted_user_ineligible_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction="Must be based in the United States")
        result = compute_eligibility_penalty(["barcelona"], ["eu"], "b", parsed, {})
        assert result == -20

    def test_remote_pure_timezone_no_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction="CET timezone only")
        result = compute_eligibility_penalty(["barcelona"], ["eu"], "b", parsed, {})
        assert result == 0

    def test_loc_pref_d_no_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction="Netherlands only")
        result = compute_eligibility_penalty(["barcelona"], ["eu"], "d", parsed, {})
        assert result == 0

    def test_eu_region_restriction_eu_user_no_penalty(self):
        from shared.scoring_core import compute_eligibility_penalty

        parsed = self._make_parsed("remote", restriction="EU only, remote")
        result = compute_eligibility_penalty(["barcelona"], ["eu", "eea"], "b", parsed, {})
        assert result == 0


# ─── Step 1.4 ────────────────────────────────────────────────────────────────


class TestHeuristicScore:
    """1.4: heuristic_score() combines all dimensions into 0-100 score."""

    def _make_profile(self, **overrides):
        base = {
            "domains": {"data": 15, "saas": 10},
            "seniority": {"principal": 15, "senior": 8},
            "home_locations": ["barcelona", "spain"],
            "home_regions": ["eu", "eea"],
            "location_preference": "b",
            "country_weights": {"spain": 10, "remote": 10},
            "languages": [],
            "company_type_weights": {},
        }
        base.update(overrides)
        return base

    def _make_parsed(self, **overrides):
        base = {
            "domain": "data",
            "seniority": "principal",
            "location_type": "remote",
            "remote_restriction": None,
            "locations_mentioned": [],
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "",
            "red_flags": [],
        }
        base.update(overrides)
        return base

    def test_strong_fit_remote_data_principal(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        parsed = self._make_parsed()
        job = {"location": "Remote, Europe"}
        # domain(15) + seniority(15) + location(10) + country(remote=10) = 50
        score = heuristic_score(profile, parsed, job)
        assert score == 50

    def test_skill_score_added(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        parsed = self._make_parsed()
        job = {"location": "Remote, Europe"}
        base = heuristic_score(profile, parsed, job, skill_score=0)
        with_skills = heuristic_score(profile, parsed, job, skill_score=16)
        assert with_skills == base + 16

    def test_domain_override(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        parsed = self._make_parsed(domain="other")  # would give 0 without override
        job = {"location": "Remote"}
        score_override = heuristic_score(profile, parsed, job, domain_override="data")
        score_no_override = heuristic_score(profile, parsed, job, domain_override=None)
        assert score_override > score_no_override  # override correctly applies data(15)

    def test_missing_profile_keys_graceful(self):
        from shared.scoring_core import heuristic_score

        # Minimal profile — missing optional keys
        profile = {"domains": {}, "seniority": {}, "home_locations": [], "home_regions": []}
        parsed = self._make_parsed()
        job = {}
        score = heuristic_score(profile, parsed, job)
        assert 0 <= score <= 100

    def test_eligibility_penalty_applied(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        parsed_restricted = self._make_parsed(remote_restriction="Must be based in the United States")
        parsed_open = self._make_parsed(remote_restriction=None)
        job = {"location": "Remote"}
        score_restricted = heuristic_score(profile, parsed_restricted, job)
        score_open = heuristic_score(profile, parsed_open, job)
        # penalty(-20) + location(-8) + country_weight_loss(-10, remote key not injected) = -38
        assert score_restricted == score_open - 38

    def test_red_flags_reduce_score(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        job = {"location": "Remote"}
        clean = heuristic_score(profile, self._make_parsed(red_flags=[]), job)
        flagged = heuristic_score(profile, self._make_parsed(red_flags=["requires enterprise sales experience"]), job)
        assert flagged == clean - 5

    def test_score_clamped_to_zero(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile(country_weights={})
        parsed = self._make_parsed(
            domain="other",
            seniority="intern",  # not in profile → 0
            location_type="onsite",
            remote_restriction=None,
            locations_mentioned=["new york"],
            red_flags=["flag1", "flag2", "flag3"],
        )
        job = {"location": "New York, NY"}
        score = heuristic_score(profile, parsed, job)
        assert score >= 0

    def test_score_clamped_to_hundred(self):
        from shared.scoring_core import heuristic_score

        profile = self._make_profile()
        # Pass enormous skill_score to force clamping
        score = heuristic_score(profile, self._make_parsed(), {"location": "Remote"}, skill_score=200)
        assert score == 100
