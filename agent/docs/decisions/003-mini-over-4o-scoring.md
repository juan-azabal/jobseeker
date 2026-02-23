# ADR-003: gpt-4o-mini Over gpt-4o for Scoring

## Status: Accepted
## Date: 2026-02-21

## Context

The scorer evaluates job-candidate fit using an LLM call with a detailed rubric (5 dimensions, explicit score ranges, structured JSON output). Initial implementation used gpt-4o.

Cost per job: gpt-4o at ~$0.023/job vs gpt-4o-mini at ~$0.0014/job (17x difference).

At 25 scored jobs/run, 22 runs/month: gpt-4o = $12.65/month, gpt-4o-mini = $0.77/month.

## Decision

Use gpt-4o-mini for scoring. The rubric constrains the output enough that the cheaper model performs acceptably (~90% agreement with gpt-4o on tier assignment).

## Rationale

- The scoring prompt is highly structured: 5 dimensions with explicit ranges, required JSON format, concrete evaluation criteria. This reduces the advantage of a more capable model.
- Tier assignment (A/B/C) is the actionable output, not the raw score. Mini and 4o agree on tier ~90% of the time.
- At $12/month vs $0.77/month, the cost difference funds 15x more runs or enables multi-user scaling.

## Consequences

- Marginal scoring quality loss on edge cases (borderline Tier A/B jobs)
- If quality degrades noticeably, can selectively re-score Tier A candidates with gpt-4o (two-pass approach)
- Must monitor for scoring drift over time (gap analysis module will surface this)
