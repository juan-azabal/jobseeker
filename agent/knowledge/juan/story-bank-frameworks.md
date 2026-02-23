# Story Bank - Frameworks & Quick Reference

## Interface
**Purpose**: Interview preparation frameworks, universal answers, question-to-story mapping, failure modes. Use with story-bank-stories.md for full story content.
**Input requires**: Role context or specific interview questions
**Output produces**: Selected stories, adapted answers, preparation plan
**Standalone?**: NO (needs story-bank-stories.md for full story content)

---

## Usage Rules

1. Don't tell the full story. Select axis based on question.
2. Go deep only on the relevant segment.
3. Causal language, not narrative. "Because X, I decided Y" > "And then we did Y".
4. Expose trade-offs before actions.
5. Never say "it was easy" or "trivial". State what you did and the result. If they ask timeline, then say how long.
6. Don't say "I'm better than my devs". Say "my way of working is understanding the complete system before prioritizing it".
7. Max 2 minutes per story. If they want more, they'll ask.

## The Cross-Cutting Pattern

All stories follow the same pattern:
1. Arrive and look at raw data
2. Something doesn't add up
3. Investigate to root cause (code, network, algorithm, config)
4. Act fast on what gives 80% of the result
5. Build system/protocol so it doesn't happen again
6. Iterate on that base to create broader capabilities

If unsure which story to tell, describe the pattern and use the best-fitting example.

---

# PART 1: UNIVERSAL QUESTIONS (Tier 1)

## Tell me about yourself (75-90s)

TMAY es una narrativa de convergencia, no un speech fijo. Cada entrevista requiere una version diferente. Requiere ANALYZE primero — si no hay JD, pedirla.

**Protocolo (3 pasos antes de cada entrevista):**
1. Del analisis: los 2 skills con mas peso en el rol + el problema central que la empresa resuelve + algo especifico de empresa/equipo que solo alguien que investigo sabria
2. Para cada skill, el hito (H1-H13) con metrica mas fuerte. Max 2 hitos en el core.
3. Closing: "Lo que me trae aqui es [problema que ellos resuelven] — algo en lo que llevo [X anos] trabajando. Y especificamente [empresa] porque [razon concreta]." Si no se puede rellenar con datos reales, señalar que falta investigacion.

**Estructura:**
- Apertura (10s): "Soy Senior PM con background de ingenieria, mas de una decada en [AdTech / data platforms / monetizacion / ML products segun rol]."
- Core (50-55s): Bloque 1 — patron invariable: "Tengo un patron consistente: llego a sitios donde los datos estan rotos o no existen. En cada empresa he auditado lo que habia, detectado que la instrumentacion no era fiable, y reconstruido la base de medicion antes de optimizar nada encima." Bloque 2+3 — 2 hitos del story bank mapeados a los skills prioritarios del rol. Formato: contexto minimo + accion + metrica + contraste vs. industria.
- Closing (20-25s): Generado segun paso 3. Nunca generico. Terminar con nombre de empresa y razon especifica.

**Closings fallback (sin JD):** Data platform: "Quiero que la plataforma de datos IS el producto. [Empresa] esta construyendo eso con [tech especifico]." | AdTech: "He trabajado en ambos lados del stack — quiero combinar eso en productos de optimizacion. [Empresa] tiene los datos para hacerlo a escala." | AI/ML: "He construido las bases que alimentan ML. Quiero ser dueno de lo que vive encima. [Empresa] tiene el momento." | Generalista: "Busco entorno product-led con complejidad tecnica real. Lo que veo en [empresa] es [razon especifica]."

**Reglas:** No leer el core — el patron esta internalizado. Preparar 2-3 versiones del closing. Si interrumpen, dejar de hablar. Failure mode: "He tenido un camino bastante variado..." = core no preparado. Al terminar ANALYZE, ofrecer boton "Generar TMAY para este rol" automaticamente.

## Why are you leaving Gartner? (Tier 1)

"Gartner Digital Markets, which includes Capterra, GetApp and Software Advice, has been sold to G2. The deal was announced in January 2026 and is expected to close in Q1. With the acquisition, the future of the team, the platform and the roadmap is uncertain. I'd rather be proactive about my next move than wait for a reorg to decide for me."

If asked more:
- "The platform I built is solid and in production. I'm proud of what we shipped. But the strategic context has changed and I want to be somewhere where what I build has a clear long-term home."
- Never badmouth Gartner or G2.

If asked about staying at G2:
- If offered: "I'm evaluating options but I want to be intentional about what's next rather than defaulting to whatever lands."
- If not offered: "The transition is still in progress. I decided to start exploring now rather than waiting."

## How do you prioritize? (45-60s)

"I prioritize by starting with outcomes, not ideas.

First, I make sure we're aligned on what we're trying to move and why now. One primary outcome and a small set of guardrails. If that's unclear, prioritization is just noise.

Then I look for the real bottleneck in the system, where progress is constrained today, and prioritize work that removes or relaxes that constraint instead of optimizing locally.

I factor in confidence next: when evidence is weak, I bias toward learning before building through instrumentation, experiments, or small pilots.

Finally, I consider delivery risk and long-term compounding value, preferring options that reduce future cost or unlock reusable capabilities.

In practice, that means high-impact work moves first, risky bets are staged, and low-impact work only ships if it unblocks something bigger."

For examples: H2 (video) for Pareto, H1 (ad loading) for bottleneck, H4 (Gartner) for compounding value.

Full logic if they ask to develop:
1. Outcomes: what to move, why now. KPI tree with primary metric and guardrails.
2. Bottleneck impact: where is the real constraint. Prioritize what relaxes the bottleneck.
3. Confidence: when evidence is weak, learn before building.
4. Cost and dependencies: map effort and cross-team dependencies. If fragile, staged delivery.
5. Compounding value: between similar options, choose what creates reusable capability.

## A mistake you made

Use H12 (Flink architecture) as the primary answer — stronger lesson, more interesting technically, and the self-awareness angle lands well.

Key delivery points (H12): Let the team default to Flink streaming for conversion uploads. Conversions don't need real-time. Batch from data lake would have been simpler, auditable, debuggable. The contrast: did Snowplow right (protected research time, became internal reference). Did Flink wrong (too many workstreams, deferred to team default). Lesson: PM discipline, not technical ignorance — irreversible architecture decisions require protected thinking time regardless of pressure.

**Alternative — Organizational (governance/data contracts):** CRO team needed Snowflake data, fast path was PowerBI bridge, governance blocked it, CRO waited 3 months. Lesson: in enterprise environments, map the governance path before scoping delivery. Use this if the role has heavy organizational complexity or the Flink story has already appeared in the same interview. No H number — standalone answer.

## A disagreement or conflict

Full story: H13 (Analytics Director at Gartner).

Key points for delivery: Real issue was threat to ownership + fear of exposing GA4 gaps, not technical disagreement. Resolved 1:1 outside project meetings, not by escalating or winning the argument. Incorporated his concerns into design (staged rollout, parallel validation, ownership clarity). Shifted the conversation from "should this exist" to "how do we make this safe." He became the strongest advocate.

If follow-up invites depth: full narrative in H13. If already used H9 in the same interview (7-team alignment), move to H8 (paywalls, editorial vs. ads vs. subscriptions) to avoid repeating the Gartner context.

## Valuable feedback you received

"Early in a senior role, I received direct feedback that my communication was sometimes too technical for executive audiences.

The issue wasn't accuracy. It was that I was leading with details instead of decisions, which slowed alignment and increased back-and-forth.

I changed my approach to decision-first communication: I start with the problem we're solving, lay out the real options, make a clear recommendation, and call out risks and guardrails explicitly. I only go deep on details if they're needed to support the decision.

The impact was faster decisions, fewer clarification cycles, and stronger trust from leadership."

---

# PART 2: COMMON QUESTIONS (Tier 2)

## How do you make decisions with incomplete data?
Separate reversible from irreversible bets. Use proxies and cohorts. Document assumptions. Pair each decision with measurement improvement. Example: H2 - stopped campaigns without knowing exact cause because cost of waiting > risk of stopping.

## A project you killed or said no to
"I don't typically kill work. I evolve it." Three examples: timeout reduction -> ad speed optimization (H1), CEO-killed analytics -> Compass (H7), AMP Next failure -> Flowcards (H7). If pressed: "My instinct is to find what's salvageable and redirect it."

## Mentoring / developing people
LaVanguardia: 2 PMs in Ads proposing features reactively. Taught data-first: detect patterns, dig to root cause, evolve. Marfeel: fundamentals, how AdTech works, never trust instrumentation at face value.

## Go-to-market / launching products
"Iterative, not event-driven. Test with early adopters, roll out in phases, announce with real production data." H3 (MCM) as example. If role has strong GTM: "My strength is proving value with data before scaling. Less experienced in sales-led launches."

## What kind of company do you thrive in?
Product-led, real complexity, clarity of thinking > rigid process.

## Influence without authority
Shared metrics, written decisions, visible trade-offs. H9 (7 teams at Gartner).

## How technical are you?
"Started as developer, moved away deliberately for architecture and decision-making. Still read docs, review code, inspect network, design data models. With AI, execution gap closed: prototype tooling, queries, scripts when speed > delegation. Differentiator: knowing where to look and what's broken."

---

# PART 4: QUICK MAPPING

| Question | Primary | Alternative |
|---|---|---|
| Tell me about yourself | Cross-cutting pattern + H4 or H1 | - |
| Biggest impact | H1 (ad loading, 40% ARPU) | H2 (video, 70%) |
| Data-driven decision | H2 (video, Ad Manager data) | H1 (pos 2 > pos 1) |
| Technical challenge | H1 (web worker header bidding) | H4 (data platform) |
| Moved fast / under pressure | H3 (MCM, 800 publishers, 1 month) | H2 (video, 3 days) |
| Built from scratch | H4 (data platform Gartner) | H7 (Compass) |
| Ambiguity | H4 (Gartner, no reference) | H6 (Softonic, unreliable data) |
| Cross-functional | H9 (7 teams) | H3 (MCM, CS+eng+publishers) |
| Trade-offs | H8 (paywalls, subs vs ads) | H9 (7 teams, priorities) |
| Innovation | H1 (header bidding web worker) | H7 (Compass NLP analytics) |
| AI/ML | H7 (Compass NLP + Flowcards recommender) | H5 (Snowplow/data for ML) |
| Scale | H3 (800 publishers) | H10 (600+ publishers) |
| Ramp-up / learning | H4 (Snowplow detail in execution) | H6 (Softonic, new role) |
| How technical are you | Tier 2 answer + H1 (network) | H4 (full stack ramp-up) |
| Privacy/compliance | H10 (GDPR, CMP) | H3 (sellers.json, TCF) |
| Stakeholder conflict | H13 (Analytics Director) | H8 (editorial vs ads vs subs) |
| Process/operations | H3 (MCM migration) | H2 (video protocol) |
| Tools you built | H3 (Apps Script spec+iterate) | H4 (data model, ER diagrams) |
| Mistake | H12 (Flink, architecture) | Governance/data contracts (Tier 1 standalone) |
| Disagreement | H13 (Analytics Director) | H8 (disagreeing stakeholders) |
| Feedback received | Tier 1 answer (too technical) | - |
| Prioritization | Tier 1 framework + H2 (Pareto) | H1 (bottleneck) |
| Incomplete data | H2 (act before knowing everything) | H1 (discard hypotheses) |
| Influence without authority | H9 (7 teams) | H3 (MCM, CS+publishers) |
| Build vs buy | H10 (CMP propio Marfeel) | H4 (Snowplow vs GA4) |
| Kill decision / saying no | Tier 2 (evolve not kill) + H7 | - |
| Mentoring / developing people | Tier 2 (Godo + Marfeel) | H8 (reusable playbooks) |
| Go-to-market / launch | Tier 2 (iterative GTM) + H3 | H10 (CMP rollout) |

---

# PART 5: INTERVIEW FAILURE MODES

## FAILURE MODE 1: Diagnosing too early

**What happens:** They give context about their product/roadmap. Your instinct is to analyze immediately and say what's wrong. Lost at least two processes this way.

**What the evaluator hears:** "This guy will question everything from day 1. Won't row."

**What you wanted to communicate:** "I see deeper than most. I can contribute strategic direction, not just execution."

**The fix is sequence, not containment:**
1. Show you understand their direction and why. "I can see why you're going this direction given X and Y."
2. Show you can execute within it. "I'd approach execution by..."
3. Only then, offer alternative vision as exploration. "One thing I'd want to explore once I'm deeper in the business is whether..."

**Template for live business cases:**
- When presented a roadmap: FIRST ask reasoning, SECOND show execution, THIRD plant diagnosis as experiment.
- When asked if they should do X: NEVER "No, that's wrong because...". ALWAYS "My instinct from the market is [real opinion]. But I could be wrong. What signals are you seeing?"

**Red flags to detect it happening:** urgency to correct something they said, about to say "Actually...", wanting to show you see what they don't.

## FAILURE MODE 2: Compressing stories

**What happens:** Describe in 30 seconds something that deserves 2 minutes. Evaluator has no context to know it's exceptional.

**Why it happens:** Everything feels normal to you. Impostor syndrome calibrated low.

**The fix: never give the result without contrast.**
- "Most ad networks took 3-6 months for MCM migration and lost 10-30% of revenue. I did 800 publishers in one month with minimal loss."
- "I joined without having written SQL in 20 years. Within months I was the Snowplow reference for the entire organization, ahead of the engineering team."
- "The industry standard was header bidding on the main thread, which blocked rendering. We moved it to a web worker, which was genuinely novel at the time."

Not bragging. Giving context. Without contrast, the evaluator assigns average value.

---

# PART 7: CHEATSHEET

Trigger: "generate cheatsheet", "cheat sheet". Requires ANALYZE state or prep doc.
Output: .docx 2p A4, Google Docs style (white, Calibri). English by default.

P1: Header + TMAY (NOW/PAST/WHY, trigger words) + Quick Anchors + Q1 (5-6 beats)
P2: Q2 (5-6 beats) + Story Map table + Questions to Ask (3 bold + 2 dim) + FM + footer italic

Quick Anchors: "Why leaving" (2 bullets) + "Why here" (2 bullets) + 1 likely technical Q (3 bullets)
Story Map: 2-col table · left=question type · right=H# bold blue + key metric · 7 rows max
Beats: 1-2=context grey · 3=problem bold · 4-5=execution · 6=result green + lesson red (mistake)
Design: titles bold blue #1155CC + bottom border · UPPERCASE sublabels dim · spacing only · no colored bg
Questions from ANALYZE, never generic · FM: 4 from PART 4, FM# red bold + fix dim
