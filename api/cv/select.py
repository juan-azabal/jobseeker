"""Deterministic CV content selection using ChromaDB.

select_cv_content(master_cv, job, user_id) -> dict | None
  Queries ChromaDB for most relevant work entries + highlights.
  Returns None when master_cv has no work entries (caller falls back to legacy).
  Returns structured dict with work entries, selected highlights, relevance scores,
  and skill intersection.
"""

from __future__ import annotations

from api.master_cv_vectorstore import query_similar_highlights, query_similar_work

_MAX_WORK_ENTRIES = 4
_MAX_HIGHLIGHTS_PER_ENTRY = 5


def select_cv_content(master_cv: dict, job: dict, user_id: int) -> dict | None:
    """Select relevant CV content for tailored CV generation.

    Uses ChromaDB to rank work entries and highlights by relevance to the job.
    Falls back to original work order when ChromaDB returns no results.

    Returns None when master_cv has no work entries (signal to use legacy pipeline).
    """
    work = master_cv.get("work") or []
    if not work:
        return None

    query = _build_query(job)
    selected_work = _select_work_entries(work, user_id, query)
    skill_intersection = _compute_skill_intersection(work, job)

    return {
        "work": selected_work,
        "skill_intersection": skill_intersection,
    }


def _build_query(job: dict) -> str:
    """Build a text query from job requirements."""
    must = job.get("must_have_skills") or []
    nice = job.get("nice_to_have_skills") or []
    domain = job.get("domain") or ""
    desc_snippet = (job.get("description") or "")[:200]
    parts = list(must) + list(nice) + ([domain] if domain else []) + [desc_snippet]
    return " ".join(parts).strip()


def _select_work_entries(
    work: list[dict],
    user_id: int,
    query: str,
) -> list[dict]:
    """Return work entries ranked by relevance, with selected highlights."""
    work_index = {entry["id"]: entry for entry in work}

    chroma_results = query_similar_work(user_id, query, n_results=_MAX_WORK_ENTRIES)
    if chroma_results:
        ordered_ids = [r["id"] for r in chroma_results if r["id"] in work_index]
        distance_map = {r["id"]: r["distance"] for r in chroma_results}
    else:
        # Fallback: use original order
        ordered_ids = [e["id"] for e in work[:_MAX_WORK_ENTRIES]]
        distance_map = {e["id"]: 0.5 for e in work[:_MAX_WORK_ENTRIES]}

    result = []
    for work_id in ordered_ids:
        entry = work_index[work_id]
        highlights = _select_highlights(entry, user_id, query)
        relevance_score = max(0.0, 1.0 - distance_map.get(work_id, 0.5))
        result.append(
            {
                "id": entry["id"],
                "company": entry.get("company", ""),
                "position": entry.get("position", ""),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "selected_highlights": highlights,
                "skills_used": entry.get("skills_used") or [],
                "relevance_score": round(relevance_score, 3),
            }
        )
    return result


def _select_highlights(entry: dict, user_id: int, query: str) -> list[str]:
    """Return top highlights for a work entry, ranked by relevance."""
    all_highlights = entry.get("highlights") or []
    if not all_highlights:
        return []

    chroma_results = query_similar_highlights(user_id, query, n_results=_MAX_HIGHLIGHTS_PER_ENTRY)
    work_id = entry["id"]
    chroma_docs = {r["document"]: r["distance"] for r in chroma_results if r["id"].startswith(work_id)}

    if chroma_docs:
        # Sort by distance (ascending = more relevant)
        ranked = sorted(all_highlights, key=lambda h: chroma_docs.get(h, 1.0))
    else:
        ranked = all_highlights

    return ranked[:_MAX_HIGHLIGHTS_PER_ENTRY]


def _compute_skill_intersection(work: list[dict], job: dict) -> list[str]:
    """Skills required by job that appear in any work entry's skills_used."""
    must = [s.lower() for s in (job.get("must_have_skills") or [])]
    nice = [s.lower() for s in (job.get("nice_to_have_skills") or [])]

    all_work_skills: set[str] = set()
    for entry in work:
        for skill in entry.get("skills_used") or []:
            all_work_skills.add(skill.lower())

    return [s for s in (must + nice) if s in all_work_skills]
