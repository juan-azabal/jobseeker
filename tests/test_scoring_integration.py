"""
Integration tests for Phase 13.6: Domain scoring regression suite.

Verifies that the full domain scoring pipeline (enum match → keyword override →
semantic fallback) produces correct ranking outcomes with mixed positive/negative
domain weights.

Expected ranking (highest to lowest):
  data_job (domain=data, weight=+15) > saas_job (domain=saas, weight=+10) >
  generic_job (domain=other, no keywords) > game_job (domain=game, weight=-25)
"""

from api.scoring import heuristic_score


# ---------------------------------------------------------------------------
# Shared profile with mixed positive and negative domain weights
# ---------------------------------------------------------------------------

MIXED_PROFILE = {
    "domains": {
        "data": 15,
        "saas": 10,
        "gaming": -25,
        "edtech": -10,
    },
    "seniority": {"senior": 15, "mid": 10, "staff": 12},
    "skills": ["python", "sql"],
    "home_locations": ["barcelona", "spain"],
    "home_regions": ["eu"],
    "languages": ["es"],
    "location_preference": "b",
    "country_weights": {},
    "company_type_weights": {},
}


def _make_job(company: str, location: str = "Remote") -> dict:
    return {"company": company, "location": location, "description": ""}


# ---------------------------------------------------------------------------
# Fixture jobs
# ---------------------------------------------------------------------------

DATA_JOB_PARSED = {
    "domain": "data",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": ["python", "sql"],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Build data platform and pipelines",
    "red_flags": [],
}

SAAS_JOB_PARSED = {
    "domain": "saas",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Lead SaaS product roadmap for B2B clients",
    "red_flags": [],
}

GAME_JOB_PARSED = {
    "domain": "gaming",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Product manager for mobile gaming studio",
    "red_flags": [],
}

GAME_JOB_AS_OTHER_PARSED = {
    # Parsed with old enum (domain='other') but has game keywords
    "domain": "other",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Product manager for video game development studio",
    "red_flags": [],
}

GENERIC_JOB_PARSED = {
    "domain": "other",
    "seniority": "senior",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Strategy and operations at a consulting firm",
    "red_flags": [],
}

CLIMATE_JOB_PARSED = {
    "domain": "climate",
    "seniority": "mid",
    "location_type": "remote",
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "technical_stack": [],
    "responsibilities_summary": "Carbon offset marketplace product",
    "red_flags": [],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDomainRankingOrder:
    """Games rank below data/saas; data ranks highest."""

    def _score(self, parsed: dict, company: str = "Acme") -> int:
        return heuristic_score(MIXED_PROFILE, parsed, _make_job(company), is_reloc=False, db_path=None)

    def test_data_job_scores_highest(self):
        data_score = self._score(DATA_JOB_PARSED, "DataCo")
        saas_score = self._score(SAAS_JOB_PARSED, "SaasCo")
        assert data_score > saas_score, f"Data job ({data_score}) should outscore SaaS job ({saas_score})"

    def test_game_job_ranks_below_saas(self):
        saas_score = self._score(SAAS_JOB_PARSED, "SaasCo")
        game_score = self._score(GAME_JOB_PARSED, "Riot Games")
        assert game_score < saas_score, f"Game job ({game_score}) should rank below SaaS job ({saas_score})"

    def test_game_job_as_other_also_penalized(self):
        """Old-enum game job (domain='other' + keywords) gets penalized same as enum game."""
        game_enum_score = self._score(GAME_JOB_PARSED, "Riot Games")
        game_other_score = self._score(GAME_JOB_AS_OTHER_PARSED, "Riot Games")
        saas_score = self._score(SAAS_JOB_PARSED, "SaasCo")
        # Both should rank below SaaS
        assert game_other_score < saas_score, (
            f"Game-as-other job ({game_other_score}) should rank below SaaS ({saas_score})"
        )
        # And comparable to each other (same domain penalty applied)
        assert abs(game_enum_score - game_other_score) <= 5, (
            f"game enum ({game_enum_score}) and game-as-other ({game_other_score}) should produce similar scores"
        )

    def test_negative_domain_score_clamped_nonnegative(self):
        game_score = self._score(GAME_JOB_PARSED, "Riot Games")
        assert game_score >= 0, f"Score must be >= 0, got {game_score}"


class TestNewDomainClassification:
    """New enum values are correctly classified and scored."""

    def _score(self, parsed: dict) -> int:
        return heuristic_score(MIXED_PROFILE, parsed, _make_job("Acme"), is_reloc=False, db_path=None)

    def test_climate_job_neutral_score(self):
        # climate not in MIXED_PROFILE domains → weight 0 → neutral score
        climate_score = self._score(CLIMATE_JOB_PARSED)
        saas_score = self._score(SAAS_JOB_PARSED)
        assert climate_score < saas_score, (
            f"Climate job ({climate_score}) without domain weight should score "
            f"less than SaaS job ({saas_score}) with weight +10"
        )

    def test_edtech_job_penalized(self):
        """edtech:-10 in profile → edtech job penalized."""
        edtech_parsed = {
            "domain": "edtech",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Build e-learning platform",
            "red_flags": [],
        }
        edtech_score = self._score(edtech_parsed)
        saas_score = self._score(SAAS_JOB_PARSED)
        assert edtech_score < saas_score, (
            f"Edtech job ({edtech_score}) with weight -10 should score "
            f"less than SaaS job ({saas_score}) with weight +10"
        )


class TestSkillsAndDomainInteraction:
    """Skills boost doesn't compensate for a large negative domain penalty."""

    def test_game_job_with_skills_still_ranks_below_saas_no_skills(self):
        """Even with skill match, game job can't outscore saas job with no skills."""
        profile_with_game_skills = {
            **MIXED_PROFILE,
            "skills": ["python", "sql", "unity", "game engine"],
        }
        game_parsed_with_skills = {
            "domain": "gaming",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": ["unity", "game engine"],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "Game PM at mobile gaming studio",
            "red_flags": [],
        }
        saas_no_skills = {
            "domain": "saas",
            "seniority": "senior",
            "location_type": "remote",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "SaaS product roadmap",
            "red_flags": [],
        }

        game_score = heuristic_score(
            profile_with_game_skills,
            game_parsed_with_skills,
            _make_job("GameCo"),
            is_reloc=False,
            db_path=None,
        )
        saas_score = heuristic_score(
            profile_with_game_skills,
            saas_no_skills,
            _make_job("SaasCo"),
            is_reloc=False,
            db_path=None,
        )
        # game: -25 + seniority: +15 + skills: +10 + loc: +10 = +10
        # saas: +10 + seniority: +15 + skills: 0 + loc: +10 = +35
        assert game_score < saas_score, (
            f"Game job with skills ({game_score}) should rank below SaaS job without skills ({saas_score})"
        )
