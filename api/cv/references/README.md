# CV Reference Files

This directory contains personal reference files used by the CV generation pipeline.
These files **must NOT be committed to git** — they contain personal data including
full work history, contact information, and CV content.

## Required files

| File | Description |
|------|-------------|
| `generate-cv.md` | Workflow instructions for the LLM: how to tailor the CV |
| `ats-rules.md` | ATS formatting rules the LLM must follow |
| `master-cv-profile.md` | Summary, selected impact, core skills |
| `master-cv-experience.md` | Full work history, education, languages |

All four files are required. The CV generation endpoint will raise `FileNotFoundError`
with the missing filename if any are absent.

## Setup

Copy the reference files from the `career-helper` skill:

```bash
unzip -j career-helper.skill \
  "career-helper/references/generate-cv.md" \
  "career-helper/references/ats-rules.md" \
  "career-helper/references/master-cv-profile.md" \
  "career-helper/references/master-cv-experience.md" \
  -d api/cv/references/
```

Or override the directory at runtime:

```bash
CV_REFERENCES_DIR=/path/to/your/references uvicorn api.main:app
```

## Docker

Mount as a volume in docker-compose or Railway/Render/Fly:

```yaml
volumes:
  - ./api/cv/references:/app/api/cv/references:ro
```
