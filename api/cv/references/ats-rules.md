# ATS Rules

## Interface
**Purpose**: Complete ATS compliance rules for CV generation. Applies to every CV produced.
**Input requires**: CV content ready for formatting
**Output produces**: ATS-compliant .docx CV
**Standalone?**: YES

---

## Objective

Generate CVs that:
- Pass ATS filters (including Workday, Greenhouse, Lever).
- Are readable and credible for senior hiring managers.
- Show no clear AI telltales.
- Resist hostile line-by-line review.

Priority: clarity > credibility > ATS optimization.

## Base ATS Principles (non-negotiable)

- Single column.
- No tables, text boxes, icons, graphics or multiple columns.
- All content in main document flow.
- Recommended format: simple .docx.
- PDF only if real text and portal explicitly accepts it.

## Headers (mandatory and ATS-safe)

Use only these headers, exactly as written:
- Summary
- Selected Impact
- Core Skills
- Projects (optional, see below)
- Work Experience
- Education and Certifications
- Languages

Projects header inclusion rule:
- INCLUDE for roles where AI, LLM, data platform or technical portfolio is a key signal (AI PM, data platform, technical PM, ML infrastructure roles).
- OMIT for traditional PM roles, generalist roles or when Projects content adds no screening value. In this case, distribute relevant project keywords into Core Skills instead.

Prohibited: creative headers, semantic variants (Profile, Highlights, Capabilities, etc.).

Format: H1/H2/H3 in Markdown or Word equivalent. Same size or slightly larger than body. Simple bold allowed. No underline, dividers, boxes.

## Character and Symbol Rules (hard)

PROHIBITED everywhere in the CV:
- Em dash (---)
- En dash (--)
- Arrows (->, =>, <-, ->)
- Tilde (~)
- Non-ASCII decorative bullets

Rules:
- Use only ASCII hyphen: -
- Parentheses allowed: ( )
- Symbols allowed sparingly: %, &

Mandatory check: search and replace ---, --, ->, ~. Copy entire CV to plain text and review visually.

## Dates (single format)

Mandatory format:
- MM/YYYY - MM/YYYY
- MM/YYYY - Present

Rules: ASCII hyphen only. Never year-only. Never mix formats. Never use "Current" or "Now".

## Anti-AI Principles (hard rules)

Prohibited:
- Oxford comma.
- Perfect rhythm in bullets.
- Identical length between phrases.
- Repeated round metrics without context.
- Empty aspirational language.

AI CV telltales to avoid:
- Generic openings like "Experienced professional with...".
- Series of verbs without real friction.
- Continuous success without trade-offs.
- Round section closings.

## Summary (3-5 lines)

Rules:
- Real context, not pitch.
- At least one phrase not optimized for keywords.
- Include explicit limits or preferences.
- Also say what you are NOT looking for.

## Selected Impact (3-6 bullets)

Rules:
- Mix hard metrics and qualitative results.
- Not all bullets with percentages.
- Each line must answer: problem, decision, consequence.

Valid patterns:
- Problem -> action -> result.
- Action -> trade-off -> impact.

## Core Skills

Rules:
- Group by thematic blocks.
- 2-3 bullets per block.
- Concrete, technical language.

## Projects (when included)

Rules:
- 1-3 projects maximum.
- Each project: 2-3 lines. Problem it solves, stack, one measurable outcome or decision.
- No narrative arcs. Result + mechanism only, same as Work Experience bullets.
- Include repo URL where public. No mention of private/public status.
- Sub-headers (### Project Name) are acceptable within the Projects section.

## Work Experience

Fixed format per role:
Company, City, Country
Role | MM/YYYY - MM/YYYY

Content rules:
- What was broken or missing.
- Uncomfortable decisions or discards.
- What changed after.
- Avoid cloned bullets between roles.

## Recommended Language

Prefer: concrete verbs (replaced, removed, constrained, limited), real nouns (pipeline, SDK, contracts, paywall rules).

Avoid: empowered, innovative, scalable solutions, "end-to-end ownership" without context.

## Education and Certifications

One line per degree. No storytelling. Detail goes in experience.

## Languages

One line per language. Clear, simple level.

## Final Checklist (mandatory)

Before sending:
- Single column.
- Exact standard headers.
- Consistent dates with ASCII hyphen.
- No ---, --, ->, ~.
- No Oxford comma.
- Imperfect rhythm in bullets.
- Contextualized metrics.
- Plain text copy reviewed.
- Every line defensible in interview.

## Golden Rule

A human CV does not try to impress. It tries to withstand hostile questions.
