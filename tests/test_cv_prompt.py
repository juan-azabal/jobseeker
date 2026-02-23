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
    "parsed": json.dumps({
        "description": "We are looking for a Senior PM to lead our data platform team. "
                       "You will define the roadmap, work with engineering, and drive KPIs."
    }),
    "scored": json.dumps({
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
    }),
}


@pytest.fixture
def mock_references_dir(tmp_path):
    """Create a temp dir with the 4 required reference files."""
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "generate-cv.md").write_text("# Generate CV Instructions\nTailor to the JD.")
    (refs / "ats-rules.md").write_text("# ATS Rules\nNo tables. No unicode bullets.")
    (refs / "master-cv-profile.md").write_text("# Profile\nJuan Azabal, Senior PM.")
    (refs / "master-cv-experience.md").write_text("# Experience\nAcme Corp 2020-2023.")
    return refs


def test_system_prompt_contains_all_four_sections(monkeypatch, mock_references_dir):
    """System prompt must include all 4 reference file sections."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module
    importlib.reload(prompt_module)

    system, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "SECTION: generate-cv.md" in system
    assert "SECTION: ats-rules.md" in system
    assert "SECTION: master-cv-profile.md" in system
    assert "SECTION: master-cv-experience.md" in system
    assert "Generate CV Instructions" in system
    assert "ATS Rules" in system


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
    assert "TAB" in system or "\t" in system, (
        "Prompt must specify tab character as role/date separator"
    )


def test_system_prompt_contains_anti_slop_rules(monkeypatch, mock_references_dir):
    """System prompt must prohibit generic AI language in the Summary."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module
    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")

    assert "strong track record" in system.lower(), (
        "Prompt must explicitly prohibit 'strong track record'"
    )


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
    """System prompt must be > 5000 chars (includes real reference content)."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    # Use a bigger ref dir for this test
    big_refs = mock_references_dir.parent / "big_references"
    big_refs.mkdir()
    for name in ["generate-cv.md", "ats-rules.md", "master-cv-profile.md", "master-cv-experience.md"]:
        (big_refs / name).write_text("x" * 1400)  # 4 files × 1400 = 5600 chars

    monkeypatch.setenv("CV_REFERENCES_DIR", str(big_refs))

    import importlib
    import api.cv.prompt as prompt_module
    importlib.reload(prompt_module)

    system, _ = prompt_module.build_cv_prompts(SAMPLE_JOB, "")
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
    """Missing reference file raises FileNotFoundError with the filename."""
    incomplete_refs = tmp_path / "incomplete"
    incomplete_refs.mkdir()
    # Only create 3 of the 4 files
    (incomplete_refs / "generate-cv.md").write_text("content")
    (incomplete_refs / "ats-rules.md").write_text("content")
    (incomplete_refs / "master-cv-profile.md").write_text("content")
    # master-cv-experience.md is missing

    monkeypatch.setenv("CV_REFERENCES_DIR", str(incomplete_refs))

    import importlib
    import api.cv.prompt as prompt_module
    importlib.reload(prompt_module)

    with pytest.raises(FileNotFoundError, match="master-cv-experience.md"):
        prompt_module.build_cv_prompts(SAMPLE_JOB, "")


def test_user_cv_included_when_provided(monkeypatch, mock_references_dir):
    """User's cv.md content is appended to the user prompt when provided."""
    monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))

    import importlib
    import api.cv.prompt as prompt_module
    importlib.reload(prompt_module)

    _, user = prompt_module.build_cv_prompts(SAMPLE_JOB, "My personal cv content here.")
    assert "My personal cv content here." in user
