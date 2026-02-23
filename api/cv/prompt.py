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

Do NOT use **bold** or _italic_ markers anywhere in body text — the document builder
handles all formatting automatically. The ONLY exception is the role context line
under each company, which uses _single underscore italics_ on its own line.

## Required output format

# [Full Name]
[Professional Title — plain text, no bold markers]
[City, Country | email | phone | linkedin | github]

## Summary

3-5 lines of prose. Must include at least one sentence about scope limitations or
what you are NOT looking for (e.g. "Not looking for...", "I work best in contexts
where..."). No generic language.

## Selected Impact

- Bullet: problem, action, result. Max 2 lines per bullet.
- Bullet: mix metrics and qualitative impact.

## Core Skills

Theme Name: Prose describing skills in this theme. No bullet points. No bold markers.

Another Theme: Another prose paragraph.

## Projects

### Project Name  URL-if-applicable
2-3 lines. Problem, stack, outcome. No bold markers.

## Work Experience

### Company Name - Role Title	Date Range
_One sentence explaining what the company does and your scope there._

- Bullet one. Max 2 lines. Result + mechanism only.
- Bullet two.

### Another Company - Role	Date Range
_Context line._

- Bullet.

## Education and Certifications

Degree - Institution, Year

## Languages

Spanish (native) | English (advanced)

---

## Formatting rules

1. Company + Role + Date on ONE line (### heading). Use a LITERAL TAB character
   between the role title and the date range. Example:
   ### Acme Corp - Senior PM\t07/2024 - Present
   (where \t is a real tab character, not the two characters backslash-t)

2. Under each company, add a one-sentence context line wrapped in _single underscores_
   (italic) describing the company and your high-level scope. This line comes immediately
   after the ### company line, before the bullets.

3. Core Skills: format as "Theme Name: prose text on same line". Do NOT use **bold**
   markers or separate lines for theme/prose. Each theme is one paragraph.

4. Do NOT wrap any text in **bold** markers anywhere. The builder determines bold based
   on element position (name, headers, company line run 1).

5. Project name and URL on the same ### line, separated by two spaces before the URL.

6. Body text, bullets, and descriptions must be plain text only.

---

## Content quality rules

1. The Summary MUST contain at least one sentence about limits: what you are not looking
   for, or the contexts where you work best.

2. The Summary MUST NOT contain: "strong track record", "drive measurable business impact",
   "proven ability", "results-driven", "data-driven leader", "passionate about", or any
   generic PM aspirational language that could apply to any candidate.

3. Each bullet under Work Experience: max 2 lines. Result + mechanism only. No narrative
   arcs, no "I", no adjectives. Start with a verb or a noun phrase.

4. Years of experience: if the master CV states 10+ years, do not write "7+ years".

5. Bullets must be rewritten for the target role — not copy-pasted from the master CV.

6. If the target role involves consulting, working across multiple clients, or embedded
   product work, include a sentence about adaptability to different environments.
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
