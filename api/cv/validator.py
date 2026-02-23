"""CV validator — programmatic source-fidelity checks (Step 6.4).

Validates generated CV markdown against the plan's source_facts and JD context
before docx conversion.  All checks are deterministic — no LLM call required.

Usage:
    from api.cv.validator import validate_cv, build_fix_prompt

    result = validate_cv(generated_markdown, cv_plan)
    if not result["passed"]:
        fix_system, fix_user = build_fix_prompt(generated_markdown, result["errors"])
        fixed_markdown = generate_cv(fix_system, fix_user)
"""
import re
from typing import Any

# ── Slop blacklist ────────────────────────────────────────────────────────

_SLOP_PHRASES: list[str] = [
    "strong track record",
    "drive measurable business impact",
    "proven ability",
    "passionate about",
    "results-driven",
    "data-driven leader",
    "leveraging",
    "utilizing",
    "thought leader",
    "collaborative approach",
    "dynamic environment",
]

# Consulting signals (any one of these in Summary → no_consulting_mention is clear)
_CONSULTING_SIGNALS: list[str] = [
    "consulting", "consultant", "client", "embedded", "adapt",
    "multiple environments", "different environments",
]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def validate_cv(generated_markdown: str, cv_plan: dict) -> dict:
    """Validate the generated CV markdown against plan source facts.

    Args:
        generated_markdown: Raw CV markdown string from the LLM.
        cv_plan: Plan dict from build_cv_plan().

    Returns:
        Dict with keys:
            passed   — True iff errors is empty
            errors   — list of dicts {code, detail}; must-fix issues
            warnings — list of dicts {code, detail}; quality issues
    """
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    source_facts: dict = {}
    jd_context: dict = {}
    bullet_allocation: dict = {}

    if cv_plan:
        source_facts     = cv_plan.get("source_facts", {}) or {}
        jd_context       = cv_plan.get("jd_context", {}) or {}
        bullet_allocation = cv_plan.get("bullet_allocation", {}) or {}

    text = generated_markdown or ""
    text_lower = text.lower()

    # ── Errors (block generation) ─────────────────────────────────────────

    # title_downgraded
    expected_title = source_facts.get("title", "")
    if expected_title:
        errors.extend(_check_title(text, expected_title))

    # years_downgraded
    expected_years = source_facts.get("years_experience", "")
    if expected_years:
        errors.extend(_check_years(text, expected_years))

    # slop_detected
    errors.extend(_check_slop(text_lower))

    # ── Warnings (log, don't block) ───────────────────────────────────────

    # missing_language
    languages = source_facts.get("languages") or []
    warnings.extend(_check_languages(text, languages))

    # missing_theme
    themes = source_facts.get("core_skills_themes") or []
    warnings.extend(_check_themes(text, themes))

    # bullet_budget_violation
    if bullet_allocation:
        warnings.extend(_check_bullet_budgets(text, bullet_allocation))

    # no_consulting_mention
    company_type = jd_context.get("company_type", "")
    if company_type == "consultancy":
        warnings.extend(_check_consulting_mention(text_lower))

    # gerund_start
    warnings.extend(_check_gerund_starts(text))

    return {
        "passed":   len(errors) == 0,
        "errors":   errors,
        "warnings": warnings,
    }


def build_fix_prompt(generated_markdown: str, errors: list[dict]) -> tuple[str, str]:
    """Build a targeted fix prompt for specific validation errors.

    The fix prompt is intentionally narrow: the LLM must fix ONLY the listed
    issues and change nothing else.  This keeps the fix call cheap (~500 tokens).

    Args:
        generated_markdown: The CV that failed validation.
        errors: List of error dicts from validate_cv() (code + detail fields).

    Returns:
        Tuple (system_prompt, user_prompt) ready for api.cv.llm.generate_cv().
    """
    system_prompt = (
        "You are a precise CV editor. Fix ONLY the listed issues in the CV provided. "
        "Do not change any other content, structure, or formatting. "
        "Do not rewrite sentences that are not affected by the listed issues. "
        "Output ONLY the corrected CV markdown starting with # [Full Name]. "
        "No preamble, no explanations, no code fences."
    )

    error_lines = []
    for err in errors:
        code   = err.get("code", "unknown")
        detail = err.get("detail", "")
        error_lines.append(f"- [{code}] {detail}")

    user_prompt = "\n".join([
        "## Issues to fix",
        "",
        *error_lines,
        "",
        "## CV to fix",
        "",
        generated_markdown.strip(),
        "",
        "---",
        "",
        "Fix ONLY the issues listed above. Output the corrected CV markdown.",
    ])

    return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════════════
# Error checks
# ═══════════════════════════════════════════════════════════════════════════

def _check_title(text: str, expected_title: str) -> list[dict]:
    """Error if expected title not found in the first 10 lines of the CV."""
    lines = text.splitlines()[:10]
    header_block = "\n".join(lines).lower()
    if expected_title.lower() in header_block:
        return []
    return [{
        "code": "title_downgraded",
        "detail": (
            f"Expected '{expected_title}' in CV title area. "
            f"Candidate title was downgraded or omitted."
        ),
    }]


def _check_years(text: str, expected_years: str) -> list[dict]:
    """Error if the expected years bucket is not mentioned in the CV.

    expected_years is a string like '10+', '15+', '5+'.
    The check looks for the numeric prefix in the CV text.
    """
    # Extract the numeric part: "10+" → "10", "15+" → "15"
    m = re.match(r"(\d+)", expected_years.strip())
    if not m:
        return []
    expected_num = m.group(1)

    # Look for "N+ years" or "N years" in the CV text
    found = re.search(rf"\b{re.escape(expected_num)}\+?\s*years?\b", text, re.IGNORECASE)
    if found:
        return []

    # Also check for "N+" as standalone (e.g., "10+ in data")
    found_standalone = re.search(rf"\b{re.escape(expected_num)}\+", text)
    if found_standalone:
        return []

    return [{
        "code": "years_downgraded",
        "detail": (
            f"Expected '{expected_years}' years of experience mentioned in CV. "
            f"Years may have been downgraded or omitted."
        ),
    }]


def _check_slop(text_lower: str) -> list[dict]:
    """Error if any blacklisted phrase appears in the CV."""
    found_phrases: list[str] = []
    for phrase in _SLOP_PHRASES:
        if phrase in text_lower:
            found_phrases.append(phrase)
    if not found_phrases:
        return []
    return [{
        "code": "slop_detected",
        "detail": (
            f"Blacklisted phrase(s) found: {', '.join(repr(p) for p in found_phrases)}. "
            f"Rewrite Summary to remove generic aspirational language."
        ),
    }]


# ═══════════════════════════════════════════════════════════════════════════
# Warning checks
# ═══════════════════════════════════════════════════════════════════════════

def _extract_languages_section(text: str) -> str:
    """Extract the text of the Languages section."""
    m = re.search(
        r"^## Languages?\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _check_languages(text: str, languages: list[str]) -> list[dict]:
    """Warning for each language in source_facts not found in Languages section."""
    lang_section = _extract_languages_section(text).lower()
    # Fall back to full text search if section not found
    search_text = lang_section if lang_section else text.lower()

    warnings: list[dict] = []
    for lang_entry in languages:
        # Extract base language name: "Spanish (native)" → "spanish"
        lang_name = lang_entry.split("(")[0].strip().lower()
        if lang_name and lang_name not in search_text:
            warnings.append({
                "code": "missing_language",
                "detail": (
                    f"Language '{lang_entry}' from source_facts not found "
                    f"in CV Languages section."
                ),
            })
    return warnings


def _check_themes(text: str, themes: list[str]) -> list[dict]:
    """Warning for each Core Skills theme not fuzzy-matched in the CV."""
    # Extract Core Skills section
    m = re.search(
        r"^## Core Skills?\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    skills_text = (m.group(1).strip() if m else "").lower()
    # Fall back to full text if section not found
    search_text = skills_text if skills_text else text.lower()

    warnings: list[dict] = []
    for theme in themes:
        if _theme_found(theme, search_text):
            continue
        warnings.append({
            "code": "missing_theme",
            "detail": (
                f"Core Skills theme '{theme}' from source_facts not found in CV "
                f"(token overlap < 50%)."
            ),
        })
    return warnings


_THEME_STOP_WORDS: frozenset[str] = frozenset(
    {"and", "or", "of", "the", "in", "for", "a", "to", "with", "by"}
)


def _theme_found(theme: str, text: str) -> bool:
    """Return True if the theme's significant tokens are >50% present in the text.

    Filters common stopwords but keeps short meaningful tokens like 'AI' and 'ML'.
    """
    tokens = [
        t for t in theme.lower().split()
        if t not in _THEME_STOP_WORDS and len(t) >= 2
    ]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in text)
    return (hits / len(tokens)) > 0.5


def _check_bullet_budgets(text: str, bullet_allocation: dict) -> list[dict]:
    """Warning if any role's actual bullet count differs from its budget by > 2."""
    warnings: list[dict] = []
    for company, spec in bullet_allocation.items():
        budget = spec.get("budget", 0)
        actual = _count_bullets_for_company(company, text)
        if actual == 0:
            # Company not found in CV — skip (other checks cover completeness)
            continue
        if abs(actual - budget) > 2:
            warnings.append({
                "code": "bullet_budget_violation",
                "detail": (
                    f"'{company}': bullet budget is {budget} but found {actual} bullets "
                    f"(difference > 2)."
                ),
            })
    return warnings


def _count_bullets_for_company(company_name: str, text: str) -> int:
    """Count bullet lines under the given company's section."""
    lines = text.splitlines()
    collecting = False
    count = 0
    company_lower = company_name.lower()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### ") and company_lower in stripped.lower():
            collecting = True
            continue
        if collecting:
            if stripped.startswith("### "):
                break  # next company
            if stripped.startswith("## "):
                break  # next section
            if stripped.startswith("- "):
                count += 1
    return count


def _check_consulting_mention(text_lower: str) -> list[dict]:
    """Warning if Summary has no consulting/client/embedded signal."""
    # Extract Summary section
    m = re.search(
        r"## Summary\s*\n(.*?)(?=^## |\Z)",
        text_lower,
        re.MULTILINE | re.DOTALL,
    )
    summary = m.group(1).strip() if m else text_lower

    for signal in _CONSULTING_SIGNALS:
        if signal in summary:
            return []
    return [{
        "code": "no_consulting_mention",
        "detail": (
            "Plan indicates a consultancy role but Summary has no mention of "
            "consulting context, clients, or adaptability to different environments."
        ),
    }]


def _check_gerund_starts(text: str) -> list[dict]:
    """Warning for any bullet starting with a gerund (e.g., '- Leading the...')."""
    # Pattern: bullet line starting with a capital gerund (word ending -ing)
    gerund_pattern = re.compile(r"^- [A-Z][a-z]+ing\b", re.MULTILINE)
    matches = gerund_pattern.findall(text)
    if not matches:
        return []
    return [{
        "code": "gerund_start",
        "detail": (
            f"Bullet(s) start with a gerund: {matches[:3]}. "
            f"Use past tense for completed work (e.g., 'Led' not 'Leading')."
        ),
    }]
