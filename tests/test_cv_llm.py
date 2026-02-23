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

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.cv.llm import generate_cv
        result = generate_cv("system prompt", "user prompt")

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

    with patch("openai.OpenAI", return_value=mock_client):
        # Re-import to pick up new env var
        import importlib
        import api.cv.llm as llm_module
        importlib.reload(llm_module)
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

    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib
        import api.cv.llm as llm_module
        importlib.reload(llm_module)
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

    with patch("openai.OpenAI", return_value=mock_client):
        import importlib
        import api.cv.llm as llm_module
        importlib.reload(llm_module)
        llm_module.generate_cv("sys", "usr")

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4-turbo"
