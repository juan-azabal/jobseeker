# Pattern: onboard.py

## Interface

```bash
python onboard.py --cv path/to/cv.docx [--profile custom_id]
```

- `--cv`: required. Must be a `.docx` file. If not `.docx`, print error and exit.
- `--profile`: optional. Overrides the auto-generated profile ID (derived from first name).

## Input

A `.docx` CV file. No PDF support — instruct the user to export from Google Docs or Word.

## Output

Three files written at the end:

| File | Description |
|---|---|
| `config/profiles/{id}.yaml` | Complete profile, loadable by `user_config.load_profile()` |
| `knowledge/{id}/cv.md` | Full CV as markdown — same file read by `scorer.load_cv_text()` |
| `config/seen_ids/{id}.txt` | Empty file, created if not already present |

## Flow

1. **docx → markdown** (`docx_to_markdown()`): preserves headings, bullets, bold, tables.
2. **LLM extraction** (`_extract_profile()`): single `gpt-4o-mini` call, prompt at `prompts/onboard-extraction.md`. Retries once on JSON parse or API error.
3. **Summary printed**: name, current/target level, domains, languages, location, skills count.
4. **3 interactive questions** via `input()`:
   - Salary minimum (EUR integer)
   - Location preference: a=remote only, b=remote+city, c=country, d=europe
   - Notification email
5. **Profile YAML generated** (`_build_profile_yaml()`) and all files written.
6. **Completion message** printed with run command.

## LLM call

- Model: `gpt-4o-mini`
- Prompt file: `prompts/onboard-extraction.md` (source of truth, read at runtime, module-level cache)
- Input: CV markdown text, capped at 12,000 chars
- Output: JSON object with: `name`, `languages`, `home_locations`, `current_level`, `track`, `target_level`, `domains`, `skills`, `exclude_companies`
- Retry: once on `JSONDecodeError` or API error, with stricter prompt appended

## Generated YAML structure

The YAML uses the new profile format (no raw seniority weights):

```yaml
user:
  id: "{id}"
  name: "{name}"
  email: "{email}"
  active: true
  languages: [...]
  home_locations: [...]
  location_preference: "a|b|c|d"

target:
  level: "{target_level}"   # seniority weights computed at load time by user_config.py
  track: "{track}"
  domains: {...}

scoring:
  rag_threshold: 25
  salary_min: {salary}

skills: [...]

knowledge:
  dir: "knowledge/{id}"
  profile_files:
    - "cv.md"
  collection_name: "{id}_profile"

stories: {}

preferences: "config/preferences.yaml"
searches: "config/searches.yaml"
watchlist: "config/watchlist.yaml"
seen_ids: "config/seen_ids/{id}.txt"
```

## Invariants

- Generated YAML must be loadable by `user_config.load_profile()` without modification.
- Seniority weights are **never** stored in the YAML — always computed at load time from `target.level` + `target.track` by `user_config.compute_seniority_weights()`.
- `knowledge/{id}/cv.md` is the exact file that `scorer.load_cv_text()` reads via `knowledge.profile_files`.
- `onboard.py` never modifies existing profiles (asks for confirmation before overwrite).
- `onboard.py` never modifies `user_config.py`, `scorer.py`, `parser.py`, or pipeline logic.

## Dependencies

- `python-docx` (new): `.docx` parsing
- `openai`, `pyyaml`, `python-dotenv` (already in requirements.txt)
