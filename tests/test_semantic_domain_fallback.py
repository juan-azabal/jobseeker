"""
Tests for Phase 13.5: Semantic domain fallback when enum + keywords miss.

Verifies:
(a) Job with 'other' domain (no keyword match) + high similarity to 'game' →
    negative score if game weight is negative.
(b) Job matching enum exactly does NOT trigger semantic path.
(c) Low similarity (< 0.75 threshold) → score = 0.
(d) No db_path → semantic path skipped.
"""

from unittest.mock import patch

from api.scoring import _semantic_domain_score, heuristic_score


def _make_profile(**overrides):
    base = {
        "domains": {"game": -25, "data": 15},
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


def _make_parsed(domain: str = "other", summary: str = "") -> dict:
    return {
        "domain": domain,
        "seniority": "unknown",
        "location_type": "remote",
        "must_have_skills": [],
        "nice_to_have_skills": [],
        "technical_stack": [],
        "responsibilities_summary": summary,
        "red_flags": [],
    }


def _make_job(title: str = "Senior PM", company: str = "Riot Games") -> dict:
    return {"title": title, "company": company, "location": "Remote", "description": ""}


# Synthetic embeddings: simple unit vectors with different "directions"
# For testing: game domain and game job point in the same direction
_GAME_VEC = [1.0, 0.0, 0.0]
_DATA_VEC = [0.0, 1.0, 0.0]
_GAME_JOB_VEC = [0.95, 0.1, 0.0]  # cosine ≈ 0.995 with GAME_VEC → ≥ 0.75
_GENERIC_JOB_VEC = [0.1, 0.1, 0.98]  # cosine ≈ 0.14 with GAME_VEC → < 0.75


def _normalize(text: str) -> str:
    return text.strip().lower()


def _make_embedding_map(job_text: str, job_vec: list) -> dict:
    """Return a fake embeddings dict keyed by normalized text."""
    return {
        _normalize(job_text): job_vec,
        "game": _GAME_VEC,
        "data": _DATA_VEC,
    }


class TestSemanticDomainScore:
    """_semantic_domain_score() computes domain score via embedding similarity."""

    def test_high_similarity_negative_weight_returns_negative(self):
        """Riot Games + high sim to 'game' → negative score (game weight -25)."""
        profile = _make_profile()
        parsed = _make_parsed()
        job = _make_job("Senior PM", "Riot Games")
        job_text = "Riot Games other Senior PM"

        with (
            patch("api.embeddings.get_embeddings_batch") as mock_emb,
            patch("api.embeddings.cosine_similarity") as mock_cos,
        ):
            mock_emb.return_value = _make_embedding_map(job_text, _GAME_JOB_VEC)
            # Simulate: game sim = 0.90, data sim = 0.10
            mock_cos.side_effect = lambda a, b: 0.90 if b == _GAME_VEC else 0.10
            score = _semantic_domain_score(profile, parsed, job, db_path="fake.db")

        # score = int(-25 * 0.90) = -22, clamped to -15
        assert score == -15, f"Expected -15 (clamped), got {score}"

    def test_high_similarity_positive_weight_returns_positive(self):
        """Data platform job + high sim to 'data' → positive score."""
        profile = _make_profile()
        parsed = _make_parsed()
        job = _make_job("Senior Data PM", "DataCo")
        job_text = "DataCo other Senior Data PM"

        with (
            patch("api.embeddings.get_embeddings_batch") as mock_emb,
            patch("api.embeddings.cosine_similarity") as mock_cos,
        ):
            mock_emb.return_value = _make_embedding_map(job_text, _DATA_VEC)
            # Simulate: game sim = 0.05, data sim = 0.90
            mock_cos.side_effect = lambda a, b: 0.90 if b == _DATA_VEC else 0.05
            score = _semantic_domain_score(profile, parsed, job, db_path="fake.db")

        # score = int(15 * 0.90) = 13, clamped to [−15, 15] → 13
        assert score == 13, f"Expected 13, got {score}"

    def test_low_similarity_returns_zero(self):
        """Similarity < 0.75 → score = 0."""
        profile = _make_profile()
        parsed = _make_parsed()
        job = _make_job("Strategy Consultant", "McKinsey")
        job_text = "McKinsey other Strategy Consultant"

        with (
            patch("api.embeddings.get_embeddings_batch") as mock_emb,
            patch("api.embeddings.cosine_similarity") as mock_cos,
        ):
            mock_emb.return_value = _make_embedding_map(job_text, _GENERIC_JOB_VEC)
            mock_cos.return_value = 0.40  # below threshold
            score = _semantic_domain_score(profile, parsed, job, db_path="fake.db")

        assert score == 0, f"Expected 0 (below threshold), got {score}"

    def test_no_db_path_returns_zero(self):
        """No db_path → semantic path skipped, returns 0."""
        profile = _make_profile()
        parsed = _make_parsed()
        job = _make_job()
        score = _semantic_domain_score(profile, parsed, job, db_path=None)
        assert score == 0

    def test_empty_domains_returns_zero(self):
        """Profile with no domains → returns 0."""
        profile = _make_profile(domains={})
        parsed = _make_parsed()
        job = _make_job()
        score = _semantic_domain_score(profile, parsed, job, db_path="fake.db")
        assert score == 0


class TestHeuristicScoreSemanticFallback:
    """heuristic_score() triggers semantic fallback when domain='other' + no keyword match."""

    def test_enum_domain_does_not_trigger_semantic_path(self):
        """Job with domain='data' (not 'other') → semantic fallback NOT called."""
        profile = _make_profile()
        parsed = _make_parsed(domain="data")
        job = _make_job("Data PM", "DataCo")

        with patch("api.scoring._semantic_domain_score") as mock_sem:
            heuristic_score(profile, parsed, job, is_reloc=False, db_path="fake.db")
            mock_sem.assert_not_called()

    def test_other_domain_with_no_keywords_triggers_semantic(self):
        """Job with domain='other' + no keyword overlap → semantic fallback called."""
        profile = _make_profile()
        parsed = _make_parsed(domain="other", summary="strategic advisory consulting")
        job = _make_job("Strategy Consultant", "McKinsey")

        with patch("api.scoring._semantic_domain_score", return_value=0) as mock_sem:
            heuristic_score(profile, parsed, job, is_reloc=False, db_path="fake.db")
            mock_sem.assert_called_once()

    def test_other_domain_with_keywords_does_not_trigger_semantic(self):
        """'other' domain but keywords reclassify it → semantic fallback NOT called."""
        profile = _make_profile()
        # "video game" keyword should reclassify to 'game'
        parsed = _make_parsed(
            domain="other",
            summary="build video game development tools for mobile gaming studio",
        )
        job = _make_job("Game PM", "Riot Games")

        with patch("api.scoring._semantic_domain_score") as mock_sem:
            heuristic_score(profile, parsed, job, is_reloc=False, db_path="fake.db")
            mock_sem.assert_not_called()
