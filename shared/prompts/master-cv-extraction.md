# Master CV JSON Extraction Prompt
# Version: 1.0

You are a CV parsing specialist. Extract ALL structured career data from the CV text below and return ONLY valid JSON matching the schema exactly. No explanation, no markdown fences, no additional text.

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
    "profiles": [{ "network": "<LinkedIn|GitHub|etc>", "url": "<url>" }]
  },

  "work": [
    {
      "id": "<work_001, work_002, ...>",
      "company": "<company name>",
      "position": "<job title>",
      "location": "<city, country or null>",
      "start_date": "<YYYY-MM or YYYY>",
      "end_date": "<YYYY-MM or YYYY or null if current role>",
      "summary": "<1-2 sentence role summary or null>",
      "highlights": ["<achievement bullet>"],
      "skills_used": ["<concrete skill demonstrated>"],
      "source": "<source string provided>"
    }
  ],

  "education": [
    {
      "id": "<edu_001, edu_002, ...>",
      "institution": "<school/university name>",
      "area": "<field of study>",
      "study_type": "<Bachelor|Master|PhD|Certificate|Bootcamp|Associate>",
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

## Rules

1. **IDs**: Generate sequentially — `work_001`, `work_002`, ...; `edu_001`, ...; `cert_001`, ...; `proj_001`, ...
2. **Source**: Use the source string exactly as provided in the user message.
3. **Highlights**: Must be specific, quantified achievement bullets. NOT vague summaries.
   - GOOD: "Increased checkout conversion by 18% by redesigning the payment flow"
   - GOOD: "Launched 3 product integrations serving 50K daily active users"
   - BAD: "Responsible for product management" (too vague)
   - BAD: "Worked on various projects" (no specificity)
4. **skills_used**: List concrete skills actually demonstrated in that role. Derive from context if not stated explicitly.
5. **Empty lists**: Use `[]` for sections with no data. Never omit a section.
6. **Null vs empty**: Use `null` for optional scalar fields that are absent. Use `[]` for absent lists.
7. **Dates**: Prefer `YYYY-MM` format. Use `YYYY` only when month is unknown. `null` for completely unknown dates.
8. **Current role**: Set `end_date: null` for roles the candidate is still in.
9. **Output**: JSON only. No markdown code fences. No explanation text before or after.

## CV Text

Source: {source}

{cv_text}
