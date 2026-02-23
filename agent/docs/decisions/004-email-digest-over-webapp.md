# ADR-004: Email Digest Over Web Application

## Status: Accepted
## Date: 2026-02-21

## Context

Users need to review scored job listings and take action (apply, skip, review later). Two main interface options: web dashboard or email digest.

## Decision

Email digest as the primary (and only) interface. No web UI, no dashboard.

## Rationale

- **90% of value at 10% of effort.** A daily email with 3 tiers (apply/review/skip), clickable links, and key metadata covers the core use case. A web app adds auth, hosting, state management, and responsive design.
- **Zero-friction consumption.** User opens email, scans 3-5 top matches, clicks links. Total time: 5 minutes. No login, no bookmark, no app to open.
- **Push beats pull.** Job search requires consistency. An email arrives whether you're motivated or not. A dashboard requires the user to remember to check it.
- **Config-as-code audience.** Target users are developers. They configure via YAML, not UI. A web dashboard contradicts this positioning.

## Consequences

- No interactive features (sorting, filtering, saved searches) — these would require a web UI
- Email rendering constraints: table-based layout, inline CSS, limited interactivity
- If multi-user grows beyond ~10 users, a lightweight web view of past digests may be warranted
- The email template IS the product — design quality matters (see ADR-005 on design decisions)
