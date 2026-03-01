"""LLM abstraction for CV generation.

Provider-agnostic interface configured via environment variables:
  CV_LLM_PROVIDER  — anthropic (default) | openai
  LLM_MODEL_CV     — optional model override (reads via api.config; replaces CV_LLM_MODEL)
  ANTHROPIC_API_KEY — required when provider=anthropic
  OPENAI_API_KEY    — required when provider=openai

LLM calls are automatically instrumented via posthog.ai wrappers so that
token usage and latency are recorded in PostHog (no-op when PostHog is not
initialised, i.e. POSTHOG_API_KEY is absent in dev/test).
"""

import os
import re

import structlog

from api import config

logger = structlog.get_logger(__name__)

_DEFAULTS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
}

# Module-level client singletons — created on first call, reused for all subsequent CV
# generation requests.  Avoids the overhead of constructing a new PostHog AI wrapper
# (which calls posthog.setup() internally) on every generate_cv() invocation.
_anthropic_client = None
_openai_client = None


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


def generate_cv(
    system_prompt: str,
    user_prompt: str,
    *,
    distinct_id: str | None = None,
) -> str:
    """Call the configured LLM and return the generated CV markdown string.

    Args:
        system_prompt: Full system prompt including reference files and output contract.
        user_prompt: Job description + scored data + user CV context.
        distinct_id: PostHog distinct_id for LLM usage attribution (optional).

    Returns:
        Raw markdown string from the LLM (structured CV content).

    Raises:
        ValueError: If CV_LLM_PROVIDER is unknown.
        RuntimeError: If the required API key env var is missing.
    """
    provider = os.environ.get("CV_LLM_PROVIDER", "anthropic").lower()
    model_override = config.LLM_MODEL_CV.strip()

    if provider == "anthropic":
        raw = _call_anthropic(system_prompt, user_prompt, model_override, distinct_id)
    elif provider == "openai":
        raw = _call_openai(system_prompt, user_prompt, model_override, distinct_id)
    else:
        raise ValueError(f"Unknown CV_LLM_PROVIDER: '{provider}'. Must be 'anthropic' or 'openai'.")
    return strip_analysis(raw)


def _call_anthropic(
    system_prompt: str,
    user_prompt: str,
    model_override: str,
    distinct_id: str | None,
) -> str:
    global _anthropic_client
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. Set it in .env or your deployment environment."
        )

    model = model_override or _DEFAULTS["anthropic"]
    use_posthog = bool(os.environ.get("POSTHOG_API_KEY"))

    if _anthropic_client is None:
        if use_posthog:
            from posthog.ai.anthropic import Anthropic as _AnthropicCls  # noqa: PLC0415
        else:
            from anthropic import Anthropic as _AnthropicCls  # noqa: PLC0415
        _anthropic_client = _AnthropicCls(api_key=api_key)

    create_kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if use_posthog and distinct_id:
        create_kwargs["posthog_distinct_id"] = distinct_id
        create_kwargs["posthog_properties"] = {"source": "cv_generation"}

    response = _anthropic_client.messages.create(**create_kwargs)
    return response.content[0].text


def _call_openai(
    system_prompt: str,
    user_prompt: str,
    model_override: str,
    distinct_id: str | None,
) -> str:
    global _openai_client
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. Set it in .env or your deployment environment."
        )

    model = model_override or _DEFAULTS["openai"]
    use_posthog = bool(os.environ.get("POSTHOG_API_KEY"))

    if _openai_client is None:
        if use_posthog:
            from posthog.ai.openai import OpenAI as _OpenAICls  # noqa: PLC0415
        else:
            from openai import OpenAI as _OpenAICls  # noqa: PLC0415
        _openai_client = _OpenAICls(api_key=api_key)

    create_kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if use_posthog and distinct_id:
        create_kwargs["posthog_distinct_id"] = distinct_id
        create_kwargs["posthog_properties"] = {"source": "cv_generation"}

    response = _openai_client.chat.completions.create(**create_kwargs)
    return response.choices[0].message.content
