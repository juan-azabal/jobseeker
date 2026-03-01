"""Tests for parser v1.5 fields: role_in_plain_english, company_context,
verbatim_for_cv, truly_required, preferred_skills, and backward compat.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

JARGON_MARKERS = {
    "synergize",
    "leverage",
    "impactful",
    "passionate",
    "ninja",
    "rockstar",
    "thought leader",
    "bandwidth",
}

_VALID_STAGES = {"early", "growth", "mature", "public", "unknown"}
_VALID_TONES = {
    "startup_scrappy",
    "corporate_polished",
    "technical_serious",
    "mission_driven",
    "unknown",
}


def _build_v15_response(
    *,
    role_in_plain_english="You will own the data platform roadmap, work with 3 engineers, and present weekly to the VP of Product. Daily work includes backlog grooming and SQL-based analysis.",
    company_context=None,
    verbatim_for_cv=None,
    truly_required=None,
    preferred_skills=None,
) -> MagicMock:
    """Return a mock LLM response with v1.5 fields."""
    if company_context is None:
        company_context = {
            "stage": "growth",
            "what_they_value": ["data-driven decisions", "fast iteration"],
            "tone": "technical_serious",
        }
    if verbatim_for_cv is None:
        verbatim_for_cv = [
            "event-driven architecture",
            "product-led growth",
            "Series B to C transition",
            "zero-to-one product",
            "data mesh",
        ]
    if truly_required is None:
        truly_required = ["SQL", "Python", "dbt"]
    if preferred_skills is None:
        preferred_skills = ["Kafka", "Airflow"]

    content = json.dumps(
        {
            "seniority": "senior",
            "years_experience_min": 5,
            "years_experience_max": None,
            "location_type": "remote",
            "locations_mentioned": [],
            "truly_required": truly_required,
            "preferred_skills": preferred_skills,
            "technical_stack": truly_required + preferred_skills,
            "experience_requirements": ["5+ years in data engineering"],
            "domain": "data",
            "role_function": "data",
            "role_in_plain_english": role_in_plain_english,
            "company_context": company_context,
            "verbatim_for_cv": verbatim_for_cv,
            "responsibilities_summary": "Lead data platform development.",
            "team_size_hints": None,
            "salary_mentioned": None,
            "remote_restriction": None,
            "red_flags": [],
            "key_phrases": ["event-driven architecture"],
        }
    )
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 300
    mock_response.usage.completion_tokens = 500
    return mock_response


def _build_old_format_response() -> MagicMock:
    """Mock LLM response using pre-v1.5 field names for backward compat test."""
    content = json.dumps(
        {
            "seniority": "mid",
            "years_experience_min": 3,
            "years_experience_max": None,
            "location_type": "hybrid",
            "locations_mentioned": ["Barcelona"],
            "must_have_skills": ["Python", "SQL"],
            "nice_to_have_skills": ["Docker"],
            "technical_stack": ["Python", "SQL", "Docker"],
            "experience_requirements": ["3+ years in product"],
            "domain": "saas",
            "role_function": "product",
            "responsibilities_summary": "Manage product backlog.",
            "team_size_hints": None,
            "salary_mentioned": None,
            "remote_restriction": None,
            "red_flags": [],
            "key_phrases": ["B2B SaaS"],
        }
    )
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 200
    mock_response.usage.completion_tokens = 400
    return mock_response


# ---------------------------------------------------------------------------
# 1.5.1 — Prompt and schema contain v1.5 fields
# ---------------------------------------------------------------------------


class TestV15PromptAndSchema:
    def test_prompt_contains_truly_required(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"truly_required"' in content

    def test_prompt_contains_preferred_skills(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"preferred_skills"' in content

    def test_prompt_contains_role_in_plain_english(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"role_in_plain_english"' in content

    def test_prompt_contains_company_context(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"company_context"' in content

    def test_prompt_contains_verbatim_for_cv(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"verbatim_for_cv"' in content

    def test_prompt_version_is_v15(self):
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert "v1.5" in content

    def test_prompt_no_longer_uses_must_have_skills_as_field(self):
        """must_have_skills should not appear as a JSON output key in v1.5 prompt."""
        content = (PROMPTS_DIR / "parser-prompt.md").read_text()
        assert '"must_have_skills"' not in content

    def test_schema_contains_truly_required(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "truly_required" in schema

    def test_schema_contains_preferred_skills(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "preferred_skills" in schema

    def test_schema_contains_role_in_plain_english(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "role_in_plain_english" in schema

    def test_schema_contains_company_context(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "company_context" in schema

    def test_schema_contains_verbatim_for_cv(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        assert "verbatim_for_cv" in schema

    def test_schema_company_context_has_required_subkeys(self):
        schema = json.loads((SCHEMAS_DIR / "parsed_job.json").read_text())
        ctx = schema["company_context"]
        assert isinstance(ctx, dict)
        for key in ("stage", "what_they_value", "tone"):
            assert key in ctx, f"Missing company_context.{key} in schema"


# ---------------------------------------------------------------------------
# 1.5.2 — parse_jd stores v1.5 fields when LLM returns them
# ---------------------------------------------------------------------------


class TestParseJdV15Fields:
    def _make_job(self) -> dict:
        return {
            "id": "test-v15-001",
            "title": "Senior Data Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "description": "We are building a real-time data platform at Acme. " * 12,
        }

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_role_in_plain_english(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response()

        result = parser_mod.parse_jd(self._make_job())
        p = result["parsed"]
        assert p is not None
        assert isinstance(p["role_in_plain_english"], str)
        assert len(p["role_in_plain_english"]) >= 50
        assert len(p["role_in_plain_english"]) <= 300

    @patch("parser._make_openai_client")
    def test_role_in_plain_english_has_no_jargon(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response()

        result = parser_mod.parse_jd(self._make_job())
        text = (result["parsed"]["role_in_plain_english"] or "").lower()
        found_jargon = [j for j in JARGON_MARKERS if j in text]
        assert not found_jargon, f"Jargon found: {found_jargon}"

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_company_context(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response()

        result = parser_mod.parse_jd(self._make_job())
        ctx = result["parsed"]["company_context"]
        assert isinstance(ctx, dict)
        assert ctx["stage"] in _VALID_STAGES, f"Invalid stage: {ctx['stage']}"
        assert ctx["tone"] in _VALID_TONES, f"Invalid tone: {ctx['tone']}"
        values = ctx["what_they_value"]
        assert isinstance(values, list)
        assert 1 <= len(values) <= 3

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_verbatim_for_cv(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response()

        result = parser_mod.parse_jd(self._make_job())
        phrases = result["parsed"]["verbatim_for_cv"]
        assert isinstance(phrases, list)
        assert 3 <= len(phrases) <= 8, f"Expected 3-8 phrases, got {len(phrases)}"
        for phrase in phrases:
            word_count = len(phrase.split())
            assert 2 <= word_count <= 6, f"Phrase too long or short: '{phrase}'"

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_truly_required(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response(truly_required=["SQL", "Python", "dbt"])

        result = parser_mod.parse_jd(self._make_job())
        assert result["parsed"]["truly_required"] == ["SQL", "Python", "dbt"]

    @patch("parser._make_openai_client")
    def test_parse_jd_stores_preferred_skills(self, mock_factory):
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_v15_response(preferred_skills=["Kafka", "Airflow"])

        result = parser_mod.parse_jd(self._make_job())
        assert result["parsed"]["preferred_skills"] == ["Kafka", "Airflow"]


# ---------------------------------------------------------------------------
# 1.5.3 — Backward compat: old field names still work
# ---------------------------------------------------------------------------


class TestParseJdV15BackwardCompat:
    def _make_job(self) -> dict:
        return {
            "id": "test-compat-001",
            "title": "Product Manager",
            "company": "OldCo",
            "location": "Remote",
            "description": "We need a product manager to lead our growth team. " * 12,
        }

    @patch("parser._make_openai_client")
    def test_old_must_have_skills_copied_to_truly_required(self, mock_factory):
        """When LLM returns must_have_skills, truly_required is populated from it."""
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_old_format_response()

        result = parser_mod.parse_jd(self._make_job())
        p = result["parsed"]
        assert p is not None
        assert "truly_required" in p
        assert p["truly_required"] == ["Python", "SQL"]

    @patch("parser._make_openai_client")
    def test_old_nice_to_have_copied_to_preferred_skills(self, mock_factory):
        """When LLM returns nice_to_have_skills, preferred_skills is populated from it."""
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_old_format_response()

        result = parser_mod.parse_jd(self._make_job())
        p = result["parsed"]
        assert "preferred_skills" in p
        assert p["preferred_skills"] == ["Docker"]

    @patch("parser._make_openai_client")
    def test_old_response_does_not_crash(self, mock_factory):
        """Old-format LLM response does not raise and returns valid parsed data."""
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_old_format_response()

        result = parser_mod.parse_jd(self._make_job())
        assert result["parsed"] is not None
        assert result.get("parse_error") is None

    @patch("parser._make_openai_client")
    def test_new_fields_default_when_absent(self, mock_factory):
        """v1.5 fields default gracefully when LLM omits them."""
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        mock_client.chat.completions.create.return_value = _build_old_format_response()

        result = parser_mod.parse_jd(self._make_job())
        p = result["parsed"]
        # New fields default when absent from old-format response
        assert p.get("role_in_plain_english") is None
        assert p.get("company_context") is None
        assert p.get("verbatim_for_cv") == []


# ---------------------------------------------------------------------------
# 1.5.4 — @pytest.mark.slow: live validation (skipped in CI)
# ---------------------------------------------------------------------------


import os

_SKIP_LIVE = not os.environ.get("OPENAI_API_KEY")


@pytest.mark.slow
@pytest.mark.skipif(_SKIP_LIVE, reason="OPENAI_API_KEY not set")
class TestParseJdV15LiveValidation:
    """Live LLM validation — skipped unless OPENAI_API_KEY is set and -m slow is passed."""

    STARTUP_JD = """
    We're a Series B fintech startup building the next generation of B2B payments infrastructure.
    You'll be our first data engineer, owning the entire data stack.
    Must have: Python, SQL, dbt, Airflow. Nice to have: Kafka, Spark.
    You'll work directly with the CTO and 2 product engineers.
    We move fast and break things. No bureaucracy.
    """

    CORPORATE_JD = """
    Global financial services firm seeks Senior Product Manager for our
    Digital Transformation initiative. The successful candidate will
    synergize cross-functional teams and leverage best-in-class methodologies.
    Required: 8+ years experience, MBA preferred. Proficiency in Excel, PowerPoint.
    Must have: stakeholder management, executive presentation skills.
    """

    CONSULTANCY_JD = """
    Top-tier management consulting firm. You will lead data strategy engagements
    for Fortune 500 clients. Required: SQL, Python, Tableau. Experience in
    supply chain or logistics preferred. You'll be client-facing 60% of time,
    working on 3-4 projects simultaneously.
    """

    def _parse_live(self, description, title="Senior Product Manager", company="ACME"):
        """Run actual parser against live LLM."""
        import parser as parser_mod

        parser_mod._PARSER_PROMPT_CACHE = None
        job = {
            "id": "live-test",
            "title": title,
            "company": company,
            "location": "Remote",
            "description": description,
        }
        return parser_mod.parse_jd(job)

    def test_startup_job_has_early_or_growth_stage(self):
        result = self._parse_live(self.STARTUP_JD, company="FastPay")
        ctx = result["parsed"].get("company_context") or {}
        assert ctx.get("stage") in {"early", "growth"}, f"Expected early/growth, got {ctx.get('stage')}"

    def test_corporate_job_has_mature_or_public_stage(self):
        result = self._parse_live(self.CORPORATE_JD, company="BigBank")
        ctx = result["parsed"].get("company_context") or {}
        assert ctx.get("stage") in {"mature", "public", "unknown"}, f"Got stage: {ctx.get('stage')}"

    def test_startup_tone_is_startup_scrappy(self):
        result = self._parse_live(self.STARTUP_JD, company="FastPay")
        ctx = result["parsed"].get("company_context") or {}
        assert ctx.get("tone") == "startup_scrappy", f"Got tone: {ctx.get('tone')}"

    def test_corporate_tone_is_valid_enum(self):
        result = self._parse_live(self.CORPORATE_JD, company="BigBank")
        ctx = result["parsed"].get("company_context") or {}
        assert ctx.get("tone") in _VALID_TONES, f"Got invalid tone: {ctx.get('tone')}"

    def test_verbatim_phrases_are_domain_specific(self):
        result = self._parse_live(self.STARTUP_JD, company="FastPay")
        phrases = result["parsed"].get("verbatim_for_cv") or []
        assert len(phrases) >= 3, f"Expected ≥3 phrases, got {len(phrases)}"
        # None of the phrases should be generic tool names alone
        generic_tool_names = {"python", "sql", "excel", "tableau", "powerpoint"}
        for phrase in phrases:
            assert phrase.lower() not in generic_tool_names, f"Generic tool as phrase: '{phrase}'"
