"""Tests for api/cv/validator.py — programmatic CV source-fidelity validator (Step 6.4)."""
import pytest
from api.cv.validator import validate_cv, build_fix_prompt


# ── Minimal synthetic plan ────────────────────────────────────────────────

PLAN = {
    "jd_context": {
        "company_type": "consultancy",
        "location_language_hints": ["French"],
    },
    "source_facts": {
        "title": "Senior Product Manager",
        "years_experience": "10+",
        "languages": ["Spanish (native)", "English (advanced)", "French (basic)"],
        "core_skills_themes": ["Data Platforms", "Product Strategy", "AI and ML"],
    },
    "bullet_allocation": {
        "Acme Corp": {"budget": 3, "relevance": "high", "because": "data platform"},
        "Previous Corp": {"budget": 2, "relevance": "medium", "because": "analytics"},
    },
}

# A clean CV that should pass all checks
_CLEAN_CV = """# John Doe
Senior Product Manager
Barcelona, Spain | john@example.com

## Summary

10+ years leading data products in consulting and product companies. Not looking for
pure delivery or execution-only roles. Work best in contexts where strategy and
technical depth are equally valued. Comfortable adapting to different client
environments and contexts when embedded.

## Selected Impact

- Rebuilt first-party tracking pipeline; reduced data loss from 15% to <0.5%.
- Led cross-functional team of 8 across 3 time zones to launch recommendation engine.
- Defined SLIs/SLOs for pipeline reliability; improved P95 latency by 40%.
- Aligned 5 engineering teams around shared data strategy via OKR framework.

## Core Skills

Data Platforms: Deep experience with Snowplow, Kafka, dbt, and Snowflake.

Product Strategy: Roadmap prioritization, OKR frameworks, stakeholder alignment.

AI and ML: Feature engineering, NDCG/CTR metrics, production guardrails.

## Work Experience

### Acme Corp - Senior PM\t01/2020 - Present
_Global data platform team, 5 engineers._

- Built Snowplow tracking pipeline used by 20M users.
- Aligned 5 engineering teams around shared data strategy.
- Defined SLIs/SLOs for pipeline reliability.

### Previous Corp - PM\t06/2015 - 12/2019
_Analytics platform for media group._

- Launched recommendation engine with collaborative filtering.
- Led A/B testing programme across editorial teams.

## Education and Certifications

MBA - IESE Business School, 2017

## Languages

Spanish (native) | English (advanced) | French (basic)
"""


# ══════════════════════════════════════════════════════════════════════════
# Clean CV passes
# ══════════════════════════════════════════════════════════════════════════

def test_clean_cv_passes():
    """A CV matching all source_facts constraints returns passed=True with no errors."""
    result = validate_cv(_CLEAN_CV, PLAN)
    assert result["passed"] is True
    assert result["errors"] == [], f"Expected no errors, got: {result['errors']}"


def test_validate_cv_returns_required_keys():
    """validate_cv always returns a dict with passed, errors, and warnings."""
    result = validate_cv(_CLEAN_CV, PLAN)
    assert "passed" in result
    assert "errors" in result
    assert "warnings" in result
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)


# ══════════════════════════════════════════════════════════════════════════
# Error: title_downgraded
# ══════════════════════════════════════════════════════════════════════════

def test_title_downgraded_detected():
    """CV with 'Product Manager' in title line when source says 'Senior PM' → error."""
    cv = _CLEAN_CV.replace("Senior Product Manager\nBarcelona", "Product Manager\nBarcelona")
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "title_downgraded" in codes, (
        f"Expected 'title_downgraded' error, got errors: {result['errors']}"
    )


def test_title_correct_no_error():
    """CV with correct title → no title_downgraded error."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "title_downgraded" not in codes


def test_title_downgraded_blocks_passing():
    """A title_downgraded error causes passed=False."""
    cv = _CLEAN_CV.replace("Senior Product Manager\nBarcelona", "Product Manager\nBarcelona")
    result = validate_cv(cv, PLAN)
    assert result["passed"] is False


# ══════════════════════════════════════════════════════════════════════════
# Error: years_downgraded
# ══════════════════════════════════════════════════════════════════════════

def test_years_downgraded_detected():
    """CV with '7+ years' when source says '10+' → error years_downgraded."""
    cv = _CLEAN_CV.replace("10+ years", "7+ years")
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "years_downgraded" in codes, (
        f"Expected 'years_downgraded' error, got errors: {result['errors']}"
    )


def test_years_correct_no_error():
    """CV mentioning '10+ years' → no years_downgraded error."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "years_downgraded" not in codes


def test_years_not_mentioned_no_error():
    """If source_facts.years_experience is empty, no years check is performed."""
    plan_no_years = dict(PLAN)
    plan_no_years["source_facts"] = dict(PLAN["source_facts"])
    plan_no_years["source_facts"]["years_experience"] = ""
    result = validate_cv(_CLEAN_CV, plan_no_years)
    codes = [e["code"] for e in result["errors"]]
    assert "years_downgraded" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Error: slop_detected
# ══════════════════════════════════════════════════════════════════════════

def test_slop_strong_track_record_detected():
    """CV with 'strong track record' → error slop_detected."""
    cv = _CLEAN_CV.replace(
        "10+ years leading data products",
        "10+ years with a strong track record in data products",
    )
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "slop_detected" in codes


def test_slop_proven_ability_detected():
    """CV with 'proven ability' → error slop_detected."""
    cv = _CLEAN_CV.replace(
        "10+ years leading data products",
        "10+ years demonstrating proven ability in data products",
    )
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "slop_detected" in codes


def test_slop_passionate_about_detected():
    """CV with 'passionate about' → error slop_detected."""
    cv = _CLEAN_CV.replace(
        "10+ years leading data products",
        "Passionate about data products with 10+ years of experience",
    )
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "slop_detected" in codes


def test_slop_results_driven_detected():
    """CV with 'results-driven' → error slop_detected."""
    cv = _CLEAN_CV.replace(
        "10+ years leading data products",
        "Results-driven PM with 10+ years in data products",
    )
    result = validate_cv(cv, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "slop_detected" in codes


def test_no_slop_no_error():
    """Clean CV without slop phrases → no slop_detected error."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [e["code"] for e in result["errors"]]
    assert "slop_detected" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Warning: missing_language
# ══════════════════════════════════════════════════════════════════════════

def test_missing_language_warning_when_language_absent():
    """CV missing 'French' when source_facts has it → warning missing_language."""
    cv = _CLEAN_CV.replace(
        "Spanish (native) | English (advanced) | French (basic)",
        "Spanish (native) | English (advanced)",
    )
    result = validate_cv(cv, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "missing_language" in codes, (
        f"Expected 'missing_language' warning, got: {result['warnings']}"
    )


def test_all_languages_present_no_warning():
    """CV with all languages from source_facts → no missing_language warning."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "missing_language" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Warning: missing_theme
# ══════════════════════════════════════════════════════════════════════════

def test_missing_theme_warning_when_theme_absent():
    """CV missing a Core Skills theme from source_facts → warning missing_theme."""
    cv = _CLEAN_CV.replace(
        "AI and ML: Feature engineering, NDCG/CTR metrics, production guardrails.\n\n",
        "",  # Remove AI and ML theme entirely
    )
    result = validate_cv(cv, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "missing_theme" in codes, (
        f"Expected 'missing_theme' warning for removed AI/ML theme, got: {result['warnings']}"
    )


def test_all_themes_present_no_warning():
    """CV with all Core Skills themes → no missing_theme warning."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "missing_theme" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Warning: no_consulting_mention
# ══════════════════════════════════════════════════════════════════════════

def test_no_consulting_mention_warning_for_consultancy_job():
    """Plan with company_type='consultancy' but no consulting mention → warning."""
    cv = """# John Doe
Senior Product Manager
Barcelona, Spain | john@example.com

## Summary

10+ years in data platform leadership. Not looking for pure delivery roles.

## Languages

Spanish (native) | English (advanced) | French (basic)
"""
    result = validate_cv(cv, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "no_consulting_mention" in codes, (
        f"Expected 'no_consulting_mention' warning, got: {result['warnings']}"
    )


def test_consulting_mention_present_no_warning():
    """CV with consulting signal in Summary → no no_consulting_mention warning."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "no_consulting_mention" not in codes


def test_no_consulting_warning_for_in_house_job():
    """Plan with company_type='in_house' → no consulting check (not a consultancy)."""
    plan_in_house = dict(PLAN)
    plan_in_house["jd_context"] = {"company_type": "in_house", "location_language_hints": []}
    cv = """# John Doe
Senior Product Manager
Barcelona, Spain | john@example.com

## Summary

10+ years in data platform leadership. Not looking for pure delivery roles.

## Languages

Spanish (native) | English (advanced)
"""
    # Plan has no French requirement since location_language_hints is empty
    plan_no_french = dict(plan_in_house)
    plan_no_french["source_facts"] = dict(PLAN["source_facts"])
    plan_no_french["source_facts"]["languages"] = ["Spanish (native)", "English (advanced)"]
    result = validate_cv(cv, plan_no_french)
    codes = [w["code"] for w in result["warnings"]]
    assert "no_consulting_mention" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Warning: gerund_start
# ══════════════════════════════════════════════════════════════════════════

def test_gerund_start_warning_detected():
    """Bullet starting with a gerund ('- Leading the...') → warning gerund_start."""
    cv = _CLEAN_CV.replace(
        "- Built Snowplow tracking pipeline used by 20M users.",
        "- Leading the Snowplow tracking pipeline used by 20M users.",
    )
    result = validate_cv(cv, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "gerund_start" in codes, (
        f"Expected 'gerund_start' warning, got: {result['warnings']}"
    )


def test_no_gerund_start_no_warning():
    """Clean CV with no gerund-start bullets → no gerund_start warning."""
    result = validate_cv(_CLEAN_CV, PLAN)
    codes = [w["code"] for w in result["warnings"]]
    assert "gerund_start" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Graceful degradation
# ══════════════════════════════════════════════════════════════════════════

def test_empty_plan_does_not_crash():
    """validate_cv with an empty plan returns a result without raising."""
    result = validate_cv(_CLEAN_CV, {})
    assert isinstance(result, dict)
    assert "passed" in result


def test_empty_markdown_does_not_crash():
    """validate_cv with empty markdown returns a result without raising."""
    result = validate_cv("", PLAN)
    assert isinstance(result, dict)
    assert "passed" in result


def test_passed_false_when_any_error():
    """Any error in errors list → passed is False."""
    cv = _CLEAN_CV.replace(
        "Senior Product Manager\nBarcelona",
        "Product Manager\nBarcelona",
    )
    result = validate_cv(cv, PLAN)
    assert result["passed"] is False


def test_passed_true_when_only_warnings():
    """Warnings alone do not set passed=False."""
    # Remove French from Languages to trigger missing_language warning (not an error)
    cv = _CLEAN_CV.replace(
        "Spanish (native) | English (advanced) | French (basic)",
        "Spanish (native) | English (advanced)",
    )
    result = validate_cv(cv, PLAN)
    assert result["passed"] is True, (
        "Warnings alone must not fail validation (passed should be True)"
    )


# ══════════════════════════════════════════════════════════════════════════
# build_fix_prompt
# ══════════════════════════════════════════════════════════════════════════

def test_build_fix_prompt_returns_tuple():
    """build_fix_prompt returns a (system, user) string tuple."""
    errors = [{"code": "title_downgraded", "detail": "Expected 'Senior PM', found 'PM'"}]
    result = build_fix_prompt(_CLEAN_CV, errors)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


def test_build_fix_prompt_system_mentions_fix_only():
    """Fix system prompt must instruct LLM to fix ONLY listed issues."""
    errors = [{"code": "title_downgraded", "detail": "Expected 'Senior PM'"}]
    system, _ = build_fix_prompt(_CLEAN_CV, errors)
    system_lower = system.lower()
    assert "fix only" in system_lower or "only fix" in system_lower or "do not change" in system_lower, (
        "Fix system prompt must restrict changes to listed issues only"
    )


def test_build_fix_prompt_user_contains_error_codes():
    """Fix user prompt must list the specific error codes to fix."""
    errors = [
        {"code": "title_downgraded", "detail": "Expected 'Senior PM'"},
        {"code": "slop_detected", "detail": "Found 'proven ability'"},
    ]
    _, user = build_fix_prompt(_CLEAN_CV, errors)
    assert "title_downgraded" in user
    assert "slop_detected" in user


def test_build_fix_prompt_user_contains_cv():
    """Fix user prompt must include the generated CV to be fixed."""
    errors = [{"code": "slop_detected", "detail": "Found slop"}]
    _, user = build_fix_prompt(_CLEAN_CV, errors)
    assert "# John Doe" in user  # CV is included in the prompt
