"""Enriched scoring context builder from Master CV JSON.

build_scoring_context(master_cv, job, query_fn=None) -> str
  Builds a token-capped context string mapping job requirements to CV evidence.
  For each required skill: find matching work entries, attach 1-2 highlights.
  If query_fn provided: semantic fallback via ChromaDB; distance ≤ 0.5 = evidence,
    else [GAP] marker.
  Without query_fn: deterministic "No evidence" line (backward compat, no [GAP]).
  Cap: ~1500 tokens (≈6000 chars).
"""

from __future__ import annotations
from typing import Callable

_TOKEN_CAP_CHARS = 6000
_MAX_HIGHLIGHTS_PER_SKILL = 2
_SEMANTIC_MATCH_THRESHOLD = 0.5


def build_scoring_context(
    master_cv: dict,
    job: dict,
    query_fn: Callable | None = None,
) -> str:
    """Return evidence-mapped context string for RAG scoring prompt injection.

    Sections:
    1. SKILL EVIDENCE: each job skill → matching work entry highlights.
    2. CAREER SUMMARY: most recent 2 positions (company, title, dates).

    query_fn: optional callable(skill: str) -> list[{document, distance}]
      Used for semantic gap detection when no deterministic match found.
    """
    must_have = job.get("must_have_skills") or []
    nice_to_have = job.get("nice_to_have_skills") or []
    all_skills = list(must_have) + [s for s in nice_to_have if s not in must_have]

    work = master_cv.get("work") or []
    lines: list[str] = []

    # --- Skill evidence section ---
    lines.append("## Skill Evidence")
    for skill in all_skills:
        evidence = _find_evidence(skill, work)
        if evidence:
            lines.append(f"**{skill}**: {evidence}")
        elif query_fn is not None:
            lines.append(_semantic_gap_line(skill, query_fn))
        else:
            lines.append(f"**{skill}**: No evidence found in CV.")

    # --- Career summary section ---
    lines.append("")
    lines.append("## Recent Roles")
    for entry in work[:2]:
        company = entry.get("company", "")
        position = entry.get("position", "")
        start = entry.get("start_date", "")
        end = entry.get("end_date") or "present"
        lines.append(f"- {position} at {company} ({start}–{end})")

    ctx = "\n".join(lines)
    return ctx[:_TOKEN_CAP_CHARS]


def _semantic_gap_line(skill: str, query_fn: Callable) -> str:
    """Call query_fn; return semantic evidence line or [GAP] marker."""
    results = query_fn(skill)
    if results:
        best = results[0]
        if best.get("distance", 1.0) <= _SEMANTIC_MATCH_THRESHOLD:
            return f"**{skill}** (semantic match): {best['document']}"
    return f"**{skill}**: No direct evidence in CV. [GAP]"


def _find_evidence(skill: str, work: list[dict]) -> str | None:
    """Return up to 2 highlights from the best-matching work entry, or None."""
    skill_lower = skill.lower()
    best_highlights: list[str] = []

    for entry in work:
        skills_used = [s.lower() for s in (entry.get("skills_used") or [])]
        if _skill_matches(skill_lower, skills_used):
            highlights = (entry.get("highlights") or [])[:_MAX_HIGHLIGHTS_PER_SKILL]
            best_highlights.extend(highlights)
            if best_highlights:
                break

    if not best_highlights:
        return None
    return "; ".join(best_highlights)


def _skill_matches(skill: str, skills_used: list[str]) -> bool:
    """True if skill has a substring match in any element of skills_used."""
    for candidate in skills_used:
        if skill in candidate or candidate in skill:
            return True
    return False
