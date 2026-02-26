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
job["rag_score"] = {           # dict if scoring succeeded, None if failed/skipped
    "technical_depth":  str,   # "A"|"B"|"C" — LLM grade (v2)
    "profile_evidence": str,   # "A"|"B"|"C" — LLM grade (v2)
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

The scoring rubric (grade definitions, JSON output format) lives at `prompts/scoring-rubric-v2.md`. The `_build_scoring_prompt()` function in `scorer.py` dynamically interpolates profile-specific values (name, target domains, seniority levels) into the static rubric.

**Do not modify the rubric inline in `scorer.py`. Edit `prompts/scoring-rubric-v2.md` and update the f-string accordingly.**

The archived v1 rubric (numerical sub-scores) is at `prompts/scoring-rubric-v1.md`.

## Heuristic Score (main.py + api/scoring.py)

`_heuristic_score(job)` (agent) and `heuristic_score(profile, parsed, job, is_reloc, db_path, skill_lookup, domain_override)` (api) compute a quick 0–100 fit score from parsed data without API calls:
- Domain (0–15), Seniority (0–15), Location (0–10), Skill overlap (0–30), Red flags (−5 each, max −15)
- Location bonus: +10 for global remote, +8 for home-city hybrid, +6 for home-city onsite, 0 for geo-restricted remote
- Country-pinned remote jobs ("Remote from Portugal", restriction="Netherlands only") get 0 location bonus — detected via `_is_remote_requiring_reloc()` using auto-derived regions from country-converter
- Salary normalization to EUR uses CurrencyConverter (ECB reference rates, offline). Supports 18 currencies.

### Domain Scoring Cascade (Phase 13)

The API heuristic scorer resolves domain through a 4-stage cascade:

1. **User override** (`domain_override` param): if set, use directly — skips all inference
2. **Enum match**: if `parsed.domain ≠ 'other'`, use as-is
3. **Keyword inference** (`_infer_domain()`): if `parsed.domain = 'other'`, scan JD text against `_DOMAIN_KEYWORDS` (29 domains, ≥2-word rule; brand exceptions: databricks, snowflake, kubernetes, terraform)
4. **Semantic fallback** (`_semantic_domain_score()`): if still 'other', use embedding cosine similarity ≥0.75; score clamped [-15, 15]

Domain weight may be negative (user deprioritized that domain). Total heuristic score clamped to 0 minimum.
`domain_override` is stored per-user in `user_job_status.domain_override` (migration 014).

### RAG Penalty Clause (v1 only — removed in v2)

v1 rubric (`scoring-rubric-v1.md`) injected a graduated PENALTY clause for negative-weight domains. In v2, domain scoring is entirely deterministic (code-side) — the LLM no longer scores domain fit. The `{penalty_clause}` placeholder is no longer used.

## Invariants

- `score_all()` returns the same list passed in (jobs enriched in-place, no new list created)
- Jobs without `parsed` data are skipped (rag_score = None, rag_error = "no parsed data")
- Errors do not propagate — each job failure is isolated; the rest of the list is returned
- Model: defined by `SCORE_MODEL` constant at top of `scorer.py` (currently `gpt-4o`)
