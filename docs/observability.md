# Observability Reference

Complete reference for logs (structlog) and analytics (PostHog) instrumentation
added in Phase 14. Covers every event, its properties, and how to query each
data source.

---

## Table of Contents

1. [PostHog — User Events](#posthog--user-events)
2. [PostHog — LLM Observability](#posthog--llm-observability)
3. [PostHog — Frontend](#posthog--frontend)
4. [Structured Logs — API (Railway)](#structured-logs--api-railway)
5. [Structured Logs — Agent (GitHub Actions)](#structured-logs--agent-github-actions)
6. [Environment Variables](#environment-variables)
7. [Querying PostHog](#querying-posthog)
8. [Querying Railway Logs](#querying-railway-logs)

---

## PostHog — User Events

`distinct_id` is always `str(user_id)` (the DB integer as a string).
All events are **no-ops when `POSTHOG_API_KEY` is not set**.

### Backend events (server-side via `api/analytics.py`)

#### `job_viewed`
Fired on `GET /api/jobs/{id}` (every detail page open).

| Property | Type | Description |
|---|---|---|
| `job_id` | `str` | Internal job ID |
| `company` | `str \| null` | Company name |
| `domain` | `str` | 30-value canonical domain enum |
| `rag_score` | `float \| null` | RAG score if available for this user |
| `heuristic_score` | `float \| null` | Heuristic score when no RAG score |
| `tier` | `str \| null` | `"A"` / `"B"` / `"C"` |

---

#### `job_applied`
Fired on `POST /api/jobs/{id}/apply`.

| Property | Type | Description |
|---|---|---|
| `job_id` | `str` | |
| `company` | `str \| null` | |
| `domain` | `str` | |
| `score` | `float \| null` | RAG score (null if heuristic only) |
| `tier` | `str \| null` | |

---

#### `job_dismissed`
Fired on `POST /api/jobs/{id}/dismiss`.

| Property | Type | Description |
|---|---|---|
| `job_id` | `str` | |
| `company` | `str \| null` | |
| `domain` | `str` | |
| `score` | `float \| null` | |
| `tier` | `str \| null` | |

---

#### `domain_overridden`
Fired on `PATCH /api/jobs/{id}/domain`.

| Property | Type | Description |
|---|---|---|
| `job_id` | `str` | |
| `old_domain` | `str` | Domain before override |
| `new_domain` | `str` | Domain after override |

---

#### `cv_generated`
Fired asynchronously (via `BackgroundTasks`) after `POST /api/jobs/{id}/generate-cv`
returns the file. Does not block the download.

| Property | Type | Description |
|---|---|---|
| `job_id` | `str` | |
| `company` | `str \| null` | |
| `provider` | `str` | `"anthropic"` or `"openai"` |
| `model` | `str` | e.g. `"claude-sonnet-4-5-20250929"` |
| `validation_passed` | `bool` | CV validator result (errors = false) |
| `fix_applied` | `bool` | Whether the auto-fix pass ran |
| `ats_passed` | `bool` | ATS audit result |
| `ats_violation_count` | `int` | Number of ATS violations found |

---

#### `skill_added`
Fired on `POST /api/onboard/profile/skills` (one-click add from job detail).

| Property | Type | Description |
|---|---|---|
| `skill_name` | `str` | Exact skill string added |
| `source` | `str` | Always `"job_detail"` |

---

#### `onboard_completed`
Fired on `POST /api/save-profile` (first-time onboarding only).

| Property | Type | Description |
|---|---|---|
| `profile_id` | `str` | 8-char hex profile ID |
| `domains_count` | `int` | Number of target domains configured |
| `skills_count` | `int` | Number of skills added |

---

#### `profile_saved`
Fired on `PATCH /api/profile` (every subsequent profile edit).

| Property | Type | Description |
|---|---|---|
| `domains_count` | `int` | |
| `skills_count` | `int` | |
| `fields_changed` | `list[str]` | Field names from `UpdateProfileRequest` |

---

### Agent events (server-side via `agent/main.py`)

`distinct_id` for agent events is `profile_id` (the string profile identifier,
e.g. `"juan"`).

#### `agent_pipeline_start`
Fired at the beginning of each pipeline run.

| Property | Type | Description |
|---|---|---|
| `profile_id` | `str` | Profile being processed |
| `mode` | `str` | `"normal"` / `"refresh"` / `"rescore"` / `"no_score"` |
| `notify` | `bool` | Whether email digest will be sent |

---

#### `agent_pipeline_complete`
Fired at the end of every pipeline run, including early exits.

| Property | Type | Description |
|---|---|---|
| `profile_id` | `str` | |
| `mode` | `str` | Same as `pipeline_start` |
| `status` | `str` | `"success"` / `"no_jobs"` / `"all_filtered"` |
| `duration_s` | `int` | Wall-clock seconds |
| `cost_usd` | `float` | Estimated OpenAI API cost |
| `total_jobs` | `int` | Jobs after filtering (success only) |
| `n_parsed` | `int` | Jobs sent to gpt-4o-mini parser |
| `n_scored` | `int` | Jobs sent to gpt-4o RAG scorer |
| `tier_a` | `int` | Jobs with tier A score (success only) |
| `tier_b` | `int` | Jobs with tier B score (success only) |
| `tier_c` | `int` | Jobs with tier C score (success only) |

> `no_jobs` and `all_filtered` exits have `n_parsed=0, n_scored=0` and
> no tier counts.

---

## PostHog — LLM Observability

LLM calls are wrapped with `posthog.ai.anthropic.Anthropic` and
`posthog.ai.openai.OpenAI`. PostHog automatically captures token usage
and latency for every call, linked to the `distinct_id` of the user.

| Call site | Model | `distinct_id` | `posthog_properties.source` |
|---|---|---|---|
| `api/cv/llm.py` — `generate_cv()` | `claude-sonnet-4-5-20250929` (default) | user DB ID | `"cv_generation"` |
| `api/onboard_utils.py` — profile extraction | `gpt-4o` | user DB ID | `"onboard_extraction"` |
| `agent/parser.py` — `parse_jd()` | `gpt-4o-mini` | profile_id | (none) |
| `agent/scorer.py` — `score_job()` | `gpt-4o` | profile_id | (none) |

These events appear in PostHog under **LLM observability** with:
- `$ai_input_tokens` — prompt tokens used
- `$ai_output_tokens` — completion tokens
- `$ai_latency` — seconds
- `$ai_model` — model name
- `$ai_provider` — `"anthropic"` or `"openai"`

> Requires `POSTHOG_API_KEY` to be set in both the API (Railway) and
> the agent (GitHub Actions) environments.

---

## PostHog — Frontend

The frontend uses `posthog-js` initialised from `VITE_POSTHOG_KEY`.

| What | How |
|---|---|
| **Page views** | Automatic on every route change (`capture_pageview: 'history_change'`) |
| **Session recording** | Enabled by default (no cross-origin iframes) |
| **User identity** | `identifyUser(id, email, name)` called when `/api/auth/me` returns data |
| **Session reset** | `resetPostHog()` called on logout — next visitor gets a fresh anonymous ID |

No custom `posthog.capture()` calls in the frontend; user actions are
captured server-side.

---

## Structured Logs — API (Railway)

The API uses `structlog` configured in `api/logging_config.py`.

**Format:**
- **Production** (`ENVIRONMENT=production`): single-line JSON to stdout.
  Railway reads `message` + `level` from each line.
- **Development**: human-readable `ConsoleRenderer` with colours.

**Common fields** (present on every log line):

| Field | Description |
|---|---|
| `message` | Event name / description |
| `level` | `info` / `warning` / `error` |
| `timestamp` | ISO 8601 UTC |

**Key API log events:**

| `message` | Source | Notable fields |
|---|---|---|
| `Login` | `api/routes/auth.py` | `user_id`, `email`, `profile_id`, `is_admin` |
| `Admin promoted on login` | `api/routes/auth.py` | `user_id`, `email` |
| `Readiness check` | `api/routes/health.py` | `status`, `db_ok`, `env_ok`, `warnings` |
| `PostHog initialized` | `api/analytics.py` | `host` |
| `First-time onboarding for user_id=…` | `api/routes/onboard.py` | `user_id`, `profile_id` |
| `Pipeline triggered for profile …` | `api/routes/onboard.py` | `profile_id` |
| `Profile YAML missing … regenerating` | `api/routes/onboard.py` | `profile_id` |
| `Regenerated searches for profile …` | `api/routes/onboard.py` | `profile_id` |
| `GitHub file sync OK: …` | `api/routes/onboard.py` | `gh_path` |

---

## Structured Logs — Agent (GitHub Actions)

The agent uses `structlog` configured in `agent/logging_setup.py`.

**Format:**
- **GitHub Actions** (`CI=true` or `LOG_FORMAT=json`): JSON.
- **Local dev**: `ConsoleRenderer` with colours.

**Key agent log events:**

| `event` | Source | Notable fields |
|---|---|---|
| `pipeline_start` | `agent/main.py` | `profile_id`, `mode`, `notify` |
| `scrape_complete` | `agent/main.py` | `total_jobs` |
| `cache_split` | `agent/main.py` | `cache_hits`, `cache_misses` |
| `db_cache_restore` | `agent/main.py` | `jobs_restored` |
| `heuristic_gate` | `agent/main.py` | `to_score`, `heuristic_only` |
| `pipeline_complete` | `agent/main.py` | `profile_id`, `mode`, `status`, `duration_s`, `n_parsed`, `n_scored` |
| `cache_updated` | `agent/main.py` | `jobs_added` |
| `rag_score_error` | `agent/main.py` | `error`, `exc_info` |
| `email_error` | `agent/main.py` | `error` |
| `email_skipped` | `agent/main.py` | `reason` |

> In GitHub Actions, these appear under the **digest** job step
> "Run profiles sequentially". Filter by `"event"` key in the JSON output.

---

## Environment Variables

| Variable | Component | Purpose |
|---|---|---|
| `POSTHOG_API_KEY` | API (Railway), Agent (GHA) | Enables PostHog. No-op if absent. |
| `POSTHOG_HOST` | API (Railway), Agent (GHA) | PostHog ingest host. Defaults to `https://eu.i.posthog.com`. Set to `https://us.i.posthog.com` for US Cloud. |
| `VITE_POSTHOG_KEY` | Frontend build | Enables posthog-js. No-op if absent. |
| `VITE_POSTHOG_HOST` | Frontend build | PostHog ingest host for the browser. Defaults to `https://eu.i.posthog.com`. |
| `ENVIRONMENT` | API (Railway) | Set to `"production"` to emit JSON logs |
| `LOG_FORMAT` | Agent (GHA) | Set to `"json"` for JSON logs (auto-set when `CI=true`) |

---

## Querying PostHog

### 1. Funnel: Browse → Apply
Use **Funnels** with steps:
1. `job_viewed`
2. `job_applied`

Filter by `tier = "A"` to see conversion rate for top jobs.

### 2. CV quality over time
Use **Trends** on `cv_generated`, breakdown by `validation_passed` and `ats_passed`.

### 3. Pipeline cost tracking
Use **Trends** on `agent_pipeline_complete`, formula sum on `cost_usd`.
Or group by `profile_id` to compare costs per user.

### 4. LLM token usage
Go to **LLM Observability** tab → filter by `$ai_provider` or `$ai_model`.
Available metrics: total tokens, cost estimate, latency P50/P95.

### 5. User identify
Each user is identified on login with `email` and `name` properties.
Search users by email in **Persons** to see their full event timeline.

### 6. Slow CV generation
In **LLM Observability**, sort by `$ai_latency` descending.
Cross-reference the `distinct_id` with the user's `cv_generated` event
to see which job triggered it.

---

## Querying Railway Logs

Railway logs are emitted as **single-line JSON** (one object per line).
All logs go to **stdout** (Railway classifies stderr as errors).

### Filter by event type
```
message:Login
message:pipeline_start
message:Readiness check
```

### Filter by user
```
user_id:42
profile_id:juan
```

### Find errors
```
level:error
```
Or use Railway's built-in **Errors** filter.

### Find slow requests / health issues
```
message:"Readiness check" db_ok:false
```

### Structlog JSON field reference
Every JSON line has at minimum:
```json
{
  "message": "Login",
  "level": "info",
  "timestamp": "2026-02-26T08:30:00.000Z",
  "user_id": 1,
  "email": "user@example.com"
}
```

Fields beyond `message`, `level`, and `timestamp` are event-specific
(see the tables above).
