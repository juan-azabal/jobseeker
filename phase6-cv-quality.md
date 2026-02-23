# Phase 6 — CV Output Quality: formatting + content parity with skill

> **Execute. Do not plan.** If you enter plan mode, call ExitPlanMode immediately.
> If any step is ambiguous, STOP and ask. Do not assume.

## Context

### Goal

The Phase 5 CV generation pipeline works end-to-end but produces inferior output compared to the career-helper skill. Phase 6 closes the gap on two independent layers: the docx_builder (formatting) and the LLM prompt (content quality).

### Problem evidence (from real test: WeFiiT Data PM role)

**docx_builder problems (Layer 1):**
- All 57 paragraphs use style "Normal" — no style differentiation
- 40/57 paragraphs are ALL BOLD — body text, bullets, everything
- 0/57 paragraphs have bullet numbering — bullets rendered as plain paragraphs
- 0/57 paragraphs have italics — no role context lines
- No tab stops — dates not right-aligned
- No font size variation — name, headers, body all same size
- Result: a wall of bold text unreadable by both ATS and humans

**LLM content problems (Layer 2):**
- Summary contains AI slop: "Strong track record", "drive measurable business impact"
- No reframing for target role context (consulting angle missing for WeFiiT)
- Bullets copy-pasted from master CV without selection or rewriting
- No role context lines (italic one-liners under each company explaining scope)
- Pruning insufficient: bullets too long, too many per role
- "7+ years" when master CV says "10+ years"

### Target: skill-generated CV formatting spec

The career-helper skill produces .docx with this exact formatting. The docx_builder must replicate it.

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

The Phase 5 output contract must be extended to support the formatting features. The LLM must output markdown with these conventions:

```markdown
# Juan Azabal
Senior Product Manager - Data Platforms & AI
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal | github.com/juan-azabal

## Summary

Prose paragraph. 10+ years... No AI slop. Real context with limits.

## Selected Impact

- Bullet with problem, action, result. Max 2 lines.
- Another bullet. Mix metrics and qualitative.

## Core Skills

Theme Name: prose describing skills in this theme. No bullet points.

Another Theme: another prose paragraph.

## Projects

### LLM Control Plane  github.com/juan-azabal/llm-control-plane
2-3 lines. Problem, stack, outcome.

### JobAgent
2-3 lines.

## Work Experience

### Gartner Digital Markets (Capterra, GetApp, Software Advice) - Senior PM, Data Platform\t07/2024 - Present
_Replacing GA4 with a governed, first-party data platform across three global B2B marketplace brands._

- Bullet one. Max 2 lines.
- Bullet two.

### Grupo Godo (LaVanguardia.com) - Senior Product Manager\t07/2022 - 07/2024
_Data, personalization and monetization at one of Spain's largest digital news publishers._

- Bullet one.

## Education and Certifications

Degree, Institution, Year

## Languages

Spanish (native) | English (advanced) | Catalan (basic) | French (basic)
```

Key differences from Phase 5 contract:
1. **Company + Role + Date on ONE line** separated by `\t` (tab character for right-alignment)
2. **Role context lines in `_italics_`** — one sentence explaining scope/context
3. **Core Skills as `Theme: prose`** — theme name followed by colon, no `**bold**` markers
4. **Project names on same line as URL** when applicable
5. **No `**bold**` markers in body text** — the docx_builder handles bold via element type, not markdown bold

### Dependencies

| Dependency | Docs URL | Used first in |
|---|---|---|
| python-docx | https://python-docx.readthedocs.io/en/latest/ | Step 6.1 |

---

## Tasks

- [ ] Phase 6 — CV Output Quality (6.1–6.5)

---

## Execution rules

Same as Phase 5. Test-first. One step, one commit. Stay in your lane.

---

## Phase 6 — CV Output Quality

### 6.1 · Rewrite docx_builder with skill-quality formatting
**Action**: Rewrite `api/cv/docx_builder.py` to produce .docx matching the formatting spec above. This is a full rewrite, not a patch. The builder must:

**Document setup**:
- A4 page, 1 inch margins (2.54cm = 1440 twips each side)
- Default font: Calibri
- Define bullet numbering config (WD_LIST_NUMBER_FORMAT.BULLET, indent left 360 twips hanging 360 twips)
- No tables anywhere

**Parsing rules** (markdown → elements):
- `# Name` → name (18pt bold, color:#1F4E79, after:60)
- Second line (no prefix) → title (11pt, color:#444444, after:80)
- Third line (no prefix) → contact (9pt, color:#555555, after:200)
- `## Header` → section header (11pt bold, color:#1F4E79, before:240, after:80)
- `- text` → bullet paragraph (10pt, black, after:40, BULLET numbering)
- `_text_` or `*text*` (standalone line) → italic context line (10pt italic, color:#555555, after:60)
- `### Company - Role\tDate` → bold paragraph with tab stop right@9026 (10pt, before:160, after:40). TWO RUNS: run1 = "Company - Role" (bold, black), run2 = tab + date (not bold, color:#555555)
- Lines starting with `Theme:` or `Theme Name:` in Core Skills section → bold run for theme name (black), normal run for rest (black), (10pt, after:80)
- `### ProjectName  URL` in Projects section → TWO RUNS: run1 = project name (10pt bold, black, after:40), run2 = URL (9pt, color:#555555). Next non-bullet line is description (10pt, black, after:100)
- Other prose lines → normal paragraph (10pt, black, after:60)

**Color constants** (define at module top):
```python
COLOR_ACCENT = '1F4E79'   # dark blue: name, section headers
COLOR_TITLE  = '444444'   # dark gray: professional title
COLOR_MUTED  = '555555'   # medium gray: contact, dates, context lines, URLs
# Black = default (no color attribute needed)
```

**Pre-processing** (same as Phase 5):
- Strip code fences
- Strip preamble before `# `
- Strip trailing notes after last section

**Post-processing** (same as Phase 5):
- Scan for em dash, en dash, arrows, tilde, Oxford comma
- Replace with safe alternatives

**Files**: `api/cv/docx_builder.py`
**`[VERIFY-DOCS]`**: python-docx — fetch https://python-docx.readthedocs.io/en/latest/
**Verify** (unit): Pass sample markdown matching the updated contract → output .docx. Open with python-docx and verify:
- Name paragraph: 18pt, bold, after=60, color=#1F4E79
- Section headers: 11pt, bold, before=240, color=#1F4E79
- Title line: 11pt, color=#444444
- Contact line: 9pt, color=#555555
- Bullet paragraphs: have numPr in XML, 10pt, not bold, no color (black)
- Italic context lines: 10pt, italic=True, color=#555555
- Company/date lines: run1 bold black, run2 not bold color=#555555, have tab stop at position 9026
- Project URL runs: 9pt, color=#555555
- Core Skills themes: first run bold, second run not bold, both black
- Zero tables in XML
- No all-bold paragraphs except name, headers, company lines
- Total bold paragraphs < 15 (headers + company lines only)
- Only 3 non-black colors used: 1F4E79, 444444, 555555

Also test with Phase 5 format markdown (backward compat): should still produce valid .docx, just without italic/tab/color features.
**Commit**: `feat: rewrite docx_builder with skill-quality formatting`

### 6.2 · Update LLM output contract in system prompt
**Action**: Update `api/cv/prompt.py` to use the new output contract. The instruction block appended to system prompt must:

1. Replace the old output format with the updated contract from this plan
2. Add explicit formatting rules:
   - "Company name, role and date MUST be on a single line separated by a tab character"
   - "Under each company, add a one-sentence context line in _italics_ describing what the company does and what you did there at a high level"
   - "Core Skills: format as 'Theme Name: prose description'. Do NOT use **bold** markers."
   - "Do NOT wrap any text in **bold** markers. The document builder handles formatting based on element position."
   - "Body text, bullets, and descriptions must be plain text without markdown bold or italic markers, EXCEPT for role context lines which use _single underscore italics_."
3. Add content quality rules:
   - "The Summary MUST contain at least one sentence about limits or what you are NOT looking for"
   - "The Summary MUST NOT contain: 'strong track record', 'drive measurable business impact', 'proven ability', or any generic PM aspirational language"
   - "Each bullet under Work Experience: max 2 lines. Result + mechanism only. No narrative arcs."
   - "If the target role involves consulting or embedded contexts, mention adaptability to different client environments"
4. Keep the existing reference file loading logic unchanged

**Files**: `api/cv/prompt.py`
**Verify** (unit): System prompt contains new output contract format. Prompt contains anti-slop rules. Prompt contains italic context line instruction. Prompt does NOT contain `**bold**` in the format example (except where appropriate for theme names pre-colon). Old tests for reference file loading still pass.
**Commit**: `feat: update LLM output contract for skill-quality formatting`

### 6.3 · Update ATS audit for new format
**Action**: Update `api/cv/ats_audit.py` to verify the new formatting expectations:
- Add check: count all-bold paragraphs. If > 15 → warning "excessive_bold" (not a violation, but flagged)
- Add check: at least 1 paragraph with italic formatting → if 0, warning "no_context_lines"
- Add check: at least 1 paragraph with bullet numbering → if 0, violation "no_real_bullets"
- Add check: at least 1 paragraph with tab stop → if 0, warning "no_tab_stops"
- Keep all existing ATS violation checks (tables, em dashes, Oxford commas, unicode bullets, headers)

**Files**: `api/cv/ats_audit.py`
**Verify** (unit): Well-formatted .docx → all checks pass. All-bold .docx → "excessive_bold" warning. .docx without bullets → "no_real_bullets" violation. .docx without italics → "no_context_lines" warning.
**Commit**: `feat: extend ATS audit with formatting quality checks`

### 6.4 · Integration test with real contract format
**Action**: Create `tests/test_cv_integration.py` (or add to existing test file) with a golden-path test:
1. Define a sample markdown string matching the EXACT updated contract format (use a realistic 2-page CV snippet with all sections)
2. Pass through `build_docx()` → output .docx
3. Pass through `audit_docx()` → must return `passed: True`
4. Open with python-docx and verify formatting spec:
   - Name = 18pt bold, color #1F4E79
   - Section headers = 11pt bold, color #1F4E79
   - Title = color #444444, Contact = color #555555
   - Bullets have numbering, no color (black)
   - Context lines are italic, color #555555
   - Company lines run1 bold black, run2 (date) color #555555, have tab stops
   - Bold paragraphs < 15
   - Zero tables
   - Only 3 non-black colors in document: 1F4E79, 444444, 555555
5. Also test: markdown with `**bold**` markers in body text → builder strips them (does not produce bold body)

This test serves as the living spec for CV output quality. If it passes, the builder is correct.

**Files**: `tests/test_cv_integration.py`
**Verify** (unit): Test passes with golden markdown. Test fails if builder regresses to all-bold.
**Commit**: `test: add integration test for CV formatting spec`

### 6.5 · Manual quality test with real LLM output
**Action**: This is a manual verification step, not automated. After steps 6.1-6.4 pass:
1. Run the full pipeline against the WeFiiT Data PM role (job already in DB)
2. Download the .docx
3. Verify formatting: name 18pt, headers 11pt bold, body 10pt normal, bullets with indentation, italic context lines visible, dates right-aligned
4. Verify content: Summary has limits clause, no AI slop, role context lines present under each company, bullets are pruned
5. Compare side-by-side with `cv-wefiit.docx` (skill-generated) — formatting should be equivalent
6. If content quality still insufficient: the fix is in the reference files or system prompt wording, not in code. Document specific issues in CLAUDE.md under Blockers.

Update CLAUDE.md Project State: Phase 6 to Completed. Add decisions:
- docx_builder rewritten to match skill-generated CV formatting spec
- LLM output contract updated: no bold markers, italic context lines, tab-separated dates
- ATS audit extended with formatting quality checks
- Anti-slop rules added to system prompt

**Files**: `CLAUDE.md`
**Commit**: `docs: checkpoint phase 6`

**GATE**: Generated CV visually matches skill-generated CV quality. ATS audit passes. Formatting spec test passes. Bold paragraphs < 15. Bullets have real numbering. Context lines in italics. Dates right-aligned. Run **Checkpoint**.
**Demo**: Generate CV for WeFiiT role → .docx opens with clean visual hierarchy, same quality as skill-generated version. Side-by-side comparison shows formatting parity.
