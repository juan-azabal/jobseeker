"""Focused LLM rewrite of pre-selected CV content.

rewrite_cv_content(selected, job, distinct_id) -> str
  Takes structured selection (from select_cv_content()) and the job dict.
  Renders to markdown, then sends to LLM with a narrow adaptation prompt.
  Falls back to rendered markdown on LLM error (non-fatal).
"""

from __future__ import annotations

import json

from api.cv.llm import generate_cv
from api.cv.render import render_cv_markdown

_SYSTEM_PROMPT = """\
You are a professional CV writer. You will receive a work experience section
and a job description. Your task is to lightly adapt the tone and emphasis of
the CV content to better match the job, without:
- Adding experience, skills, or achievements that are not already present
- Removing any factual bullet points already listed
- Changing company names, dates, or positions
- Fabricating metrics or results

Return ONLY the adapted markdown. No commentary, no preamble."""


def rewrite_cv_content(selected: dict, job: dict, distinct_id: str) -> str:
    """Rewrite selected CV content using a narrow LLM prompt.

    The LLM only adapts tone/emphasis — no content is added or removed.
    Falls back to rendered markdown on LLM error.

    Args:
        selected: Output of select_cv_content().
        job: Full job dict (used for context).
        distinct_id: User ID for PostHog tracking.

    Returns:
        Markdown string of adapted work experience section.
    """
    rendered = render_cv_markdown(selected)
    if not rendered:
        return ""

    user_prompt = _build_user_prompt(rendered, job)

    try:
        return generate_cv(_SYSTEM_PROMPT, user_prompt, distinct_id=distinct_id)
    except Exception:
        return rendered  # non-fatal fallback


def _build_user_prompt(rendered_md: str, job: dict) -> str:
    parsed = job.get("parsed") or {}
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except (json.JSONDecodeError, TypeError):
            parsed = {}

    must_have = ", ".join(parsed.get("must_have_skills") or [])
    domain = parsed.get("domain") or job.get("domain") or ""
    responsibilities = parsed.get("responsibilities_summary") or ""

    return (
        f"## Job Context\n"
        f"Role: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Domain: {domain}\n"
        f"Key requirements: {must_have}\n"
        f"Responsibilities: {responsibilities}\n\n"
        f"## CV Work Experience to adapt\n\n"
        f"{rendered_md}"
    )
