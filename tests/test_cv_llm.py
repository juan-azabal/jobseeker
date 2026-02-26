"""Tests for api/cv/llm.py — LLM abstraction layer."""

import pytest
from unittest.mock import patch, MagicMock


def test_anthropic_provider_calls_correct_client(monkeypatch):
    """generate_cv() with CV_LLM_PROVIDER=anthropic calls anthropic client."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# John Doe\nSoftware Engineer")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    import importlib
    import api.cv.llm as llm_module

    importlib.reload(llm_module)  # reset singleton so patch takes effect

    with patch("posthog.ai.anthropic.Anthropic", return_value=mock_client):
        result = llm_module.generate_cv("system prompt", "user prompt")

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["system"] == "system prompt"
    assert call_kwargs["messages"][0]["content"] == "user prompt"
    assert result == "# John Doe\nSoftware Engineer"


def test_openai_provider_calls_correct_client(monkeypatch):
    """generate_cv() with CV_LLM_PROVIDER=openai calls openai client."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "# Jane Doe\nProduct Manager"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("posthog.ai.openai.OpenAI", return_value=mock_client):
        # Re-import to pick up new env var
        import importlib
        import api.cv.llm as llm_module

        importlib.reload(llm_module)  # reset singleton so patch takes effect
        result = llm_module.generate_cv("system prompt", "user prompt")

    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["max_tokens"] == 4096
    assert result == "# Jane Doe\nProduct Manager"


def test_invalid_provider_raises_value_error(monkeypatch):
    """generate_cv() with unknown provider raises ValueError."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "fakeai")

    import importlib
    import api.cv.llm as llm_module

    importlib.reload(llm_module)

    with pytest.raises(ValueError, match="fakeai"):
        llm_module.generate_cv("system", "user")


def test_missing_anthropic_api_key_raises_runtime_error(monkeypatch):
    """generate_cv() with missing ANTHROPIC_API_KEY raises RuntimeError."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    import importlib
    import api.cv.llm as llm_module

    importlib.reload(llm_module)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm_module.generate_cv("system", "user")


def test_missing_openai_api_key_raises_runtime_error(monkeypatch):
    """generate_cv() with missing OPENAI_API_KEY raises RuntimeError."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import importlib
    import api.cv.llm as llm_module

    importlib.reload(llm_module)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm_module.generate_cv("system", "user")


def test_cv_llm_model_override_anthropic(monkeypatch):
    """CV_LLM_MODEL env var overrides default model for anthropic."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CV_LLM_MODEL", "claude-opus-4-5")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="result")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("posthog.ai.anthropic.Anthropic", return_value=mock_client):
        import importlib
        import api.cv.llm as llm_module

        importlib.reload(llm_module)  # reset singleton so patch takes effect
        llm_module.generate_cv("sys", "usr")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-5"


def test_cv_llm_model_override_openai(monkeypatch):
    """CV_LLM_MODEL env var overrides default model for openai."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CV_LLM_MODEL", "gpt-4-turbo")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "result"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("posthog.ai.openai.OpenAI", return_value=mock_client):
        import importlib
        import api.cv.llm as llm_module

        importlib.reload(llm_module)  # reset singleton so patch takes effect
        llm_module.generate_cv("sys", "usr")

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4-turbo"


# ══════════════════════════════════════════════════════════════════════════
# strip_analysis tests (Step 6.3)
# ══════════════════════════════════════════════════════════════════════════

_CV_SAMPLE = """# John Doe
Senior Product Manager
Barcelona, Spain | john@example.com

## Summary

Experienced PM with a strong background in data platforms.

## Work Experience

### Acme Corp - Senior PM\t01/2020 - Present
_Global data platform team, 5 engineers._

- Built Snowplow tracking pipeline used by 20M users.
"""


def test_strip_analysis_removes_block():
    """<analysis>...</analysis> block is removed, returning clean CV markdown."""
    from api.cv.llm import strip_analysis

    raw = f"<analysis>\nSummary angle: emphasize consulting.\n</analysis>\n\n{_CV_SAMPLE}"
    result = strip_analysis(raw)
    assert result.startswith("# John Doe"), f"Expected output to start with '# John Doe', got: {result[:80]!r}"
    assert "<analysis>" not in result
    assert "</analysis>" not in result


def test_strip_analysis_noop_when_no_block():
    """strip_analysis is a no-op when there is no <analysis> block."""
    from api.cv.llm import strip_analysis

    result = strip_analysis(_CV_SAMPLE)
    assert result.strip() == _CV_SAMPLE.strip()


def test_strip_analysis_handles_multiline_block():
    """Multi-line <analysis> block is fully stripped."""
    from api.cv.llm import strip_analysis

    analysis = (
        "<analysis>\n"
        "Line 1: Summary angle.\n"
        "Line 2: Key skills mapping.\n"
        "Line 3: Differentiators.\n"
        "Line 4: Gaps to frame.\n"
        "</analysis>\n\n"
    )
    raw = analysis + _CV_SAMPLE
    result = strip_analysis(raw)
    assert "Line 1:" not in result
    assert "Line 4:" not in result
    assert "# John Doe" in result


def test_strip_analysis_handles_leading_whitespace():
    """Strips any blank lines between </analysis> and the CV start."""
    from api.cv.llm import strip_analysis

    raw = "<analysis>short</analysis>\n\n\n\n# Jane Smith\nSenior PM\n"
    result = strip_analysis(raw)
    assert result.startswith("# Jane Smith")


def test_strip_analysis_preserves_cv_content_exactly():
    """CV content after the analysis block is preserved."""
    from api.cv.llm import strip_analysis

    raw = "<analysis>abc</analysis>\n" + _CV_SAMPLE
    result = strip_analysis(raw)
    assert "Snowplow tracking pipeline" in result
    assert "Acme Corp" in result
    assert "## Summary" in result


def test_generate_cv_strips_analysis_automatically(monkeypatch):
    """generate_cv() automatically strips <analysis> blocks from LLM output."""
    monkeypatch.setenv("CV_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    raw_with_analysis = (
        "<analysis>\nSome reasoning here.\n</analysis>\n\n# John Doe\nSenior PM\n## Summary\nExperienced PM."
    )
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=raw_with_analysis)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("posthog.ai.anthropic.Anthropic", return_value=mock_client):
        import importlib
        import api.cv.llm as llm_module

        importlib.reload(llm_module)  # reset singleton so patch takes effect
        result = llm_module.generate_cv("system", "user")

    assert "<analysis>" not in result, "generate_cv must strip analysis blocks"
    assert "# John Doe" in result
