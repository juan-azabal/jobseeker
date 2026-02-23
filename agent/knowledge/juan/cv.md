# **Juan Azabal**
Senior Product Manager | Data, Personalization & Monetization
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal | github.com/juan-azabal
## **Summary**
Senior Product Manager with a software engineering background, focused on data platforms, personalization and monetization in high-traffic B2C media and B2B marketplace contexts. I have owned end-to-end data pipelines processing billions of events monthly, from ingestion and event taxonomy through data modeling (dbt, entity design), quality controls and downstream consumption by ML models and personalization systems. I am technical and analytical enough to dig into raw data, spot anomalies, trace issues to the code or the network layer and figure out why the numbers do not add up. That instinct has led me to rebuild or replace tracking and instrumentation at every company I have joined: Softonic, Marfeel, LaVanguardia and finally designing and owning the pipeline end-to-end at Gartner. Strong bias toward reusable platforms over one-off features. Comfortable coordinating across Engineering, Data Architecture, ML, DevOps and compliance stakeholders. Not interested in pure delivery roles.
## **Selected Impact**
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
## **Core Skills**
**Data Platforms & Tracking**
- First-party tracking (edge and client-side collection), SDK and API ownership, event taxonomies.
- Event-driven architectures: Snowplow, Kafka, Flink/SQL, S3, Snowflake, dbt.
- Data modeling: entity-relationship design, keys, table dependencies, dbt package configuration.
- Data contracts, schema validation, SLIs/SLOs for freshness, loss and latency.
- Architecture documentation: ER diagrams, data flow diagrams, migration playbooks.
- Hands-on technical diagnosis: raw data analysis, network waterfall inspection, code-level debugging of tracking and instrumentation issues.
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
- ML-assisted CRO and optimization initiatives.
- DMP, identity resolution, audience segmentation.
- Experience enabling ML teams with governed, reliable data pipelines.
- Hands-on AI development: LLM governance layers (LiteLLM, NeMo Guardrails, Ollama), prompt engineering as code (versioned prompts, interface contracts, scoring rubrics), AI agent architecture (multi-source scraping, heuristic gating, cost-optimized LLM pipelines) and composable LLM workflow design.
## **Projects**
**LLM Control Plane** (github.com/juan-azabal/llm-control-plane)
Enterprise AI governance layer that routes, guards and governs LLM usage across business teams with different risk profiles, budgets and content policies. Multi-tenant architecture with two-layer guardrails: deterministic rails (secrets detection, PII handling, budget enforcement) that cannot be bypassed, plus semantic rails (topic control, jailbreak detection) evaluated by a local LLM judge. Each tenant has independent policies: block-list topics for marketing, unrestricted access for engineering, allow-list for support. Built with LiteLLM, NeMo Guardrails, Ollama and Docker Compose. Local judge benchmarked at 90-100% F1 across tenants. 11 ADRs documenting every significant trade-off. Full test suite covering secrets, PII, topic enforcement, budget limits, jailbreak detection and fail-open behavior.
**JobAgent**
AI-powered job search agent that scores listings against a candidate profile across 5 weighted dimensions (domain fit, seniority, technical depth, profile evidence, strategic impact), detects skill gaps over time and delivers daily email digests. Scrapes Indeed, Google Jobs, LinkedIn, Greenhouse and Lever. Post-parse heuristic gate skips expensive LLM scoring for obvious non-fits (cost control). Full CV in context over RAG after benchmarking showed retrieval caused information loss without cost savings. Prompts versioned as source code with interface contracts per module. Runs daily via GitHub Actions. 73 listings scraped, filtered, parsed, scored and ranked in 90 seconds at $0.11/run. 6 ADRs. Gap tracking persists strengths and weaknesses to JSONL for longitudinal analysis.
**Claude Skills** (github.com/juan-azabal/claude-skills)
System of composable operational protocols for LLMs, packaged as skills with trigger conditions, execution logic and quality gates. Built to solve two failure modes: AI coding agents that build too much before verifying (addressed by spec-phaser, which forces incremental construction with verification gates at every step) and LLMs that repeat mistakes across sessions because context resets (addressed by externalizing operational knowledge into files the LLM loads on demand). Includes an anti-pattern library cataloged from real failures across multiple projects. Meta-skill architecture: skill-validator enforces the same patterns it uses internally.
## **Work Experience**
**Gartner Digital Markets**, Barcelona, Spain
**Senior Product Manager, Data Platform (Tracking & Analytics)** | 07/2024 - Present
**Platform & Architecture**
- Own a first-party data platform replacing GA4 across three brands (Capterra, GetApp, Software Advice), including event taxonomy, web and React SDKs, edge and client-side collection and a real-time ingestion pipeline (Snowplow to Kafka to Flink/SQL to S3 lake to Snowflake).
- Studied the Snowplow dbt package documentation in depth and specified the configuration the team needed. Designed the data model: entity relationships, keys and table dependencies. Documented the full architecture with ER and data flow diagrams.
- Became the internal reference for Snowplow across the organization, ahead of Tech Lead and Engineering Manager. Led architecture decisions on event taxonomy, enrichments, tracker configuration and SDK implementation.
- Delivered a real-time analytics pipeline used for experimentation, CRO, personalization and monetization.
**Data Quality & Observability**
- Defined data contracts and SLIs/SLOs for freshness, loss and latency. Set up Datadog dashboards and alerts with incident playbooks to detect pipeline failures early.
- Reduced data loss to effectively zero through event contracts, data quality KPIs and observability across the pipeline.
**Stakeholder Alignment & Adoption**
- Aligned 7 teams with independent roadmaps (Data, Analytics, Cloud, DevOps, Traffic Quality, ML and Martech) around a shared data platform strategy, negotiating cross-team trade-offs.
- Led platform adoption across teams: documentation standards, SDK versioning, release channels and migration runbooks.
- Partner with Marketing, Data and Finance on revenue forecasting, contribution margin and pricing experiments for marketplace offers.
**Downstream Enablement**
- Enable downstream consumers (experimentation, personalization, ML models, CRO) with reliable data access patterns.
- Enabled Google and Bing conversion uploaders and traffic-quality controls to improve attribution signal, bidding efficiency and CAC/LTV reads.
**Grupo Godo (LaVanguardia.com)**, Barcelona, Spain
**Senior Product Manager** | 07/2022 - 07/2024
**Data & Personalization**
- The site had no unified data layer. Built one by consolidating fragmented tracking into a governed event model on first-party data.
- Introduced AI-driven content recommendations and personalization on first-party data: co-designed feature engineering with ML team, defined evaluation metrics (NDCG, CTR) and set guardrails for production deployment.
- Established an experimentation framework on top of the unified data, enabling controlled A/B tests.
**Revenue & Performance**
- Balanced subscription and advertising revenue using propensity-driven paywalls, bundles and guardrails, increasing registrations by 12% without degrading ad RPM.
- Spotted anomalies in Ad Manager data: video revenue and impressions were too low. Dug into the raw data, classified errors by type and severity, traced them to specific campaigns and stopped the worst offenders, which alone delivered 80% of the revenue improvement. Then built the detection protocol: what to check, what to request from clients, how to test and how to respond when something breaks. End result: 70% video revenue growth, 20% more pages per visit and 25% faster load times.
**Organization & Leadership**
- Aligned Editorial, Engineering, Data and Ad Ops on shared KPIs and delivery cadence.
- Mentored 2 PMs on data and experimentation, creating reusable playbooks.
**Marfeel**, Barcelona, Spain
**Senior Product Manager** | 09/2018 - 07/2022
**Platform & Analytics**
- Owned an ad-wrapper SDK and unified analytics for eCPM, fill rate, latency and UX across programmatic, direct, native and video. Regularly audited raw ad-call data and network behavior across publisher sites to catch discrepancies between reported and actual performance.
- Scaled the platform to 600+ publishers and over 5B monthly impressions, becoming a single source of truth for monetization and engagement metrics.
- Expanded data collection from web-only to unified Web and Mobile SDK: events, identity resolution and postback integrations for attribution.
**Ad Loading & Performance Optimization**
- Detected that ad position 2 had more impressions than position 1, which should not happen in sequential loading. Tested the obvious fix (reducing timeout) first, no improvement. Pulled speed percentiles from Ad Manager, emulated devices and connection speeds in network analysis and traced the root cause: the sequential loading algorithm was broken, with ads blocking each other and content load. No clear rules governed what loaded first.
- Defined a critical rendering path for ad and content loading, created prioritization rules and ran multiple controlled tests. Designed a header bidding solution running in a web worker to unblock the main thread.
- Result: approximately 40% increase in ad ARPU, with total revenue growing even more because improved technical SEO brought additional traffic. This led to hiring a dedicated technical SEO specialist, building a proprietary CDN for publishers and the promotion of my manager to Chief Monetization Officer.
**AI, NLP & Product Pivot**
- Co-designed and shipped Compass, a prescriptive analytics product built on IBM Watson NLP. Watson classified articles at scale by category, tone, entities, characters and sentiment. These signals fed a tool that enabled publishers to make data-driven editorial decisions based on which content attributes correlated with engagement and revenue.
- Co-designed and productionized the recommendation engine within Flowcards (scroll-bounded engagement and conversion overlays): feature selection from NLP signals, NDCG/CTR evaluation, production guardrails and automated retraining pipeline. Flowcards evolved from an earlier project I led using AMP Next on desktop as a lightweight alternative to JS-heavy infinite scroll. That project had no impact because barely any users scrolled to the end, which revealed the real insight: you need to engage users when they lose interest in the current article, not when they finish it.
- Together, Compass and Flowcards became the products that carried Marfeel through the COVID downturn when the core marfeelization business declined. The company today operates better than ever on these products.
**Privacy & Compliance**
- Evaluated all major CMPs on the market and found none acceptable: all were slow, JS-heavy and made it impossible to precache components or skip unnecessary loads in non-GDPR geos. Led the decision to build a proprietary CMP optimized for performance, with native integration to Ad Manager and header bidding before any market CMP offered this by default.
- Ran extensive testing to maximize consent rate, since every percentage point of consent directly affected available demand partners and CPMs. Added translations for all major geos plus English as default. Partnered with CEO/CTO on privacy and monetization strategy: consent level directly affected the demand mix, requiring careful balance between compliance, banner UX and revenue.
- Drove simultaneous adoption of sellers.json, TCF consent string and related industry standards across the publisher network while maintaining revenue and compliance.
**Industry Migrations & Operations at Scale**
- Coordinated the Google MCM (Multiple Customer Management) migration across 800 publishers in approximately one month with minimal revenue loss. Defined requirements for monitoring tooling in Google Apps Script, reviewed code and iterated with a junior developer until it tracked migration status per client in real time. Segmented publishers into tiers for prioritized outreach and set up automated communications through Customer Support. Later iterated the Apps Script tooling into quick dashboards for metrics not yet available in Looker.
**Commercialization**
- Introduced freemium to Enterprise packaging with usage guardrails, SLAs and revenue-share contracts tied to quality.
- Introduced tiered data access and SLA-backed contracts for enterprise clients, tying data quality to commercial commitments.
- Represented the company in industry standardization communities (Prebid, AMP).
**Softonic**, Barcelona, Spain
**Product Manager** | 07/2017 - 09/2018
- Audited existing tracking and instrumentation by analyzing raw data and network requests. Found that live impression data from the ad server was not reaching GA4 correctly and header bidding bid data was not being captured at all. Rebuilt the measurement foundation before optimizing revenue.
- Led the shift to a SaaS-like monetization model with packaging and tiering that increased total revenue by 25%.
- Launched premium formats and growth products that increased ARPPU by 50%.
- Discovered that the analytics team was using standard A/B testing for changes that affected how advertisers bid on positions, which contaminated the control group and invalidated results. Changed the experimentation framework to geo-based testing for these cases and built dashboards in GA4 combining ad revenue with web analytics to simplify and speed up product testing.
- Worked with Engineering and Commercial teams to standardize KPI-driven optimization cycles.
**Adform**, Madrid, Spain
**Associate Product Manager, Programmatic & Data** | 06/2015 - 07/2017
- Led DMP and ML-assisted CRO initiatives for enterprise customers.
- Owned data onboarding, taxonomy design and identity resolution for privacy-safe activation and measurement.
- Coordinated multi-platform product improvements with Engineering, Data and Commercial teams.
- Became a trusted advisor for enterprise clients across full-stack AdTech (ad serving, DSP, tag management, creative production) beyond Adform's own product scope. Clients consulted me on general AdTech decisions because they knew I would not recommend anything unnecessary. Regularly visited agencies to train non-technical teams on programmatic advertising, audience strategy and AdTech tooling.
- Won Employee of the Year award after a client (Twinkey) flew me to Mexico to support their biggest account (Walmart) during Buen Fin (Mexico's Black Friday). Ran ad serving and DSP campaigns, produced creatives and diagnosed a third-party script without a timeout that was degrading site performance. Also joined client meetings with AT&T and other major players. The client brought me back to Guatemala a year later for a similar engagement.
**Various Companies**, Madrid, Spain
**Web Developer and Founder** | 08/2006 - 05/2015
- Built e-commerce platforms, media sites and a live video streaming platform for music festivals. Hands-on with full-stack development, server infrastructure and analytics.
- Founded and grew an independent sports media outlet using SEO and social distribution, managing content, analytics and audience growth.
## **Education and Certifications**
MSc, Complex Problem Solving, Universidad Internacional de La Rioja (UNIR), 2024
MBA, ThePower Business School, 2020
Postgraduate, Product Management, The Hero Camp, 2019
Postgraduate, Web Development and Digital Content, CICE, 2014
Engineer's Degree, Computer Software Technology, Universidad Europea Miguel de Cervantes, 2008

Selected certifications: Google Ad Manager Certified Partner; TensorFlow AI Certification; LinkedIn Learning (AI-first Product Leadership, Advanced Product Marketing, Agile User Stories)
## **Languages**
Spanish (native) | English (advanced) | Catalan (basic)