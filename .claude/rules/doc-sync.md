# Documentation Sync Protocol

IMPORTANT: Do all applicable updates BEFORE reporting the task as complete.

## Triggers and required actions

### Cualquier cambio de código
Before marking done, ask: does this change affect any of the sections below?
If unsure, open the file and check.

### New, deleted, or renamed Python file or directory
- Update Project Structure in CLAUDE.md
- Update Project structure in README.md

### Bug fixed (from Known Bugs section)
- Move entry to RESOLVED in CLAUDE.md with date and one-line explanation
- If it was a P0, also remove "(broken)" tags from Architecture diagram in CLAUDE.md

### Phase or milestone completed
- Update Current State in CLAUDE.md
- Update Status table in README.md

### Module function signature, input, or output changed
- Update corresponding file in patterns/
- Specific mappings:
  - scraper.py → patterns/scraper.md
  - prefilter.py → patterns/filter.md
  - scorer.py → patterns/scorer.md (fields in rag_score dict, tier thresholds)
  - notifier.py → patterns/notifier.md (_flatten_job schema, tier thresholds)
  - onboard.py → patterns/onboard.md

### LLM output structure changed (parser, scorer)
- Update corresponding file in schemas/

### Prompt file modified (prompts/*.md)
- Bump version comment in the prompt file header
- Verify the Python module reads from file at runtime (not inline string)

### Model changed (PARSE_MODEL, SCORE_MODEL, or similar constants)
- Update scorer.py / parser.py constant comment
- Update "Scoring" bullet in CLAUDE.md Current State
- Update Architecture diagram models in CLAUDE.md
- Update Tech stack section in README.md
- Update Project structure file comment in README.md
- Update ADR table description in README.md if relevant

### Feature removed (e.g. story mapping, RAG chunks, a display field)
- Remove all references from patterns/ files
- Remove field from notifier._flatten_job schema in patterns/notifier.md
- Remove from README if mentioned
- Remove from CLAUDE.md if mentioned

### Tier thresholds changed (A/B/C score boundaries)
- Update main.py ranked_jobs() and print_summary()
- Update notifier.py _build_context()
- Update patterns/scorer.md Tier Thresholds table
- Update patterns/notifier.md Tier Split section
- Update CLAUDE.md Key Invariants

### Cost estimate changed significantly
- Update Cost section in README.md

## Checklist before reporting done

After any non-trivial change, mentally run through:
- [ ] patterns/ up to date?
- [ ] CLAUDE.md Known Bugs / Current State / Architecture accurate?
- [ ] README.md Tech stack / Status / Project structure accurate?
- [ ] schemas/ up to date if output format changed?
