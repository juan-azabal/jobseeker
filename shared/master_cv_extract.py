"""LLM extraction from CV text to Master CV JSON using gpt-4o-mini."""

import json
import logging
import re
from pathlib import Path

from shared.master_cv import validate_master_cv

_PROMPT_PATH = Path(__file__).parent / "prompts" / "master-cv-extraction.md"
_MODEL = "gpt-4o-mini"
_MAX_TOKENS = 4000

logger = logging.getLogger(__name__)


def extract_master_cv_json(cv_text: str, source: str, client) -> dict:
    """Extract structured Master CV JSON from raw CV text.

    Args:
        cv_text: Extracted text from a CV file.
        source: Source label e.g. "cv_upload", "linkedin_pdf".
        client: OpenAI client instance (plain or PostHog-wrapped).

    Returns:
        Validated Master CV JSON as a dict.

    Raises:
        ValueError: If the LLM response cannot be parsed after one retry.
    """
    prompt = _build_prompt(cv_text, source)

    raw = _call_llm(client, prompt)
    parsed = _try_parse(raw)
    if parsed is None:
        logger.warning("master_cv_extract: first parse failed, retrying")
        raw = _call_llm(client, prompt)
        parsed = _try_parse(raw)

    if parsed is None:
        raise ValueError("LLM returned non-JSON response after retry")

    errors = validate_master_cv(parsed)
    if errors:
        logger.warning("master_cv_extract: schema validation warnings", extra={"errors": errors})

    return parsed


def _build_prompt(cv_text: str, source: str) -> str:
    template = _PROMPT_PATH.read_text()
    return template.replace("{source}", source).replace("{cv_text}", cv_text)


def _call_llm(client, prompt: str) -> str:
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=_MAX_TOKENS,
    )
    return response.choices[0].message.content


def _try_parse(raw: str) -> dict | None:
    """Strip markdown fences and attempt JSON parse. Returns None on failure."""
    cleaned = _strip_fences(raw.strip())
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from LLM output."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
