"""CV prompt builder.

Loads reference files and job data to build the (system_prompt, user_prompt)
tuple consumed by api.cv.llm.generate_cv().

When a cv_plan dict is provided (from api.cv.plan.build_cv_plan), the prompts
use plan-aware generation: the LLM receives structured context and must output
an <analysis> chain-of-thought block before the CV markdown.  The analysis
block is automatically stripped by api.cv.llm.generate_cv().

When cv_plan is None or empty, the function falls back to the legacy prompt
format for backward compatibility.
"""

import json
import os
from pathlib import Path

import structlog

_log = structlog.get_logger(__name__)

# Logic files committed to the repo — apply to every user.
# The candidate's personal CV comes from users.cv_md (DB), not from files.
_REFERENCE_FILES = [
    "generate-cv.md",
    "ats-rules.md",
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

3-4 sentences of prose. Must include at least one sentence about scope limitations or
what you are NOT looking for (e.g. "Not looking for...", "I work best in contexts
where..."). No generic language.

## Selected Impact

- Bullet 1: problem, action, result with metric.
- Bullet 2: different domain, mix of metrics and qualitative impact.
- Bullet 3: another high-impact achievement.
- Bullet 4: cross-functional or strategic result.
- Bullet 5: a fifth bullet only if the career has additional wins in a different area.

## Core Skills

Theme Name: Prose describing skills in this theme. No bullet points. No bold markers.

Another Theme: Another prose paragraph.

## Projects

### Project Name  URL-if-applicable
2-3 lines. Problem, stack, outcome. No bold markers.

## Work Experience

### Most Recent Company - Role Title	MM/YYYY - Present
_One sentence: what the company does and your scope/team size._

- Bullet: result + mechanism. Max 2 lines.
- Bullet: another achievement with metric.
- Bullet: third impact.

### Previous Company - Role	MM/YYYY - MM/YYYY
_Context line._

- Bullet: result + mechanism.
- Bullet: another achievement.

### Earlier Company - Role	MM/YYYY - MM/YYYY
_Context line._

- Bullet: result.

## Education and Certifications

Degree - Institution, Year

Certification, Year (if relevant)

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

## Content volume rules (CRITICAL — follow exactly)

7. Work Experience: include EVERY company from the master CV, ordered
   chronologically (most recent first). Apply this recency bullet budget:
   - Most recent company: 3-4 bullets
   - Roles from 2-5 years ago: 2-3 bullets
   - Roles older than 5 years: 1-2 bullets
   - Roles older than 8 years: 1 bullet; omit only if career spans 15+ years
     and space is exhausted
   - TOTAL across ALL Work Experience entries: 12 bullets maximum

8. Selected Impact: write 4-5 bullets drawing from the FULL career, not just the
   most recent role. Each bullet must come from a different achievement.

9. Length hard cap: the CV MUST fit within 3 pages — exceeding 3 pages is a hard
   failure. Target 2 pages. When content would push past 3 pages, cut bullets from
   the oldest roles first. If the draft would be under 1.5 pages, add bullets from
   the master CV.

10. Core Skills: write 2-3 themes. Each theme paragraph must be 1-2 sentences of
    specific, non-generic prose (name technologies, methods, or contexts).

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

---

## Character and syntax rules

- Use only ASCII hyphen (-) in dates and separators. Never em dash (—), en dash (–),
  arrows (->) or tilde (~) — replace any that appear.
- No Oxford comma: write "A, B and C" not "A, B, and C".
- No AI-telltale patterns: avoid identical bullet lengths, perfect rhythmic structure,
  round metrics without context, or generic openings ("Experienced professional with...").
  Each bullet should differ in length and structure.
- Projects section: include ONLY when the role explicitly values AI/LLM, data platform,
  ML infrastructure, or technical portfolio (signals: "AI PM", "data platform",
  "technical PM" in JD). Omit for traditional or generalist PM roles — distribute
  relevant project keywords into Core Skills instead.
"""

# Plan-aware rules — appended to the system prompt when a cv_plan is provided.
# These supplement (not replace) _OUTPUT_CONTRACT.
_PLAN_AWARE_RULES = """
---

## Plan-aware generation rules

These rules are REQUIRED when a CV Generation Plan is provided in the user message.
They supplement the output contract above.

### Source fidelity

The reference files are the **source of truth** for factual claims about this candidate.
Rules:
- Never downgrade job titles: if source_facts.title says "Senior Product Manager",
  write "Senior Product Manager" — never "Product Manager".
- Never downgrade years of experience: if source_facts.years_experience says "10+",
  never write "7+", "8+", or any lower number.
- Include ALL languages listed in source_facts.languages in the Languages section.
- Core Skills must cover every theme in source_facts.core_skills_themes that is
  relevant to the target role. Do not collapse or merge themes without good reason.

### Relevance-weighted bullet allocation

Follow the bullet_allocation plan provided. It specifies a bullet budget per company
and explains why each company is relevant. Rules:
- Respect the budget per role. If budget is 3, write 3 bullets (not 2, not 4).
- Within each role, lead with the bullet that most directly maps to a JD requirement.
- Always include the most differentiating bullet — the one competitors are least
  likely to have.
- Each bullet: max 2 lines. Mechanism + result. No narrative arcs, no "I", no preamble
  verbs. Past tense for completed work; present tense for current role.

### JD-aware tailoring

The CV plan contains jd_context analysis. Use it to shape the Summary and bullet
selection:
- If jd_context.company_type is "consultancy": the Summary MUST include a sentence
  about adaptability to different client environments (e.g., embedded work, multiple
  client contexts, rapid context-switching).
- If jd_context.location_language_hints lists a language (e.g., "French"): verify
  that language appears in the Languages section. If not present in source_facts,
  add a note only if the candidate has evidence of it.
- Surface tools from jd_context.key_tools explicitly if they appear in the reference
  material.

### Anti-slop (extended)

The Summary MUST NOT contain any of the following phrases or close paraphrases:
"strong track record", "drive measurable business impact", "proven ability",
"passionate about", "results-driven", "data-driven leader", "leveraging",
"utilizing", "thought leader", "collaborative approach", "dynamic environment".

Never start a bullet with a gerund. Wrong: "- Leading the...". Right: "- Led the..."

### Chain-of-thought

Before writing the CV, output an <analysis> block with:
1. The Summary angle given the JD context (company type, location, consulting signals).
2. For each of the top 3–5 truly_required skills in the plan, which specific bullet from
   the master CV best proves it.
3. What differentiates this candidate from typical applicants for this role.
4. Any gaps from the plan to acknowledge through framing (not invention).

The <analysis> block will be stripped before document generation. It is for your
reasoning only — not visible to the reader.

After </analysis>, output ONLY the CV markdown starting with # [Full Name].
Do not include any text between </analysis> and the first # heading.
"""


def _get_references_dir() -> Path:
    """Return the references directory path from env var or default."""
    env_override = os.environ.get("CV_REFERENCES_DIR", "").strip()
    if env_override:
        return Path(env_override)
    # Default: relative to this module file
    return Path(__file__).parent / "references"


def load_reference_files_dict() -> dict[str, str]:
    """Deprecated — returns empty dict.

    Previously loaded master-cv-profile.md and master-cv-experience.md.
    Those files contained per-user personal data and have been replaced by
    users.cv_md from the database.  The candidate's CV is now injected into
    the system prompt by build_cv_prompts() via the user_cv_markdown param.

    Kept to avoid breaking any external callers during migration.
    """
    return {}


def _load_reference_files(refs_dir: Path) -> str:
    """Load and concatenate all required reference files.

    Returns:
        Single string with all files separated by section markers.

    Raises:
        FileNotFoundError: If any required file is missing, with the filename.
    """
    _log.info("CV prompt: loading reference files", refs_dir=str(refs_dir))
    parts = []
    for filename in _REFERENCE_FILES:
        path = refs_dir / filename
        if not path.exists():
            _log.error(
                "CV reference file missing",
                filename=filename,
                refs_dir=str(refs_dir),
                refs_dir_exists=refs_dir.exists(),
                refs_dir_contents=(
                    [f.name for f in sorted(refs_dir.iterdir()) if f.is_file()] if refs_dir.exists() else []
                ),
            )
            raise FileNotFoundError(
                f"Required CV reference file not found: {filename} "
                f"(looked in {refs_dir}). "
                f"See api/cv/references/README.md for setup instructions."
            )
        content = path.read_text(encoding="utf-8")
        _log.debug("CV reference file loaded", filename=filename, size=len(content))
        parts.append(f"--- SECTION: {filename} ---\n\n{content}")
    _log.info("CV reference files loaded", count=len(parts))
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


def _format_job_summary(parsed: dict) -> str:
    """Format parser v1.5 fields as a compact job summary (~450 tokens).

    Replaces the raw JD in the plan-aware prompt path.
    Falls back to a note for old jobs without v1.5 fields.
    """
    parts: list[str] = []

    role = parsed.get("role_in_plain_english")
    if role:
        parts += ["**What you'll do:**", role, ""]

    truly_required = parsed.get("truly_required") or parsed.get("must_have_skills") or []
    if truly_required:
        parts.append("**Required:**")
        parts.extend(f"- {s}" for s in truly_required)
        parts.append("")

    preferred = parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or []
    if preferred:
        parts.append("**Preferred:**")
        parts.extend(f"- {s}" for s in preferred)
        parts.append("")

    verbatim = parsed.get("verbatim_for_cv") or []
    if verbatim:
        parts.append("**Key phrases to mirror:**")
        parts.extend(f'- "{p}"' for p in verbatim)
        parts.append("")

    ctx = parsed.get("company_context") or {}
    ctx_items: list[str] = []
    if ctx.get("stage"):
        ctx_items.append(f"{ctx['stage']} stage")
    if ctx.get("tone"):
        ctx_items.append(f"{ctx['tone']} tone")
    values = ctx.get("what_they_value") or []
    if values:
        ctx_items.append(f"values: {', '.join(values)}")
    if ctx_items:
        parts += [f"**Company context:** {' · '.join(ctx_items)}", ""]

    if not parts:
        parts.append("(No parsed summary — job predates parser v1.5.)")

    return "\n".join(["## Job Summary (parsed)", ""] + parts)


def build_cv_prompts(
    job: dict,
    user_cv_markdown: str,
    cv_plan: dict | None = None,
) -> tuple[str, str]:
    """Build the (system_prompt, user_prompt) tuple for CV generation.

    When cv_plan is provided (from api.cv.plan.build_cv_plan), the prompts use
    plan-aware generation: the system prompt gains source-fidelity, bullet
    allocation, and chain-of-thought rules; the user prompt is simplified to
    plan JSON + JD + metadata.

    When cv_plan is None or empty, falls back to the legacy format (backward
    compatible with all existing callers that don't yet pass a plan).

    Args:
        job: Full job dict from SQLite (includes parsed and scored JSON strings).
        user_cv_markdown: Content of the user's cv.md file (empty string if unavailable).
        cv_plan: Optional plan dict from build_cv_plan(). None → legacy behavior.

    Returns:
        Tuple of (system_prompt, user_prompt) ready for api.cv.llm.generate_cv().

    Raises:
        FileNotFoundError: If a required reference file is missing.
        ValueError: If the job has no extractable job description text.
    """
    # Inject the user's CV as the authoritative candidate source.
    # It replaces the old per-user reference files (master-cv-profile.md /
    # master-cv-experience.md) that used to be committed to the repo.
    cv_section = ""
    if user_cv_markdown and user_cv_markdown.strip():
        cv_section = "\n\n--- SECTION: candidate-master-cv.md ---\n\n" + user_cv_markdown.strip()

    # Parse JSON blobs from job
    parsed: dict = {}
    scored: dict = {}
    if job.get("parsed"):
        try:
            raw = job["parsed"]
            parsed = raw if isinstance(raw, dict) else json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
    if job.get("scored"):
        try:
            raw = job["scored"]
            scored = raw if isinstance(raw, dict) else json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            scored = {}

    # ── Plan-aware path ───────────────────────────────────────────────────
    if cv_plan:
        # Reference files excluded: rules captured in _OUTPUT_CONTRACT + _PLAN_AWARE_RULES.
        # Raw JD replaced by parsed distillation (~450 tokens vs 3-5K tokens).
        system_prompt = cv_section + "\n\n" + _OUTPUT_CONTRACT + "\n\n" + _PLAN_AWARE_RULES
        user_prompt = _build_plan_aware_user_prompt(job, parsed, cv_plan)
        return system_prompt, user_prompt

    # ── Legacy path (no plan) ─────────────────────────────────────────────
    refs_dir = _get_references_dir()
    reference_content = _load_reference_files(refs_dir)
    jd_text = _extract_jd_text(parsed)
    system_prompt = reference_content + cv_section + "\n\n" + _OUTPUT_CONTRACT

    # Extract scoring details
    rag = scored.get("rag_score", scored)
    breakdown = rag.get("breakdown", {})
    strengths = rag.get("strengths", [])
    gaps = rag.get("gaps", [])

    user_parts = [
        "## Job to tailor the CV for",
        "",
        f"**Title:** {job.get('title', 'N/A')}",
        f"**Company:** {job.get('company', 'N/A')}",
        f"**Location:** {job.get('location', 'N/A')}",
        f"**URL:** {job.get('url', 'N/A')}",
        f"**Score:** {job.get('score', 'N/A')} (Tier {job.get('tier', 'N/A')})",
        "",
        "## Job Description",
        "",
        jd_text,
    ]

    if breakdown:
        user_parts += ["", "## Score Breakdown", ""]
        for dim, score in breakdown.items():
            user_parts.append(f"- {dim}: {score}")

    if strengths:
        user_parts += ["", "## Candidate Strengths (from scoring)", ""]
        for s in strengths:
            user_parts.append(f"- {s}")

    if gaps:
        user_parts += ["", "## Gaps to address or mitigate", ""]
        for g in gaps:
            if isinstance(g, dict):
                severity = g.get("severity", "")
                issue = g.get("issue", str(g))
                user_parts.append(f"- [{severity}] {issue}")
            else:
                user_parts.append(f"- {g}")

    user_prompt = "\n".join(user_parts)
    return system_prompt, user_prompt


def _build_plan_aware_user_prompt(
    job: dict,
    parsed: dict,
    cv_plan: dict,
) -> str:
    """Build the simplified user prompt for plan-aware generation.

    The candidate's CV is in the system prompt (candidate-master-cv.md section).
    Raw JD replaced by _format_job_summary() — ~450 tokens vs 3-5K tokens.

    Structure:
        ## CV Generation Plan
        {plan JSON}

        ## Job Summary (parsed)
        {v1.5 parsed fields}

        ## Job Metadata
        Title / Company / Location / Score

        ---
        Generate the CV following the plan. Start with <analysis>...
    """
    plan_json = json.dumps(cv_plan, indent=2, ensure_ascii=False)

    parts = [
        "## CV Generation Plan",
        "",
        plan_json,
        "",
        _format_job_summary(parsed),
        "",
        "## Job Metadata",
        "",
        f"Title:    {job.get('title', 'N/A')}",
        f"Company:  {job.get('company', 'N/A')}",
        f"Location: {job.get('location', 'N/A')}",
        f"Score:    {job.get('score', 'N/A')} (Tier {job.get('tier', 'N/A')})",
        "",
        "---",
        "",
        "Generate the CV following the plan above.",
        "Start with <analysis>, then output the CV markdown starting with # [Full Name].",
    ]

    return "\n".join(parts)
