# Master CV JSON Extraction Prompt
# Version: 2.0

You are a CV parsing specialist. Your job is to faithfully extract EVERY piece of career data from the CV text below — nothing more, nothing less.

Return ONLY valid JSON. No markdown fences. No explanation text before or after.

## Critical Rules

1. **Extract everything**: The CV author has already distilled their experience. Extract EVERY achievement bullet from EVERY role. Do NOT summarize further. Do NOT merge bullets. Do NOT drop bullets.
2. **Subsections are part of the role**: When a role contains subsections (e.g., "Platform & Architecture", "Data Quality & Observability", "Key Achievements"), extract ALL bullets from ALL subsections as flat `highlights` entries. Do NOT lose subsection content.
3. **Highlights stay as strings**: Each highlight is a plain string. Never change the format to objects or add metadata.
4. **IDs**: Generate sequentially — `work_001`, `work_002`, ...; `edu_001`, ...; `cert_001`, ...; `proj_001`, ...
5. **Source**: Use the source string exactly as provided.
6. **Empty lists**: Use `[]` for sections with no data. Never omit a section.
7. **Null vs empty**: `null` for absent optional scalars. `[]` for absent lists.
8. **Dates**: Prefer `YYYY-MM`. Use `YYYY` only when month is unknown. `null` for completely unknown dates.
9. **Current role**: `end_date: null` for roles the candidate is still in.

## Output Schema

```json
{
  "version": "1.0",
  "updated_at": "<ISO8601 timestamp — use current date>",
  "sources": ["<source string provided>"],

  "basics": {
    "name": "<full name or null>",
    "email": "<email or null>",
    "phone": "<phone or null>",
    "location": { "city": "<city or empty string>", "country": "<ISO 3166-1 alpha-2 code or empty string>" },
    "url": "<personal website or null>",
    "profiles": [{ "network": "<LinkedIn|GitHub|etc>", "url": "<url>" }],
    "summary": "<candidate's own Summary or Profile section verbatim, or null if absent>",
    "selected_impact": ["<achievement bullet from standalone 'Selected Impact' or 'Highlights' sections NOT inside a specific role — empty list if none>"]
  },

  "work": [
    {
      "id": "<work_001, work_002, ...>",
      "company": "<company name>",
      "position": "<job title>",
      "location": "<city, country or null>",
      "start_date": "<YYYY-MM or YYYY>",
      "end_date": "<YYYY-MM or YYYY or null if current role>",
      "summary": "<1-2 sentence role summary synthesized from context, or null>",
      "context": "<1-2 sentences about situation/scope when candidate joined: company stage, team size, what they inherited — synthesized from bullets, or null if unclear>",
      "highlights": ["<EVERY achievement bullet from this role, including all subsections — string only>"],
      "skills_used": ["<concrete skill demonstrated in this role>"],
      "source": "<source string provided>"
    }
  ],

  "education": [
    {
      "id": "<edu_001, edu_002, ...>",
      "institution": "<school/university name>",
      "area": "<field of study>",
      "study_type": "<Bachelor|Master|PhD|Engineer|Certificate|Bootcamp|Associate>",
      "start_date": "<YYYY-MM or YYYY or null>",
      "end_date": "<YYYY-MM or YYYY or null>",
      "source": "<source string provided>"
    }
  ],

  "skills": [
    {
      "name": "<skill category name>",
      "level": "<junior|mid|senior|expert|null>",
      "keywords": ["<specific tool or technology>"],
      "narrative": "<descriptive paragraph about HOW the candidate uses this skill cluster, drawn from work history — null if cannot be inferred>",
      "source": "<source string provided>"
    }
  ],

  "languages": [
    { "language": "<language name>", "fluency": "<native|professional|conversational|basic>" }
  ],

  "certifications": [
    {
      "id": "<cert_001, cert_002, ...>",
      "name": "<certification name>",
      "issuer": "<issuing organisation or null>",
      "date": "<YYYY-MM or YYYY or null>",
      "source": "<source string provided>"
    }
  ],

  "projects": [
    {
      "id": "<proj_001, proj_002, ...>",
      "name": "<project name>",
      "description": "<what the project does or null>",
      "highlights": ["<outcome or achievement>"],
      "keywords": ["<technology or skill>"],
      "start_date": "<YYYY-MM or YYYY or null>",
      "end_date": "<YYYY-MM or YYYY or null>",
      "url": "<url or null>",
      "source": "<source string provided>"
    }
  ]
}
```

## CV Text

Source: {source}

{cv_text}
