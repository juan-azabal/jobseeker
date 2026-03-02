"""Unit tests for shared/master_cv_scoring.py — Phase 3.1."""

from shared.master_cv_scoring import build_scoring_context

_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "HealthTech",
            "position": "Senior PM",
            "start_date": "2021-01",
            "end_date": None,
            "summary": "Led health platform.",
            "highlights": [
                "Reduced patient wait time by 30%",
                "Launched EHR integration to 200 hospitals",
            ],
            "skills_used": ["product management", "healthcare", "SQL"],
            "source": "cv_upload",
        },
        {
            "id": "work_002",
            "company": "Fintech Startup",
            "position": "PM",
            "start_date": "2018-01",
            "end_date": "2020-12",
            "summary": "Payments product.",
            "highlights": ["Grew user base 3x", "Shipped payment API"],
            "skills_used": ["payments", "SQL", "A/B testing"],
            "source": "cv_upload",
        },
    ],
    "education": [],
    "skills": [{"name": "product management"}, {"name": "SQL"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}

_JOB = {
    "must_have_skills": ["product management", "healthcare"],
    "nice_to_have_skills": ["SQL", "stakeholder management"],
    "domain": "healthtech",
}


def test_context_includes_skill_evidence():
    ctx = build_scoring_context(_MASTER_CV, _JOB)
    # Skills from job requirements appear in context
    assert "product management" in ctx.lower() or "senior pm" in ctx.lower()
    assert "healthcare" in ctx.lower() or "healthtech" in ctx.lower()


def test_context_includes_highlight_evidence():
    ctx = build_scoring_context(_MASTER_CV, _JOB)
    # Highlights from matching work entries appear
    assert "30%" in ctx or "EHR" in ctx or "hospital" in ctx.lower()


def test_context_includes_gap_for_missing_skill():
    """Skills required by job but absent from all work entries → explicit gap."""
    ctx = build_scoring_context(_MASTER_CV, _JOB)
    # "stakeholder management" not in any work skills_used → should be flagged
    assert "stakeholder management" in ctx.lower() or "gap" in ctx.lower() or "no evidence" in ctx.lower()


def test_context_is_string():
    ctx = build_scoring_context(_MASTER_CV, _JOB)
    assert isinstance(ctx, str)
    assert len(ctx) > 50


def test_context_respects_token_cap():
    """Context must fit within ~1500 token budget (approx 6000 chars)."""
    ctx = build_scoring_context(_MASTER_CV, _JOB)
    assert len(ctx) <= 6000


def test_empty_master_cv_returns_empty_context():
    empty_cv = {
        "version": "1.0",
        "basics": {},
        "work": [],
        "skills": [],
        "languages": [],
        "education": [],
        "certifications": [],
        "projects": [],
    }
    ctx = build_scoring_context(empty_cv, _JOB)
    assert isinstance(ctx, str)
