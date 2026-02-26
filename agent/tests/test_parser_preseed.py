"""
Unit tests for Step 3.2:
parser.py runs preseed_parsed() before LLM call.
Factual pre-seeded fields override LLM output.
Interpretive fields use LLM output.
"""

import sys
import os
import json

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _llm_response(parsed_dict: dict):
    """Build a mock OpenAI chat completion response."""
    mock = MagicMock()
    mock.choices[0].message.content = json.dumps(parsed_dict)
    mock.usage.prompt_tokens = 100
    mock.usage.completion_tokens = 50
    return mock


def _base_llm_output(**overrides) -> dict:
    base = {
        "seniority": "mid",
        "years_experience_min": None,
        "years_experience_max": None,
        "location_type": "onsite",
        "locations_mentioned": ["New York"],
        "must_have_skills": ["Python", "SQL"],
        "nice_to_have_skills": [],
        "technical_stack": ["Python"],
        "experience_requirements": ["5 years PM experience"],
        "domain": "fintech",
        "role_function": "product",
        "responsibilities_summary": "Lead product strategy.",
        "team_size_hints": None,
        "salary_mentioned": None,
        "remote_restriction": None,
        "red_flags": [],
        "key_phrases": ["data-driven product", "cross-functional"],
    }
    base.update(overrides)
    return base


def _job(**kwargs) -> dict:
    base = {
        "id": "abc123",
        "title": "Senior PM",
        "company": "Acme",
        "source": "linkedin",
        "description": "A" * 200,  # long enough to parse
        "location": "Barcelona",
    }
    base.update(kwargs)
    return base


class TestPreseedInParser:

    def test_preseed_called_before_llm(self):
        """preseed_parsed is called for every job that goes to LLM."""
        from parser import parse_jd

        job = _job(job_level="Director", remote_type="fulltime")
        mock_resp = _llm_response(_base_llm_output())

        with patch("parser._make_openai_client") as mock_client_factory, \
             patch("parser.preseed_parsed") as mock_preseed:
            mock_preseed.return_value = {}
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            parse_jd(job)
            mock_preseed.assert_called_once_with(job)

    def test_factual_seniority_overrides_llm(self):
        """Pre-seeded seniority wins over LLM output."""
        from parser import parse_jd

        # LLM says "mid", pre-seed says "director" (from job_level)
        job = _job(job_level="Director")
        mock_resp = _llm_response(_base_llm_output(seniority="mid"))

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            assert result["parsed"]["seniority"] == "director"

    def test_factual_location_type_overrides_llm(self):
        """Pre-seeded location_type wins over LLM output."""
        from parser import parse_jd

        # LLM says "onsite", pre-seed says "remote" (from remote_type)
        job = _job(remote_type="fulltime")
        mock_resp = _llm_response(_base_llm_output(location_type="onsite"))

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            assert result["parsed"]["location_type"] == "remote"

    def test_factual_experience_overrides_llm(self):
        """Pre-seeded years_experience_min/max wins over LLM."""
        from parser import parse_jd

        job = _job(experience_min=5, experience_max=10)
        mock_resp = _llm_response(_base_llm_output(
            years_experience_min=3, years_experience_max=6
        ))

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            assert result["parsed"]["years_experience_min"] == 5
            assert result["parsed"]["years_experience_max"] == 10

    def test_interpretive_domain_uses_llm(self):
        """Domain is interpretive — LLM output wins (not pre-seeded override)."""
        from parser import parse_jd

        # company_industry maps to "healthtech", but LLM says "saas"
        job = _job(company_industry="Hospital & Health Care")
        mock_resp = _llm_response(_base_llm_output(domain="saas"))

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            # LLM wins for domain
            assert result["parsed"]["domain"] == "saas"

    def test_preseed_hint_in_system_prompt(self):
        """When preseed has values, they appear in the system message."""
        from parser import parse_jd

        job = _job(job_level="Director", remote_type="fulltime")
        mock_resp = _llm_response(_base_llm_output())

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            parse_jd(job)
            call_args = client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages") or call_args.args[0] if call_args.args else []
            if not messages:
                messages = call_args[1].get("messages", [])

            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            # Pre-seed values should appear in system prompt
            assert "director" in system_msg.lower() or "pre-determined" in system_msg.lower() or "pre-seeded" in system_msg.lower()

    def test_no_preseed_when_no_structured_fields(self):
        """No structured fields → preseed dict empty → prompt unchanged."""
        from parser import parse_jd

        job = _job()  # no structured fields
        mock_resp = _llm_response(_base_llm_output(seniority="senior"))

        with patch("parser._make_openai_client") as mock_client_factory, \
             patch("parser.preseed_parsed", return_value={}) as mock_preseed:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            # LLM output used as-is when no preseed
            assert result["parsed"]["seniority"] == "senior"

    def test_salary_factual_override(self):
        """Pre-seeded salary_mentioned wins over null LLM output."""
        from parser import parse_jd

        job = _job(
            min_amount=80000.0, max_amount=100000.0,
            currency="EUR", interval="yearly",
            salary_source="direct_data",
        )
        mock_resp = _llm_response(_base_llm_output(salary_mentioned=None))

        with patch("parser._make_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_factory.return_value = client

            result = parse_jd(job)
            sal = result["parsed"].get("salary_mentioned")
            assert sal is not None
            assert "80" in sal

    def test_short_description_skips_preseed(self):
        """Jobs with too-short description skip parsing entirely (no crash)."""
        from parser import parse_jd

        job = _job(description="Short")  # < 100 chars
        result = parse_jd(job)
        assert result["parsed"] is None
        assert result["parse_error"] is not None
