"""Tests for api/cv/plan.py — deterministic CV plan builder (Phase 6.2)."""

import json
import pytest
from api.cv.plan import build_cv_plan


# ── Synthetic fixtures ────────────────────────────────────────────────────

# Job dict that mimics a Paris-based data consulting role with scored data.
# Parsed description contains explicit English consultancy signals.
WEFIIT_LIKE_JOB = {
    "title": "Product Manager Data & IA",
    "company": "WeFiiT",
    "location": "Paris, FR",
    "parsed": json.dumps(
        {
            "seniority": "mid",
            "locations_mentioned": ["Paris, FR"],
            "must_have_skills": ["SQL", "Python", "data product experience", "agile mindset"],
            "nice_to_have_skills": ["excellent relational skills", "proactive"],
            "technical_stack": ["SQL", "Python", "R"],
            "domain": "data",
            "responsibilities_summary": "Build vision for Data Products, define roadmap.",
            "description": (
                "WeFiiT is a consulting firm specialised in data and AI. "
                "As a Product Manager, you will work with our clients on high-impact "
                "data products. You will be embedded in client teams and expected to "
                "understand client challenges rapidly. Consulting mindset required."
            ),
        }
    ),
    "scored": json.dumps(
        {
            "score": 72,
            "score_breakdown": {
                "domain_fit": 20,
                "seniority_fit": 15,
                "technical_depth": 18,
                "profile_evidence": 15,
                "strategic_impact": 4,
            },
            "strengths": [
                {"claim": "Strong data platform experience.", "evidence": "Snowplow, Kafka, Snowflake at Gartner."},
            ],
            "gaps": [
                {"gap": "Seniority mismatch (mid vs senior).", "severity": "medium", "mitigation": "Emphasise scope."},
            ],
        }
    ),
}

# Job with no scored data — plan should still build with graceful defaults.
NO_SCORE_JOB = {
    "title": "Product Manager",
    "company": "Unknown Corp",
    "parsed": json.dumps(
        {
            "seniority": "unknown",
            "locations_mentioned": ["Berlin, DE"],
            "must_have_skills": ["Kafka", "Python"],
            "technical_stack": ["Kafka"],
            "domain": "data",
            "description": "Join our team to build our product.",
        }
    ),
    "scored": None,
}

# Minimal profile + experience text for source_facts extraction tests
SAMPLE_PROFILE = """# Master CV - Test User

## Contact

Test User
Senior Product Manager | Data & Analytics
Barcelona, Spain | test@test.com | linkedin.com/in/test

## Summary

Senior Product Manager with a software engineering background.
Not interested in pure delivery roles.

## Core Skills

**Data Platforms & Tracking**
First-party tracking, event taxonomies, Snowplow, Kafka, dbt.

**Product Strategy**
Roadmap prioritization, OKR frameworks, stakeholder alignment.

**AI and ML Products**
Feature engineering, NDCG/CTR metrics, production guardrails.

## Languages

Spanish (native) | English (advanced) | Catalan (basic)
"""

SAMPLE_EXPERIENCE = """# Master CV - Experience

## Work Experience

### Acme Corp, Barcelona, Spain
Senior Product Manager | 01/2020 - Present

- Built first-party data platform with Snowplow, Kafka, Snowflake.
- Aligned 5 engineering teams around shared data strategy.
- Defined SLIs/SLOs for pipeline reliability.

### Previous Corp, Madrid, Spain
Product Manager | 06/2015 - 12/2019

- Launched recommendation engine with collaborative filtering.
- Led A/B testing programme across editorial teams.

### Early Corp, Madrid, Spain
Associate Product Manager | 03/2013 - 05/2015

- Ran analytics and experimentation projects.

## Education and Certifications

MBA - IESE Business School, 2017

## Languages

Spanish (native) | English (advanced) | Catalan (basic)
"""

SAMPLE_REF_FILES = {
    "master-cv-profile.md": SAMPLE_PROFILE,
    "master-cv-experience.md": SAMPLE_EXPERIENCE,
}


# ── Helper ────────────────────────────────────────────────────────────────


def _plan(job=WEFIIT_LIKE_JOB, ref_files=None):
    return build_cv_plan(job, ref_files or SAMPLE_REF_FILES)


# ══════════════════════════════════════════════════════════════════════════
# jd_context tests
# ══════════════════════════════════════════════════════════════════════════


def test_jd_context_company_type_consultancy():
    """Job with explicit consulting signals → company_type == 'consultancy'."""
    plan = _plan()
    assert plan["jd_context"]["company_type"] == "consultancy", (
        f"Expected 'consultancy', got {plan['jd_context']['company_type']!r}"
    )


def test_jd_context_company_type_in_house():
    """Job with in-house signals → company_type == 'in_house'."""
    in_house_job = {
        "title": "Product Manager",
        "company": "StartupCo",
        "parsed": json.dumps(
            {
                "seniority": "senior",
                "locations_mentioned": ["London, UK"],
                "must_have_skills": ["Python"],
                "technical_stack": ["Python"],
                "domain": "data",
                "description": "We are building our platform to scale our product. Join our team!",
            }
        ),
        "scored": None,
    }
    plan = build_cv_plan(in_house_job, SAMPLE_REF_FILES)
    assert plan["jd_context"]["company_type"] == "in_house"


def test_jd_context_location_hints_french_for_paris():
    """Paris-based job → location_language_hints contains 'French'."""
    plan = _plan()
    hints = plan["jd_context"]["location_language_hints"]
    assert "French" in hints, f"Expected 'French' in location_language_hints for Paris job, got {hints}"


def test_jd_context_location_hints_german_for_berlin():
    """Berlin-based job → location_language_hints contains 'German'."""
    plan = build_cv_plan(NO_SCORE_JOB, SAMPLE_REF_FILES)
    hints = plan["jd_context"]["location_language_hints"]
    assert "German" in hints, f"Expected 'German' in hints for Berlin job, got {hints}"


def test_jd_context_location_hints_empty_for_english_cities():
    """London / New York → no language hint (English assumed)."""
    uk_job = {
        "title": "PM",
        "company": "Corp",
        "parsed": json.dumps(
            {
                "seniority": "senior",
                "locations_mentioned": ["London, UK"],
                "must_have_skills": [],
                "technical_stack": [],
                "domain": "data",
                "description": "Join our product team.",
            }
        ),
        "scored": None,
    }
    plan = build_cv_plan(uk_job, SAMPLE_REF_FILES)
    assert plan["jd_context"]["location_language_hints"] == [], (
        f"Expected empty hints for London, got {plan['jd_context']['location_language_hints']}"
    )


def test_jd_context_key_tools_filtered_to_known_tools():
    """key_tools must only contain recognised tool names, not soft skills."""
    plan = _plan()
    tools = plan["jd_context"]["key_tools"]
    # SQL and Python from must_have_skills should appear
    assert any("sql" in t.lower() for t in tools), f"SQL not in key_tools: {tools}"
    assert any("python" in t.lower() for t in tools), f"Python not in key_tools: {tools}"
    # Soft-skill phrases should NOT appear
    for tool in tools:
        assert len(tool) < 50, f"Tool phrase too long (likely not a real tool): {tool!r}"


def test_jd_context_has_all_required_keys():
    """jd_context must contain all required keys."""
    REQUIRED = {
        "company_type",
        "business_model",
        "vertical",
        "location",
        "seniority_read",
        "key_tools",
        "team_signals",
        "location_language_hints",
    }
    plan = _plan()
    missing = REQUIRED - set(plan["jd_context"].keys())
    assert not missing, f"Missing jd_context keys: {missing}"


# ══════════════════════════════════════════════════════════════════════════
# score_summary tests
# ══════════════════════════════════════════════════════════════════════════


def test_score_summary_total_matches_input():
    """score_summary.total must equal the job's score."""
    plan = _plan()
    assert plan["score_summary"]["total"] == 72


def test_score_summary_dimension_guidance_has_entry_for_each_dimension():
    """score_summary.dimension_guidance must have an entry for every score dimension."""
    plan = _plan()
    breakdown = plan["score_summary"]["breakdown"]
    guidance = plan["score_summary"]["dimension_guidance"]
    assert set(breakdown.keys()) == set(guidance.keys()), (
        f"Guidance dimensions {set(guidance.keys())} don't match breakdown {set(breakdown.keys())}"
    )


def test_score_summary_high_dimension_has_instruction():
    """High-scoring dimension (domain_fit=20) → level='high' with non-empty instruction."""
    plan = _plan()
    domain_guidance = plan["score_summary"]["dimension_guidance"]["domain_fit"]
    assert domain_guidance["level"] == "high"
    assert domain_guidance["instruction"], "High dimension must have non-empty instruction"


def test_score_summary_low_dimension_has_instruction():
    """Low-scoring dimension (strategic_impact=4) → level='low' with non-empty instruction."""
    plan = _plan()
    strat_guidance = plan["score_summary"]["dimension_guidance"]["strategic_impact"]
    assert strat_guidance["level"] == "low"
    assert strat_guidance["instruction"]


def test_score_summary_strengths_and_gaps_present():
    """strengths and gaps must be lists taken from scored data."""
    plan = _plan()
    assert isinstance(plan["strengths"], list)
    assert len(plan["strengths"]) >= 1, "Expected at least 1 strength"
    assert isinstance(plan["gaps"], list)
    assert len(plan["gaps"]) >= 1, "Expected at least 1 gap"


# ══════════════════════════════════════════════════════════════════════════
# source_facts tests
# ══════════════════════════════════════════════════════════════════════════


def test_source_facts_title_extracted():
    """source_facts.title must match the professional title in the profile."""
    plan = _plan()
    assert plan["source_facts"]["title"] == "Senior Product Manager", (
        f"Expected 'Senior Product Manager', got {plan['source_facts']['title']!r}"
    )


def test_source_facts_years_experience_from_experience_dates():
    """source_facts.years_experience must be '10+' (earliest PM role: 2013, 13 years)."""
    plan = _plan()
    years = plan["source_facts"]["years_experience"]
    # Earliest PM role in SAMPLE_EXPERIENCE is 03/2013 → 13 years → "10+"
    assert years == "10+", f"Expected '10+' years, got {years!r}"


def test_source_facts_languages_contains_spanish():
    """source_facts.languages must include Spanish."""
    plan = _plan()
    langs_lower = [l.lower() for l in plan["source_facts"]["languages"]]
    assert any("spanish" in l for l in langs_lower), (
        f"Expected Spanish in languages, got {plan['source_facts']['languages']}"
    )


def test_source_facts_languages_non_empty():
    """source_facts.languages must be a non-empty list."""
    plan = _plan()
    assert isinstance(plan["source_facts"]["languages"], list)
    assert len(plan["source_facts"]["languages"]) >= 1


def test_source_facts_core_skills_themes_extracted():
    """source_facts.core_skills_themes must list at least 2 theme names."""
    plan = _plan()
    themes = plan["source_facts"]["core_skills_themes"]
    assert isinstance(themes, list)
    assert len(themes) >= 2, f"Expected ≥2 core skills themes, got {themes}"


def test_source_facts_themes_contain_expected_names():
    """Theme names must match **Theme** headers from SAMPLE_PROFILE."""
    plan = _plan()
    themes = plan["source_facts"]["core_skills_themes"]
    theme_text = " ".join(themes).lower()
    assert "data" in theme_text, f"Expected 'data' theme in {themes}"
    assert "product" in theme_text or "strategy" in theme_text or "ai" in theme_text.lower(), (
        f"Expected a strategy/product/AI theme in {themes}"
    )


# ══════════════════════════════════════════════════════════════════════════
# bullet_allocation tests
# ══════════════════════════════════════════════════════════════════════════


def test_bullet_allocation_total_budget_le_12():
    """Total bullet budget across all companies must not exceed 12."""
    plan = _plan()
    total = sum(v["budget"] for v in plan["bullet_allocation"].values())
    assert total <= 12, f"Total bullet budget {total} exceeds maximum of 12"


def test_bullet_allocation_companies_match_experience():
    """bullet_allocation must have an entry for each company in experience file."""
    plan = _plan()
    expected_companies = {"Acme Corp", "Previous Corp", "Early Corp"}
    allocated_companies = set(plan["bullet_allocation"].keys())
    missing = expected_companies - allocated_companies
    assert not missing, f"Missing companies in bullet_allocation: {missing}"


def test_bullet_allocation_each_entry_has_required_keys():
    """Each bullet_allocation entry must have budget, relevance, because."""
    plan = _plan()
    for company, entry in plan["bullet_allocation"].items():
        for key in ("budget", "relevance", "because"):
            assert key in entry, f"Missing key '{key}' for company '{company}'"
        assert entry["relevance"] in ("high", "medium", "low"), (
            f"Invalid relevance '{entry['relevance']}' for '{company}'"
        )
        assert isinstance(entry["budget"], int), f"Budget must be int for '{company}'"


def test_bullet_allocation_sql_rich_company_gets_higher_budget():
    """Company with more SQL/Python content gets higher or equal budget than unrelated one."""
    plan = _plan()
    allocation = plan["bullet_allocation"]
    # Acme Corp has SQL/Kafka/Snowflake mentions → should get higher budget than Early Corp
    acme_budget = allocation.get("Acme Corp", {}).get("budget", 0)
    early_budget = allocation.get("Early Corp", {}).get("budget", 0)
    assert acme_budget >= early_budget, f"Expected Acme Corp ({acme_budget}) ≥ Early Corp ({early_budget}) budget"


def test_bullet_allocation_empty_when_no_experience():
    """Empty experience file → empty bullet_allocation."""
    plan = build_cv_plan(
        WEFIIT_LIKE_JOB,
        {
            "master-cv-profile.md": SAMPLE_PROFILE,
            "master-cv-experience.md": "",
        },
    )
    assert plan["bullet_allocation"] == {}


# ══════════════════════════════════════════════════════════════════════════
# Graceful degradation tests
# ══════════════════════════════════════════════════════════════════════════


def test_no_scored_data_plan_still_builds():
    """Job with no scored data must still return a valid plan (no exceptions)."""
    plan = build_cv_plan(NO_SCORE_JOB, SAMPLE_REF_FILES)
    assert isinstance(plan, dict)
    for key in ("jd_context", "score_summary", "strengths", "gaps", "bullet_allocation", "source_facts"):
        assert key in plan, f"Missing top-level key: {key}"


def test_no_scored_data_score_summary_defaults():
    """No scored data → score_summary.total == 0, dimension_guidance == {}."""
    plan = build_cv_plan(NO_SCORE_JOB, SAMPLE_REF_FILES)
    assert plan["score_summary"]["total"] == 0
    assert plan["score_summary"]["dimension_guidance"] == {}
    assert plan["strengths"] == []
    assert plan["gaps"] == []


def test_no_scored_data_bullet_allocation_still_built():
    """No scored data → bullet_allocation is built from experience, even allocation."""
    plan = build_cv_plan(NO_SCORE_JOB, SAMPLE_REF_FILES)
    # Allocation should still have companies (even with no JD overlap)
    assert len(plan["bullet_allocation"]) > 0
    total = sum(v["budget"] for v in plan["bullet_allocation"].values())
    assert total <= 12


def test_parsed_as_dict_accepted():
    """Job where 'parsed' is already a dict (not a JSON string) must work."""
    job_with_dict = dict(WEFIIT_LIKE_JOB)
    job_with_dict["parsed"] = json.loads(WEFIIT_LIKE_JOB["parsed"])
    plan = build_cv_plan(job_with_dict, SAMPLE_REF_FILES)
    assert plan["jd_context"]["company_type"] == "consultancy"


def test_missing_reference_files_returns_empty_source_facts():
    """Missing reference files → source_facts fields are empty but plan builds."""
    plan = build_cv_plan(WEFIIT_LIKE_JOB, {})
    assert plan["source_facts"]["title"] == ""
    assert plan["source_facts"]["years_experience"] == ""
    assert plan["source_facts"]["languages"] == []
    assert plan["source_facts"]["core_skills_themes"] == []


def test_plan_has_all_top_level_keys():
    """Plan must always contain all 6 top-level keys."""
    REQUIRED = {"jd_context", "score_summary", "strengths", "gaps", "bullet_allocation", "source_facts"}
    plan = _plan()
    assert set(plan.keys()) == REQUIRED
