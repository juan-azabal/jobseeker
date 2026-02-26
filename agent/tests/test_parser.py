"""Tests for parser.py and parser-prompt.md v1.4."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

VALID_ROLE_FUNCTIONS = {
    "product",
    "engineering",
    "design",
    "data",
    "marketing",
    "sales",
    "ops",
    "support",
    "other",
}


# ---------------------------------------------------------------------------
# 17.1.1 — role_function field in prompt and schema
# ---------------------------------------------------------------------------


class TestRoleFunctionInPrompt:
    def test_parser_prompt_contains_role_function_field(self):
        """Prompt JSON output schema must include role_function key."""
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"role_function"' in content

    def test_parser_prompt_lists_all_role_function_values(self):
        """Prompt must enumerate all 9 role_function values."""
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        for value in VALID_ROLE_FUNCTIONS:
            assert value in content, f"Missing role_function value '{value}' in prompt"

    def test_parser_prompt_contains_role_function_guide(self):
        """Prompt must include a _role_function_guide field for LLM guidance."""
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"_role_function_guide"' in content

    def test_schema_contains_role_function(self):
        """parsed_job.json schema must include role_function field."""
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "role_function" in schema

    def test_schema_role_function_enum_string(self):
        """schema role_function value must be the enum string."""
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        rf = schema["role_function"]
        for value in VALID_ROLE_FUNCTIONS:
            assert value in rf, f"Missing '{value}' in schema role_function"


class TestParseJdRoleFunction:
    def _make_llm_response(self, role_function="product"):
        """Build a minimal mock LLM response with role_function."""
        content = json.dumps(
            {
                "seniority": "senior",
                "years_experience_min": 5,
                "years_experience_max": None,
                "location_type": "remote",
                "locations_mentioned": [],
                "must_have_skills": ["Python"],
                "nice_to_have_skills": [],
                "technical_stack": ["Python"],
                "experience_requirements": [],
                "domain": "saas",
                "responsibilities_summary": "Lead product.",
                "team_size_hints": None,
                "salary_mentioned": None,
                "remote_restriction": None,
                "red_flags": [],
                "key_phrases": ["product-led growth"],
                "role_function": role_function,
            }
        )
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        return mock_response

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_role_function(self, mock_factory):
        """parse_jd must store role_function from LLM response."""
        from parser import parse_jd, _PARSER_PROMPT_CACHE  # noqa: F401
        import parser as parser_mod

        # Reset cache so fresh prompt is loaded
        parser_mod._PARSER_PROMPT_CACHE = None

        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_llm_response("product")

        job = {
            "id": "test-001",
            "title": "Senior Product Manager",
            "company": "Acme",
            "location": "Remote",
            "description": "We are looking for a Senior Product Manager " * 10,
        }
        result = parse_jd(job)
        assert result["parsed"] is not None
        assert result["parsed"]["role_function"] == "product"

    @patch("parser._make_openai_client")
    def test_parse_jd_handles_missing_role_function(self, mock_factory):
        """parse_jd gracefully handles LLM response without role_function (backward compat)."""
        from parser import parse_jd  # noqa: F811
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None

        response = self._make_llm_response("product")
        content_dict = json.loads(response.choices[0].message.content)
        del content_dict["role_function"]
        response.choices[0].message.content = json.dumps(content_dict)

        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = response

        job = {
            "id": "test-002",
            "title": "Senior PM",
            "company": "Acme",
            "location": "Remote",
            "description": "We are looking for a Senior Product Manager " * 10,
        }
        result = parse_jd(job)
        # Must not crash; role_function simply absent
        assert result["parsed"] is not None
        assert "role_function" not in result["parsed"] or result["parsed"].get("role_function") is None
