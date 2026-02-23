# Story Bank - Complete Stories (H1-H11)

## Interface
**Purpose**: Full interview stories with context, hypotheses, decisions, execution, results, and transferable learnings.
**Input requires**: Question or interview context to select relevant stories
**Output produces**: Story selection with adapted framing
**Depends on**: story-bank-frameworks.md for mapping and usage rules
**Standalone?**: NO

---

## H1: Ad Loading at Marfeel (pos 2 > pos 1)

**Tags:** #high_impact #technical #ambiguity #innovation

**One line:** Position 2 had more impressions than position 1. Investigated until finding the sequential algorithm was broken, redesigned the critical path and invented header bidding in web worker. ~40% ARPU lift.

### Context
- Company: Marfeel (ad monetization platform, 600+ publishers)
- Product: Ad wrapper SDK and ad loading system
- Moment: Early in role, reviewing performance data

### Real problem
- Broken: Second ad position had more impressions than the first. Impossible in sequential loading.
- Systemic: Affected all publishers. The loading algorithm had never been questioned.
- Inaction cost: Permanently suboptimal revenue. Nobody had detected it.

### Causal hypotheses
- H1: Timeout too high on pos 1 (discarded: reduced timeout, no improvement)
- H2: Variable network latency (investigated: pulled speed percentiles from Ad Manager, emulated devices and speeds)
- H3 (root cause): Sequential algorithm loaded pos 2 before pos 1 in many cases. Ads blocked each other and content. No loading priority rules existed.

### Decision
- Decided: Redesign the complete critical rendering path. Create prioritization rules. Move header bidding to web worker.
- NOT decided: Did not patch existing algorithm. Replaced it.
- Risks: Deep change to product core. Possible regression for publishers "working fine" with broken system.

### Execution
- Critical rendering path defined with clear priority rules
- Multiple controlled tests
- Header bidding in web worker to unblock main thread (cutting-edge in 2019-2020)

### Result
- ~40% ad ARPU increase. Total revenue grew even more from technical SEO improvement (less render blocking = better Core Web Vitals = more traffic).
- Organizational: hired dedicated technical SEO specialist, built proprietary CDN for publishers, manager promoted to Chief Monetization Officer.
- Negative externalities: higher loading system complexity, larger test surface.

### Transferable learning
- Rule: When data doesn't add up, the problem isn't the data. It's the system generating it.
- Alert signals: Metrics violating basic system laws (pos 2 > pos 1) always indicate something deep.

### Use for
Complex technical problem, Innovation, Working with engineering, Second-order effects, Biggest impact, Any AdTech or monetization role.

---

## H2: Video Revenue at LaVanguardia

**Tags:** #high_impact #data #speed #process

**One line:** Detected Ad Manager anomaly, classified errors, killed broken campaigns (80% of improvement in 3 days) and created prevention protocol.

### Context
- Company: Grupo Godo (LaVanguardia.com)
- Product: Video advertising
- Moment: Reviewing video performance data

### Real problem
- Broken: Video revenue and impressions too low for site traffic. Nobody had investigated.
- Systemic: Campaigns with errors generating incorrect data and revenue loss. No detection protocol.

### Decision
- Decided: Stop problematic campaigns immediately. Pareto: identify the most damaging ones.
- NOT decided: Did not wait for complete solution. Acted on what we knew.
- Risks: Stopping active campaigns can upset clients/Ad Ops.

### Execution
- Raw Ad Manager analysis
- Error classification by type and severity
- Stopped broken campaigns (80% of improvement)
- Detection protocol: what to check, what to request from clients, how to test, how to respond when something breaks

### Result
- 70% video revenue growth, 20% more pages per visit, 25% faster load times.
- Time: 3 days from detection to main action.

### Transferable learning
- Rule: Act first on what gives 80% of the result. Protocol after.

### Use for
Data-driven decision, Biggest impact, How do you prioritize (Pareto), Moving fast, How do you approach a new problem.

---

## H3: MCM Migration at Marfeel (800 publishers, 1 month)

**Tags:** #scale #time_pressure #process #stakeholders

**One line:** Google forced MCM. Migrated 800 publishers in one month with minimal revenue loss, building custom Apps Script tooling.

### Context
- Company: Marfeel
- Product: Publisher network (800 publishers)
- Moment: Google imposes MCM with deadline. Networks that don't migrate lose access.

### Real problem
- External change forced by Google. 800 publishers depended on our network. No migration = no revenue for everyone.
- Reference: other networks took 3-6 months and lost 10-30% of revenue.

### Decision
- Decided: Do it in one month. Build custom tooling for real-time monitoring. Segment by tiers.
- NOT decided: Did not wait for Google's tools. Did not treat all publishers equally.

### Execution
- Defined requirements for Apps Script tooling + Ad Manager API. Reviewed code and iterated with junior dev until it tracked migration status per client in real time.
- Publisher segmentation by revenue tier
- Automated communications by tier via Customer Support
- Simultaneously: sellers.json, TCF consent string and other industry changes
- Later: Apps Script tooling reused for quick dashboards of metrics not in Looker

### Result
- 800 publishers migrated in ~1 month, minimal revenue loss.
- Tooling reused for quick dashboarding.

### Transferable learning
- Rule: Facing external deadline, build your own visibility. Don't wait for tools to be provided.

### Use for
Executing under pressure/deadline, Operating at scale, Competing priorities, Building tools/processes, Working with stakeholders.

---

## H4: Data Platform at Gartner (replacing GA4)

**Tags:** #high_impact #technical #ambiguity #core_system #stakeholders

**One line:** Built first-party data platform replacing GA4 for three marketplace brands. Lakehouse architecture. Zero data loss. 7 teams aligned.

### Context
- Company: Gartner Digital Markets (Capterra, GetApp, Software Advice)
- Product: Data platform (tracking, analytics, experimentation)
- Moment: GA4 as source of truth. No control over data, no real experimentation.

### Real problem
- GA4 not first-party. No data control. Three brands with different needs, no common platform.
- Everything dependent on data (CRO, personalization, ML, attribution, bidding) was limited.

### Decision
- Decided: Replace GA4 with own pipeline. Snowplow > Kafka > Flink > S3 > Snowflake. Edge and client-side collection.
- NOT decided: Did not build own warehouse. Used Snowflake as query engine over S3 (lakehouse).
- Risks: Replacing source of truth for three brands. Complex coexistence period.

### Execution
- Became internal Snowplow reference ahead of Tech Lead and EM
- Studied Snowplow dbt package documentation in depth, specified configuration
- Designed data model: entities, relationships, keys, dependencies
- Documented with ER diagrams and data flow diagrams
- Defined data contracts, SLIs/SLOs (freshness, loss, latency). Datadog for observability
- Aligned 7 teams with independent roadmaps (Data, Analytics, Cloud, DevOps, Traffic Quality, ML, Martech)
- Led adoption: SDK versioning, release channels, migration runbooks

### Result
- Data loss to effectively zero. Real-time pipeline for experimentation, CRO, personalization, ML.
- Conversion uploaders for Google/Bing improving attribution.

### Transferable learning
- Rule: Platform decisions are justified by the use cases they unlock, not by the technology.

### Use for
Building from scratch, Ambiguity, Cross-functional alignment (7 teams), Platform vs feature decisions, Data quality/governance, Data architecture.

---

## H6: Instrumentation at Softonic

**Tags:** #diagnosis #data #pattern #experimentation

**One line:** Found ad server impressions and header bidding bids weren't reaching GA4 correctly, and the analytics team was using A/B testing for changes that affected advertiser bidding, invalidating tests. Fixed instrumentation, changed to geo-based testing, built combined dashboards.

### Context
- Company: Softonic
- Moment: Start of role

### Real problem
- Instrumentation: Live ad server impression data not reaching GA4 correctly. Header bidding bids not being captured at all. Nobody had checked.
- Experimentation: Analytics team using standard A/B testing for changes affecting advertiser bidding, contaminating control group. Tests were invalid and nobody knew.

### Execution
- Fixed instrumentation: ad server impressions and header bidding bids reaching GA4 correctly.
- Changed experimentation framework: tests affecting advertiser bidding done in specific geos instead of standard A/B, avoiding contamination.
- Built testing dashboards in GA4 combining ad revenue with web analytics.

### Result
- With reliable data and correct testing framework: SaaS packaging lifted revenue 25%, premium formats lifted ARPPU 50%.

### Transferable learning
- Rule: Before optimizing, validate that measurement is correct AND that the experimentation framework is valid for what you're measuring.
- Alert: When a product change affects demand (how advertisers bid), classic A/B testing doesn't work because B is not independent of A.

### Use for
Inheriting a messy situation, Why is data quality important, Experimentation methodology (geo testing vs A/B), How do you approach a new role, AdTech roles.

---

