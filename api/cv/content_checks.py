"""CV content checks — company hallucination + length bounds.

Deterministic checks on generated CV markdown that don't require
a cv_plan dict. Designed to complement validate_cv() from validator.py.

SYNC RULE: extract_cv_companies() duplicates the regex from
plan.py:_parse_companies_from_experience(). If one changes, update both.
"""

import re

# ── Thresholds ───────────────────────────────────────────────────────────

_MIN_LINES = 30
_MAX_LINES = 90


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def extract_cv_companies(cv_markdown: str) -> list[str]:
    """Extract company names from ``### Company, City`` section headers.

    SYNC RULE: regex duplicated from plan.py:_parse_companies_from_experience().
    """
    companies: list[str] = []
    for line in cv_markdown.splitlines():
        if line.startswith("### "):
            content = line[4:].strip()
            company = re.split(r",\s*(?![^(]*\))", content)[0].strip()
            if company:
                companies.append(company)
    return companies


def check_company_hallucination(
    cv_markdown: str,
    known_companies: list[str],
) -> list[dict[str, str]]:
    """Error for each company in the CV not found in known_companies.

    Returns list of ``{code, detail}`` error dicts.
    Empty *known_companies* → skip check (return []).
    """
    if not known_companies:
        return []

    known_lower = {c.lower() for c in known_companies}
    cv_companies = extract_cv_companies(cv_markdown)

    errors: list[dict[str, str]] = []
    for company in cv_companies:
        if company.lower() not in known_lower:
            errors.append(
                {
                    "code": "company_hallucinated",
                    "detail": (f"Company '{company}' in generated CV not found in known companies list."),
                }
            )
    return errors


def check_length_bounds(cv_markdown: str) -> list[dict[str, str]]:
    """Warning if CV has fewer than {_MIN_LINES} or more than {_MAX_LINES} non-empty lines."""
    non_empty = [ln for ln in (cv_markdown or "").splitlines() if ln.strip()]
    count = len(non_empty)

    if count < _MIN_LINES:
        return [
            {
                "code": "cv_too_short",
                "detail": (
                    f"CV has {count} non-empty lines (minimum {_MIN_LINES}). Content may be suspiciously short."
                ),
            }
        ]
    if count > _MAX_LINES:
        return [
            {
                "code": "cv_too_long",
                "detail": (f"CV has {count} non-empty lines (maximum {_MAX_LINES}). Likely exceeds 3-page limit."),
            }
        ]
    return []
