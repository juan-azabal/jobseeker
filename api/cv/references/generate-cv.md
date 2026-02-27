# Generate CV

## Interface
**Purpose**: Workflow for generating tailored, ATS-compliant CVs from master-cv.md content.
**Input requires**: Target role context (ideally from ANALYZE mode output), master-cv.md for content, ats-rules.md for format
**Output produces**: .docx CV file ready to submit
**Depends on**: master-cv.md (content), ats-rules.md (format rules)
**Standalone?**: NO

---

## STEP 0: ATS constraints (read before writing a single line)

Hard stops. Violating any of these = broken output, do not deliver.

**Structure:**
- Single column only. Zero tables anywhere (not even for contact info or skills layout).
- Standard headers exactly as written: Summary / Selected Impact / Core Skills / Projects (optional) / Work Experience / Education and Certifications / Languages
- Bullets via proper list formatting (LevelFormat.BULLET in docx-js). Never unicode bullet characters.

**Characters:**
- ASCII hyphen only: -
- No em dash (--), no en dash (-), no arrows (->, =>), no tilde (~)
- No Oxford comma (", and" at end of a list)

**Dates:**
- MM/YYYY - MM/YYYY or MM/YYYY - Present
- ASCII hyphen. Never year-only. Never "Current" or "Now".

**Tab stops for same-line right-aligned text** (e.g. role title + date):
- Use tab stops, not tables. Tables collapse in some renderers.

---

## Workflow

### Step 1: Identify emphasis

If ANALYZE mode was run for this role, use its output:
- CV emphasis areas
- Keywords to include
- Gaps to address or minimize

If no prior analysis, extract from JD:
- Top 3-5 requirements
- Keywords and terminology used
- Seniority signals
- Technical vs strategic balance

### Step 2: Tailor Summary

Rewrite Summary from master-cv.md following ATS rules:
- 3-5 lines, real context not pitch
- At least one non-keyword-optimized phrase
- Include limits/preferences
- Say what NOT looking for
- Mirror JD language where authentic (don't force keywords)

### Step 3: Select and order Impact bullets

From master-cv.md Selected Impact:
- Choose 3-6 bullets most relevant to role
- Reorder by relevance to JD (most relevant first)
- Ensure mix of hard metrics and qualitative results
- Each must answer: problem, decision, consequence
- Adjust language to mirror JD terminology where natural

**PRUNING HARD RULE - Selected Impact:**
Each bullet is 1-2 lines maximum. If a bullet has more than one result or sub-clause, split it or cut the weakest part. The master CV bullets are source material for facts, not copy-paste text. Rewrite every bullet from scratch for the target role. No bullet should contain a narrative arc - that belongs in the interview.

### Step 4: Tailor Core Skills

From master-cv.md Core Skills:
- Reorder blocks by relevance to role
- Within blocks, lead with most relevant items
- Remove blocks that add no value for this specific role
- Add any missing JD keywords that Juan genuinely has
- Format as prose paragraphs grouped by theme, not as a table

**PRUNING HARD RULE - Core Skills:**
Maximum 3 prose lines per thematic block. Cut anything the evaluator will not need to make a yes/no screening decision. Skills that appear in Work Experience bullets do not need to be re-explained here.

### Step 4b: Projects section (conditional)

**Include Projects section when:** the role explicitly values AI/LLM experience, data platform architecture, technical portfolio or hands-on technical PM work. Typical signals: "AI PM", "technical product manager", "data platform", "ML infrastructure", "LLM", "AI governance" in JD.

**Omit Projects section when:** traditional PM role, generalist role, or when project content adds no screening value. In this case, distribute relevant project keywords into Core Skills (Step 4) instead.

When including:
- Select 1-3 projects from master-cv.md Projects based on relevance to JD
- Rewrite each to 2-3 lines maximum: problem, stack, one measurable outcome
- Include repo URL where public
- Order by relevance to role (most relevant first)
- For LLM Control Plane: emphasize governance, multi-tenant policy, guardrails
- For JobAgent: emphasize AI agent architecture, cost optimization, scoring rubric design
- For Claude Skills: emphasize composable system design, failure mode cataloging, meta-architecture

**PRUNING HARD RULE - Projects:**
Same discipline as Work Experience. Result + mechanism only. No narrative arcs. The master CV project descriptions are source material, not copy-paste text.

### Step 5: Tailor Work Experience

From master-cv.md Work Experience:
- Keep all roles (no gaps)
- Within each role, reorder bullets by relevance to JD
- For most relevant roles: 4-5 bullets maximum
- For secondary roles: 2-3 bullets maximum
- For old/less relevant roles (10+ years ago): 1 bullet maximum
- Ensure no cloned bullets between roles
- Check: what was broken, uncomfortable decisions, what changed

**PRUNING HARD RULE - Work Experience (critical):**
This is where verbose CVs fail. Every bullet must be 1-2 lines. The master CV contains full diagnostic narratives (how the problem was found, what was tested, what failed first) - these are interview stories, not CV bullets. For the CV: result + mechanism only. Cut the how. The evaluator needs to know what happened and at what scale, not how you reasoned through it. If a bullet requires more than 2 lines to make its point, it has two points - cut one.

Bullet density by role seniority signal:
- Core/most relevant role: 4-5 bullets, 1-2 lines each
- Supporting relevant role: 3-4 bullets, 1 line each
- Old or tangential role: 1-2 bullets, 1 line each

**Length target: the finished CV must fit in 2 pages.** If it exceeds 2 pages, cut more - do not reduce font size or margins below readable. Cutting is always the right answer.

### Step 6: Education, Certifications, Languages

Copy from master-cv.md. One line each. No changes needed unless role has specific requirements.

### Step 7: Generate .docx

Read /mnt/skills/public/docx/SKILL.md. Then build with these constraints enforced:
- No Table objects anywhere in the document
- All text in Paragraph elements only
- Tab stops for right-aligned dates on same line as role title
- LevelFormat.BULLET for all bullet lists (never unicode characters)
- ASCII hyphen in all dates

### Step 8: Mandatory ATS audit (do not skip, do not deliver without passing)

```bash
pandoc cv.docx -t plain | grep -P "\x{2014}|\x{2013}|\x{2012}|->|=>|~" | wc -l
# must be 0 (em dash, en dash, figure dash, arrows, tilde)

pandoc cv.docx -t plain | grep -c ", and "
# must be 0 (Oxford comma)

pandoc cv.docx -t plain | grep -iE "^(Profile|Highlights|Capabilities|Experience|Skills|About)" | head -5
# must be 0 (non-standard headers)
```

If any check fails: identify the failing lines, fix in source, regenerate, re-run audit. Deliver only after all pass.

### Step 9: Adversarial review

Before delivering:
- Read every line: "Can Juan defend this in a hostile interview?"
- Flag any line that sounds inflated or lacks specific context
- Check for AI telltales (perfect rhythm, cloned bullet structure, aspirational language without friction)
- Verify imperfect bullet rhythm (bullets should differ in length and structure)
- **Compression check:** Count lines per bullet across all Work Experience. Any bullet exceeding 2 lines = cut or split. Any role with 6+ bullets = cut to 5 maximum. If total CV exceeds 2 pages = cut more before delivering. The master CV is a source of facts, not a template to reproduce.

## Output

Deliver .docx file via present_files. Accompany with:
- Brief note on key tailoring decisions (what was emphasized, what was reordered)
- Whether Projects section was included or omitted, and why
- Any flags (lines that might get challenged, gaps visible in CV)
- ATS audit results (confirm 0 violations)
- Do NOT write extensive explanation of the document
