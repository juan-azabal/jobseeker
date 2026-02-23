# JobSeeker — Scoring Rules Audit

> **Execute. Do not plan.** If you enter plan mode, call ExitPlanMode immediately.

## Task: Audit scoring rules for user-specificity

### Context
JobSeeker uses jobagent for job scoring across 5 dimensions: domain fit, seniority, technical depth, profile evidence, strategic impact. The scoring was originally built for a single user (PM/tech profile). Before opening the product to other users, we need to identify which scoring rules are **generic** (work for any profile) vs **hardcoded to the original user's profile** (PM-specific thresholds, hardcoded skill lists, calibration values that assume a specific background).

This is an AUDIT — do not change any code. Only produce a report.

### What to examine

Read ALL scoring-related code in the jobagent repo (typically `../jobagent` or the path in `JOBAGENT_DIR`). This includes:
- Scoring modules (wherever the 5 dimensions are computed)
- Prompts sent to LLMs for scoring (if scoring uses LLM calls)
- Any YAML/JSON config files with thresholds, weights, or criteria
- Tier classification logic (how scores map to Apply / Review / Skip)
- The job parser (especially `must_have_skills` and `experience_requirements` extraction)
- Profile matching logic (how user profile fields are compared against job requirements)

### What to report

For EACH item found, classify it into one of these categories:

**🔴 HARDCODED-PERSONAL**: Values or rules that only make sense for the original user's profile. Examples:
- Hardcoded skill lists (e.g., "SQL, Python, dbt" as expected skills)
- Seniority assumptions (e.g., "10+ years experience" as baseline)
- Domain-specific weights (e.g., "product management" weighted higher than other domains)
- Geographic preferences baked into scoring logic
- Company-type biases (e.g., consultancy penalized or boosted)

**🟡 CALIBRATION**: Values that are reasonable defaults but should be configurable per user. Examples:
- Tier thresholds (what score = Apply vs Review vs Skip)
- Dimension weights (how much each of the 5 dimensions contributes)
- Minimum score floors
- Seniority band definitions

**🟢 GENERIC**: Rules that work for any user and need no changes. Examples:
- "Match user's listed skills against job requirements"
- "Score higher if job location matches user preference"
- "Parse job description to extract required skills"

### Output format

Create a file `scoring-audit-report.md` in the jobseeker repo root with this structure:

```markdown
# Scoring Audit Report

## Summary
- Total items found: N
- 🔴 Hardcoded-personal: N
- 🟡 Calibration: N  
- 🟢 Generic: N

## Detailed Findings

### [Dimension or Module Name]

#### [Finding title]
- **Category**: 🔴/🟡/🟢
- **File**: `path/to/file.py` (line N–M)
- **What it does**: [1-2 sentences]
- **Why this category**: [1 sentence justification]
- **Code snippet**: [relevant lines, keep short]

[repeat for each finding]

## Recommendations
[Brief summary of what needs to change before multi-user launch, grouped by priority]
```

### Sequence
1. Find the jobagent repo path. Check `JOBAGENT_DIR` env var, fall back to `../jobagent`.
2. List the full directory structure of jobagent to understand the codebase layout.
3. Read ALL Python files related to scoring, parsing, and profile matching. Be thorough — check every file, not just the obvious ones.
4. Read any YAML/JSON config files that contain scoring parameters.
5. Read any prompt templates used for LLM-based scoring.
6. Classify each finding per the categories above.
7. Write the report to `scoring-audit-report.md`.
8. Commit: `docs: scoring rules audit for multi-user readiness`
