# Story Bank - Complete Stories (H7-H11) | See stories-3 for H12-H13

## Interface
**Purpose**: Full interview stories with context, hypotheses, decisions, execution, results, and transferable learnings.
**Input requires**: Question or interview context to select relevant stories
**Output produces**: Story selection with adapted framing
**Depends on**: story-bank-frameworks.md for mapping and usage rules
**Standalone?**: NO

---

## H7: Compass, Flowcards and the Marfeel Pivot

**Tags:** #pivot #ai #nlp #llm #0_to_1 #survival #prescriptive_analytics

**One line:** Marfeel's core business was declining in COVID. Pivoted to Compass (prescriptive analytics on Watson NLP) and Flowcards (engagement/conversion with recommender). Company is better than ever today.

### Context
- Company: Marfeel (600+ publishers)
- Moment: COVID. Core business (full mobile site marfeelization) deteriorating.
- Risk: Without pivot, company wouldn't survive medium-term.

### The two products (DISTINCT, don't confuse)

**Compass = Prescriptive analytics on NLP**
- What: Analytical tool for publishers. Told them what to write about.
- NLP layer: IBM Watson classified incoming articles at scale: categories, tone, characters, entities, sentiment.
- Product layer: Dashboard crossing Watson-extracted content signals with engagement and revenue metrics. Prescriptive output: which content attributes correlated with better results.
- My role: Co-designed with ML engineers. Defined which signals to extract from Watson, how to cross with business metrics, what to show publishers.
- Why it matters for AI roles: This is language-model-as-product. The language model was the sensor extracting signals from unstructured content. I defined which signals mattered and what product to build on top. Pattern is identical to current GenAI products (extracting listing attributes, generating descriptions, classifying content), just with previous-generation models.

**Flowcards = Engagement product with recommender**
- What: Scroll-bounded overlays activating when user loses interest, recommending alternative content.
- Origin: I had launched an AMP Next project on desktop as lightweight alternative to JS-heavy infinite scroll. No impact because barely any users reached the end. That limitation revealed the real insight: engage users when they lose interest, not when they finish.
- ML layer: Recommendation engine fed by Watson NLP signals (content features). Evaluation with NDCG for ranking quality, CTR for engagement. Production guardrails. Automated retraining cadence.
- My role: Co-designed recommender with ML engineers (feature selection, evaluation metrics, guardrails). Client testing, instrumentation, iteration.

### Strategic decision
- Pivoting to Flowcards + Compass was the CEO's decision. Not mine.
- My contribution: the seed project (AMP Next revealing the insight), the NLP product (Compass), the recommender co-design (Flowcards), and instrumentation of both.

### Result
- Compass and Flowcards became Marfeel's core products.
- Company not only survived COVID but operates better than ever today.

### Transferable learning
- AI as lever, not goal. The language model is the sensor. What you do with the signals is the product.
- A "small" technical project (AMP Next on desktop) can seed a company pivot if it solves a real problem.
- Evaluating AI models requires product metrics, not model metrics. NDCG and CTR were proxies for engagement and revenue, not academic metrics.
- CAUTION: Don't claim the pivot decision. State your concrete contribution.
- CAUTION: Don't say "Watson was an LLM". It was previous-gen NLP. The pattern is identical, the technology evolved.

### Use for
Working with ML/AI teams, Building products on language models, Success metrics for AI products, Building 0 to 1, Company pivot/adaptability, "Tell me about a product that had outsized impact", "How would you evaluate whether an LLM-powered feature is ready for production?"

---

## H8: Paywalls at LaVanguardia

**Tags:** #trade_offs #experimentation #dual_business

**One line:** Balanced subscriptions and advertising with propensity-based paywalls, without degrading ad RPM.

### Context
- Company: Grupo Godo (LaVanguardia.com)
- Product: Paywall and subscription system

### Real problem
- Dual business: subscriptions and ads. Aggressive paywall kills ads. No paywall, no subscriptions.
- Disagreeing stakeholders: Editorial, Ad Ops, Subscriptions, Business.

### Decision
- Decided: Propensity-based paywalls. Show paywall only when conversion probability justifies losing the ad impression.
- NOT decided: No universal paywall. Did not sacrifice one revenue stream for another.

### Execution
- Unified data layer on first-party data (didn't exist)
- Experimentation framework on top of that data
- Propensity-driven paywalls
- Bundles and guardrails protecting both revenue streams
- Aligned Editorial, Engineering, Data and Ad Ops on shared KPIs

### Result
- +12% registrations without degrading ad RPM.
- Mentored 2 PMs on data and experimentation, creating reusable playbooks.

### Use for
Balancing competing business goals, Trade-offs, Experimentation, Media/subscriptions/monetization roles.

---

## H9: 7-Team Alignment at Gartner

**Tags:** #leadership #stakeholders #conflict #core_system

**One line:** Data, Analytics, Cloud, DevOps, Traffic Quality, ML and Martech. All with own roadmaps. Aligned with weekly meetings, coordinated roadmaps, pipeline-phase documentation, data contracts with clear ownership and automated alerts per broken contract.

### Context
- Company: Gartner Digital Markets
- 7 teams with different, incompatible priorities
- I was PM of the data platform everyone needed but nobody wanted to adjust their roadmap for

### Real problem
- Data wanted coverage. Analytics wanted fast access. Cloud wanted controlled costs. DevOps wanted stability. Traffic Quality wanted precision. ML wanted features and training data. Martech wanted integrations.
- Most visible conflict was with Analytics Director (full story: H13 in stories-3.md).

### Execution

**Alignment mechanisms:**
- Weekly cross-team coordination meetings
- Coordinated roadmaps: not one shared roadmap (impossible with 7 teams) but visibility of cross-dependencies and critical dates
- Ad-hoc documentation per pipeline phase: each team knew what came in, what went out, what was expected

**Data contracts as interface:**
- Schemas and data contracts for each pipeline phase (ingestion, processing, storage, consumption)
- Each contract defined: which fields, what format, what freshness, which owner
- Automated alerts when a contract broke, with clear ownership of who handles the fix
- Converted "your team broke my data" conflicts into "alert X fired, owner of contract Y handles it"

**Concessions:**
- Allowed site development teams to pass their current GA4 payload as-is instead of forcing new schema from day 1. Simplified their implementation but moved validation problem to tracking team. Advantage: data parity in Snowflake within days, enabling fast discovery.
- Sacrificed rollout speed for staged delivery to protect Analytics needs (reporting continuity, parallel validation)
- Accepted some teams consuming data read-only without contributing to quality, because forcing full participation would have blocked everything

### Result
- 7 teams aligned with shared platform and clear data contracts.
- Ownership conflicts converted to automated alerts with assigned responsible.
- Analytics Director went from blocker to active platform user.

### Transferable learning
- Rule: Don't try to align with meetings. Align with contracts and alerts. Meetings resolve what contracts don't cover.
- Rule: In multi-team alignment, concessions matter more than victories. What you sacrifice generates trust.

### Use for
Cross-functional leadership, Conflicting priorities, Influencing without authority, Managing stakeholders, Data governance, Platform adoption.

---

## H10: Privacy, Compliance and Custom CMP at Marfeel

**Tags:** #compliance #scale #stakeholders #build_vs_buy #performance

**One line:** GDPR, consent-aware tracking for 600+ European publishers. All market CMPs were slow, JS-heavy and impossible to optimize for performance. Built a custom one.

### Context
- Company: Marfeel
- European publishers under GDPR. Each with their own CMP, varying consent levels.
- Site performance was critical for business (Core Web Vitals, ad loading speed, SEO).

### Real problem
- All available CMPs were slow, JavaScript-heavy, couldn't precache loading, couldn't skip unnecessary loads in non-GDPR geos.
- In a business where milliseconds affect revenue (ad loading, Core Web Vitals, SEO rankings), a slow CMP destroys value.

### Decision: Build vs Buy
- Evaluated market CMPs. None solved the performance problem.
- Decided: Build custom CMP optimized for performance. Full control over what loads, when and where.
- NOT decided: Did not buy and patch. Integration with a slow CMP would have been worse than no CMP.
- Risks: Maintaining custom CMP is expensive (regulation changes, TCF evolves, audits).

### Execution
- Custom CMP: precache what's needed, skip unnecessary components in non-GDPR geos, native integration with ad loading stack
- Ad Manager and header bidding integration built-in, before market CMPs offered it by default
- Extensive consent rate testing: less consent = fewer demand partners = lower CPMs. Every percentage point of consent had direct revenue impact
- Translations for all major geos plus English default
- Consent-aware data flows, GDPR-compliant taxonomy, data minimization
- Privacy vs monetization strategy with CEO/CTO: consent level directly affects demand mix
- Simultaneously: sellers.json, TCF consent string and other industry changes

### Result
- GDPR compliance across entire network without performance degradation.
- No material monetization loss.
- Full control over consent experience.

### Transferable learning
- Rule: Buy vs build isn't just cost. When the vendor doesn't solve your critical constraint (performance in this case), build is the only real option.
- Rule: Privacy isn't just compliance. In ad-funded businesses, privacy decisions are revenue decisions.

### Use for
Privacy/compliance challenges, Build vs buy decisions, Performance optimization, Regulatory requirements, AdTech roles where performance and compliance intersect.

---
