"""Tests for scorer.py v2 — categorical grades output and rubric v2 path."""

import json
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scorer
from tests.fixtures import BASELINE_PROFILE


def _reset_scorer():
    scorer._SCORING_RUBRIC_CACHE = None


def _make_v2_response(technical_depth="A", profile_evidence="B"):
    content = json.dumps(
        {
            "technical_depth": technical_depth,
            "profile_evidence": profile_evidence,
            "strengths": [{"claim": "Strong data platform experience", "evidence": "Led Kafka migration"}],
            "gaps": [
                {
                    "gap": "No Snowflake experience",
                    "severity": "low",
                    "category": "vendor-specific",
                    "mitigation": "Easy to learn",
                }
            ],
            "deal_breakers": [],
            "talking_points": ["Led cross-team data platform ownership at scale"],
            "one_line_verdict": "Strong technical fit, minor skill gap in Snowflake",
        }
    )
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


def _make_v1_response(score=75):
    """Legacy v1 response with top-level score."""
    content = json.dumps(
        {
            "score": score,
            "score_breakdown": {
                "domain_fit": 20,
                "seniority_fit": 18,
                "technical_depth": 17,
                "profile_evidence": 15,
                "strategic_impact": 5,
            },
            "strengths": [{"claim": "Good fit", "evidence": "5 years PM"}],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": ["Strong domain match"],
            "one_line_verdict": "Good fit",
        }
    )
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


JOB = {
    "id": "scorer-v2-test-001",
    "title": "Senior Data PM",
    "company": "Acme",
    "location": "Remote",
    "parsed": {
        "domain": "data",
        "seniority": "senior",
        "location_type": "remote",
        "must_have_skills": ["SQL", "dbt"],
        "nice_to_have_skills": ["Kafka"],
        "technical_stack": ["SQL", "dbt", "Kafka"],
        "responsibilities_summary": "Own data platform strategy.",
        "red_flags": [],
        "key_phrases": ["data platform ownership"],
    },
}


class TestScorerV2RubricPath:
    def setup_method(self):
        _reset_scorer()

    def test_scoring_rubric_path_points_to_v2(self):
        """_SCORING_RUBRIC_PATH must point to scoring-rubric-v2.md."""
        assert "scoring-rubric-v2" in str(scorer._SCORING_RUBRIC_PATH)

    def test_build_scoring_prompt_uses_v2(self):
        """Generated prompt must contain v2 grade fields, not score_breakdown."""
        import copy

        prompt = scorer._build_scoring_prompt(copy.deepcopy(BASELINE_PROFILE))
        assert "technical_depth" in prompt
        assert "profile_evidence" in prompt
        assert "score_breakdown" not in prompt

    def test_build_scoring_prompt_has_no_score_integer(self):
        """v2 prompt must not instruct LLM to produce a top-level score integer."""
        import copy

        prompt = scorer._build_scoring_prompt(copy.deepcopy(BASELINE_PROFILE))
        assert '"score":' not in prompt


class TestScoreJobV2Output:
    def setup_method(self):
        _reset_scorer()

    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_score_job_returns_technical_depth_grade(self, mock_openai_cls, mock_retrieve):
        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "Led data platform"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response("A", "B")

        import copy

        result = scorer.score_job(copy.deepcopy(JOB), MagicMock(), copy.deepcopy(BASELINE_PROFILE))
        assert result["rag_score"] is not None
        assert result["rag_score"]["technical_depth"] == "A"
        assert result["rag_score"]["profile_evidence"] == "B"

    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_score_job_has_no_score_breakdown(self, mock_openai_cls, mock_retrieve):
        """v2 rag_score must NOT contain score_breakdown when LLM returns v2 format."""
        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response("B", "C")

        import copy

        result = scorer.score_job(copy.deepcopy(JOB), MagicMock(), copy.deepcopy(BASELINE_PROFILE))
        assert "score_breakdown" not in result["rag_score"]

    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_score_job_retains_qualitative_fields(self, mock_openai_cls, mock_retrieve):
        """v2 rag_score must retain strengths, gaps, deal_breakers, talking_points, verdict."""
        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response("A", "A")

        import copy

        result = scorer.score_job(copy.deepcopy(JOB), MagicMock(), copy.deepcopy(BASELINE_PROFILE))
        rs = result["rag_score"]
        assert "strengths" in rs
        assert "gaps" in rs
        assert "deal_breakers" in rs
        assert "talking_points" in rs
        assert "one_line_verdict" in rs

    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_score_job_handles_v1_response_gracefully(self, mock_openai_cls, mock_retrieve):
        """Backward compat: v1 response (has score field) must not crash score_job."""
        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v1_response(75)

        import copy

        result = scorer.score_job(copy.deepcopy(JOB), MagicMock(), copy.deepcopy(BASELINE_PROFILE))
        # Must not raise; rag_score dict is preserved as-is
        assert result["rag_score"] is not None
        # v1 response preserved (legacy path)
        assert result["rag_score"]["score"] == 75

    def test_max_tokens_is_800(self):
        """scorer.py max_tokens must be 800 for v2 (shorter output)."""
        import inspect

        src = inspect.getsource(scorer.score_job)
        assert "max_tokens=800" in src
