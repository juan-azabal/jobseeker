# Phase 6 — CV Output Quality: formatting, plan-driven generation, programmatic validation

> **Execute. Do not plan.** If you enter plan mode, call ExitPlanMode immediately.
> If any step is ambiguous, STOP and ask. Do not assume.

## Context

### Goal

The Phase 5 CV generation pipeline works end-to-end but produces inferior output compared to the career-helper skill. Phase 6 closes the gap on three layers:
1. **Formatting** — docx_builder rewrite to match skill-quality visual output
2. **Content intelligence** — deterministic CV plan built from scored data, so the LLM writes instead of analyzing
3. **Validation** — programmatic checks catch source fidelity errors before the .docx is built

### Architecture: why plan-driven generation

The current pipeline sends the LLM everything (4 reference files + JD + scores) and asks it to analyze, select, AND write simultaneously. The skill produces better output because it separates analysis from writing in a 9-step workflow.

The key insight: **the scoring pipeline (JobAgent) already performs 70% of the analysis**. Every ingested job has `parsed` and `rag_score` containing:

```json
{
  "parsed": {
    "seniority": "mid",
    "location_type": "onsite",
    "locations_mentioned": ["Paris, FR"],
    "must_have_skills": ["SQL", "Python", "data product experience"],
    "nice_to_have_skills": [...],
    "technical_stack": ["SQL", "Python", "R"],
    "domain": "data",
    "responsibilities_summary": "..."
  },
  "rag_score": {
    "score": 72,
    "score_breakdown": {"domain_fit": 20, "seniority_fit": 15, "technical_depth": 18, ...},
    "strengths": [{"claim": "...", "evidence": "..."}],
    "gaps": [{"gap": "...", "severity": "medium", "mitigation": "..."}],
    "talking_points": [...],
    "stories_to_prepare": [...]
  }
}
```

Throwing this away and asking the LLM to re-analyze the JD is wasted cost and wasted quality. Instead:

```
Scored data (already paid for)
        ↓
CV Plan Builder (deterministic, no LLM, instant)
        ↓
CV plan JSON (what to emphasize, bullet budget, context signals)
        ↓
LLM call (writes CV following the plan + chain-of-thought for judgment calls)
        ↓
CV Validator (deterministic, no LLM, catches source fidelity errors)
        ↓
Optional fix call (LLM, cheap, targeted — only if validator fails)
        ↓
docx_builder → .docx
```

The scorer call is cheap and runs for ALL jobs. The CV generation call is expensive and runs only when the user clicks "Generate CV". Maximizing what we extract from the cheap call is pure arbitrage: better quality for the same total cost.

### Problem evidence (from real test: WeFiiT Data PM role)

**docx_builder problems (Layer 1):**
- All 57 paragraphs use style "Normal" — no style differentiation
- 40/57 paragraphs are ALL BOLD — body text, bullets, everything
- 0/57 paragraphs have bullet numbering — bullets rendered as plain paragraphs
- 0/57 paragraphs have italics — no role context lines
- No tab stops — dates not right-aligned
- No font size variation — name, headers, body all same size

**Remaining formatting issues (discovered in v3 iteration):**
- Bullets use "List Bullet" style (visual bullets) but lack `<w:numPr>` in XML. ATS parsers (Workday, Greenhouse, Lever) read numPr, not style names. Must use "List Paragraph" style with explicit numPr.
- Font sizes 1pt inflated vs spec: body 11pt (should be 10pt), headers 12pt (should be 11pt), name 20pt (should be 18pt). Extra point in body can push a 2-page CV to 3 pages.

**LLM content problems (Layer 2):**
- Title downgraded from "Senior Product Manager" to "Product Manager"
- Years of experience downgraded from "10+" to "7+"
- No reframing for consulting context (WeFiiT is a consultancy)
- Core Skills collapsed from 5 themes to 3 (lost Governance/Privacy and Technical)
- Missing differentiating bullets (Snowplow reference, CMP, Walmart client work)
- French language omitted despite Paris-based role
- AI slop in Summary: "Strong track record", "drive measurable business impact"
- All languages from reference material not included

### Target: skill-generated CV formatting spec

```
ELEMENT                  | FONT SIZE | BOLD | ITALIC | COLOR   | SPACING (twips)      | SPECIAL
─────────────────────────┼───────────┼──────┼────────┼─────────┼──────────────────────┼─────────────────
Name (# heading)         | 18pt      | Yes  | No     | #1F4E79 | after: 60            |
Title line               | 11pt      | No   | No     | #444444 | after: 80            |
Contact line             | 9pt       | No   | No     | #555555 | after: 200           |
Section headers (## )    | 11pt      | Yes  | No     | #1F4E79 | before: 240 after:80 |
Summary body             | 10pt      | No   | No     | (black) | after: 60            |
Impact bullets (- )      | 10pt      | No   | No     | (black) | after: 40            | BULLET numbering
Core Skills prose        | 10pt      | No   | No     | (black) | after: 80            | Theme name bold inline
Project name (### )      | 10pt      | Yes  | No     | (black) | after: 40            |
Project URL              | 9pt       | No   | No     | #555555 | (inline after name)  |
Project description      | 10pt      | No   | No     | (black) | after: 100           |
Company + Role (run 1)   | 10pt      | Yes  | No     | (black) | before:160 after:40  | tab stop right@9026
Date (run 2, after tab)  | 10pt      | No   | No     | #555555 | (same paragraph)     |
Role context line (_..._)| 10pt      | No   | Yes    | #555555 | after: 60            |
Experience bullets (- )  | 10pt      | No   | No     | (black) | after: 40            | BULLET numbering
Education lines          | 10pt      | No   | No     | (black) | after: 40            |
Languages                | 10pt      | No   | No     | (black) | after: 40            |
```

Color palette:
- `#1F4E79` (dark blue): name + section headers — creates visual hierarchy without being aggressive
- `#444444` (dark gray): professional title line
- `#555555` (medium gray): secondary info (contact, dates, context lines, URLs) — relegates to background
- Black (default): body text, bullets, company names — primary reading content

Page: A4, margins 1 inch, font Calibri throughout. Zero tables. Tab stop position 9026 twips (A4 content width with 1" margins).

### Updated LLM output contract

Same markdown format as Phase 5 with these additions:
1. **Company + Role + Date on ONE line** separated by `\t` (tab character for right-alignment)
2. **Role context lines in `_italics_`** — one sentence explaining scope/context
3. **Core Skills as `Theme: prose`** — theme name followed by colon, no `**bold**` markers
4. **Project names on same line as URL** when applicable
5. **No `**bold**` markers in body text** — the docx_builder handles bold via element type

(Full format example preserved in _OUTPUT_CONTRACT within prompt.py — see step 6.3)

### Dependencies

| Dependency | Docs URL | Used first in |
|---|---|---|
| python-docx | https://python-docx.readthedocs.io/en/latest/ | Step 6.1 |

---

## Tasks

- [x] Phase 6 — CV Output Quality (6.1–6.7)

---

## Execution rules

Same as Phase 5. Test-first. One step, one commit. Stay in your lane.

---

## Phase 6 — CV Output Quality

### 6.1 · Rewrite docx_builder with skill-quality formatting
**Action**: Rewrite `api/cv/docx_builder.py` to produce .docx matching the formatting spec above. Full rewrite, not a patch.

**Document setup**:
- A4 page, 1 inch margins (2.54cm = 1440 twips each side)
- Default font: Calibri
- Bullet numbering: "List Paragraph" style with explicit `<w:numPr>` in XML (NOT "List Bullet" style which lacks numPr and fails ATS parsers)
- Bullet indent: left 360 twips, hanging 360 twips
- No tables anywhere

**Parsing rules** (markdown → elements):
- `# Name` → name (18pt bold, color:#1F4E79, after:60)
- Second line (no prefix) → title (11pt, color:#444444, after:80)
- Third line (no prefix) → contact (9pt, color:#555555, after:200)
- `## Header` → section header (11pt bold, color:#1F4E79, before:240, after:80)
- `- text` → bullet paragraph (10pt, black, after:40, BULLET numbering)
- `_text_` or `*text*` (standalone line) → italic context line (10pt italic, color:#555555, after:60)
- `### Company - Role\tDate` → TWO RUNS: run1 = "Company - Role" (10pt bold, black), run2 = tab + date (10pt, not bold, color:#555555). Paragraph: before:160, after:40, tab stop right@9026
- Core Skills lines with `Theme:` pattern → bold run for theme name (black), normal run for rest (black), (10pt, after:80)
- `### ProjectName  URL` → TWO RUNS: run1 = project name (10pt bold, black), run2 = URL (9pt, color:#555555). After:40. Next prose line = description (10pt, black, after:100)
- Other prose lines → normal paragraph (10pt, black, after:60)

**Color constants** (define at module top):
```python
COLOR_ACCENT = '1F4E79'   # dark blue: name, section headers
COLOR_TITLE  = '444444'   # dark gray: professional title
COLOR_MUTED  = '555555'   # medium gray: contact, dates, context lines, URLs
```

**Pre/post-processing**: same as Phase 5 (strip fences/preamble, replace em dashes etc.)

**Files**: `api/cv/docx_builder.py`
**`[VERIFY-DOCS]`**: python-docx — fetch https://python-docx.readthedocs.io/en/latest/
**Verify** (unit):
- Name: 18pt, bold, color=#1F4E79 | Section headers: 11pt, bold, color=#1F4E79
- Title: 11pt, color=#444444 | Contact: 9pt, color=#555555
- Bullets: numPr in XML, 10pt, not bold, black
- Italic context lines: 10pt, italic, color=#555555
- Company/date: run1 bold black, run2 color=#555555, tab stop @9026
- Project URLs: 9pt, color=#555555
- Bold paragraphs < 15 | Zero tables | Only 3 non-black colors: 1F4E79, 444444, 555555
- Backward compat: Phase 5 format markdown still produces valid .docx

**Commit**: `feat: rewrite docx_builder with skill-quality formatting`

---

### 6.2 · CV plan builder (deterministic, no LLM)
**Action**: Create `api/cv/plan.py` — builds a CV generation plan from the scored job data that already exists in the DB. Pure Python, no LLM call, instant.

```python
def build_cv_plan(job: dict, reference_files: dict) -> dict:
    """Build CV generation plan from scored data + reference material.
    
    Args:
        job: Full job dict from SQLite (parsed + scored JSON strings).
        reference_files: Dict of loaded reference file contents keyed by filename.
    
    Returns:
        Plan dict consumed by prompt builder and validator.
    """
```

**Plan output structure:**

```json
{
  "jd_context": {
    "company_type": "consultancy|in_house|agency|unknown",
    "business_model": "B2B|B2C|marketplace|platform|unknown",
    "vertical": "data|adtech|media|...",
    "location": "Paris, FR",
    "seniority_read": "mid",
    "key_tools": ["SQL", "Python", "dbt"],
    "team_signals": "embedded in client teams",
    "location_language_hints": ["French"]
  },
  "score_summary": {
    "total": 72,
    "breakdown": {"domain_fit": 20, "seniority_fit": 15, ...},
    "dimension_guidance": {
      "domain_fit": {"score": 20, "level": "high", "instruction": "Lead with domain proof bullets"},
      "technical_depth": {"score": 18, "level": "high", "instruction": "Include technical mechanisms in bullets"},
      "seniority_fit": {"score": 15, "level": "high", "instruction": "Maintain seniority level from source"},
      "profile_evidence": {"score": 15, "level": "high", "instruction": "Emphasize concrete evidence"},
      "strategic_impact": {"score": 4, "level": "low", "instruction": "Reframe as platform-level strategic thinking"}
    }
  },
  "strengths": [...],
  "gaps": [...],
  "bullet_allocation": {
    "Gartner Digital Markets": {"budget": 4, "relevance": "high", "because": "data platform ownership maps directly to JD"},
    "Grupo Godo": {"budget": 3, "relevance": "high", "because": "AI/ML + data layer"},
    "Marfeel": {"budget": 4, "relevance": "high", "because": "analytics platform, NLP, scale, consulting-like multi-client"},
    "Softonic": {"budget": 2, "relevance": "medium", "because": "measurement rebuild + SaaS packaging"},
    "Adform": {"budget": 2, "relevance": "medium", "because": "client-facing consulting angle + AdTech depth"},
    "Various": {"budget": 1, "relevance": "low", "because": "entrepreneurial signal"}
  },
  "source_facts": {
    "title": "Senior Product Manager",
    "years_experience": "10+",
    "languages": ["Spanish (native)", "English (advanced)", "Catalan (basic)", "French (basic)"],
    "core_skills_themes": ["Data Platforms and Tracking", "Data Governance and Privacy", "AI and ML Products", "Product Delivery", "Technical"]
  }
}
```

**How each section is built:**

`jd_context`:
- `company_type`: heuristic from parsed JD keywords. "consultant" / "consulting" / "embedded" / "client" / "mission" → "consultancy". "We are building" / "our platform" / "our product" → "in_house". Default "unknown".
- `business_model`: from parsed.domain + JD keyword scan ("B2B", "B2C", "marketplace", "SaaS", "platform").
- `location`: from parsed.locations_mentioned[0].
- `location_language_hints`: map location country to likely useful languages (FR→French, DE→German, etc). Simple dict lookup, not NLP.
- `key_tools`: parsed.technical_stack + parsed.must_have_skills filtered to known tools (SQL, Python, dbt, Kafka, etc vs soft skills).
- `seniority_read`: parsed.seniority.

`score_summary`:
- Copy score_breakdown from rag_score.
- For each dimension, classify score into level: ≥16 "high", ≥10 "medium", <10 "low".
- Map level to instruction string (deterministic lookup table).

`bullet_allocation`:
- Extract company names from master-cv-experience.md (parse ### headers).
- For each company, compute relevance score based on: overlap between company's bullets keywords and parsed.must_have_skills + parsed.technical_stack. Simple token intersection, not embedding similarity.
- Assign budget: high relevance (top 2-3 companies) → 4-5, medium → 2-3, low → 1-2.
- Total budget capped at ~16 bullets (fits 2 pages).

`source_facts`:
- Extract title from first line of master-cv-profile.md (after name).
- Extract years from Summary line (regex for `\d+\+?\s*years`).
- Extract languages from Languages section of master-cv-experience.md.
- Extract Core Skills theme names from master-cv-profile.md or master-cv-experience.md (### or **Theme:** patterns).

These are the facts the validator will check against the generated output.

**Files**: `api/cv/plan.py`
**Verify** (unit):
- Pass WeFiiT job dict → plan.jd_context.company_type == "consultancy" (JD contains "mission", "clients", "consulting")
- plan.jd_context.location_language_hints contains "French"
- plan.source_facts.title == "Senior Product Manager"
- plan.source_facts.years_experience == "10+"
- plan.source_facts.languages contains "French"
- plan.bullet_allocation total budget ≤ 18
- plan.score_summary.dimension_guidance has entry for each score dimension
- Pass job with no rag_score → plan still builds with defaults (empty strengths/gaps, even bullet allocation)

**Commit**: `feat: add deterministic CV plan builder from scored data`

---

### 6.3 · Rewrite prompt.py with plan-aware generation + chain-of-thought
**Action**: Rewrite `api/cv/prompt.py`. The prompt now receives the CV plan and injects it as structured context. The LLM's job is to WRITE, not analyze. Analysis that requires judgment gets a chain-of-thought block that the docx_builder strips.

**New `build_cv_prompts` signature:**

```python
def build_cv_prompts(job: dict, user_cv_markdown: str, cv_plan: dict) -> tuple[str, str]:
```

**System prompt structure:**

```
[Reference files: generate-cv.md, ats-rules.md, master-cv-profile.md, master-cv-experience.md]

[Output contract: markdown format spec — same as current _OUTPUT_CONTRACT but updated with
 italic context lines, tab dates, Core Skills themes, etc]

[Formatting rules — from current spec]

[Content quality rules:]

Source fidelity:
- The reference files are the source of truth. Never downgrade job titles, years of
  experience, skill levels, or factual claims from the reference material.
- Include ALL languages from the reference material. If the target role is in a specific
  country or city, add a contextual note to relevant languages.
- Core Skills must cover every theme area in the reference material that is relevant to
  the target role. Do not collapse or merge themes.

Relevance-weighted bullet allocation:
- Follow the bullet allocation plan provided. It specifies how many bullets per role and why.
- Within each role, lead with the bullet that most directly maps to a JD requirement.
  Always include the most differentiating bullet (the one competitors are least likely to have).
- Each bullet: max 2 lines. Mechanism + result. No narrative arcs, no preamble verbs.

JD-aware tailoring:
- The CV plan provides JD context analysis (company type, vertical, location signals).
  Use it to shape the Summary and bullet selection.
- If company_type is "consultancy", the Summary must mention adaptability to different
  client environments.
- If the JD emphasizes specific tools that appear in reference material, surface them
  explicitly.

Anti-slop:
- The Summary MUST NOT contain: "strong track record", "drive measurable business impact",
  "proven ability", "passionate about", "results-driven", or any aspirational language
  that cannot be verified from the CV.
- The Summary SHOULD contain at least one concrete limit, preference, or constraint.
- Never start a bullet with a gerund. Past tense for completed work, present for current role.

Chain-of-thought:
- Before writing the CV, output an <analysis> block with your reasoning about:
  1. Summary angle given the JD context
  2. For each of the top 5 must_have_skills, which specific bullet from the master CV best proves it
  3. What differentiates this candidate from typical applicants for this role
  4. Any gaps to acknowledge through framing (not invention)
- The <analysis> block will be stripped before document generation. It is for reasoning only.
- After the </analysis> block, output ONLY the CV markdown starting with # [Name].
```

**User prompt structure:**

```
## CV Generation Plan

{cv_plan JSON, pretty-printed}

## Job Description

{JD text}

## Job Metadata

Title: {title}
Company: {company}
Location: {location}
Score: {score} (Tier {tier})

---

Generate the CV following the plan above. Start with <analysis>, then output the CV markdown.
```

Note: the user prompt is now MUCH simpler. No more score breakdown, strengths, gaps listed separately — they're all in the plan JSON. The reference files are in the system prompt. The user prompt is just: plan + JD + metadata + go.

**Pre-processing in docx_builder or in prompt post-processing:**
The `<analysis>...</analysis>` block must be stripped before passing to docx_builder. Add this to the existing pre-processing in docx_builder (strip before first `#`) OR add a `strip_analysis()` function in prompt.py that the endpoint calls after `generate_cv()` returns.

Recommended: add `strip_analysis()` in `api/cv/llm.py` as a post-processing step within `generate_cv()` itself, so the caller always gets clean markdown.

**Files**: `api/cv/prompt.py`, `api/cv/llm.py` (add analysis stripping)
**Verify** (unit):
- build_cv_prompts with plan → system prompt contains "Follow the bullet allocation plan"
- build_cv_prompts with plan → user prompt contains pretty-printed plan JSON
- build_cv_prompts with plan → user prompt does NOT re-list strengths/gaps separately (they're in the plan)
- build_cv_prompts with plan containing company_type="consultancy" → system prompt contains consulting instruction
- strip_analysis removes `<analysis>...</analysis>` block and returns clean markdown starting with `#`
- Backward compat: build_cv_prompts with cv_plan=None or cv_plan={} → falls back to current behavior (plan-less generation still works)

**Commit**: `feat: plan-aware CV prompt with chain-of-thought analysis`

---

### 6.4 · Programmatic CV validator
**Action**: Create `api/cv/validator.py` — checks the generated CV markdown against the plan's source_facts before docx conversion. Pure Python, no LLM.

```python
def validate_cv(generated_markdown: str, cv_plan: dict) -> dict:
    """Validate generated CV against plan source facts.
    
    Returns:
        {"passed": bool, "errors": [...], "warnings": [...]}
        errors = must-fix issues (title downgraded, years wrong)
        warnings = quality issues (slop detected, missing themes)
    """
```

**Checks:**

Errors (block generation, trigger fix call):
- `title_downgraded`: source_facts.title not found in generated title line (case-insensitive substring match)
- `years_downgraded`: source_facts.years_experience number not found in Summary (regex `\d+\+?\s*years`)
- `slop_detected`: any blacklisted phrase found in generated text. Blacklist: "strong track record", "drive measurable business impact", "proven ability", "passionate about", "results-driven", "data-driven leader", "leveraging", "utilizing"

Warnings (logged, don't block):
- `missing_language`: any language in source_facts.languages not found in generated Languages section
- `missing_theme`: any theme in source_facts.core_skills_themes not fuzzy-matched in generated Core Skills (token overlap > 50%)
- `bullet_budget_violation`: for any role in bullet_allocation, actual bullet count differs from budget by >2
- `no_consulting_mention`: plan.jd_context.company_type == "consultancy" but Summary doesn't contain "consulting" / "client" / "embedded" / "adapt"
- `gerund_start`: any bullet starts with a gerund (regex: `^- [A-Z][a-z]+ing\b`)

**Fix flow** (called from endpoint if errors > 0):

```python
def build_fix_prompt(generated_markdown: str, errors: list) -> tuple[str, str]:
    """Build a targeted fix prompt for specific validation errors.
    
    System: "Fix ONLY the listed issues. Change nothing else."
    User: the generated CV + list of specific errors to fix.
    """
```

This is a cheap LLM call (~500 tokens output) that patches specific issues. The endpoint flow becomes:

```
plan = build_cv_plan(job, refs)
system, user = build_cv_prompts(job, cv_md, plan)
raw = generate_cv(system, user)           # expensive call
result = validate_cv(raw, plan)
if not result["passed"]:
    fix_system, fix_user = build_fix_prompt(raw, result["errors"])
    raw = generate_cv(fix_system, fix_user)  # cheap fix call
# proceed to docx_builder
```

**Files**: `api/cv/validator.py`
**Verify** (unit):
- CV with "Product Manager" when source says "Senior Product Manager" → error title_downgraded
- CV with "7+ years" when source says "10+" → error years_downgraded
- CV with "strong track record" → error slop_detected
- CV missing "French" when source has it → warning missing_language
- CV with company_type=consultancy but no consulting mention → warning no_consulting_mention
- CV with "- Leading the team..." → warning gerund_start
- Clean CV matching all source_facts → passed=True, empty errors and warnings
- build_fix_prompt produces prompt mentioning specific errors only

**Commit**: `feat: add programmatic CV validator with fix loop`

---

### 6.5 · Update ATS audit for new format
**Action**: Update `api/cv/ats_audit.py` with formatting quality checks (in addition to existing ATS violation checks):
- `excessive_bold`: count all-bold paragraphs > 15 → warning
- `no_context_lines`: 0 italic paragraphs → warning
- `no_real_bullets`: 0 paragraphs with numPr → violation
- `no_tab_stops`: 0 paragraphs with tab stop → warning
- Keep all existing checks (tables, em dashes, Oxford commas, unicode bullets, headers)

**Files**: `api/cv/ats_audit.py`
**Verify**: Well-formatted .docx → pass. All-bold → warning. No bullets → violation.
**Commit**: `feat: extend ATS audit with formatting quality checks`

---

### 6.6 · Update endpoint to use plan + validator pipeline
**Action**: Update `POST /api/jobs/{id}/generate-cv` in `api/routes/jobs.py` to use the new pipeline:

```python
# 1. Load job
# 2. Load reference files
# 3. Build plan (deterministic, instant)
plan = build_cv_plan(job, reference_files)
# 4. Build prompts (plan-aware)
system, user = build_cv_prompts(job, cv_md, plan)
# 5. Generate CV (expensive LLM call)
raw_markdown = generate_cv(system, user)
# 6. Validate against plan
validation = validate_cv(raw_markdown, plan)
# 7. Fix if needed (cheap LLM call)
if not validation["passed"]:
    fix_system, fix_user = build_fix_prompt(raw_markdown, validation["errors"])
    raw_markdown = generate_cv(fix_system, fix_user)
    # Re-validate (don't loop more than once)
    validation = validate_cv(raw_markdown, plan)
# 8. Build docx
docx_path = build_docx(raw_markdown, output_path)
# 9. ATS audit
audit = audit_docx(docx_path)
# 10. Return file with headers
# X-CV-Validation: passed/warnings
# X-ATS-Audit: passed/warnings
# X-CV-Fix-Applied: true/false
```

Add response headers:
- `X-CV-Validation`: JSON string of validation result (passed + warnings)
- `X-CV-Fix-Applied`: "true" if fix call was triggered, "false" otherwise
- `X-ATS-Audit`: existing audit header

**Files**: `api/routes/jobs.py`
**Verify**: Full flow with mocked LLM. Plan is built. Prompts include plan. Validation runs. Fix call triggered when validation fails. Headers present in response.
**Commit**: `feat: plan-driven CV generation pipeline with validation`

---

### 6.7 · Integration test with full pipeline
**Action**: Create `tests/test_cv_pipeline.py` with:

1. **Formatting golden-path test**: sample markdown → build_docx → audit_docx passes. Verify: name 18pt bold #1F4E79, headers 11pt bold #1F4E79, title #444444, contact #555555, bullets with numPr, italic context lines #555555, company date runs with tab stops, bold paragraphs < 15, zero tables, only 3 non-black colors.

2. **Plan builder test**: WeFiiT job dict → build_cv_plan → verify company_type="consultancy", location_language_hints contains "French", source_facts.title="Senior Product Manager", bullet_allocation total ≤ 18.

3. **Validator test**: CV with known defects → validate_cv catches them. Clean CV → passes.

4. **Bold-stripping test**: markdown with `**bold**` markers in body → docx_builder does NOT produce bold body text.

5. **Analysis-stripping test**: LLM output with `<analysis>...</analysis>` + CV markdown → strip_analysis returns clean markdown starting with `#`.

**Files**: `tests/test_cv_pipeline.py`
**Verify**: All tests pass. Any regression to all-bold or title downgrade causes failure.
**Commit**: `test: add full CV pipeline integration tests`

---

### 6.8 · Manual quality test with real LLM output
**Action**: Manual verification after all automated tests pass.
1. Generate CV for WeFiiT Data PM role using full pipeline
2. Verify formatting: visual hierarchy matches skill-generated CV
3. Verify content: Summary mentions consulting context. Title says "Senior". Years say "10+". French included with Paris note. Core Skills has 4+ themes. Bullet allocation follows plan.
4. Compare side-by-side with `cv-wefiit.docx` (skill-generated)
5. If content still insufficient: the fix is in reference files or plan builder heuristics, not in the LLM prompt. Document specific issues in CLAUDE.md.

Update CLAUDE.md Project State: Phase 6 → Completed. Document decisions:
- docx_builder rewritten to match skill-generated CV formatting spec (colors, sizes, bullets, tabs)
- Plan-driven architecture: deterministic plan from scored data → plan-aware LLM call → programmatic validation
- Chain-of-thought analysis block stripped before docx conversion
- Validator catches source fidelity errors with optional auto-fix LLM call
- Anti-slop rules enforced programmatically, not just via prompt instructions

**Files**: `CLAUDE.md`
**Commit**: `docs: checkpoint phase 6`

**GATE**: Generated CV visually matches skill-generated quality. ATS audit passes. Validator passes. Plan correctly identifies consulting context for WeFiiT. Title = Senior. Years = 10+. French included. No slop phrases. Bold paragraphs < 15. Bullets have numPr. Dates right-aligned with tab stops. Run **Checkpoint**.

**Demo**: Generate CV for WeFiiT → .docx opens with clean visual hierarchy. Side-by-side with skill-generated version shows formatting parity and comparable content quality.
