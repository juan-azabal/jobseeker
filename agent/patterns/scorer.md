# Pattern: Scorer Module

## Contract

```python
# Score all jobs concurrently
score_all(
    jobs: list[dict],
    collection,             # vectorstore collection (from build_vectorstore())
    profile: dict,          # user profile loaded from YAML
    max_workers: int = 2,   # gpt-4o is slower/pricier than mini
) -> list[dict]             # same list, jobs enriched in-place

# Score a single job
score_job(
    job: dict,
    collection,
    profile: dict,
    n_chunks: int = 8,
) -> dict                   # job dict enriched with rag_score and rag_error
```

## Fields Added to Job Dict

After scoring, each job has two new fields:

```python
job["rag_score"] = {        # dict if scoring succeeded, None if failed/skipped
    "score":            int,             # 0-100
    "score_breakdown":  dict,            # 5 sub-scores, see schemas/scored_job.json
    "strengths":        list[dict],      # [{"claim": str, "evidence": str}]
    "gaps":             list[dict],      # [{"gap": str, "severity": str, "category": str, "mitigation": str}]
    "deal_breakers":    list[str],
    "talking_points":   list[str],
    "one_line_verdict": str,
}
job["rag_error"] = str | None           # error message if scoring failed, else None
```

See `schemas/scored_job.json` for the full output contract.

## Tier Thresholds

| Tier | Score range | Email treatment |
|---|---|---|
| A | ≥ 50 | Full card: strength, gap |
| B | 30–49 | Compact row |
| C | < 30 | Single muted line |

**These thresholds are synced with `notifier.py:_build_context()`. If you change them here, update notifier too.**

## Business Logic Prompt

The scoring rubric (dimensions, score ranges, JSON output format) lives at `prompts/scoring-rubric.md`. The `_build_scoring_prompt()` function in `scorer.py` dynamically interpolates profile-specific values (name, target domains, seniority levels) into the static rubric.

**Do not modify the rubric inline in `scorer.py`. Edit `prompts/scoring-rubric.md` and update the f-string accordingly.**

## Invariants

- `score_all()` returns the same list passed in (jobs enriched in-place, no new list created)
- Jobs without `parsed` data are skipped (rag_score = None, rag_error = "no parsed data")
- Errors do not propagate — each job failure is isolated; the rest of the list is returned
- Model: defined by `SCORE_MODEL` constant at top of `scorer.py` (currently `gpt-4o`)
