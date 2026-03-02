"""Heuristic merge logic for Master CV JSON.

Rules:
- Same company (normalized) + overlapping dates (≥ 6 months) → merge into one entry.
- Different company or non-overlapping dates → keep both.
- Highlights: union, exact-duplicate dedup.
- Skills: union by name, case-insensitive dedup.
- Work IDs are reassigned sequentially (work_001, work_002, …) after merge.
"""

import re
from datetime import date


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_SUFFIXES = re.compile(
    r"\s+(ltd\.?|limited|inc\.?|incorporated|s\.l\.?|sl|gmbh|b\.v\.?|bv|ab|ag|sa|"
    r"corp\.?|corporation|llc|plc|pty)\.?\s*$",
    re.IGNORECASE,
)


def _normalize_company(name: str) -> str:
    """Lowercase, strip legal suffixes and punctuation."""
    name = name.strip()
    name = _SUFFIXES.sub("", name)
    name = re.sub(r"[^\w\s]", "", name)  # remove punctuation
    return name.strip().lower()


def _parse_ym(ym: str | None) -> date | None:
    """Parse 'YYYY-MM' to date(YYYY, MM, 1). Returns None if None/empty."""
    if not ym:
        return None
    try:
        y, m = ym.split("-")
        return date(int(y), int(m), 1)
    except (ValueError, AttributeError):
        return None


def _dates_overlap(
    start1: str | None,
    end1: str | None,
    start2: str | None,
    end2: str | None,
    min_months: int = 6,
) -> bool:
    """Return True if two date ranges overlap by at least min_months months."""
    today = date.today()
    s1 = _parse_ym(start1) or date.min
    e1 = _parse_ym(end1) or today
    s2 = _parse_ym(start2) or date.min
    e2 = _parse_ym(end2) or today

    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    if overlap_start >= overlap_end:
        return False

    # Approximate months
    months = (overlap_end.year - overlap_start.year) * 12 + (overlap_end.month - overlap_start.month)
    return months >= min_months


# ---------------------------------------------------------------------------
# Section merge helpers
# ---------------------------------------------------------------------------


def _merge_work(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge two work-entry lists.

    Strategy: for each incoming entry, check if any existing entry has the
    same normalised company AND overlapping dates (≥ 6 months). If so, merge
    highlights + skills_used into the existing entry. Otherwise append.
    """
    result: list[dict] = [dict(e) for e in existing]  # shallow copy each

    for inc in incoming:
        inc_company = _normalize_company(inc.get("company", ""))
        merged = False
        for existing_entry in result:
            ex_company = _normalize_company(existing_entry.get("company", ""))
            if ex_company != inc_company:
                continue
            if _dates_overlap(
                existing_entry.get("start_date"),
                existing_entry.get("end_date"),
                inc.get("start_date"),
                inc.get("end_date"),
            ):
                # Merge highlights (dedup by exact string)
                ex_highlights = list(existing_entry.get("highlights") or [])
                for h in inc.get("highlights") or []:
                    if h not in ex_highlights:
                        ex_highlights.append(h)
                existing_entry["highlights"] = ex_highlights

                # Merge skills_used (dedup)
                ex_skills = list(existing_entry.get("skills_used") or [])
                for s in inc.get("skills_used") or []:
                    if s not in ex_skills:
                        ex_skills.append(s)
                existing_entry["skills_used"] = ex_skills

                merged = True
                break

        if not merged:
            result.append(dict(inc))

    # Reassign sequential IDs
    for i, entry in enumerate(result, start=1):
        entry["id"] = f"work_{i:03d}"

    return result


def _merge_skills(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Union skills by name (case-insensitive), preserving order."""
    seen: set[str] = set()
    result: list[dict] = []
    for skill in list(existing) + list(incoming):
        key = skill.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(skill)
    return result


def _merge_list_by_field(existing: list[dict], incoming: list[dict], key: str) -> list[dict]:
    """Generic dedup merge by a single field key (e.g. 'institution' for education)."""
    seen: set[str] = {e.get(key, "").lower() for e in existing}
    result = list(existing)
    for item in incoming:
        if item.get(key, "").lower() not in seen:
            result.append(item)
            seen.add(item.get(key, "").lower())
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def merge_master_cvs(existing: dict, incoming: dict) -> dict:
    """Merge two Master CV JSON dicts. existing wins for basics/metadata.

    Sections merged:
    - work: heuristic dedup (same company + overlapping dates)
    - education: dedup by institution
    - skills: union by name
    - languages: union by language
    - certifications: union by name
    - projects: union by name

    Returns a new dict; inputs are not mutated.
    """
    merged = dict(existing)
    merged["work"] = _merge_work(
        existing.get("work") or [],
        incoming.get("work") or [],
    )
    merged["education"] = _merge_list_by_field(
        existing.get("education") or [],
        incoming.get("education") or [],
        "institution",
    )
    merged["skills"] = _merge_skills(
        existing.get("skills") or [],
        incoming.get("skills") or [],
    )
    merged["languages"] = _merge_list_by_field(
        existing.get("languages") or [],
        incoming.get("languages") or [],
        "language",
    )
    merged["certifications"] = _merge_list_by_field(
        existing.get("certifications") or [],
        incoming.get("certifications") or [],
        "name",
    )
    merged["projects"] = _merge_list_by_field(
        existing.get("projects") or [],
        incoming.get("projects") or [],
        "name",
    )
    return merged
