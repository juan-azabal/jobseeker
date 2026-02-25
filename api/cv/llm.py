"""LLM abstraction for CV generation.

Provider-agnostic interface configured via environment variables:
  CV_LLM_PROVIDER  — anthropic (default) | openai
  CV_LLM_MODEL     — optional model override
  ANTHROPIC_API_KEY — required when provider=anthropic
  OPENAI_API_KEY    — required when provider=openai
"""
import os
import re

import structlog

logger = structlog.get_logger(__name__)

_DEFAULTS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
}


def strip_analysis(text: str) -> str:
    """Strip the <analysis>...</analysis> chain-of-thought block from LLM output.

    The plan-aware system prompt instructs the LLM to output an <analysis> block
    with reasoning before the CV markdown.  This function removes that block so
    the caller always receives clean CV markdown ready for docx_builder.

    Args:
        text: Raw LLM output, possibly starting with <analysis>...</analysis>.

    Returns:
        CV markdown string with the analysis block removed.  If no analysis block
        is present the input is returned unchanged (safe to call unconditionally).
    """
    cleaned = re.sub(r"<analysis>.*?</analysis>\s*", "", text, flags=re.DOTALL)
    return cleaned.strip()


def generate_cv(system_prompt: str, user_prompt: str) -> str:
    """Call the configured LLM and return the generated CV markdown string.

    Args:
        system_prompt: Full system prompt including reference files and output contract.
        user_prompt: Job description + scored data + user CV context.

    Returns:
        Raw markdown string from the LLM (structured CV content).

    Raises:
        ValueError: If CV_LLM_PROVIDER is unknown.
        RuntimeError: If the required API key env var is missing.
    """
    provider = os.environ.get("CV_LLM_PROVIDER", "anthropic").lower()
    model_override = os.environ.get("CV_LLM_MODEL", "").strip()

    if provider == "anthropic":
        raw = _call_anthropic(system_prompt, user_prompt, model_override)
    elif provider == "openai":
        raw = _call_openai(system_prompt, user_prompt, model_override)
    else:
        raise ValueError(
            f"Unknown CV_LLM_PROVIDER: '{provider}'. Must be 'anthropic' or 'openai'."
        )
    return strip_analysis(raw)


def _call_anthropic(system_prompt: str, user_prompt: str, model_override: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it in .env or your deployment environment."
        )

    import anthropic

    model = model_override or _DEFAULTS["anthropic"]
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_openai(system_prompt: str, user_prompt: str, model_override: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it in .env or your deployment environment."
        )

    import openai

    model = model_override or _DEFAULTS["openai"]
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
