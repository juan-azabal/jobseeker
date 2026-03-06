"""
End-to-end integration test: non-Juan profile through the full scoring pipeline.

Verifies that a "Senior Data Engineer, US-based, remote-preferred" profile:
- Rubric says "Data Engineer", "US, remote-preferred" — no "PM", no "EU"
- Prefilter accepts "Senior Data Engineer" titles, rejects "Product Manager"
- Heuristic scoring uses the user's domains/skills, not Juan's
- No "barcelona", "SaaS, B2B", or other Juan-specific values in outputs

Phase 8.4
"""

import sys
import os
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scorer import _build_scoring_prompt
from scoring import load_heuristic_config as _load_heuristic_config, heuristic_score as _heuristic_score
from prefilter import prefilter_jobs
import scorer

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_de_profile():
    with open(os.path.join(FIXTURES_DIR, "de-profile.yaml")) as f:
        return yaml.safe_load(f)


def _reset_rubric_cache():
    scorer._SCORING_RUBRIC_CACHE = None


# ---------------------------------------------------------------------------
# Synthetic job fixtures
# ---------------------------------------------------------------------------

JOB_DE_STRONG = {
    "id": "de001",
    "title": "Senior Data Engineer - Data Platform",
    "company": "DataCo",
    "location": "Remote, US",
    "description": "Build and maintain data pipelines using Spark and Airflow...",
    "parsed": {
        "seniority": "senior",
        "location_type": "remote",
        "domain": "data",
        "must_have_skills": ["SQL", "Python", "Spark", "dbt"],
        "nice_to_have_skills": ["Kafka", "Airflow", "Snowflake"],
        "technical_stack": ["Spark", "dbt", "Snowflake", "Airflow"],
        "responsibilities_summary": "Build and maintain data pipelines, data warehouse, ETL processes.",
        "salary_mentioned": "160000-200000 USD",
        "red_flags": [],
        "key_phrases": ["data pipeline", "data warehouse", "ETL"],
    },
}

JOB_PM_REJECT = {
    "id": "pm001",
    "title": "Senior Product Manager - Analytics",
    "company": "PMCo",
    "location": "Remote, US",
    "description": "Own the analytics product roadmap...",
    "parsed": {
        "seniority": "senior",
        "location_type": "remote",
        "domain": "saas",
        "must_have_skills": ["product roadmap", "analytics", "stakeholders"],
        "nice_to_have_skills": ["SQL"],
        "technical_stack": ["Looker"],
        "responsibilities_summary": "Drive analytics product roadmap for B2B SaaS.",
        "salary_mentioned": "not mentioned",
        "red_flags": [],
        "key_phrases": ["product strategy"],
    },
}

JOB_DE_NYC = {
    "id": "de002",
    "title": "Staff Data Engineer",
    "company": "NYDataCo",
    "location": "New York, NY (hybrid)",
    "description": "Join our data team in NYC...",
    "parsed": {
        "seniority": "staff",
        "location_type": "hybrid",
        "domain": "data",
        "must_have_skills": ["SQL", "Python", "data pipeline"],
        "nice_to_have_skills": ["Snowflake", "dbt"],
        "technical_stack": ["Snowflake", "dbt", "Python"],
        "responsibilities_summary": "Build scalable data pipelines and data models.",
        "salary_mentioned": "not mentioned",
        "red_flags": [],
        "key_phrases": ["data pipeline", "data model"],
    },
}

JOB_HEALTHCARE = {
    "id": "hc001",
    "title": "Product Manager - Healthcare",
    "company": "HealthCorp",
    "location": "Barcelona, Spain",
    "description": "Own healthcare workflow features...",
    "parsed": {
        "seniority": "mid",
        "location_type": "onsite",
        "domain": "healthcare",
        "must_have_skills": ["HIPAA", "clinical workflows"],
        "nice_to_have_skills": [],
        "technical_stack": ["Epic"],
        "responsibilities_summary": "Healthcare product workflows.",
        "salary_mentioned": "not mentioned",
        "red_flags": [],
        "key_phrases": [],
    },
}


# ---------------------------------------------------------------------------
# Rubric tests
# ---------------------------------------------------------------------------


class TestRubricForDE:
    """Rubric must reflect Data Engineer profile, not PM/EU."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = _load_de_profile()
        self.rubric = _build_scoring_prompt(self.profile)

    def test_contains_data_engineer(self):
        assert "Data Engineer" in self.rubric

    def test_contains_us_geography(self):
        assert "US, remote-preferred" in self.rubric

    def test_contains_alice_name(self):
        assert "Alice Chen" in self.rubric

    def test_no_pm_in_rubric(self):
        assert "experienced PM" not in self.rubric
        assert "tech PM" not in self.rubric

    def test_no_eu_in_rubric(self):
        assert "EU or remote" not in self.rubric

    def test_no_barcelona(self):
        assert "barcelona" not in self.rubric.lower()

    def test_no_saas_b2b(self):
        assert "SaaS, B2B" not in self.rubric

    def test_contains_data_domains(self):
        assert "data, ml" in self.rubric


# ---------------------------------------------------------------------------
# Prefilter tests
# ---------------------------------------------------------------------------


class TestPrefilterForDE:
    """Prefilter with DE preferences should accept DE titles, reject PM titles."""

    def test_accepts_data_engineer(self):
        jobs = [JOB_DE_STRONG.copy()]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            config_path=os.path.join(FIXTURES_DIR, "de-preferences.yaml"),
            applied_path="/dev/null",
            seen_ids=None,
            home_locations=["new york", "us"],
        )
        assert len(passed) == 1
        assert passed[0]["title"] == "Senior Data Engineer - Data Platform"

    def test_rejects_product_manager(self):
        jobs = [JOB_PM_REJECT.copy()]
        passed, rejected, stats = prefilter_jobs(
            jobs,
            config_path=os.path.join(FIXTURES_DIR, "de-preferences.yaml"),
            applied_path="/dev/null",
            seen_ids=None,
            home_locations=["new york", "us"],
        )
        assert len(passed) == 0
        assert len(rejected) == 1


# ---------------------------------------------------------------------------
# Heuristic scoring tests
# ---------------------------------------------------------------------------


class TestHeuristicScoringForDE:
    """Heuristic scoring uses the DE profile's domains/skills, not Juan's."""

    def setup_method(self):
        self.profile = _load_de_profile()
        _load_heuristic_config(self.profile)

    def test_strong_de_job_scores_high(self):
        score = _heuristic_score(JOB_DE_STRONG)
        # domain: data=15, seniority: senior=15, remote=10, skills: sql+python+spark+dbt+kafka+airflow+snowflake+data pipeline+etl = many matches
        assert score >= 50, f"Expected >= 50, got {score}"

    def test_hybrid_nyc_scores_with_home_bonus(self):
        score = _heuristic_score(JOB_DE_NYC)
        # domain: data=15, seniority: staff=12, hybrid new york (home) =8, skills: sql+python+data pipeline+snowflake+dbt
        assert score >= 40, f"Expected >= 40, got {score}"

    def test_healthcare_pm_scores_low(self):
        score = _heuristic_score(JOB_HEALTHCARE)
        # domain: healthcare not in DE profile → 0, seniority: mid=0, onsite barcelona (not home) = 0, no skill overlap
        assert score == 0, f"Expected 0, got {score}"

    def test_no_juan_specific_values_in_scoring(self):
        """Ensure _HOME_LOCATIONS was set to DE profile's, not Juan's."""
        from scoring import _HOME_LOCATIONS

        assert "barcelona" not in _HOME_LOCATIONS
        assert "new york" in _HOME_LOCATIONS or "us" in _HOME_LOCATIONS


# ---------------------------------------------------------------------------
# Full pipeline integration (without live API calls)
# ---------------------------------------------------------------------------


class TestFullPipelineNonJuan:
    """No Juan-specific values appear anywhere in outputs."""

    def setup_method(self):
        _reset_rubric_cache()
        self.profile = _load_de_profile()
        _load_heuristic_config(self.profile)
        self.rubric = _build_scoring_prompt(self.profile)

    def test_no_juan_name(self):
        assert "Juan" not in self.rubric

    def test_no_barcelona_anywhere(self):
        assert "barcelona" not in self.rubric.lower()
        assert "madrid" not in self.rubric.lower()
        assert "spain" not in self.rubric.lower()
        assert "españa" not in self.rubric.lower()

    def test_no_pm_role_type(self):
        assert "experienced PM" not in self.rubric
        assert "tech PM" not in self.rubric
        assert "Product Manager" not in self.rubric

    def test_no_eu_geography(self):
        assert "EU or remote" not in self.rubric

    def test_no_saas_b2b_fallback(self):
        assert "SaaS, B2B" not in self.rubric

    def test_correct_identity(self):
        assert "Alice Chen" in self.rubric
        assert "Data Engineer" in self.rubric
        assert "US, remote-preferred" in self.rubric
