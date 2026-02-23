# Master CV - Juan Azabal

## Interface
**Purpose**: Detailed work experience by role. Used for CV generation.
**Input requires**: none
**Output produces**: experience, skills, impact bullets, education
**Standalone?**: YES

---

## Work Experience

### Gartner Digital Markets, Barcelona, Spain
Senior Product Manager, Data Platform (Tracking & Analytics) | 07/2024 - Present

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

### Grupo Godo (LaVanguardia.com), Barcelona, Spain
Senior Product Manager | 07/2022 - 07/2024

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

### Marfeel, Barcelona, Spain
Senior Product Manager | 09/2018 - 07/2022

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
- Co-designed and productionized the recommendation engine within Flowcards (scroll-bounded engagement and conversion overlays): feature selection from NLP signals, NDCG/CTR evaluation, production guardrails and automated retraining pipeline. Flowcards evolved from an earlier project I led using AMP Next on desktop as a lightweight alternative to JS-heavy infinite scroll. That project had no impact because barely any users scrolled to the end, which revealed the real insight: you need to engage users when they lose interest in the current article, not when they finish it. My role in Flowcards included the recommendation engine co-design, client testing, instrumentation and iteration.
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

### Softonic, Barcelona, Spain
Product Manager | 07/2017 - 09/2018

- Audited existing tracking and instrumentation by analyzing raw data and network requests. Found that live impression data from the ad server was not reaching GA4 correctly and header bidding bid data was not being captured at all. Rebuilt the measurement foundation before optimizing revenue.
- Led the shift to a SaaS-like monetization model with packaging and tiering that increased total revenue by 25%.
- Launched premium formats and growth products that increased ARPPU by 50%.
- Discovered that the analytics team was using standard A/B testing for changes that affected how advertisers bid on positions, which contaminated the control group and invalidated results. Changed the experimentation framework to geo-based testing for these cases and built dashboards in GA4 combining ad revenue with web analytics to simplify and speed up product testing.
- Worked with Engineering and Commercial teams to standardize KPI-driven optimization cycles.

### Adform, Madrid, Spain
Associate Product Manager, Programmatic & Data | 06/2015 - 07/2017

- Led DMP and ML-assisted CRO initiatives for enterprise customers.
- Owned data onboarding, taxonomy design and identity resolution for privacy-safe activation and measurement.
- Coordinated multi-platform product improvements with Engineering, Data and Commercial teams.
- Became a trusted advisor for enterprise clients across full-stack AdTech (ad serving, DSP, tag management, creative production) beyond Adform's own product scope. Clients consulted me on general AdTech decisions because they knew I would not recommend anything unnecessary. Regularly visited agencies to train non-technical teams on programmatic advertising, audience strategy and AdTech tooling.
- Won Employee of the Year award after a client (Twinkey) flew me to Mexico to support their biggest account (Walmart) during Buen Fin (Mexico's Black Friday). Ran ad serving and DSP campaigns, produced creatives and diagnosed a third-party script without a timeout that was degrading site performance. Also joined client meetings with AT&T and other major players. The client brought me back to Guatemala a year later for a similar engagement.

### Various Companies, Madrid, Spain
Web Developer and Founder | 08/2006 - 05/2015

- Built e-commerce platforms, media sites and a live video streaming platform for music festivals. Hands-on with full-stack development, server infrastructure and analytics.
- Founded and grew an independent sports media outlet using SEO and social distribution, managing content, analytics and audience growth.
