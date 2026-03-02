"""Tests for scorer.py enriched context injection from master_cv.json — Phase 3.2."""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scorer
from tests.fixtures import BASELINE_PROFILE

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
            "highlights": ["Reduced patient wait time by 30%", "Launched EHR integration"],
            "skills_used": ["product management", "healthcare", "SQL"],
            "source": "cv_upload",
        }
    ],
    "education": [],
    "skills": [{"name": "product management"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}

_JOB = {
    "id": "test-enrich-001",
    "title": "PM Health Platform",
    "company": "MedCo",
    "location": "Remote",
    "parsed": {
        "domain": "healthtech",
        "seniority": "senior",
        "location_type": "remote",
        "must_have_skills": ["product management", "healthcare"],
        "nice_to_have_skills": ["SQL"],
        "technical_stack": [],
        "responsibilities_summary": "Own health product roadmap.",
        "red_flags": [],
        "key_phrases": ["health platform"],
    },
}


def _make_v2_response():
    content = json.dumps(
        {
            "technical_depth": "A",
            "profile_evidence": "B",
            "strengths": [],
            "gaps": [],
            "deal_breakers": [],
            "talking_points": [],
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


class TestScorerMasterCvEnrichment:
    def setup_method(self):
        scorer._SCORING_RUBRIC_CACHE = None

    @patch.dict(os.environ, {"POSTHOG_API_KEY": ""})
    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_master_cv_context_injected_when_file_exists(self, mock_openai_cls, mock_retrieve):
        """When master_cv.json exists in knowledge_dir, context is injected into the prompt."""
        import copy

        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            cv_path = os.path.join(tmpdir, "master_cv.json")
            with open(cv_path, "w") as f:
                json.dump(_MASTER_CV, f)

            scorer.score_job(
                copy.deepcopy(_JOB),
                MagicMock(),
                copy.deepcopy(BASELINE_PROFILE),
                knowledge_dir=tmpdir,
            )

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Master CV Evidence" in user_msg or "Skill Evidence" in user_msg
        assert "product management" in user_msg.lower()

    @patch.dict(os.environ, {"POSTHOG_API_KEY": ""})
    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_no_injection_when_file_missing(self, mock_openai_cls, mock_retrieve):
        """When master_cv.json is absent, scoring behaves exactly as before."""
        import copy

        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response()

        result = scorer.score_job(
            copy.deepcopy(_JOB),
            MagicMock(),
            copy.deepcopy(BASELINE_PROFILE),
            knowledge_dir="/tmp/nonexistent_dir_xyz",
        )

        assert result["rag_score"] is not None
        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Master CV Evidence" not in user_msg

    @patch.dict(os.environ, {"POSTHOG_API_KEY": ""})
    @patch("vectorstore.retrieve_relevant_chunks")
    @patch("openai.OpenAI")
    def test_no_injection_when_knowledge_dir_empty(self, mock_openai_cls, mock_retrieve):
        """knowledge_dir='' (default) — no injection, backward compatible."""
        import copy

        mock_retrieve.return_value = [{"source": "cv", "section": "exp", "text": "PM experience"}]
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_v2_response()

        result = scorer.score_job(
            copy.deepcopy(_JOB),
            MagicMock(),
            copy.deepcopy(BASELINE_PROFILE),
        )

        assert result["rag_score"] is not None
