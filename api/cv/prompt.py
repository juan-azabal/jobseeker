"""CV prompt builder.

Loads reference files and job data to build the (system_prompt, user_prompt)
tuple consumed by api.cv.llm.generate_cv().
"""
import json
import os
from pathlib import Path

# Ordered list of reference files required by the CV generation pipeline
_REFERENCE_FILES = [
    "generate-cv.md",
    "ats-rules.md",
    "master-cv-profile.md",
    "master-cv-experience.md",
]

# Output contract appended to the system prompt — the LLM must follow this format exactly
_OUTPUT_CONTRACT = """
---

Output ONLY the CV content in the structured markdown format specified below.
No preamble, no explanations, no code fences, no notes after the CV.

## Required output format

# [Full Name]
[Title Line]
[Contact line: City, Country | email | phone | linkedin]

## Summary

3-5 lines of prose.

## Selected Impact

- Bullet one
- Bullet two

## Core Skills

**Theme Name**
Prose paragraph for this theme.

**Another Theme**
Another prose paragraph.

## Projects

### Project Name
2-3 lines. Problem, stack, outcome. URL.

## Work Experience

### Company Name, City, Country
**Role Title | MM/YYYY - MM/YYYY**

- Bullet one
- Bullet two

## Education and Certifications

- Degree - Institution, Year

## Languages

- Language - Level
"""


def _get_references_dir() -> Path:
    """Return the references directory path from env var or default."""
    env_override = os.environ.get("CV_REFERENCES_DIR", "").strip()
    if env_override:
        return Path(env_override)
    # Default: relative to this module file
    return Path(__file__).parent / "references"


def _load_reference_files(refs_dir: Path) -> str:
    """Load and concatenate all required reference files.

    Returns:
        Single string with all files separated by section markers.

    Raises:
        FileNotFoundError: If any required file is missing, with the filename.
    """
    parts = []
    for filename in _REFERENCE_FILES:
        path = refs_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required CV reference file not found: {filename} "
                f"(looked in {refs_dir}). "
                f"See api/cv/references/README.md for setup instructions."
            )
        content = path.read_text(encoding="utf-8")
        parts.append(f"--- SECTION: {filename} ---\n\n{content}")
    return "\n\n".join(parts)


def _extract_jd_text(parsed: dict) -> str:
    """Extract job description text from parsed job dict.

    Tries keys in order: description, full_text, body.

    Raises:
        ValueError: If no extractable JD text is found.
    """
    for key in ("description", "full_text", "body"):
        value = parsed.get(key, "")
        if value and str(value).strip():
            return str(value).strip()
    raise ValueError(
        "No job description available for CV generation. "
        "The parsed job data has no 'description', 'full_text', or 'body' field."
    )


def build_cv_prompts(job: dict, user_cv_markdown: str) -> tuple[str, str]:
    """Build the (system_prompt, user_prompt) tuple for CV generation.

    Args:
        job: Full job dict from SQLite (includes parsed and scored JSON strings).
        user_cv_markdown: Content of the user's cv.md file (empty string if unavailable).

    Returns:
        Tuple of (system_prompt, user_prompt) ready for api.cv.llm.generate_cv().

    Raises:
        FileNotFoundError: If a required reference file is missing.
        ValueError: If the job has no extractable job description text.
    """
    refs_dir = _get_references_dir()
    reference_content = _load_reference_files(refs_dir)

    system_prompt = reference_content + "\n\n" + _OUTPUT_CONTRACT

    # Parse JSON blobs from job
    parsed = {}
    scored = {}
    if job.get("parsed"):
        try:
            parsed = json.loads(job["parsed"])
        except (json.JSONDecodeError, TypeError):
            parsed = {}
    if job.get("scored"):
        try:
            scored = json.loads(job["scored"])
        except (json.JSONDecodeError, TypeError):
            scored = {}

    jd_text = _extract_jd_text(parsed)

    # Extract scoring details
    rag = scored.get("rag_score", scored)
    breakdown = rag.get("breakdown", {})
    strengths = rag.get("strengths", [])
    gaps = rag.get("gaps", [])

    # Build user prompt
    user_parts = [
        f"## Job to tailor the CV for",
        f"",
        f"**Title:** {job.get('title', 'N/A')}",
        f"**Company:** {job.get('company', 'N/A')}",
        f"**Location:** {job.get('location', 'N/A')}",
        f"**URL:** {job.get('url', 'N/A')}",
        f"**Score:** {job.get('score', 'N/A')} (Tier {job.get('tier', 'N/A')})",
        f"",
        f"## Job Description",
        f"",
        jd_text,
    ]

    if breakdown:
        user_parts += [
            f"",
            f"## Score Breakdown",
            f"",
        ]
        for dim, score in breakdown.items():
            user_parts.append(f"- {dim}: {score}")

    if strengths:
        user_parts += [
            f"",
            f"## Candidate Strengths (from scoring)",
            f"",
        ]
        for s in strengths:
            user_parts.append(f"- {s}")

    if gaps:
        user_parts += [
            f"",
            f"## Gaps to address or mitigate",
            f"",
        ]
        for g in gaps:
            if isinstance(g, dict):
                severity = g.get("severity", "")
                issue = g.get("issue", str(g))
                user_parts.append(f"- [{severity}] {issue}")
            else:
                user_parts.append(f"- {g}")

    if user_cv_markdown and user_cv_markdown.strip():
        user_parts += [
            f"",
            f"## Candidate's CV (for additional context)",
            f"",
            user_cv_markdown.strip(),
        ]

    user_prompt = "\n".join(user_parts)
    return system_prompt, user_prompt
