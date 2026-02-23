# ADR-002: LLM-Friendly Developer Experience as Design Principle

## Status: Accepted
## Date: 2026-02-21

## Context

80% of development on JobAgent is done via LLM coding assistants (Claude Code). The primary "developer" consuming the repo's structure, conventions, and documentation is not a human reading code line by line, but an LLM processing context windows.

Industry practice (Feb 2026) focuses on Level 1: a CLAUDE.md/AGENTS.md file that provides project context. This is necessary but insufficient — it describes the system without encoding replicable patterns or verifiable contracts.

## Decision

Design the repo for LLM consumption as a first-class DX concern, at three levels:

**Level 1 — Context document (implemented):** CLAUDE.md as system prompt containing architecture, invariants, constraints, and module specs. This is the onboarding manual for every LLM session.

**Level 2 — Conventions as contracts (implemented):** `/patterns/` documents interface contracts per module type. `/schemas/` contains output fixtures. `/prompts/` contains versioned business logic prompts. An LLM follows the pattern mechanically and can validate its output against the schema.

**Level 3 — Self-verifiable system (future, when repo > 15 files):** `verify.py` that the LLM runs after changes to confirm convention compliance. Checks include: interface contracts, schema compliance, invariant sync across files, CLAUDE.md accuracy vs repo state.

## Rationale

- LLM-friendly is a superset of human-friendly. Every improvement for LLM consumption (explicit interfaces, documented invariants, output schemas) also helps human developers.
- Without patterns, each LLM session produces slightly different structures for the same type of module. Patterns reduce variance.
- Without schemas, the LLM cannot self-verify its output. Schemas close the feedback loop.
- Level 3 is deferred because verification overhead must be proportional to repo complexity. At 8 Python files, pattern docs are sufficient. At 15+, automated checks pay for themselves.

## Consequences

- CLAUDE.md must be maintained as carefully as production code
- Every breaking change requires updating CLAUDE.md first, code second
- New modules must have their interface documented in `/patterns/` before implementation
- Prompts are versioned documents, not inline strings — changes require explicit reasoning
