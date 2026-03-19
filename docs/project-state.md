# Project State — Phase History

## Completed Phases

### Phase 0 — Scaffold
### Phase 1 — MVP: Ingest + browse jobs with period/tier filters
### Phase 2 — Auth: Google OAuth (authlib + SessionMiddleware, HTTP-only cookie)
### Phase 3 — Onboarding: CV upload (.docx) → generate-profile → edit → save-profile
### Phase 4 — UI overhaul + job tracking + profile page
- Dark theme (zinc-950), violet-500 primary, semantic tier colors
- Job tracking: `user_job_status` table, `POST /jobs/{id}/apply`
- CV generation button, bulk selection, profile page, header redesign
- Tier C hidden by default

### Phase 5 — CV Generation (in-app tailored CV download)
- LLM provider configurable, .docx with python-docx, ATS audit

### Phase 6 — CV Output Quality
- Plan-driven architecture, programmatic validator, 3-page hard cap

### Phase 7 — Deparameterize Scoring (rubric role_type/geography, adjacent domains)
### Phase 8 — Per-Profile Pipeline (searches, watchlist, prefilter per-user)

### Phase 9 — Per-User Scoring + New-User Bootstrap
- `jobs` shared, `user_job_scores` per-user RAG, heuristic at query time
- Onboarding triggers GHA pipeline via workflow_dispatch

### Phase 10 — Ops: Persistence, Health, Admin
- Railway volume, auto-prune 90 days, admin system

### Phase 11 — Cross-User Dedup + Sequential Pipeline
- batch-lookup, api_cache.py, sequential GHA loop

### Phase 12 — Semantic Skill Matching
- 256-dim embeddings, cosine similarity, backfill scripts, diagnostics

### Phase 13 — Domain Scoring Fix (v2)
- 13.1: RAG penalty clause (graduated)
- 13.2: 30-domain enum, parser v1.3, keyword matching
- 13.3: Heuristic gate dict
- 13.4: Domain override (user + admin)
- 13.5: Admin reparse-domains
- 13.6: Keyword collision regression tests; 415 backend + 194 agent tests

### Phase 14 — Instrumentation + Observability
- structlog, health endpoint, PostHog Python + frontend + AI wrappers + agent events

### Phase 15 (Landing) — Landing Page + Waitlist
- Public landing, Instrument Serif, WCAG AA, waitlist API, MockDashboard

### Phase 15 (Geo) — Geo Filtering
- 3-layer detection, WTTJ partial-remote tightening, ATS geo filter, unified prefilter
- PostHog per-job tracking, derive_target_countries(); 458 agent tests

### Phase 16 — Landing Page Iteration
- MockJobDetail, MockCVButton, CV callout, 4-step how-it-works

### Phase 17 — Decomposed Hybrid Scoring
- 17.1: role_function enum + parser v1.4 + migration 017
- 17.2: Scoring rubric v2 (A/B/C grades), grade_mapping.py
- 17.3: DB grade storage + reparse_rescore.py
- 17.4: hybrid_score() + API wiring
- 17.5: role_function gate (-15 penalty)
- 17.6: Profile fields + onboarding
- 17.7: Regression test suite (gaming, PM mismatch, cross-user differentiation)

### Phase 18 — Profile Data Integrity
- merge_profiles() pure function, CV Replace server-side merge
- _yaml_to_flat_profile() / _apply_flat_to_yaml() extracted
- CVReplaceSummary component; 598 backend tests

### Phase 19 — Location Eligibility + Scoring Recalibration
- Kill v1 RAG path, eligibility penalty (-20), graduated location scoring
- Tier recalibration (A>60, B>40, C≤40)
- eligibility_warning field + UI badges
- Cross-system parity tests; 639 backend + 470 agent tests

### Phase 20 — Email Digest Overhaul
- Rebrand JobAgent→JobSeeker, platform links, violet accent, dark mode
- Preheader, rollback toggle, 517 agent tests

### Ingestion Overhaul (2026-02-26)
- Phase 0: WTTJ geo filter, make_job_id normalization, nan sanitization, smoke tests
- Phase 1: RawJob Pydantic model, JobSpy/WTTJ/ATS field enrichment, pipeline wiring
- Phase 2: merge_jobs() with source priority, smart description merge
- Phase 3: preseed_parsed() + parser pre-seed integration
- Phase 4: Migration 019 (14 enriched columns), ingest + API exposure
- 562 backend + 376 agent tests

### Phase 20b — Email Digest API Architecture (2026-03-01)
- GET /api/digest/{profile_id}, notifier rewritten for API-only scoring
- _sync_to_railway() in pipeline, GHA curl sync removed
- 659 backend + 625 agent tests

### Scoring Data Extraction (2026-03-01)
- shared/scoring_data.py (pure constants), shared/scoring_core.py (~370 lines)
- 692 backend + 429 agent tests

### Phase Staging (2026-03-01)
- ENVIRONMENT config, staging middleware, DB export/import, auto-seed
- StagingBanner, admin refresh button; 717 backend tests

### Master CV JSON (2026-03-02)
- Parser v1.5 fields, shared/master_cv_scoring.py, ChromaDB scoring enrichment
- CV generation from Master CV (select/render/rewrite pipeline)
- Career history UI (AddSourceModal, AddEntryModal); 841 backend + 601 agent tests

### Parser Enrichment + CV Pipeline Optimization (2026-03-02)
- Parser v1.5 (4 new fields), plan-aware CV prompt (~40% token reduction)
- JobDetailPage self-sufficient, scorer rubric v2.1; 716 backend + 598 agent tests

### Career History UX — Async CV Processing (2026-03-02)
- BackgroundTasks for replace-cv and add-source (202 immediate return)
- AddSourceModal routing (.docx vs .pdf/text); 892 backend tests

### Phase UID — User ID Migration (2026-03-11)
- Migration 024: profile_id→user_id; agent endpoints use int user_id
- load_profile_data(user_id: int); 975 backend tests

### Phase QC — Deterministic Quality Checks (2026-03-19)
- CV content assertions (hallucination + length bounds)
- Parse quality monitoring (null_field_rates, alert thresholds)
- Golden prompt tests (17 regression tests); 1011 backend tests
