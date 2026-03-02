**Juan Azabal**
Senior Product Manager | Data, Personalization & Monetization
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal | github.com/juan-azabal
# **Summary**
Senior Product Manager with a software engineering background, focused on data platforms, personalization and monetization in high-traffic B2C media and B2B marketplace contexts. I have owned end-to-end data pipelines processing billions of events monthly, from ingestion and event taxonomy through data modeling (dbt, entity design), quality controls and downstream consumption by ML models and personalization systems. I am technical and analytical enough to dig into raw data, spot anomalies, trace issues to the code or the network layer and figure out why the numbers do not add up. That instinct has led me to rebuild or replace tracking and instrumentation at every company I have joined: Softonic, Marfeel, LaVanguardia and finally designing and owning the pipeline end-to-end at Gartner. Strong bias toward reusable platforms over one-off features. Comfortable coordinating across Engineering, Data Architecture, ML, DevOps and compliance stakeholders. Not interested in pure delivery roles.
I also build AI products end-to-end. I have designed and shipped a multi-user job search platform with a 6-phase scoring pipeline (scrape, prefilter, parse, RAG score, hybrid rank, notify), semantic skill matching via embeddings and cosine similarity plus automated tailored CV generation. The system serves real users on a production deployment, running daily automated pipelines within a budget of under two euros per user per month through deliberate model selection and cost optimization. I bring the same architectural rigor to AI products that I apply to data platforms: ADRs for every significant trade-off, test-first development and separation of deterministic logic from LLM inference.
# **Selected Impact**
- Built a first-party data platform (Snowplow, Kafka, Flink, S3, Snowflake) replacing GA4 across three marketplace brands serving millions of monthly software buyers. Designed the data model, specified dbt package configuration, defined event contracts, SLIs/SLOs and Datadog observability that reduced data loss to effectively zero.
- Aligned 7 teams with independent roadmaps (Data, Analytics, Cloud, DevOps, Traffic Quality, ML and Martech) around a shared data platform strategy, negotiating cross-team trade-offs on quality, latency and access patterns.
- Increased video revenue by 70% by analyzing raw Ad Manager data, classifying error types, killing broken campaigns (80% of the gain) and building a detection and response protocol that prevented recurrence.
- Diagnosed a broken ad loading sequence by analyzing raw Ad Manager data and network behavior. Redesigned the critical rendering path and built a header bidding solution in a web worker, lifting ad ARPU by approximately 40% and driving additional revenue through technical SEO improvements.
- Co-designed and shipped Compass, a prescriptive analytics product built on IBM Watson NLP that classified articles at scale by category, tone, entities, characters and sentiment. Together with Flowcards (scroll-bounded recommendation engine), these became the core products that carried Marfeel through the COVID downturn and remain central to the business today.
- Designed and shipped a multi-user AI job search platform from zero to production: 6-phase scoring pipeline, semantic skill matching, automated CV generation, landing page with waitlist, daily automated pipelines via GitHub Actions, deployed on Railway in open beta with early users at under two euros per user per month.
# **Core Skills**
**Data Platforms & Tracking**
- First-party tracking (edge and client-side collection), SDK and API ownership, event taxonomies. Event-driven architectures: Snowplow, Kafka, Flink/SQL, S3, Snowflake, dbt.
- Data modeling: entity-relationship design, keys, table dependencies, dbt package configuration. Data contracts, schema validation, SLIs/SLOs for freshness, loss and latency.
- Hands-on technical diagnosis: raw data analysis, network waterfall inspection, code-level debugging. Moved away from coding deliberately to focus on architecture and decision-making. Now uses AI to prototype tooling and close the execution gap when speed matters more than delegation.
**Data Governance, Privacy & Compliance**
- GDPR-compliant tracking, consent management (CMP), data minimization. Consent-aware data flows, privacy-by-design, data classification.
- Observability: Datadog dashboards, alerting, incident runbooks. Error-budget thinking applied to data quality and pipeline reliability.
**Personalization, Experimentation & Monetization**
- Paywalls, subscriptions, pricing and packaging; ARPU, LTV and CAC. AI-driven recommendations with guardrail metrics. A/B tests, holdouts, cohort analysis and funnel diagnostics.
- Programmatic advertising: header bidding, eCPM, fill rate, latency optimization. Ad monetization: direct, programmatic, native and video formats. Web performance and ad loading optimization: critical rendering path, Core Web Vitals, web workers.
**Product Management & Stakeholder Leadership**
- Cross-functional alignment across 7+ teams with independent roadmaps. Product roadmap ownership, sprint planning, agile delivery. Build vs buy decisions, vendor evaluation, platform adoption strategies.
**AI, ML & Language Model Products**
- Products built on language model outputs: prescriptive analytics on IBM Watson NLP, recommendation systems with feature engineering from NLP signals, NDCG/CTR evaluation, guardrails and retraining cadence. DMP, identity resolution, audience segmentation. Experience enabling ML teams with governed, reliable data pipelines.
- Hands-on AI development: full-stack AI product architecture from zero to production. Multi-model orchestration (gpt-4o-mini for parsing and scoring, OpenAI embeddings for semantic matching, Claude/GPT-4o for CV generation). Cost-optimized LLM pipelines: model selection per task, heuristic pre-gating to skip expensive inference, budget tracking per user.
- Agentic workflows: multi-source scraping, prefiltering, parsing, RAG scoring, notification pipelines as daily automated cron jobs. Prompt engineering as code: versioned prompts, interface contracts, scoring rubrics, categorical grades over numerical scores for stability.
- Embedding-based semantic matching: OpenAI text-embedding-3-small with cosine similarity for skill and domain matching, batch precomputation for performance. RAG pipeline design: ChromaDB vector storage, context window management.
- LLM governance layers (LiteLLM, NeMo Guardrails, Ollama): multi-tenant policy routing, deterministic and semantic rails, local LLM judge for content evaluation. Product analytics for AI: PostHog instrumentation for LLM observability. Built with Claude Code as development accelerator, maintaining architecture ownership through ADRs, patterns and schemas.
# **Projects**
**Jobseeker** (github.com/juan-azabal/jobseeker)
- AI-powered job search platform deployed in production on Railway, in open beta with early free users. Monorepo: FastAPI + SQLite (api/), React 19 + TypeScript + Tailwind v4 (web/), scraper + scorer (agent/). Google OAuth, GitHub Actions for daily pipelines. 358 tests.
- 6-phase scoring pipeline: Scrape (JobSpy + ATS + WTTJ) - Prefilter - Parse (gpt-4o-mini, 30-domain enum, role_function classification) - RAG Score (categorical grades A/B/C instead of numerical scores) - Hybrid Rank (deterministic scorers combined with LLM grades at query time) - Notify. Cross-user deduplication with per-user scoring.
- Semantic skill matching via OpenAI embeddings with cosine similarity, precomputed and cached in SQLite. One-click ATS-ready CV generation tailored per job. Under two euros per user per month through deliberate model selection and heuristic pre-gating. Honest scoring that penalizes poor fits rather than inflating confidence.
**LLM Control Plane** (github.com/juan-azabal/llm-control-plane)
- Enterprise AI governance layer routing LLM usage across business teams with different risk profiles, budgets and content policies. Two-layer guardrails: deterministic rails (secrets detection, PII handling, budget enforcement) plus semantic rails (topic control, jailbreak detection) evaluated by a local LLM judge.
- Multi-tenant architecture with independent policies per tenant. Built with LiteLLM, NeMo Guardrails, Ollama and Docker Compose. Local judge benchmarked at 90-100% F1 across tenants. 11 ADRs documenting trade-offs.
**Claude Skills** (github.com/juan-azabal/claude-skills)
- System of composable operational protocols for LLMs with trigger conditions, execution logic and quality gates. Production library of 10+ active skills covering phased implementation planning, career assistance, content creation, investment analysis and complex problem solving. Meta-skill architecture: skill-validator enforces the same patterns it uses internally.
# **Work Experience**
**Gartner Digital Markets, Barcelona, Spain**
**Senior Product Manager, Data Platform (Tracking & Analytics)**	07/2024 - Present
**Platform & Architecture**
- Own a first-party data platform replacing GA4 across three brands (Capterra, GetApp, Software Advice), including event taxonomy, web and React SDKs, edge and client-side collection and a real-time ingestion pipeline (Snowplow to Kafka to Flink/SQL to S3 lake to Snowflake).
- Studied the Snowplow dbt package documentation in depth and specified the configuration the team needed. Designed the data model: entity relationships, keys and table dependencies. Documented the full architecture with ER and data flow diagrams.
- Became the internal reference for Snowplow across the organization, ahead of Tech Lead and Engineering Manager. Led architecture decisions on event taxonomy, enrichments, tracker configuration and SDK implementation.
**Data Quality & Observability**
- Defined data contracts and SLIs/SLOs for freshness, loss and latency. Set up Datadog dashboards and alerts with incident playbooks to detect pipeline failures early.
- Reduced data loss to effectively zero through event contracts, data quality KPIs and observability across the pipeline.
**Stakeholder Alignment & Adoption**
- Aligned 7 teams with independent roadmaps (Data, Analytics, Cloud, DevOps, Traffic Quality, ML and Martech) around a shared data platform strategy, negotiating cross-team trade-offs.
- Led platform adoption across teams: documentation standards, SDK versioning, release channels and migration runbooks.
**Downstream Enablement**
- Enable downstream consumers (experimentation, personalization, ML models, CRO) with reliable data access patterns.
- Enabled Google and Bing conversion uploaders and traffic-quality controls to improve attribution signal, bidding efficiency and CAC/LTV reads.
**Grupo Godo (LaVanguardia.com), Barcelona, Spain**
**Senior Product Manager**	07/2022 - 07/2024
**Data & Personalization**
- The site had no unified data layer. Built one by consolidating fragmented tracking into a governed event model on first-party data.
- Introduced AI-driven content recommendations and personalization on first-party data: co-designed feature engineering with ML team, defined evaluation metrics (NDCG, CTR) and set guardrails for production deployment.
**Revenue & Performance**
- Balanced subscription and advertising revenue using propensity-driven paywalls, bundles and guardrails, increasing registrations by 12% without degrading ad RPM.
- Spotted anomalies in Ad Manager data: video revenue and impressions were too low. Dug into the raw data, classified errors by type and severity, traced them to specific campaigns and stopped the worst offenders, which alone delivered 80% of the revenue improvement. Then built the detection protocol. End result: 70% video revenue growth, 20% more pages per visit and 25% faster load times.
**Organization & Leadership**
- Aligned Editorial, Engineering, Data and Ad Ops on shared KPIs and delivery cadence.
- Mentored 2 PMs on data and experimentation, creating reusable playbooks.
**Marfeel, Barcelona, Spain**
**Senior Product Manager**	09/2018 - 07/2022
**Platform & Analytics**
- Owned an ad-wrapper SDK and unified analytics for eCPM, fill rate, latency and UX across programmatic, direct, native and video. Regularly audited raw ad-call data and network behavior across publisher sites.
- Scaled the platform to 600+ publishers and over 5B monthly impressions, becoming a single source of truth for monetization and engagement metrics.
**Ad Loading & Performance Optimization**
- Detected that ad position 2 had more impressions than position 1, which should not happen in sequential loading. Traced the root cause: the sequential loading algorithm was broken, with ads blocking each other and content load.
- Defined a critical rendering path for ad and content loading, created prioritization rules and ran multiple controlled tests. Designed a header bidding solution running in a web worker to unblock the main thread.
- Result: approximately 40% increase in ad ARPU, with total revenue growing even more because improved technical SEO brought additional traffic.
**AI, NLP & Product Pivot**
- Co-designed and shipped Compass, a prescriptive analytics product built on IBM Watson NLP. Watson classified articles at scale by category, tone, entities, characters and sentiment. These signals fed a tool enabling publishers to make data-driven editorial decisions.
- Co-designed and productionized the recommendation engine within Flowcards: feature selection from NLP signals, NDCG/CTR evaluation, production guardrails and automated retraining pipeline. Flowcards evolved from an earlier project I led (AMP Next on desktop) that had no impact because barely any users scrolled to the end, revealing the real insight: engage users when they lose interest, not when they finish.
- Together, Compass and Flowcards became the products that carried Marfeel through the COVID downturn. The company today operates better than ever on these products.
**Privacy & Compliance**
- Evaluated all major CMPs and found none acceptable for performance. Led the decision to build a proprietary CMP optimized for performance, with native integration to Ad Manager and header bidding.
- Drove simultaneous adoption of sellers.json, TCF consent string and related industry standards across the publisher network while maintaining revenue and compliance.
**Industry Migrations & Operations at Scale**
- Coordinated the Google MCM migration across 800 publishers in approximately one month with minimal revenue loss. Specified monitoring tooling in Google Apps Script, segmented publishers into tiers for prioritized outreach and set up automated communications.
**Commercialization**
- Introduced freemium to Enterprise packaging with usage guardrails, SLAs and revenue-share contracts tied to quality.
- Represented the company in industry standardization communities (Prebid, AMP).
**Softonic, Barcelona, Spain**
**Product Manager**	07/2017 - 09/2018
- Audited existing tracking and instrumentation by analyzing raw data and network requests. Found that live impression data from the ad server was not reaching GA4 correctly and header bidding bid data was not being captured at all. Rebuilt the measurement foundation before optimizing revenue.
- Led the shift to a SaaS-like monetization model with packaging and tiering that increased total revenue by 25%. Launched premium formats and growth products that increased ARPPU by 50%.
- Discovered the analytics team was using standard A/B testing for changes that affected how advertisers bid on positions, which contaminated the control group. Changed the experimentation framework to geo-based testing for these cases.
**Adform, Madrid, Spain**
**Associate Product Manager, Programmatic & Data**	06/2015 - 07/2017
- Led DMP and ML-assisted CRO initiatives for enterprise customers. Owned data onboarding, taxonomy design and identity resolution for privacy-safe activation and measurement.
- Became a trusted advisor for enterprise clients across full-stack AdTech beyond Adform's product scope. Regularly visited agencies to train non-technical teams on programmatic advertising, audience strategy and AdTech tooling.
- Won Employee of the Year award after supporting a client's largest account (Walmart) during Buen Fin in Mexico. Ran ad serving and DSP campaigns, produced creatives and diagnosed a third-party script degrading site performance.
**Various Companies, Madrid, Spain**
**Web Developer and Founder**	08/2006 - 05/2015
- Built e-commerce platforms, media sites and a live video streaming platform for music festivals. Founded and grew an independent sports media outlet using SEO and social distribution.
# **Education and Certifications**
MSc, Complex Problem Solving, Universidad Internacional de La Rioja (UNIR), 2024
MBA, ThePower Business School, 2020
Postgraduate, Product Management, The Hero Camp, 2019
Postgraduate, Web Development and Digital Content, CICE, 2014
Engineer's Degree, Computer Software Technology, Universidad Europea Miguel de Cervantes, 2008

Selected certifications: Google Ad Manager Certified Partner; TensorFlow AI Certification; LinkedIn Learning (AI-first Product Leadership, Advanced Product Marketing, Agile User Stories)
# **Languages**
Spanish (native) | English (advanced) | Catalan (basic)