# Master CV - Juan Azabal

## Interface
**Purpose**: Complete professional history, skills, and impact. Source of truth for CV generation and offer analysis.
**Input requires**: none
**Output produces**: experience, skills, impact bullets, education
**Standalone?**: YES

---

## Contact

Juan Azabal
Senior Product Manager | Data, Personalization & Monetization
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal

## Summary

Senior Product Manager with a software engineering background, focused on data platforms, personalization and monetization in high-traffic B2C media and B2B marketplace contexts. I have owned end-to-end data pipelines processing billions of events monthly, from ingestion and event taxonomy through data modeling (dbt, entity design), quality controls and downstream consumption by ML models and personalization systems. I am technical and analytical enough to dig into raw data, spot anomalies, trace issues to the code or the network layer and figure out why the numbers do not add up. That instinct has led me to rebuild or replace tracking and instrumentation at every company I have joined: Softonic, Marfeel, LaVanguardia and finally designing and owning the pipeline end-to-end at Gartner. Strong bias toward reusable platforms over one-off features. Comfortable coordinating across Engineering, Data Architecture, ML, DevOps and compliance stakeholders. Not interested in pure delivery roles.

## Selected Impact

- Built a first-party data platform (Snowplow, Kafka, Flink, S3, Snowflake) replacing GA4 across three marketplace brands serving millions of monthly software buyers. Designed the data model, specified dbt package configuration, defined event contracts, SLIs/SLOs and Datadog observability that reduced data loss to effectively zero.

- Aligned 7 teams with independent roadmaps (Data, Analytics, Cloud, DevOps, Traffic Quality, ML and Martech) around a shared data platform strategy, negotiating cross-team trade-offs on quality, latency and access patterns.

- Became the internal reference for Snowplow across the organization, ahead of engineering, leading architecture decisions on event taxonomy, enrichments, dbt package configuration and SDK implementation.

- Defined data governance frameworks including consent-aware collection, GDPR-compliant taxonomies and data minimization policies across multiple brands, geographies and regulatory contexts.

- Introduced data contracts and incident runbooks for freshness, loss and latency, cutting mean time to detect pipeline issues from hours to minutes.

- Increased video revenue by 70% by analyzing raw Ad Manager data, classifying error types, killing broken campaigns (80% of the gain) and building a detection and response protocol that prevented recurrence.

- Scaled an ad monetization and analytics platform to 600+ publishers and over 5B monthly impressions while enforcing latency and quality thresholds.

- Coordinated the Google MCM migration for 800 publishers in approximately one month with minimal revenue loss. Specified and iterated on monitoring tooling in Apps Script connecting Ad Manager data for real-time status tracking, tiered outreach operations and automated communications, while simultaneously adapting to sellers.json and consent string requirements.

- Diagnosed a broken ad loading sequence by analyzing raw Ad Manager data and network behavior. Redesigned the critical rendering path and built a header bidding solution in a web worker, lifting ad ARPU by approximately 40% and driving additional revenue through technical SEO improvements.

- Shipped SaaS packaging and tiering that lifted total revenue by 25% and increased ARPPU by 50% on premium formats.

- Co-designed and shipped Compass, a prescriptive analytics product built on IBM Watson NLP that classified articles at scale by category, tone, entities, characters and sentiment. These signals powered a tool enabling publishers to make data-driven editorial decisions based on which content attributes correlated with engagement and revenue.

- Co-designed and productionized the recommendation engine within Flowcards (scroll-bounded engagement and conversion overlays): feature selection from NLP signals, NDCG/CTR evaluation, production guardrails and automated retraining pipeline. Flowcards evolved from an earlier project I led using AMP Next on desktop as a lightweight alternative to JS-heavy infinite scroll. That project had no impact because barely any users scrolled to the end, revealing the real insight: engage users when they lose interest in the current article, not when they finish it. Compass and Flowcards became the core products that carried Marfeel through the COVID downturn and remain central to the business today.

- Balanced subscription and advertising revenue using propensity-driven paywalls, bundles and guardrails, increasing registrations by 12% without degrading ad RPM.

- Led cross-functional alignment across Engineering, Data, Marketing and Finance to standardize KPI definitions, data access patterns and reporting cadences.

- Enabled Google and Bing conversion uploaders and traffic-quality controls to improve attribution signal, bidding efficiency and CAC/LTV reads.

- Designed, built and shipped a multi-user AI scoring platform from zero to production using AI-assisted development (Claude Code). Full stack: FastAPI API, React 19 frontend, RAG scoring pipeline with multi-model orchestration (GPT-4o-mini for parsing, GPT-4o for grading), semantic skill matching via OpenAI embeddings and cosine similarity, Google OAuth, CI/CD on GitHub Actions and Railway deploy. Four active users, sub-2 EUR per user per month through deliberate model selection per pipeline phase.

## Projects

### Jobseeker - AI-Powered Job Matching and CV Platform | 2024 - Present

Built end-to-end as sole product owner and developer, using Claude Code as execution multiplier. The platform ingests job postings from multiple sources, scores them against user profiles and generates tailored CVs per application.

- Designed a 6-phase scoring pipeline: ingest (multi-source scraper with domain classification) to heuristic pre-filter to RAG grading (LLM-as-judge with structured rubrics) to deterministic re-scoring with user-editable preference weights. Heuristic and RAG scores complement each other: heuristic handles dimensions with clear business rules (domain, seniority, location), RAG handles subjective fit (technical depth, profile evidence).
- Implemented semantic skill matching using 256-dimensional OpenAI embeddings with numpy matrix operations for cosine similarity, replacing exact keyword matching. Users see which of their skills match a posting and which are gaps, with conceptual proximity rather than string equality.
- Architected for multi-user from day one: profile YAML as single source of truth per user, cross-user job deduplication via shared database, zero coupling between user-facing API and background processing agent.
- Achieved sub-2 EUR monthly cost per user through strategic model selection: GPT-4o-mini for high-volume low-complexity tasks (parsing, classification), GPT-4o for low-volume high-judgment tasks (fit scoring). CV generation accounts for 95% of LLM spend.
- Stack: FastAPI, SQLite (raw migrations), React 19, TypeScript, Tailwind v4, ChromaDB, OpenAI API, Google OAuth, Railway, GitHub Actions.

## Core Skills

**Data Platforms & Tracking**
- First-party tracking (edge and client-side collection), SDK and API ownership, event taxonomies.
- Event-driven architectures: Snowplow, Kafka, Flink/SQL, S3, Snowflake, dbt.
- Data modeling: entity-relationship design, keys, table dependencies, dbt package configuration.
- Data contracts, schema validation, SLIs/SLOs for freshness, loss and latency.
- Architecture documentation: ER diagrams, data flow diagrams, migration playbooks.
- Hands-on technical diagnosis: raw data analysis, network waterfall inspection, code-level debugging of tracking and instrumentation issues. Moved away from coding deliberately to focus on architecture and decision-making. Now uses AI to prototype tooling and close the execution gap when speed matters more than delegation.

**Data Governance, Privacy & Compliance**
- GDPR-compliant tracking, consent management (CMP), data minimization.
- Consent-aware data flows, privacy-by-design, data classification.
- Observability: Datadog dashboards, alerting, incident runbooks.
- Error-budget thinking applied to data quality and pipeline reliability.

**Personalization, Experimentation & Monetization**
- Paywalls, subscriptions, pricing and packaging; ARPU, LTV and CAC.
- AI-driven recommendations with guardrail metrics.
- A/B tests, holdouts, cohort analysis and funnel diagnostics.
- Programmatic advertising: header bidding, eCPM, fill rate, latency optimization.
- Ad monetization: direct, programmatic, native and video formats.
- Web performance and ad loading optimization: critical rendering path, Core Web Vitals, web workers.

**Product Management & Stakeholder Leadership**
- Cross-functional alignment across 7+ teams with independent roadmaps.
- Product roadmap ownership, sprint planning, agile delivery.
- Build vs buy decisions, vendor evaluation, platform adoption strategies.
- Clear communication of trade-offs to senior stakeholders.

**AI, ML & Language Model Products**
- Products built on language model outputs: prescriptive analytics on IBM Watson NLP (content classification at scale by category, tone, entities, sentiment).
- Recommendation systems: feature engineering from NLP signals, NDCG/CTR evaluation, guardrails, retraining cadence.
- RAG pipelines: retrieval-augmented generation with structured rubrics, LLM-as-judge scoring, prompt engineering as code.
- Multi-model orchestration: model selection by task complexity and cost, pipeline decomposition into deterministic and LLM-graded phases.
- Embedding-based semantic matching: vector similarity for skill detection, domain classification and content proximity.
- AI-assisted development: spec-to-production using Claude Code, test-first methodology, phased implementation plans.
- ML-assisted CRO and optimization initiatives.
- DMP, identity resolution, audience segmentation.
- Experience enabling ML teams with governed, reliable data pipelines.


## Education and Certifications

MSc, Complex Problem Solving, Universidad Internacional de La Rioja (UNIR), 2024
MBA, ThePower Business School, 2020
Postgraduate, Product Management, The Hero Camp, 2019
Postgraduate, Web Development and Digital Content, CICE, 2014
Engineer's Degree, Computer Software Technology, Universidad Europea Miguel de Cervantes, 2008

Selected certifications: Google Ad Manager Certified Partner; TensorFlow AI Certification; LinkedIn Learning (AI-first Product Leadership, Advanced Product Marketing, Agile User Stories)

## Languages

Spanish (native) | English (advanced) | Catalan (basic)
