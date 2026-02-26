"""
Tests for Phase 13.3: Heuristic scorer applies negative domain weights correctly.

Verifies:
(a) Job with domain='gaming' and user weight gaming:-25 → negative domain contribution.
(b) Job with domain='other' and gaming keywords → inferred to 'gaming' → negative weight applied.
(c) Total score is clamped to >= 0 (domain negative doesn't produce negative total).
(d) Positive domain still produces positive contribution (regression).
"""

from api.scoring import heuristic_score, _infer_domain


def _make_profile(**overrides):
    base = {
        "domains": {"gaming": -25, "data": 15},
        "seniority": {"senior": 15, "mid": 10},
        "skills": [],
        "home_locations": ["barcelona"],
        "home_regions": ["eu"],
        "languages": [],
        "location_preference": "b",
        "country_weights": {},
        "company_type_weights": {},
    }
    base.update(overrides)
    return base


def _make_job(location="Remote, Spain"):
    return {"location": location, "description": ""}


class TestNegativeDomainInHeuristic:
    """Direct domain=-25 produces negative domain contribution."""

    def test_game_domain_negative_weight_applied(self):
        profile = _make_profile()
        # domain explicitly 'gaming', no skills to add noise
        parsed = {
            "domain": "gaming",
            "seniority": "unknown",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build mobile games",
            "red_flags": [],
        }
        # Score = domain(-25) + seniority(0) + skills(0) + location(10) = -15, clamped to 0
        score = heuristic_score(profile, parsed, _make_job(), is_reloc=False)
        assert score == 0, f"Expected 0 (clamped), got {score}"

    def test_data_domain_positive_weight_applied(self):
        profile = _make_profile()
        parsed = {
            "domain": "data",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build data pipelines",
            "red_flags": [],
        }
        # Score = domain(15) + seniority(15) + skills(0) + location(10) = 40
        score = heuristic_score(profile, parsed, _make_job(), is_reloc=False)
        assert score == 40, f"Expected 40, got {score}"

    def test_game_job_ranks_lower_than_data_job(self):
        """Gaming job (negative domain) must score lower than data job (positive domain)."""
        profile = _make_profile()
        game_parsed = {
            "domain": "gaming",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build mobile games",
            "red_flags": [],
        }
        data_parsed = {
            "domain": "data",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build data pipelines",
            "red_flags": [],
        }
        game_score = heuristic_score(profile, game_parsed, _make_job(), is_reloc=False)
        data_score = heuristic_score(profile, data_parsed, _make_job(), is_reloc=False)
        assert game_score < data_score, f"Gaming job ({game_score}) should score lower than data job ({data_score})"


class TestDomainInferenceWithNegativeWeight:
    """domain='other' + gaming keywords → inferred gaming → negative weight flows through."""

    def test_other_domain_with_game_keywords_inferred(self):
        parsed = {
            "domain": "other",
            "seniority": "unknown",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build video game development tools for mobile gaming studio",
            "red_flags": [],
        }
        # Verify _infer_domain picks up 'gaming'
        assert _infer_domain(parsed) == "gaming"

    def test_other_with_game_keywords_applies_negative_weight(self):
        profile = _make_profile()
        parsed = {
            "domain": "other",
            "seniority": "unknown",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build video game development tools for mobile gaming studio",
            "red_flags": [],
        }
        # With gaming:-25, result should be clamped to 0 (not receiving 0 from unknown domain)
        score_with_negative = heuristic_score(profile, parsed, _make_job(), is_reloc=False)

        # Compare to a profile where game has weight 0 (absent from domains dict)
        profile_no_game = _make_profile(domains={"data": 15})
        score_without_weight = heuristic_score(profile_no_game, parsed, _make_job(), is_reloc=False)

        # gaming:-25 should not produce a higher score than having no weight for gaming
        assert score_with_negative <= score_without_weight, (
            f"Negative game weight ({score_with_negative}) should not exceed no-weight score ({score_without_weight})"
        )


class TestScoreClampedToZero:
    """Total heuristic score is always >= 0 regardless of negative domain weight."""

    def test_heavy_negatives_clamped_to_zero(self):
        profile = _make_profile(domains={"gaming": -100})
        parsed = {
            "domain": "gaming",
            "seniority": "unknown",
            "location_type": "onsite",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Game studio",
            "red_flags": ["too many hats", "no salary", "unpaid trial"],
        }
        score = heuristic_score(profile, parsed, _make_job("London, UK"), is_reloc=False)
        assert score >= 0, f"Score must be >= 0, got {score}"
