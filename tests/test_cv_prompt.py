"""Tests for api/cv/prompt.py — CV prompt builder."""

import json
import pytest
from pathlib import Path


SAMPLE_JOB = {
    "job_id": "abc123",
    "title": "Senior Product Manager",
    "company": "Acme Corp",
    "location": "Barcelona, Spain",
    "url": "https://example.com/job/123",
    "score": 75,
    "tier": "A",
    "parsed": json.dumps(
        {
            "description": "We are looking for a Senior PM to lead our data platform team. "
            "You will define the roadmap, work with engineering, and drive KPIs."
        }
    ),
    "scored": json.dumps(
        {
            "rag_score": {
                "total": 75,
                "breakdown": {
                    "domain_fit": 20,
                    "seniority_fit": 18,
                    "skills_match": 15,
                    "location_fit": 12,
                    "language_fit": 10,
                },
                "strengths": ["Strong data background", "Proven PM experience"],
                "gaps": [{"issue": "No fintech experience", "severity": "low"}],
            }
        }
    ),
}


@pytest.fixture
def mock_references_dir(tmp_path):
    """Create a temp dir with the 2 required logic reference files."""
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "generate-cv.md").write_text("# Generate CV Instructions\nTailor to the JD.")
    (refs / "ats-rules.md").write_text("# ATS Rules\nNo tables. No unicode bullets.")
    return refs


def test_system_prompt_contains_logic_sections_and_cv(monkeypatch, mock_references_dir):
    """System prompt must include the 2 logic file sections plus candidate CV."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    cv_content = "# My CV\nSenior PM with 10 years experience."
    system, user = prompt_module.build_cv_prompts(SAMPLE_JOB, cv_content)

    assert "SECTION: generate-cv.md" in system
    assert "SECTION: ats-rules.md" in system
    assert "SECTION: candidate-master-cv.md" in system
    assert "Generate CV Instructions" in system
    assert "ATS Rules" in system
    assert "Senior PM with 10 years experience." in system


def test_system_prompt_contains_output_contract(monkeypatch, mock_references_dir):
    """System prompt must include the output contract instruction block."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "Output ONLY the CV content" in system
    assert "structured markdown format" in system
    assert "## Summary" in system
    assert "## Work Experience" in system


def test_system_prompt_no_bold_markers_in_format_example(monkeypatch, mock_references_dir):
    """Format example must not use **bold** markers (builder handles bold via element type)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    # The format example must not instruct LLM to output **bold** markers in role lines
    assert "**Role" not in system, "Format example must not use **Role** pattern"
    assert "**Theme" not in system, "Format example must not use **Theme** pattern"


def test_system_prompt_contains_italic_context_line_instruction(monkeypatch, mock_references_dir):
    """System prompt must instruct LLM to output _italic context lines_ under each company."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "_single underscore" in system or "context line" in system.lower(), (
        "Prompt must mention italic context lines under each company"
    )


def test_system_prompt_contains_tab_date_format(monkeypatch, mock_references_dir):
    """System prompt must show tab-separated Company - Role + Date format."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    # Must mention TAB as the separator between role and date
    assert "TAB" in system or "\t" in system, "Prompt must specify tab character as role/date separator"


def test_system_prompt_contains_anti_slop_rules(monkeypatch, mock_references_dir):
    """System prompt must prohibit generic AI language in the Summary."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "strong track record" in system.lower(), "Prompt must explicitly prohibit 'strong track record'"


def test_system_prompt_contains_limits_clause_requirement(monkeypatch, mock_references_dir):
    """System prompt must require Summary to contain a limits/not-looking-for sentence."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    # Should mention "not looking for" or "limits" requirement
    system_lower = system.lower()
    assert "not looking for" in system_lower or "limits" in system_lower, (
        "Prompt must require a limits clause in the Summary"
    )


def test_system_prompt_is_substantial(monkeypatch, mock_references_dir):
    """System prompt must be > 5000 chars (logic files + user CV + output contract)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    # Use a bigger ref dir for this test
    big_refs = mock_references_dir.parent / "big_references"
    big_refs.mkdir()
    for name in ["generate-cv.md", "ats-rules.md"]:
        (big_refs / name).write_text("x" * 1000)  # 2 files × 1000 + cv = 5000+ with output contract

    monkeypatch.setenv("CV_REFERENCES_DIR", str(big_refs))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    # The output contract alone is ~3000 chars; add 2000 from files + cv to exceed 5000
    big_cv = "y" * 3000
    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, big_cv)
    assert len(system) > 5000


def test_user_prompt_contains_job_data(monkeypatch, mock_references_dir):
    """User prompt must contain job title, company, and JD text."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "Senior Product Manager" in user
    assert "Acme Corp" in user
    assert "data platform team" in user  # from parsed.description


def test_user_prompt_with_full_text_key(monkeypatch, mock_references_dir):
    """Falls back to full_text key if description is absent."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    job = dict(SAMPLE_JOB)
    job["parsed"] = json.dumps({"full_text": "Looking for a PM with full_text field."})

    _, user = prompt_module.build_cv_prompts(job, "")
    assert "full_text field" in user


def test_user_prompt_with_body_key(monkeypatch, mock_references_dir):
    """Falls back to body key if description and full_text are absent."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    job = dict(SAMPLE_JOB)
    job["parsed"] = json.dumps({"body": "PM role with body field."})

    _, user = prompt_module.build_cv_prompts(job, "")
    assert "body field" in user


def test_missing_jd_raises_value_error(monkeypatch, mock_references_dir):
    """Job with no extractable JD text raises ValueError."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    job = dict(SAMPLE_JOB)
    job["parsed"] = json.dumps({"other_field": "no description here"})

    with pytest.raises(ValueError, match="No job description"):
        prompt_module.build_cv_prompts(job, "")


def test_missing_reference_file_raises_file_not_found(monkeypatch, tmp_path):
    """Missing logic reference file raises FileNotFoundError with the filename."""
    incomplete_refs = tmp_path / "incomplete"
    incomplete_refs.mkdir()
    # Only create generate-cv.md; ats-rules.md is missing
    (incomplete_refs / "generate-cv.md").write_text("content")

    monkeypatch.setenv("CV_REFERENCES_DIR", str(incomplete_refs))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    with pytest.raises(FileNotFoundError, match="ats-rules.md"):
        prompt_module.build_cv_prompts(SAMPLE_JOB, "")


def test_user_cv_included_in_system_prompt(monkeypatch, mock_references_dir):
    """User's cv.md content appears in the system prompt as the authoritative source."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "My personal cv content here.")
    assert "My personal cv content here." in system
    assert "SECTION: candidate-master-cv.md" in system


def test_system_prompt_contains_volume_rules(monkeypatch, mock_references_dir):
    """System prompt must include content volume rules: all companies, recency budget, hard cap."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")
    system_lower = system.lower()

    assert "every company" in system_lower or "all compan" in system_lower, (
        "Prompt must instruct LLM to include every company from master CV"
    )
    assert "12 bullet" in system_lower or "12 bullets" in system_lower, (
        "Prompt must specify a total Work Experience bullet cap (12 bullets max)"
    )
    assert "3 page" in system_lower or "3-page" in system_lower, "Prompt must set a hard page cap (3 pages)"
    assert "1.5" in system and "page" in system_lower, "Prompt must reference 1.5 pages as minimum threshold"


def test_system_prompt_contains_selected_impact_volume(monkeypatch, mock_references_dir):
    """System prompt must instruct LLM to write 4-5 Selected Impact bullets."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "4-5" in system or "4–5" in system, "Prompt must specify 4-5 bullets for Selected Impact"


def test_system_prompt_selected_impact_example_has_five_bullets(monkeypatch, mock_references_dir):
    """The Selected Impact format example must show at least 4 bullet lines."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    # Count bullet lines in the Selected Impact section of the output contract
    # (between "## Selected Impact" and the next "##")
    import re

    impact_block = re.search(r"## Selected Impact\s*(.*?)(?=##|\Z)", system, re.DOTALL)
    assert impact_block is not None, "Selected Impact section not found in system prompt"
    bullets = [l for l in impact_block.group(1).splitlines() if l.strip().startswith("-")]
    assert len(bullets) >= 4, f"Selected Impact example must have ≥4 bullets, found {len(bullets)}"


# ══════════════════════════════════════════════════════════════════════════
# Plan-aware prompt tests (Step 6.3)
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_PLAN = {
    "jd_context": {
        "company_type": "consultancy",
        "business_model": "B2B",
        "vertical": "data",
        "location": "Paris, FR",
        "seniority_read": "mid",
        "key_tools": ["sql", "python"],
        "team_signals": "embedded",
        "location_language_hints": ["French"],
    },
    "score_summary": {
        "total": 72,
        "breakdown": {"domain_fit": 20, "seniority_fit": 15},
        "dimension_guidance": {
            "domain_fit": {"score": 20, "level": "high", "instruction": "Lead with domain proof."},
            "seniority_fit": {"score": 15, "level": "high", "instruction": "Maintain seniority."},
        },
    },
    "strengths": [{"claim": "Strong data background.", "evidence": "Snowplow, Kafka."}],
    "gaps": [{"gap": "Seniority mismatch.", "severity": "medium", "mitigation": "Emphasise scope."}],
    "bullet_allocation": {
        "Acme Corp": {"budget": 3, "relevance": "high", "because": "data platform"},
    },
    "source_facts": {
        "title": "Senior Product Manager",
        "years_experience": "10+",
        "languages": ["Spanish (native)", "English (advanced)"],
        "core_skills_themes": ["Data Platforms", "Product Strategy"],
    },
}


def test_build_cv_prompts_with_plan_user_contains_plan_json(monkeypatch, mock_references_dir):
    """User prompt with plan must contain the plan as JSON (key sections present)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "jd_context" in user
    assert "bullet_allocation" in user
    assert "source_facts" in user


def test_build_cv_prompts_with_plan_user_no_raw_jd(monkeypatch, mock_references_dir):
    """User prompt with plan must NOT contain the raw JD text (replaced by parsed summary)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    # Raw JD removed from plan-aware path — replaced by parsed distillation
    assert "data platform team" not in user, "Raw JD text must not appear in plan-aware user prompt"
    assert "## Job Summary (parsed)" in user


def test_build_cv_prompts_with_plan_system_contains_bullet_allocation_instruction(monkeypatch, mock_references_dir):
    """System prompt with plan must mention following the bullet allocation."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "bullet allocation" in system.lower(), "System prompt must instruct LLM to follow the bullet allocation plan"


def test_build_cv_prompts_with_plan_system_contains_source_fidelity_rules(monkeypatch, mock_references_dir):
    """System prompt with plan must include source fidelity rules (never downgrade)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)
    system_lower = system.lower()

    assert "source of truth" in system_lower or "never downgrade" in system_lower, (
        "System prompt must include source fidelity rules"
    )


def test_build_cv_prompts_with_plan_system_contains_chain_of_thought_instruction(monkeypatch, mock_references_dir):
    """System prompt with plan must instruct LLM to output an <analysis> block first."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "<analysis>" in system, "System prompt must instruct LLM to output chain-of-thought <analysis> block"


def test_build_cv_prompts_with_plan_system_contains_consultancy_instruction(monkeypatch, mock_references_dir):
    """System prompt with plan must mention consulting adaptability requirement."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)
    system_lower = system.lower()

    assert "consultancy" in system_lower or "consulting" in system_lower or "client environment" in system_lower, (
        "System prompt must include consultancy-specific tailoring instruction"
    )


def test_build_cv_prompts_with_plan_user_no_separate_strengths_section(monkeypatch, mock_references_dir):
    """User prompt with plan must NOT re-list strengths/gaps separately (they're in the plan)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "## Candidate Strengths" not in user, (
        "With a plan, strengths are inside the plan JSON — not a separate section"
    )
    assert "## Gaps to address" not in user, "With a plan, gaps are inside the plan JSON — not a separate section"


def test_build_cv_prompts_with_plan_user_no_separate_score_breakdown(monkeypatch, mock_references_dir):
    """User prompt with plan must NOT re-list the score breakdown separately."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "## Score Breakdown" not in user, (
        "With a plan, score breakdown is inside the plan JSON — not a separate section"
    )


def test_build_cv_prompts_with_plan_cv_in_system_prompt(monkeypatch, mock_references_dir):
    """User's cv.md content appears in the system prompt even when a plan is provided."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "My personal CV context.", SAMPLE_PLAN)

    assert "My personal CV context." in system
    assert "SECTION: candidate-master-cv.md" in system


def test_build_cv_prompts_backward_compat_no_plan_arg(monkeypatch, mock_references_dir):
    """build_cv_prompts without cv_plan arg still builds a valid prompt tuple."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert len(system) > 100
    assert "Senior Product Manager" in user


def test_build_cv_prompts_backward_compat_none_plan(monkeypatch, mock_references_dir):
    """build_cv_prompts with cv_plan=None still builds a valid prompt tuple."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", None)

    assert len(system) > 100
    assert "Senior Product Manager" in user


def test_build_cv_prompts_backward_compat_empty_plan(monkeypatch, mock_references_dir):
    """build_cv_prompts with cv_plan={} still builds a valid prompt tuple (graceful)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", {})

    assert len(system) > 100
    assert "Senior Product Manager" in user


# ══════════════════════════════════════════════════════════════════════════
# Phase 3.1 tests — parsed distillation replaces raw JD in plan-aware path
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_JOB_V15 = {
    **SAMPLE_JOB,
    "parsed": json.dumps(
        {
            "description": "Full raw job description text goes here.",
            "role_in_plain_english": "You will own the roadmap and work with the data team.",
            "truly_required": ["SQL", "Python"],
            "preferred_skills": ["dbt", "Airflow"],
            "verbatim_for_cv": ["event-driven architecture", "self-serve analytics"],
            "company_context": {
                "stage": "growth",
                "what_they_value": ["speed", "data"],
                "tone": "startup_scrappy",
            },
        }
    ),
}


def test_build_cv_prompts_with_plan_system_no_reference_files(monkeypatch, mock_references_dir):
    """System prompt in plan-aware path must NOT contain reference file sections."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "SECTION: generate-cv.md" not in system, "Reference files must not appear in plan-aware system prompt"
    assert "SECTION: ats-rules.md" not in system, "Reference files must not appear in plan-aware system prompt"


def test_build_cv_prompts_with_plan_user_v15_fields_in_summary(monkeypatch, mock_references_dir):
    """Plan-aware user prompt includes v1.5 parsed fields in Job Summary section."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB_V15, "", SAMPLE_PLAN)

    assert "## Job Summary (parsed)" in user
    assert "You will own the roadmap" in user
    assert "SQL" in user
    assert "dbt" in user
    assert "event-driven architecture" in user
    assert "growth stage" in user
    assert "startup_scrappy tone" in user
    # Raw JD must not leak through
    assert "Full raw job description text" not in user


def test_build_cv_prompts_with_plan_user_no_v15_fallback(monkeypatch, mock_references_dir):
    """Plan-aware user prompt shows fallback note when no v1.5 fields available."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    # SAMPLE_JOB has no v1.5 fields — fallback note should appear
    assert "## Job Summary (parsed)" in user
    assert "predates parser v1.5" in user


# ══════════════════════════════════════════════════════════════════════════
# Phase 3.2 tests — profile target context in plan-aware user prompt
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_PROFILE_DATA = {
    "domains": {"data": 15, "saas": 10, "fintech": 5, "gaming": -10},
    "role_type": "Senior Product Manager",
    "role_function": "product",
    "skills": [
        "sql",
        "python",
        "stakeholder management",
        "roadmapping",
        "data analysis",
        "a/b testing",
        "agile",
        "scrum",
        "jira",
        "product strategy",
    ],
    "seniority": {},
    "home_locations": [],
    "home_regions": [],
    "languages": [],
    "location_preference": "b",
    "country_weights": {},
    "company_type_weights": {},
}


def test_build_cv_prompts_with_plan_and_profile_injects_candidate_target(monkeypatch, mock_references_dir):
    """Plan-aware user prompt includes Candidate Target section when profile_data provided."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN, SAMPLE_PROFILE_DATA)

    assert "## Candidate Target" in user
    assert "data" in user
    assert "Senior Product Manager" in user
    assert "sql" in user


def test_build_cv_prompts_with_plan_profile_omits_negative_domains(monkeypatch, mock_references_dir):
    """Candidate Target must NOT list negative-weight domains."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN, SAMPLE_PROFILE_DATA)

    assert "gaming" not in user


def test_build_cv_prompts_with_plan_no_profile_no_candidate_target(monkeypatch, mock_references_dir):
    """Plan-aware user prompt omits Candidate Target when no profile_data provided."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)

    assert "## Candidate Target" not in user


def test_build_cv_prompts_profile_data_none_is_no_op(monkeypatch, mock_references_dir):
    """Passing profile_data=None behaves identically to omitting the param."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module

    importlib.reload(prompt_module)

    _, user_default = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN)
    _, user_none = prompt_module.build_cv_prompts(SAMPLE_JOB, "", SAMPLE_PLAN, None)

    assert user_default == user_none
