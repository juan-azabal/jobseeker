# Story Bank - Complete Stories (H12-H13)

## Interface
**Purpose**: Full interview stories for H12 (architecture mistake) and H13 (stakeholder conflict).
**Input requires**: Question or interview context to select relevant stories
**Output produces**: Story selection with adapted framing
**Depends on**: story-bank-frameworks.md for mapping and usage rules
**Standalone?**: NO

---

## H12: Flink Conversion Uploads at Gartner (Architecture Mistake)

**Tags:** #mistake #architecture #PM_discipline #technical_decision

**One line:** Let the team implement conversion uploads to Google/Bing via real-time Flink streaming. It should have been a batch job. The mistake wasn't technical — it was not protecting the time to think properly.

### Context
- Company: Gartner Digital Markets
- Project: Conversion data pipeline to Google Ads and Bing for attribution (part of the broader data platform)
- Moment: Multiple workstreams running simultaneously. Flink was already in the pipeline.

### Real problem
- Architecture decision made by default, not by analysis. Flink was already there, the team was confident, we were moving fast. Nobody stopped to ask whether streaming was actually the right model for conversions.
- Conversions don't need real-time delivery. A batch job reading from the data lake every few hours would have been simpler, fully auditable, and easy to debug.
- Streaming added complexity for zero business value. Debugging attribution discrepancies through a streaming pipeline is hard: no clean way to inspect exactly what was sent, no easy replay, no simple audit trail.

### The contrast
- Earlier in the same project (Snowplow ramp-up, part of H4): had time to go deep. Studied the entire system, became the internal reference, made well-informed architecture decisions.
- For conversion uploads: same person, same project, different conditions. Too many simultaneous workstreams. Didn't protect the research time. Deferred to the team's default.

### Decision
- Decided: Go with Flink streaming because the team recommended it and Flink was already there.
- NOT decided: Did not independently research whether streaming was the right model for this use case.
- Root cause: PM discipline failure, not technical ignorance. Knew how to avoid this. Didn't apply the standard.

### Result
- Pipeline shipped and worked. Attribution data reached Google and Bing.
- Debugging was painful when discrepancies appeared. No clean audit trail. Tracing issues through the streaming pipeline cost significant time.
- The better architecture (batch from data lake) was obvious in retrospect and would have taken similar or less effort to build.

### Transferable learning
- Rule: Understanding the full technical context before committing to an architecture is the PM's job, not optional. When pressure mounts and there are ten competing workstreams, that's exactly when to slow down on irreversible decisions.
- Rule: "The team is confident" and "the technology is already there" are not architecture justifications. They're defaults. Defaults need to be challenged.
- Irreversible architecture decisions have a higher cost of being wrong than the cost of being two weeks slower.

### Use for
"Tell me about a mistake", "Tell me about a time you failed", "What would you do differently?", Roles where technical architecture decision-making is core.

---

## H13: Analytics Director Conflict at Gartner

**Tags:** #conflict #stakeholders #trust #political #influence_without_authority

**One line:** The Analytics Director actively resisted the data platform project. The real issue was threat to his ownership and fear of exposing gaps in his GA4 implementation. Resolved through repeated 1:1 investment outside project meetings. He ended up being one of the strongest advocates.

### Context
- Company: Gartner Digital Markets
- Moment: Early stages of building the first-party data platform to replace GA4.
- Stakeholder: Analytics Director, responsible for the existing GA4 setup, managing analytics reporting for all three brands.

### Real problem
- Surface: Technical disagreement about approach and rollout risk.
- Real: A new platform with proper instrumentation would expose gaps in the GA4 implementation he'd been responsible for. Additional workload concern for his team during migration.
- Behavior: Used his influence to slow the project down — raising risks in steering meetings, flagging concerns in written comms, creating friction in dependencies.

### What I didn't do
- Did not escalate to his manager or mine.
- Did not debate the technical merits in group settings, which would have made it political.
- Did not try to win the argument. Winning arguments with threatened people creates enemies.

### Execution
- Invested in the relationship outside the project context. Multiple coffee conversations, no agenda, just understanding his constraints.
- Made the framing explicit: I'm not here to replace what you built or expose problems. I'm here to give your team better tools to fix gaps you already know about but don't have the means to address.
- Incorporated his concerns directly into the design: staged rollout with parallel validation, clear data ownership boundaries, continuity guarantees for existing reporting.
- Shifted the conversation from "should this exist" to "how do we make this safe."

### Result
- Dynamic changed completely once he saw me as someone who wanted to help rather than a threat.
- His team's domain knowledge of the existing analytics setup was critical for migration decisions — knowledge I wouldn't have had access to if the relationship had stayed adversarial.
- He became an active advocate for the platform.
- Referenced in H9 (7-team alignment): "Analytics Director went from blocker to active platform user."

### Transferable learning
- Rule: Resistance from stakeholders is usually self-protection, not disagreement about the technical merits. Diagnose the real concern before deciding how to engage.
- Rule: Public victories create private enemies. Resolve political conflicts privately.
- Rule: Concessions in design (staged rollout, parallel validation) cost little and buy genuine trust. They're not weakness — they're leverage.

### Use for
"Tell me about a disagreement with a stakeholder", "Influencing without authority", "Managing resistance to change", "Cross-functional alignment", Roles with complex internal stakeholder landscapes.
