"""Centralised environment-variable configuration for the API.

Reading order: env var → default shown below.
In staging, override LLM_MODEL_* with cheaper models (e.g. claude-haiku-4-5-20251001).
"""

import os

# ── Environment ──────────────────────────────────────────────────────────────
# "production" or "staging".  Controls staging gate middleware and auto-seed.
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

# ── LLM models ───────────────────────────────────────────────────────────────
# Empty string means "use the provider default" (anthropic: claude-sonnet-4-5-20250929,
# openai: gpt-4o).  Set to a cheaper model in staging, e.g. claude-haiku-4-5-20251001.
LLM_MODEL_CV: str = os.getenv("LLM_MODEL_CV", "")

# Model used for CV/profile parsing (onboard extraction).  Defaults to current hardcoded value.
LLM_MODEL_PARSING: str = os.getenv("LLM_MODEL_PARSING", "gpt-4o-mini")

# Model used for scoring LLM calls (reserved; no api-side scoring LLM currently).
LLM_MODEL_SCORING: str = os.getenv("LLM_MODEL_SCORING", "gpt-4o-mini")

# ── Notifications ─────────────────────────────────────────────────────────────
# Set to "false" in staging to suppress outbound email/notifications.
# The API itself has no outbound notification sends (agent handles email digest).
NOTIFICATIONS_ENABLED: bool = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"

# ── Staging snapshot ──────────────────────────────────────────────────────────
# URL of the production API, used by staging to download a DB snapshot.
# Empty in production.  Example: https://jobseeker-production.up.railway.app
PROD_API_URL: str = os.getenv("PROD_API_URL", "")

# Shared secret for the DB export/import endpoints (machine-to-machine).
# Fail-closed: empty string → all export requests return 403.
DB_EXPORT_API_KEY: str = os.getenv("DB_EXPORT_API_KEY", "")
