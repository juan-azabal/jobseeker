"""
JD Parser: extracts structured requirements from job descriptions using OpenAI.
Instrumented with Langfuse for observability.
"""

import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from preseed import preseed_parsed

load_dotenv()

# Pre-seeded fields that are factual (structured data wins over LLM interpretation).
# LLM wins for everything else (domain, skills, responsibilities, etc.).
_FACTUAL_FIELDS = frozenset(
    {
        "seniority",
        "salary_mentioned",
        "location_type",
        "years_experience_min",
        "years_experience_max",
        "locations_mentioned",
    }
)


def _make_openai_client():
    """Return an OpenAI client wrapped with PostHog AI observability when available.

    Falls back to a plain openai.OpenAI() when POSTHOG_API_KEY is absent or the
    posthog.ai wrapper is unavailable (e.g. import error in minimal envs).
    The PostHog AI wrapper tracks token usage and latency; the plain client does not.
    """
    if os.environ.get("POSTHOG_API_KEY"):
        try:
            from posthog.ai.openai import OpenAI as _PhOpenAI  # noqa: PLC0415

            return _PhOpenAI()
        except Exception:
            pass
    from openai import OpenAI  # noqa: PLC0415

    return OpenAI()


# Optional: Langfuse tracing
try:
    from langfuse import Langfuse

    langfuse = Langfuse()
    LANGFUSE_ENABLED = True
    print("Langfuse tracing enabled")
except Exception:
    LANGFUSE_ENABLED = False


# Parser prompt loaded from prompts/parser-prompt.md (source of truth).
# Cached at module level — read once per process.
_PARSER_PROMPT_PATH = Path(__file__).parent / "prompts" / "parser-prompt.md"
_PARSER_PROMPT_CACHE: str | None = None


def _get_parser_prompt() -> str:
    global _PARSER_PROMPT_CACHE
    if _PARSER_PROMPT_CACHE is None:
        with open(_PARSER_PROMPT_PATH) as f:
            content = f.read()
        # Strip markdown header lines and HTML comments
        lines = [line for line in content.splitlines() if not line.startswith("#") and not line.startswith("<!--")]
        _PARSER_PROMPT_CACHE = "\n".join(lines).strip()
    return _PARSER_PROMPT_CACHE


def parse_jd(job, model="gpt-4o-mini"):
    """Parse a single job description. Returns the job dict enriched with parsed data."""

    description = job.get("description", "")
    if not description or len(description) < 100:
        job["parsed"] = None
        job["parse_error"] = "description too short or missing"
        return job

    if len(description) > 8000:
        description = description[:8000] + "\n[...truncated]"

    client = _make_openai_client()

    # Pre-seed from structured scraper fields (reduces LLM hallucination on factual data)
    seed = preseed_parsed(job)

    system_prompt = _get_parser_prompt()
    if seed:
        seed_json = json.dumps(seed, ensure_ascii=False)
        system_prompt = (
            system_prompt + "\n\nThe following fields have been pre-determined from structured source data. "
            "Use these values unless the job description CLEARLY contradicts them:\n" + seed_json
        )

    user_content = f"""Job Title: {job["title"]}
Company: {job["company"]}
Location: {job.get("location", "Not specified")}

Job Description:
{description}"""

    trace = None
    generation = None
    if LANGFUSE_ENABLED:
        try:
            trace = langfuse.trace(
                name="parse_jd",
                metadata={
                    "job_id": job["id"],
                    "company": job["company"],
                    "title": job["title"],
                },
            )
            generation = trace.generation(
                name="jd_extraction",
                model=model,
                input=user_content[:500],
            )
        except Exception:
            pass

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = json.loads(raw)

        # Normalize renamed fields for backward compat with old LLM outputs.
        # v1.5 renames: must_have_skills → truly_required, nice_to_have_skills → preferred_skills.
        if "must_have_skills" in parsed and "truly_required" not in parsed:
            parsed["truly_required"] = parsed["must_have_skills"]
        if "nice_to_have_skills" in parsed and "preferred_skills" not in parsed:
            parsed["preferred_skills"] = parsed["nice_to_have_skills"]

        # Default new v1.5 fields if LLM omits them.
        parsed.setdefault("role_in_plain_english", None)
        parsed.setdefault("company_context", None)
        parsed.setdefault("verbatim_for_cv", [])
        parsed.setdefault("truly_required", parsed.get("must_have_skills") or [])
        parsed.setdefault("preferred_skills", parsed.get("nice_to_have_skills") or [])

        # Apply factual pre-seed overrides (structured data wins for factual fields).
        # Log divergences for analysis.
        for field, value in seed.items():
            if field in _FACTUAL_FIELDS:
                llm_val = parsed.get(field)
                if llm_val is not None and llm_val != value:
                    import structlog as _sl

                    _sl.get_logger("agent.parser").info(
                        "preseed_divergence",
                        job_id=job.get("id"),
                        field=field,
                        preseed=value,
                        llm=llm_val,
                    )
                parsed[field] = value

        job["parsed"] = parsed
        job["parse_error"] = None

        if generation:
            try:
                generation.end(
                    output=raw[:500],
                    usage={
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                    },
                )
            except Exception:
                pass

    except json.JSONDecodeError as e:
        job["parsed"] = None
        job["parse_error"] = f"JSON parse error: {e}"

    except Exception as e:
        job["parsed"] = None
        job["parse_error"] = f"API error: {e}"

    return job


def parse_all(jobs, model="gpt-4o-mini", max_workers=8):
    """Parse all job descriptions concurrently. Returns enriched job list."""
    print(f"\nParsing {len(jobs)} job descriptions with {model} ({max_workers} concurrent)...")

    parsed_count = 0
    error_count = 0
    first_error = None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(parse_jd, job, model): i for i, job in enumerate(jobs)}

        done = 0
        for future in as_completed(futures):
            done += 1
            job = future.result()
            if job.get("parsed"):
                parsed_count += 1
            else:
                error_count += 1
                if first_error is None:
                    first_error = job.get("parse_error", "unknown error")

            if done % 10 == 0 or done == len(jobs):
                print(f"   Parsed {done}/{len(jobs)}...")

    print(f"\nParsing complete: {parsed_count} OK, {error_count} errors")
    if error_count > 0 and first_error:
        print(f"   First parse error: {first_error}")

    if LANGFUSE_ENABLED:
        try:
            langfuse.flush()
        except Exception:
            pass

    return jobs
