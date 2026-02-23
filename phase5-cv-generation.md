# Phase 5 — CV Generation: In-app tailored CV from job description

> **Execute. Do not plan.** If you enter plan mode, call ExitPlanMode immediately.
> If any step is ambiguous, STOP and ask. Do not assume.

## Context

### Goal

Users click "Generate CV" on a job detail page and receive a tailored .docx CV. The system uses the job description, score breakdown, and the user's master CV content to produce an ATS-compliant CV via LLM. The LLM provider is configurable (Anthropic or OpenAI). Output is a .docx file built with python-docx for full ATS compliance control, downloaded directly.

### ⛔ CRITICAL INVARIANT: Zero Disruption

All Phase 1-4 behavior must remain functional. The existing "copy prompt to clipboard" button is REPLACED by the new in-app generation flow. No other existing endpoints or flows change.

### ⛔ ATS COMPLIANCE: Non-negotiable

The .docx output MUST pass ATS parsers (Workday, Greenhouse, Lever). This means:
- Zero tables anywhere in the document XML (not even for layout)
- Bullets via python-docx numbering (WD_LIST_NUMBER_FORMAT.BULLET), never unicode characters
- Tab stops for right-aligned dates on same line as role title
- Single column, all content in Paragraph elements
- ASCII hyphen only (no em dash, en dash, arrows, tilde)
- No Oxford comma
- Standard headers exactly: Summary / Selected Impact / Core Skills / Projects (optional) / Work Experience / Education and Certifications / Languages

python-docx is used instead of pandoc because pandoc's default .docx template uses internal tables and unicode bullets that break ATS parsers. python-docx gives full control over the XML structure.

### Architecture

```
JobDetailPage → POST /api/jobs/{id}/generate-cv
  → api/cv/prompt.py       — builds system + user prompt from reference files + job data
  → api/cv/llm.py          — calls LLM (Anthropic or OpenAI, configurable)
  → api/cv/docx_builder.py — parses LLM markdown output → python-docx → .docx
  → api/cv/ats_audit.py    — post-build ATS compliance verification
  → FileResponse            — browser downloads .docx
```

- LLM abstraction: `api/cv/llm.py` — provider-agnostic, configured via `CV_LLM_PROVIDER` env var
- .docx builder: `api/cv/docx_builder.py` — parses structured markdown, emits ATS-safe .docx via python-docx
- ATS audit: `api/cv/ats_audit.py` — post-build safety net, inspects .docx XML for violations
- CV reference files: `api/cv/references/` — gitignored, loaded from `CV_REFERENCES_DIR` env var with fallback
- New env vars: `CV_LLM_PROVIDER` (default: `anthropic`), `CV_LLM_MODEL` (default per provider), `ANTHROPIC_API_KEY`, `CV_REFERENCES_DIR` (optional override)

### LLM output contract

The LLM MUST output structured markdown following this exact format. The system prompt enforces it. The docx_builder parses it deterministically.

```markdown
# Juan Azabal
Senior Product Manager | Data, Personalization & Monetization
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal

## Summary

3-5 lines of prose.

## Selected Impact

- Bullet one
- Bullet two

## Core Skills

**Theme Name**
Prose paragraph for this theme.

**Another Theme**
Another prose paragraph.

## Projects

### Project Name
2-3 lines. Problem, stack, outcome. URL.

## Work Experience

### Company Name, City, Country
**Role Title | MM/YYYY - MM/YYYY**

- Bullet one
- Bullet two

### Another Company, City, Country
**Another Role | MM/YYYY - MM/YYYY**

- Bullet

## Education and Certifications

- Degree - Institution, Year

## Languages

- Language - Level
```

The docx_builder maps this structure 1:1 to python-docx elements. No heuristic parsing.

### Context budget per LLM call

| File | ~Tokens |
|---|---|
| generate-cv.md (workflow instructions) | 2,000 |
| ats-rules.md (format rules) | 1,100 |
| master-cv-profile.md (summary, impact, skills) | 2,800 |
| master-cv-experience.md (work history) | 3,000 |
| JD + scored data (user prompt) | 2,000-4,000 |
| **Total input** | **~12,000-14,000** |

### Dependencies requiring doc verification

| Dependency | Docs URL | Used first in |
|---|---|---|
| anthropic Python SDK | https://docs.anthropic.com/en/api/messages | Step 5.2 |
| python-docx | https://python-docx.readthedocs.io/en/latest/ | Step 5.4 |

### Security: reference files not in git

The CV reference files contain personal data (full CV, phone, email, experience). They MUST NOT be committed to the repo. They are:
- Listed in `.gitignore`
- Loaded at runtime from `CV_REFERENCES_DIR` env var (default: `api/cv/references/`)
- Copied manually to the server or mounted as a volume in Docker
- Documented in README with setup instructions

---

## Tasks

- [ ] Phase 5 — CV Generation (5.1–5.8)

---

## Execution rules

These override your defaults. Follow them exactly.

1. **Test-first**: For every step, write the test FIRST → run → must FAIL → implement minimum to pass → run ALL tests → must PASS. No exceptions.
2. **One step, one commit**: Commit and push after every step. Never accumulate changes across steps.
3. **`[VERIFY-DOCS]`**: Before implementing a step with this tag, WebFetch the listed docs URL. Verify import paths, API signatures, method names are current. If docs contradict the plan, STOP and report.
4. **Stuck protocol**: If a test fails after 3 fix attempts → STOP. Add a TodoWrite item: `"BLOCKER [step]: [error + what you tried]"`. Do NOT proceed.
5. **Checkpoint**: At every GATE, update CLAUDE.md Project State (move phase to Completed, advance Current, log any decisions or blockers). Commit: `docs: checkpoint`.
6. **Stay in your lane**: Implement ONLY what the current step describes. No "while I'm here" additions.

---

## Phase 5 — CV Generation

### 5.1 · Reference files setup
**Action**: Create `api/cv/references/` directory. Copy these files into it: `generate-cv.md`, `ats-rules.md`, `master-cv-profile.md`, `master-cv-experience.md` (source: career-helper skill references). Add `api/cv/references/*.md` to `.gitignore`. Create `api/cv/references/README.md` (NOT gitignored) explaining: what files are expected, where to get them, that they contain personal data and must not be committed. Add `CV_REFERENCES_DIR` to `.env.example` with comment.
**Files**: `api/cv/references/`, `.gitignore`, `api/cv/references/README.md`, `.env.example`
**Verify** (output): `git status` does NOT show the .md reference files as tracked. README.md IS tracked. `.env.example` has `CV_REFERENCES_DIR`.
**Commit**: `feat: add CV reference files structure (gitignored)`

### 5.2 · LLM abstraction layer
**Action**: Create `api/cv/llm.py` with `generate_cv(system_prompt: str, user_prompt: str) -> str`. Reads `CV_LLM_PROVIDER` env var (default: `anthropic`). Reads `CV_LLM_MODEL` env var (default: `claude-sonnet-4-5-20250514` for anthropic, `gpt-4o` for openai). If `anthropic`: uses `anthropic.Anthropic().messages.create()`, max_tokens=4096. If `openai`: uses `openai.OpenAI().chat.completions.create()`, max_tokens=4096. Raises `ValueError` if provider unknown. Raises `RuntimeError` with clear message if API key env var is missing. Create `api/cv/__init__.py`.
**Files**: `api/cv/llm.py`, `api/cv/__init__.py`
**`[VERIFY-DOCS]`**: anthropic Python SDK — fetch https://docs.anthropic.com/en/api/messages
**Verify** (unit): Mock both providers. `generate_cv()` with `CV_LLM_PROVIDER=anthropic` calls anthropic client with correct model. With `openai` calls openai client. With `invalid` raises ValueError. With missing API key raises RuntimeError. `CV_LLM_MODEL` override works for both providers.
**Commit**: `feat: add configurable LLM abstraction for CV generation`

### 5.3 · CV prompt builder
**Action**: Create `api/cv/prompt.py` with `build_cv_prompts(job: dict, user_cv_markdown: str) -> tuple[str, str]` returning (system_prompt, user_prompt). System prompt: loads and concatenates the 4 reference files with `--- SECTION: {filename} ---` separators. Files loaded from `CV_REFERENCES_DIR` env var, fallback to `api/cv/references/` relative to module. Raises `FileNotFoundError` with explicit message listing missing files. Appends instruction block at end of system prompt: "Output ONLY the CV content in the structured markdown format specified below. No preamble, no explanations, no code fences, no notes after the CV." followed by the output contract format from this plan's Architecture section. User prompt: formats job title, company, location, URL, score, tier, JD text (from `job["parsed"]` — tries keys `description`, `full_text`, `body` in order), score breakdown, strengths, and gaps (from `job["scored"]`). Appends user's cv.md if available. If no JD text extractable from parsed, raises `ValueError("No job description available for CV generation")`.
**Files**: `api/cv/prompt.py`
**Verify** (unit): With sample job dict containing `parsed.description` → system prompt contains all 4 reference sections + output contract. User prompt contains job title, company, JD text. System prompt > 5000 chars. Job with empty/missing parsed → raises ValueError. Missing reference file → raises FileNotFoundError with filename.
**Commit**: `feat: add CV prompt builder with output contract`

### 5.4 · ATS-compliant .docx builder
**Action**: Create `api/cv/docx_builder.py` with `build_docx(markdown: str, output_path: str) -> str`. Parses the structured markdown from LLM output and builds a .docx using python-docx with these ATS constraints:

**Pre-processing**: Strip code fences if LLM wraps output in ```markdown. Strip any preamble text before the first `# ` heading. Strip any text after the last section.

**Parsing**: Split markdown by `## ` headers. Within Work Experience, split by `### ` for companies. Parse `**Role | Date**` lines. Parse `- ` lines as bullets. Parse `**Theme**` + following paragraph in Core Skills. Contact info from first 3 lines (name, title line, details line).

**Document setup**:
- Page size: A4 (standard for EU/Spain)
- Margins: 1 inch all sides (2.54cm)
- Default font: Calibri 11pt (high ATS compatibility)
- No tables anywhere

**Element mapping**:
- Name → Heading 1 (Calibri 14pt bold)
- Title line + contact line → Normal paragraphs, 10pt
- `## ` headers → Heading 2 (Calibri 12pt bold, space before 12pt)
- `### ` (company/project names) → Heading 3 (Calibri 11pt bold)
- `**Role | Date**` → Normal paragraph with tab stop right-aligned at page width for date
- `- ` items → List paragraphs with WD_LIST_NUMBER_FORMAT.BULLET, indent left 0.25in hanging 0.25in
- Prose paragraphs → Normal, 11pt
- `**Theme Name**` in Core Skills → Bold run within paragraph, followed by newline + prose

**Post-processing**: After building, scan all paragraph text for ATS violations: em dash (—), en dash (–), arrows (→, =>), tilde (~), Oxford comma (", and "). Replace with safe alternatives (em/en dash → ASCII hyphen, arrows → removed, Oxford comma → comma without "and"). Log replacements as warnings.

**Files**: `api/cv/docx_builder.py`
**`[VERIFY-DOCS]`**: python-docx — fetch https://python-docx.readthedocs.io/en/latest/
**Verify** (unit): Pass sample structured markdown → output .docx exists, >0 bytes. Open with python-docx and verify: zero Table elements in document XML, Heading1 is name, Heading2 count matches section count, bullet paragraphs use list numbering (not unicode), no em dashes in any paragraph text. Pass markdown with em dashes and Oxford commas → post-processing removes them. Pass markdown wrapped in code fences → fences stripped, valid .docx produced. Pass empty/malformed markdown → raises ValueError.
**Commit**: `feat: add ATS-compliant docx builder with python-docx`

### 5.5 · ATS audit utility
**Action**: Create `api/cv/ats_audit.py` with `audit_docx(path: str) -> dict`. Opens .docx with python-docx AND parses the underlying XML. Returns `{"passed": bool, "violations": list[str], "stats": dict}`. Checks:
1. Zero `<w:tbl>` elements in document XML
2. No em dash, en dash, arrows, tilde in any paragraph text
3. No Oxford comma (", and ") in any paragraph text
4. No unicode bullet characters (•, ◦, ▪) in paragraph text
5. Headers present and match expected set (Summary, Selected Impact, Core Skills, Work Experience, Education and Certifications, Languages)
6. Date format matches MM/YYYY pattern where dates appear
7. Stats: section count, bullet count, paragraph count, estimated page count (heuristic: ~45 lines per page)

Called after docx_builder as safety net. Result exposed via `X-ATS-Audit` response header (`pass` or `fail:{count} violations`).

**Files**: `api/cv/ats_audit.py`
**Verify** (unit): Clean ATS-compliant .docx → `passed: True`, empty violations. .docx with table element in XML → violation "table_found". .docx with em dash → violation "prohibited_char:em_dash". Missing standard header → violation "missing_header:Summary". Stats return reasonable numbers.
**Commit**: `feat: add ATS audit utility for generated CVs`

### 5.6 · CV generation endpoint
**Action**: Add `POST /api/jobs/{id}/generate-cv` to `api/routes/jobs.py`. Requires auth. Flow:
1. Load job by id (404 if not found)
2. Load user's cv.md from `JOBAGENT_DIR/knowledge/{profile_id}/cv.md` (empty string if missing)
3. Call `build_cv_prompts(job, user_cv)` — catches ValueError for missing JD → 422 `{"error": "no_jd", "detail": "Job description not available for CV generation"}`
4. Call `generate_cv(system, user)` — catches exceptions → 500 `{"error": "llm_error", "detail": str(e)}`
5. Write to tempfile, call `build_docx(markdown, temp_path)`
6. Run `audit_docx(temp_path)`, add `X-ATS-Audit` response header
7. Return `FileResponse`, filename `cv-{company_slug}-{title_slug}.docx` (slugified, max 60 chars)
8. Cleanup tempfile via `BackgroundTask`

**Files**: `api/routes/jobs.py`
**Verify** (integration): Mock LLM to return sample structured markdown. `POST /api/jobs/{valid_id}/generate-cv` with auth → 200 + .docx content-type + `X-ATS-Audit: pass` header. No auth → 401. Invalid job_id → 404. Job without parseable JD → 422. LLM failure → 500 with error detail. Filename contains company name slug.
**Commit**: `feat: add CV generation endpoint`

### 5.7 · Frontend: generate CV with download
**Action**: Replace clipboard-copy `handleGenerateCV` in `JobDetailPage.tsx`. New behavior:
- POST to `/api/jobs/{id}/generate-cv`
- Button shows "Generating CV..." with spinner, disabled during request
- Below button: "This usually takes 15-20 seconds" (visible only during loading)
- On success: create blob URL from response, trigger download via temporary `<a>` element, show "CV downloaded" confirmation for 3s
- On error: show inline error below button (red text). Map error codes: `no_jd` → "No job description available for this role", `llm_error` → "CV generation failed, try again", generic → "Something went wrong"
- Button re-enables after completion or error
- Remove `buildCVPrompt` function, `cvCopied` state, and all clipboard logic

**Files**: `web/src/pages/JobDetailPage.tsx`
**Verify** (visual): Click "Generate CV" → button shows loading with time estimate → .docx downloads → confirmation shown. Click during loading → button disabled. Error → error message shown, button re-enables. No clipboard references remain in file.
**Commit**: `feat: replace clipboard CV with in-app generation and download`

### 5.8 · Update dependencies, env, and docs
**Action**: Add `anthropic` and `python-docx` to `requirements.txt`. Add to `.env.example`: `CV_LLM_PROVIDER`, `CV_LLM_MODEL`, `ANTHROPIC_API_KEY`, `CV_REFERENCES_DIR`. Add to `.env` with real values. Update CLAUDE.md Project State: Phase 5 to Completed. Add decisions:
- LLM provider configurable via CV_LLM_PROVIDER (anthropic|openai), model via CV_LLM_MODEL
- .docx built with python-docx for ATS compliance (pandoc rejected: generates tables and unicode bullets in XML)
- CV reference files gitignored (contain personal data), loaded from CV_REFERENCES_DIR
- ATS audit runs post-build as safety net, result in X-ATS-Audit response header
- LLM output follows strict structured markdown contract, docx_builder parses deterministically
- Post-processing auto-fixes em dashes, Oxford commas, unicode bullets as last line of defense
**Files**: `requirements.txt`, `.env.example`, `.env`, `CLAUDE.md`
**Verify** (output): `pip install -r requirements.txt` succeeds. `.env.example` has all new vars. CLAUDE.md reflects Phase 5 complete with decisions.
**Commit**: `docs: update deps, env, and project state for CV generation`

**GATE**: Full flow works: click Generate CV on job detail → LLM generates tailored CV → .docx downloads → ATS audit passes. LLM provider switchable. Reference files not in git. All tests green. Run **Checkpoint**.
**Demo**: Navigate to a Tier A job → click Generate CV → wait ~20s → .docx downloads. Open in Word/Google Docs: single column, standard headers, proper bullets, tab-aligned dates, no tables. ATS audit → 0 violations.

---

## Post-phase: manual verification (not automated)

After GATE passes, manually test with one real Tier A job:
1. Generate CV via the endpoint with real LLM (not mocked)
2. Open .docx in Word — visual inspection for layout, formatting
3. Copy all text to plain text — check for em dashes, unicode bullets, Oxford commas
4. Inspect .docx XML: `unzip -p cv.docx word/document.xml | grep -c "w:tbl"` → must be 0
5. Review content quality: tailored to JD? Bullets pruned? 2 pages max?

If content quality is insufficient, the fix is in the reference files and system prompt, not in the code.
