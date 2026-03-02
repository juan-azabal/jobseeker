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


# --- Phase 3.3: ChromaDB-enhanced gap detection ---

_CV_NO_HEALTHCARE = {
    **_MASTER_CV,
    "work": [
        {
            **_MASTER_CV["work"][0],
            "skills_used": ["product management"],  # healthcare removed
        }
    ],
}

_JOB_HEALTHCARE_REQ = {
    "must_have_skills": ["healthcare"],
    "nice_to_have_skills": [],
}


def test_query_fn_provides_semantic_evidence_when_close_match():
    """query_fn returning distance ≤ 0.5 → highlight shown as semantic evidence."""

    def mock_query(_skill):
        return [{"document": "Reduced patient wait time by 30%", "distance": 0.2}]

    ctx = build_scoring_context(_CV_NO_HEALTHCARE, _JOB_HEALTHCARE_REQ, query_fn=mock_query)
    assert "30%" in ctx or "patient wait time" in ctx.lower()


def test_query_fn_marks_gap_when_no_semantic_match():
    """query_fn returning distance > 0.5 → [GAP] marker added."""

    def mock_query(_skill):
        return [{"document": "unrelated content about fintech", "distance": 0.9}]

    ctx = build_scoring_context(_CV_NO_HEALTHCARE, _JOB_HEALTHCARE_REQ, query_fn=mock_query)
    assert "[GAP]" in ctx


def test_query_fn_marks_gap_when_empty_results():
    """query_fn returning empty list → [GAP] marker added."""

    def mock_query(_skill):
        return []

    ctx = build_scoring_context(_CV_NO_HEALTHCARE, _JOB_HEALTHCARE_REQ, query_fn=mock_query)
    assert "[GAP]" in ctx


def test_no_query_fn_uses_deterministic_gap_no_marker():
    """Without query_fn, gap shows 'No evidence' but no [GAP] marker (backward compat)."""
    ctx = build_scoring_context(_CV_NO_HEALTHCARE, _JOB_HEALTHCARE_REQ)
    assert "No evidence" in ctx
    assert "[GAP]" not in ctx
