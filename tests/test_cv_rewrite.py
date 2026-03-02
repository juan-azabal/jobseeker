"""Unit tests for api/cv/rewrite.py — Phase 4.2."""

import json
from unittest.mock import MagicMock, patch

from api.cv.rewrite import rewrite_cv_content

_SELECTED = {
    "work": [
        {
            "id": "work_001",
            "company": "HealthTech",
            "position": "Senior PM",
            "start_date": "2021-01",
            "end_date": None,
            "selected_highlights": ["Reduced patient wait time by 30%"],
            "skills_used": ["product management", "healthcare"],
            "relevance_score": 0.9,
        }
    ],
    "skill_intersection": ["product management"],
}

_JOB = {
    "title": "Head of Product",
    "company": "MedCo",
    "parsed": {
        "must_have_skills": ["product management"],
        "domain": "healthtech",
        "responsibilities_summary": "Own health platform roadmap.",
    },
}


def _make_llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestRewriteCvContent:
    @patch("api.cv.rewrite.generate_cv")
    def test_returns_string(self, mock_gen):
        mock_gen.return_value = (
            "## Work Experience\n\n### HealthTech\n**Senior PM** | 2021-01 – present\n- Reduced wait time."
        )
        result = rewrite_cv_content(_SELECTED, _JOB, distinct_id="user_1")
        assert isinstance(result, str)
        assert len(result) > 10

    @patch("api.cv.rewrite.generate_cv")
    def test_calls_generate_cv_with_distinct_id(self, mock_gen):
        mock_gen.return_value = "## Work Experience"
        rewrite_cv_content(_SELECTED, _JOB, distinct_id="user_42")
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert "user_42" in str(call_kwargs)

    @patch("api.cv.rewrite.generate_cv")
    def test_preserves_company_name(self, mock_gen):
        mock_gen.return_value = "## Work Experience\n\n### HealthTech\n**Senior PM** | 2021-01 – present"
        result = rewrite_cv_content(_SELECTED, _JOB, distinct_id="u1")
        assert "HealthTech" in result

    @patch("api.cv.rewrite.generate_cv", side_effect=Exception("LLM unavailable"))
    def test_falls_back_to_rendered_markdown_on_error(self, mock_gen):
        """If LLM fails, return the rendered markdown unchanged."""
        result = rewrite_cv_content(_SELECTED, _JOB, distinct_id="u1")
        assert isinstance(result, str)
        # Should fall back to rendered markdown
        assert "HealthTech" in result
