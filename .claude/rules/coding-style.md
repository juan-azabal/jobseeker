# Coding Conventions

- Error handling: modules called by main.py must not raise. Catch, log, return partial/False.
- Prompts: NEVER inline prompt strings in Python. Source of truth is prompts/*.md, read at runtime.
- New dependencies: add to requirements.txt immediately.
- Output language: English (code, docs, comments). Spanish only in user-facing conversation.
- Config: user-specific settings in config/profiles/{id}.yaml. Shared defaults in config/preferences.yaml.
- Dedup: always use make_job_id() from scraper.py. Never create alternative ID functions.
- Seniority weights: computed at load time from target.level + target.track. Never stored in YAML.
