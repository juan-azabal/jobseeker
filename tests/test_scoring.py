"""Tests for api/scoring.py: heuristic scoring, tier computation, domain inference."""

from api.scoring import (
    _compute_seniority_weights,
    _infer_domain,
    compute_tier,
    heuristic_score,
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
        assert _infer_domain(p) == "ml"


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
        parsed_bad = _make_parsed(domain="healthcare")
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
            domain="healthcare",
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
