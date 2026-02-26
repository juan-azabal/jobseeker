# Post-mortem: Scoring parity between list and detail endpoints

**Date:** 2026-02-26
**Commits fixed:** a3aebfb, 65c039a, f1c69f1, 0ea8755
**Symptoms:** Same job showed different scores in `/jobs` list vs `/jobs/{id}` detail — diffs of 3 to 20 points.

---

## Root causes found (3)

### 1. `remote_restriction` is not a DB column

**What happened:**
`GET /api/jobs` (list) extracts `remote_restriction` via SQL:
```sql
json_extract(j.parsed, '$.remote_restriction') AS remote_restriction
```
`GET /api/jobs/{id}` (detail) uses `SELECT * FROM jobs` — no such column exists → `job.get("remote_restriction")` is always `None` → `_is_remote_requiring_reloc()` skips the LLM-parsed fallback → different `is_reloc` result → different relocation penalty.

**Fix applied:** Inject from parsed dict after JSON-parsing in `get_job()`.

**Architectural fix needed:** Add `remote_restriction` as a proper column on the `jobs` table (migration), populated at ingest time. Then `SELECT *` returns it naturally and the injection hack is not needed.

---

### 2. Global skill_lookup triggers substring fallback

**What happened:**
`_score_and_tier_jobs()` batched all unique skills from all jobs into one `precompute_skill_lookup()` call. With ~300 unique job skills × 17 profile skills = ~6,000 pairs, this exceeded the 500-pair limit in `match_skills()`, which silently fell back to substring matching. Substring matching produced false positives (e.g. `"data and reporting services"` matching profile skill `"data"`) → inflated scores in list.

The detail path had a small skill set (one job's ~8 skills × 17 = 136 pairs) → semantic matching via embeddings → correct, lower scores.

**Fix applied:** Removed the global skill_lookup entirely. Both paths now score skills per-job via `db_path` (semantic matching, SQLite embedding cache). 0 mismatches across 57 jobs.

**Architectural fix needed:** Two options:
- **A (simpler):** Raise or remove the pair limit in `match_skills()` / `skill_matcher.py` — the SQLite cache makes large batches fast anyway.
- **B (better):** Pre-compute the skill lookup per unique job skill at ingest/backfill time and store in the DB. Scoring at query time then becomes pure dict lookup with no pair-limit concern.

---

### 3. Scoring logic split across two code paths

**What happened:**
`_score_and_tier_jobs()` (list) and `get_job()` (detail) each had their own scoring code that diverged over time:
- List used `heuristic_score()` directly; detail used `heuristic_score()` with different params.
- List applied relocation penalty outside `_score_single_job()`; detail did it differently.
- v2 scored jobs (hybrid) only handled in list; detail fell back to raw stored score.

**Fix applied:** Extracted `_score_single_job()` helper used by both paths. Three explicit branches: v2 hybrid → v1 RAG → unscored heuristic.

**Architectural fix needed:** The real fix for 1 and 2 above would make this helper trivially correct. With `remote_restriction` as a DB column and skill scores pre-stored, scoring at query time is stateless and both endpoints naturally produce the same result without shared helper gymnastics.

---

## Underlying pattern

The divergence happened because **two query shapes** (`get_jobs` CTE vs `SELECT *`) feed the same scoring function, but deliver different data. Any field computed in the list query but absent from `SELECT *` becomes a silent difference.

**General rule to enforce:** Scoring functions must never access fields that differ between query paths. Either:
1. All scored fields come from `parsed` (the JSON blob, always present in both), or
2. The field is a real DB column present in `SELECT *`.

Computed SQL expressions (json_extract, COALESCE, ROW_NUMBER) are list-only and must never be relied on by scoring.

---

## Operational note

The server was running from a stale worktree (`peaceful-rhodes`) instead of `main`. Fixes applied to `main` were not live until the server was restarted pointing to `main`. To prevent this: always run the backend from the canonical repo path (`/Users/juanazabal/Proyectos/jobsearch`), never from a worktree path.
