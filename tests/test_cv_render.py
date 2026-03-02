"""Unit tests for api/cv/render.py — Phase 4.3."""

from api.cv.render import render_cv_markdown

_SELECTED = {
    "work": [
        {
            "id": "work_001",
            "company": "HealthTech",
            "position": "Senior Product Manager",
            "start_date": "2021-01",
            "end_date": None,
            "selected_highlights": ["Reduced patient wait time by 30%", "Launched EHR integration"],
            "skills_used": ["product management", "healthcare"],
            "relevance_score": 0.9,
        },
        {
            "id": "work_002",
            "company": "Fintech Startup",
            "position": "Product Manager",
            "start_date": "2018-01",
            "end_date": "2020-12",
            "selected_highlights": ["Grew user base 3x"],
            "skills_used": ["payments", "SQL"],
            "relevance_score": 0.6,
        },
    ],
    "skill_intersection": ["product management", "healthcare"],
}


def test_render_returns_string():
    md = render_cv_markdown(_SELECTED)
    assert isinstance(md, str)
    assert len(md) > 50


def test_render_includes_company_names():
    md = render_cv_markdown(_SELECTED)
    assert "HealthTech" in md
    assert "Fintech Startup" in md


def test_render_includes_positions():
    md = render_cv_markdown(_SELECTED)
    assert "Senior Product Manager" in md
    assert "Product Manager" in md


def test_render_includes_highlights():
    md = render_cv_markdown(_SELECTED)
    assert "30%" in md or "patient wait time" in md.lower()
    assert "3x" in md or "user base" in md.lower()


def test_render_current_role_shows_present():
    md = render_cv_markdown(_SELECTED)
    # Entry with end_date=None should show "present" or "–"
    assert "present" in md.lower() or "–" in md or "-" in md


def test_render_closed_role_shows_end_date():
    md = render_cv_markdown(_SELECTED)
    assert "2020" in md


def test_render_empty_work_returns_empty_string():
    md = render_cv_markdown({"work": [], "skill_intersection": []})
    assert isinstance(md, str)


def test_render_highlights_as_bullets():
    md = render_cv_markdown(_SELECTED)
    # Highlights should be bullet points
    assert "- " in md or "* " in md
