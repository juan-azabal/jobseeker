"""Tests for shared/master_cv_extract.py — LLM extraction to Master CV JSON."""

import json
import unittest.mock as mock


def _valid_master_cv_json() -> str:
    cv = {
        "version": "1.0",
        "updated_at": "2024-01-01T00:00:00Z",
        "sources": ["cv_upload"],
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": None,
            "location": {"city": "Madrid", "country": "ES"},
            "url": None,
            "profiles": [],
        },
        "work": [
            {
                "id": "work_001",
                "company": "Spotify",
                "position": "Senior Product Manager",
                "location": "Stockholm, SE",
                "start_date": "2020-01",
                "end_date": None,
                "summary": "Led music recommendation features.",
                "highlights": ["Increased stream-start rate by 15% via A/B tested recommendation algorithm"],
                "skills_used": ["Product strategy", "A/B testing", "SQL"],
                "source": "cv_upload",
            }
        ],
        "education": [
            {
                "id": "edu_001",
                "institution": "MIT",
                "area": "Computer Science",
                "study_type": "Master",
                "start_date": "2015",
                "end_date": "2017",
                "source": "cv_upload",
            }
        ],
        "skills": [{"name": "Programming", "level": "senior", "keywords": ["Python", "SQL"], "source": "cv_upload"}],
        "languages": [{"language": "English", "fluency": "native"}],
        "certifications": [],
        "projects": [],
    }
    return json.dumps(cv)


def _make_fake_client(response_content: str):
    """Return a mock OpenAI client that returns fixed content."""
    response = mock.MagicMock()
    response.choices = [mock.MagicMock()]
    response.choices[0].message.content = response_content

    client = mock.MagicMock()
    client.chat.completions.create.return_value = response
    return client


class TestExtractMasterCvJson:
    def test_returns_dict_with_work_entries(self):
        from shared.master_cv_extract import extract_master_cv_json

        client = _make_fake_client(_valid_master_cv_json())
        result = extract_master_cv_json("Jane Doe, PM at Spotify...", "cv_upload", client)

        assert isinstance(result, dict)
        assert len(result["work"]) == 1
        assert result["work"][0]["company"] == "Spotify"
        assert result["work"][0]["id"] == "work_001"

    def test_returns_dict_with_education(self):
        from shared.master_cv_extract import extract_master_cv_json

        client = _make_fake_client(_valid_master_cv_json())
        result = extract_master_cv_json("CV text...", "cv_upload", client)

        assert len(result["education"]) == 1
        assert result["education"][0]["institution"] == "MIT"

    def test_schema_validation_passes(self):
        from shared.master_cv_extract import extract_master_cv_json

        client = _make_fake_client(_valid_master_cv_json())
        result = extract_master_cv_json("CV text...", "cv_upload", client)

        from shared.master_cv import validate_master_cv

        errors = validate_master_cv(result)
        assert errors == []

    def test_strips_json_code_fences(self):
        from shared.master_cv_extract import extract_master_cv_json

        # LLM sometimes wraps with ```json
        fenced = f"```json\n{_valid_master_cv_json()}\n```"
        client = _make_fake_client(fenced)
        result = extract_master_cv_json("CV text...", "cv_upload", client)
        assert isinstance(result, dict)

    def test_retries_once_on_invalid_json(self):
        from shared.master_cv_extract import extract_master_cv_json

        # First call returns invalid JSON, second returns valid
        response_invalid = mock.MagicMock()
        response_invalid.choices = [mock.MagicMock()]
        response_invalid.choices[0].message.content = "NOT VALID JSON {{{"

        response_valid = mock.MagicMock()
        response_valid.choices = [mock.MagicMock()]
        response_valid.choices[0].message.content = _valid_master_cv_json()

        client = mock.MagicMock()
        client.chat.completions.create.side_effect = [response_invalid, response_valid]

        result = extract_master_cv_json("CV text...", "cv_upload", client)
        assert isinstance(result, dict)
        assert client.chat.completions.create.call_count == 2

    def test_highlights_are_lists(self):
        from shared.master_cv_extract import extract_master_cv_json

        client = _make_fake_client(_valid_master_cv_json())
        result = extract_master_cv_json("CV text...", "cv_upload", client)

        for entry in result["work"]:
            assert isinstance(entry["highlights"], list)

    def test_max_tokens_is_8000(self):
        """Step 1.1 — _MAX_TOKENS must be 8000 to avoid truncating long CVs."""
        from shared import master_cv_extract

        assert master_cv_extract._MAX_TOKENS == 8000

    def test_llm_called_with_max_tokens_8000(self):
        """Step 1.1 — LLM is called with max_tokens=8000."""
        from shared.master_cv_extract import extract_master_cv_json

        client = _make_fake_client(_valid_master_cv_json())
        extract_master_cv_json("CV text...", "cv_upload", client)

        call_kwargs = client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 8000
