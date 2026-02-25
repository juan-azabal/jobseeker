"""Tests for api/scoring.py: heuristic scoring, tier computation, domain inference."""

from unittest.mock import patch

from api.scoring import (
    _compute_seniority_weights,
    _infer_domain,
    compute_tier,
    heuristic_score,
    precompute_skill_lookup,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(**overrides):
    """Create a minimal profile dict for heuristic_score()."""
    base = {
        "domains": {"data": 15, "saas": 8},
        "seniority": {"senior": 15, "staff": 10, "mid": 6},
        "skills": ["python", "sql", "kafka", "snowflake"],
        "home_locations": ["barcelona", "spain"],
        "home_regions": ["eu"],
        "languages": ["es", "en"],
        "location_preference": "b",
        "country_weights": {},
        "company_type_weights": {},
    }
    base.update(overrides)
    return base


def _make_parsed(**overrides):
    """Create a minimal parsed job dict."""
    base = {
        "seniority": "senior",
        "location_type": "remote",
        "domain": "data",
        "must_have_skills": ["python", "sql"],
        "nice_to_have_skills": ["kafka"],
        "technical_stack": ["snowflake", "dbt"],
        "responsibilities_summary": "Build data pipelines.",
        "red_flags": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# compute_tier
# ---------------------------------------------------------------------------


class TestComputeTier:
    def test_tier_a_boundary(self):
        assert compute_tier(50) == "A"

    def test_tier_a_high(self):
        assert compute_tier(100) == "A"

    def test_tier_b_boundary(self):
        assert compute_tier(30) == "B"

    def test_tier_b_high(self):
        assert compute_tier(49) == "B"

    def test_tier_c_boundary(self):
        assert compute_tier(29) == "C"

    def test_tier_c_zero(self):
        assert compute_tier(0) == "C"


# ---------------------------------------------------------------------------
# _compute_seniority_weights
# ---------------------------------------------------------------------------


class TestComputeSeniorityWeightsAPI:
    def test_exact_match(self):
        w = _compute_seniority_weights("senior", "ic")
        assert w["senior"] == 15

    def test_one_off(self):
        w = _compute_seniority_weights("senior", "ic")
        assert w["staff"] == 10
        assert w["mid"] == 10

    def test_two_off(self):
        w = _compute_seniority_weights("senior", "ic")
        assert w["principal"] == 6

    def test_ic_caps_director(self):
        w = _compute_seniority_weights("staff", "ic")
        assert w["director"] <= 4

    def test_management_doesnt_cap(self):
        w = _compute_seniority_weights("director", "management")
        assert w["director"] == 15


# ---------------------------------------------------------------------------
# _infer_domain
# ---------------------------------------------------------------------------


class TestInferDomain:
    def test_keeps_known_domain(self):
        assert _infer_domain({"domain": "data"}) == "data"

    def test_overrides_other_with_keyword(self):
        p = {
            "domain": "other",
            "responsibilities_summary": "Build data pipeline and ETL",
            "must_have_skills": [],
            "technical_stack": [],
        }
        assert _infer_domain(p) == "data"

    def test_other_stays_if_no_keywords(self):
        p = {
            "domain": "other",
            "responsibilities_summary": "General product work",
            "must_have_skills": [],
            "technical_stack": [],
        }
        assert _infer_domain(p) == "other"

    def test_ml_keywords_detected(self):
        p = {
            "domain": "other",
            "responsibilities_summary": "Deploy machine learning models",
            "must_have_skills": [],
            "technical_stack": ["tensorflow"],
        }
        assert _infer_domain(p) == "ai_ml"

    def test_fintech_not_data_for_financial_compliance(self):
        """'compliance analytics platform for financial institutions' → fintech, not data.

        Regression for keyword collision: 'analytics platform' (data keyword) must not
        win over 'financial institution' (fintech keyword) for clearly fintech JDs.
        """
        p = {
            "domain": "other",
            "responsibilities_summary": "compliance analytics platform for financial institutions",
            "must_have_skills": [],
            "technical_stack": [],
        }
        result = _infer_domain(p)
        assert result == "fintech", (
            f"Expected 'fintech' for financial compliance JD, got '{result}'"
        )

    def test_hr_tech_for_corporate_training(self):
        """'corporate training management system' → hr_tech.

        Regression for keyword gap: training management systems are HR/L&D tools,
        not AI/ML or edtech (which covers student-facing education).
        """
        p = {
            "domain": "other",
            "responsibilities_summary": "corporate training management system",
            "must_have_skills": [],
            "technical_stack": [],
        }
        result = _infer_domain(p)
        assert result == "hr_tech", (
            f"Expected 'hr_tech' for corporate training JD, got '{result}'"
        )


# ---------------------------------------------------------------------------
# heuristic_score
# ---------------------------------------------------------------------------


class TestHeuristicScore:
    def test_returns_zero_for_empty_parsed(self):
        profile = _make_profile()
        assert heuristic_score(profile, {}, {}, False) == 0

    def test_returns_zero_for_none_parsed(self):
        profile = _make_profile()
        assert heuristic_score(profile, None, {}, False) == 0

    def test_strong_fit_scores_high(self):
        profile = _make_profile()
        parsed = _make_parsed()
        job = {"location": "Remote, Europe"}
        score = heuristic_score(profile, parsed, job, False)
        assert score >= 40

    def test_domain_mismatch_scores_lower(self):
        profile = _make_profile()
        parsed_good = _make_parsed()
        parsed_bad = _make_parsed(domain="healthtech")
        job = {"location": "Remote"}
        score_good = heuristic_score(profile, parsed_good, job, False)
        score_bad = heuristic_score(profile, parsed_bad, job, False)
        assert score_bad < score_good

    def test_red_flags_reduce_score(self):
        profile = _make_profile()
        parsed_clean = _make_parsed()
        parsed_flags = _make_parsed(
            red_flags=["requires relocation", "visa required", "entry level"]
        )
        job = {"location": "Remote"}
        score_clean = heuristic_score(profile, parsed_clean, job, False)
        score_flags = heuristic_score(profile, parsed_flags, job, False)
        assert score_flags < score_clean

    def test_null_red_flags_ignored(self):
        profile = _make_profile()
        parsed_null = _make_parsed(red_flags=["None mentioned", "N/A", "null"])
        parsed_clean = _make_parsed(red_flags=[])
        job = {"location": "Remote"}
        score_null = heuristic_score(profile, parsed_null, job, False)
        score_clean = heuristic_score(profile, parsed_clean, job, False)
        assert score_null == score_clean

    def test_score_clamped_to_0_100(self):
        profile = _make_profile()
        # Many red flags to push negative
        parsed = _make_parsed(
            red_flags=["a", "b", "c", "d", "e", "f"],
            domain="healthtech",
            seniority="mid",
        )
        job = {"location": "Remote"}
        score = heuristic_score(profile, parsed, job, False)
        assert 0 <= score <= 100

    def test_skill_matching_normalizes_hyphens(self):
        profile = _make_profile(skills=["stakeholder-management", "a/b-testing"])
        parsed = _make_parsed(
            must_have_skills=["stakeholder management"],
            nice_to_have_skills=[],
            technical_stack=[],
        )
        job = {"location": "Remote"}
        score = heuristic_score(profile, parsed, job, False)
        # Same job but with a skill that won't match
        profile_nomatch = _make_profile(skills=["nonexistent-skill"])
        score_nomatch = heuristic_score(profile_nomatch, parsed, job, False)
        assert score > score_nomatch

    def test_location_preference_a_favors_remote(self):
        profile = _make_profile(location_preference="a")
        parsed_remote = _make_parsed(location_type="remote")
        parsed_onsite = _make_parsed(location_type="onsite")
        job = {"location": "Remote"}
        s_remote = heuristic_score(profile, parsed_remote, job, False)
        s_onsite = heuristic_score(profile, parsed_onsite, job, False)
        assert s_remote > s_onsite

    def test_seniority_contributes_to_score(self):
        profile = _make_profile()
        parsed_match = _make_parsed(seniority="senior")
        parsed_mismatch = _make_parsed(seniority="junior")
        job = {"location": "Remote"}
        score_match = heuristic_score(profile, parsed_match, job, False)
        score_mismatch = heuristic_score(profile, parsed_mismatch, job, False)
        assert score_match > score_mismatch

    def test_semantic_skill_matching(self, tmp_path):
        """With semantic matching, 'data analysis' should match 'analytics'."""
        from api.db.init import init_db
        from api.skill_matcher import SkillMatch

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        profile = _make_profile(skills=["data analysis"])
        parsed = _make_parsed(must_have_skills=["analytics"])
        job = {"location": "Remote"}

        # Mock match_skills to return semantic match
        mock_results = [
            SkillMatch(job_skill="analytics", status="matched", user_skill="data analysis", similarity=0.87),
        ]
        with patch("api.scoring.match_skills", return_value=mock_results):
            score = heuristic_score(profile, parsed, job, False, db_path=db_path)

        # Without semantic matching, "data analysis" would NOT match "analytics" (no substring overlap)
        score_no_semantic = heuristic_score(profile, parsed, job, False)
        assert score > score_no_semantic

    def test_partial_match_gives_partial_points(self, tmp_path):
        """Partial matches should give 2 pts for must-have skills."""
        from api.db.init import init_db
        from api.skill_matcher import SkillMatch

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        profile = _make_profile(skills=["javascript"])
        parsed = _make_parsed(must_have_skills=["typescript"])
        job = {"location": "Remote"}

        # Mock match_skills to return partial match
        mock_results = [
            SkillMatch(job_skill="typescript", status="partial", user_skill="javascript", similarity=0.73),
        ]
        with patch("api.scoring.match_skills", return_value=mock_results):
            score = heuristic_score(profile, parsed, job, False, db_path=db_path)

        # Without semantic matching, no substring match → 0 skill points
        score_no_semantic = heuristic_score(profile, parsed, job, False)
        assert score > score_no_semantic

    def test_precompute_skill_lookup_returns_correct_dict(self, tmp_path):
        """precompute_skill_lookup returns dict keyed by normalized job skill."""
        from api.db.init import init_db
        from api.skill_matcher import SkillMatch

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        mock_results = [
            SkillMatch(job_skill="Python", status="matched", user_skill="python", similarity=1.0),
            SkillMatch(job_skill="SQL Server", status="partial", user_skill="sql", similarity=0.75),
        ]
        with patch("api.scoring.match_skills", return_value=mock_results):
            lookup = precompute_skill_lookup(["python", "sql"], ["Python", "SQL Server"], db_path)

        assert "python" in lookup
        assert "sql server" in lookup
        assert lookup["python"].status == "matched"
        assert lookup["sql server"].status == "partial"

    def test_score_skills_with_lookup_matches_without(self, tmp_path):
        """_score_skills with skill_lookup gives same result as semantic matching."""
        from api.db.init import init_db
        from api.skill_matcher import SkillMatch

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        profile = _make_profile(skills=["python", "sql"])
        parsed = _make_parsed(must_have_skills=["python", "analytics"])
        job = {"location": "Remote"}

        # Create a lookup that matches "python" and partially matches "analytics"
        lookup = {
            "python": SkillMatch(job_skill="python", status="matched", user_skill="python", similarity=1.0),
            "analytics": SkillMatch(job_skill="analytics", status="partial", user_skill="sql", similarity=0.72),
        }

        # With lookup
        score_with_lookup = heuristic_score(profile, parsed, job, False, db_path=db_path, skill_lookup=lookup)

        # With direct semantic matching (mocked to return correct results per call)
        must_results = [
            SkillMatch(job_skill="python", status="matched", user_skill="python", similarity=1.0),
            SkillMatch(job_skill="analytics", status="partial", user_skill="sql", similarity=0.72),
        ]

        def mock_match(user_skills, job_skills, db):
            if not job_skills:
                return []
            return [r for r in must_results if r.job_skill in [s.lower() for s in job_skills]]

        with patch("api.scoring.match_skills", side_effect=mock_match):
            score_semantic = heuristic_score(profile, parsed, job, False, db_path=db_path)

        assert score_with_lookup == score_semantic
