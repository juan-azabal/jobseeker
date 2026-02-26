"""Persist gap/strength data from scored jobs for future trend analysis."""

import json
import os
from datetime import datetime, timedelta


def append_gap_history(jobs: list, profile: dict, history_dir: str = "data/gap_history") -> int:
    """Append scored job gap/strength data to per-user JSONL file.

    Returns number of entries appended.
    Prunes entries older than 90 days on each call.
    """
    user_id = profile.get("user", {}).get("id", "default")
    os.makedirs(history_dir, exist_ok=True)
    filepath = os.path.join(history_dir, f"{user_id}.jsonl")

    # Read existing entries and prune old ones
    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    existing = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("date", "") >= cutoff:
                        existing.append(line)
                except json.JSONDecodeError:
                    continue

    # Build new entries
    today = datetime.now().strftime("%Y-%m-%d")
    new_entries = []
    for job in jobs:
        rag = job.get("rag_score")
        if not rag:
            continue
        parsed = job.get("parsed") or {}
        strengths_list = rag.get("strengths") or []
        gaps_list = rag.get("gaps") or []

        # Score: v1 = stored numeric; v2 = sum of grade points (LLM contribution only)
        _gp = {"A": 20, "B": 12, "C": 5}
        score = rag.get("score") if rag.get("score") is not None else (
            _gp.get(str(rag.get("technical_depth") or "").upper(), 10)
            + _gp.get(str(rag.get("profile_evidence") or "").upper(), 10)
        )
        entry = {
            "date": today,
            "role_id": job.get("id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "score": score,
            "salary_eur": job.get("_salary_eur", 0) or 0,
            "domain": parsed.get("domain", ""),
            "seniority": parsed.get("seniority", ""),
            "strengths": [s.get("claim", "") for s in strengths_list if isinstance(s, dict)],
            "gaps": [g.get("gap", "") for g in gaps_list if isinstance(g, dict)],
            "gap_severities": [g.get("severity", "") for g in gaps_list if isinstance(g, dict)],
            "location_type": parsed.get("location_type", ""),
            "url": job.get("job_url", ""),
        }
        new_entries.append(json.dumps(entry, ensure_ascii=False))

    if not new_entries and len(existing) == _count_lines(filepath):
        return 0

    # Rewrite pruned + append new
    with open(filepath, "w") as f:
        for line in existing:
            f.write(line + "\n")
        for line in new_entries:
            f.write(line + "\n")

    return len(new_entries)


def _count_lines(filepath: str) -> int:
    """Count non-empty lines in file."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, "r") as f:
        return sum(1 for line in f if line.strip())
