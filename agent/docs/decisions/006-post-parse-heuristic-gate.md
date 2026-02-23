# ADR-006: Post-Parse Heuristic Gate for Cost Control

## Status: Accepted
## Date: 2026-02-21

## Context

The pipeline parses all prefiltered jobs with gpt-4o-mini, then scores each with another LLM call. Many parsed jobs are obviously poor fits (wrong seniority, low salary, wrong domain) that the heuristic alone can identify.

Without a gate: 64 parsed jobs x $0.002/score = $0.128/run. With a gate at heuristic threshold 25: ~25 jobs scored x $0.002 = $0.05/run.

## Decision

After parsing and before scoring, compute a heuristic score for all jobs. Skip LLM scoring for jobs below `scoring.rag_threshold` or with salary below `scoring.salary_min`. These jobs still appear in the digest with their heuristic score (Tier C).

## Rationale

- **Not a hard filter.** Skipped jobs are visible but not expensively scored. The user sees them and can adjust thresholds if good roles are being skipped.
- **Configurable per user.** Thresholds live in the profile YAML. A user targeting niche roles can lower the threshold; one getting flooded can raise it.
- **Backward compatible.** If the scoring block is missing from the profile, all jobs go to scoring (threshold = 0).

## Consequences

- Some borderline jobs may get lower scores than LLM scoring would assign
- Users must calibrate thresholds against their market (too high = miss opportunities, too low = waste tokens)
- The heuristic must be reasonably accurate for this to work — if it systematically underscores good jobs, the gate does harm
