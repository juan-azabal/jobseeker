"""
Phase 2: RAG-based fit scoring.
Retrieves relevant chunks from the knowledge base and calls gpt-4o-mini
to score each parsed job against the user's profile.
"""

import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

SCORE_MODEL = "gpt-4o-mini"  # ADR-003: mini scores tier correctly ~90% of the time at 17x lower cost

# Scoring rubric v2 is read from prompts/scoring-rubric-v2.md (source of truth).
# _build_scoring_prompt() interpolates profile-specific values at runtime.
# v2: asks for 2 categorical grades (technical_depth, profile_evidence) instead of
# numerical sub-scores. Domain/seniority/location scoring is now deterministic in code.
_SCORING_RUBRIC_PATH = Path(__file__).parent / "prompts" / "scoring-rubric-v2.md"
_SCORING_RUBRIC_CACHE: str | None = None


def _get_scoring_rubric() -> str:
    """Load the scoring rubric template from file. Cached after first read."""
    global _SCORING_RUBRIC_CACHE
    if _SCORING_RUBRIC_CACHE is None:
        with open(_SCORING_RUBRIC_PATH) as f:
            content = f.read()
        # Strip markdown header lines and HTML comments
        lines = [line for line in content.splitlines() if not line.startswith("#") and not line.startswith("<!--")]
        _SCORING_RUBRIC_CACHE = "\n".join(lines).strip()
    return _SCORING_RUBRIC_CACHE


def _build_scoring_prompt(profile: dict) -> str:
    """Build the scoring prompt dynamically from the user profile."""
    user = profile.get("user", {})
    target = profile.get("target", {})
    name = user.get("name", "the candidate")
    domains = target.get("domains", {})
    # 3-tier fallback: seniority_weights (current) > seniority (legacy) > derive from level+track
    stored_sw = target.get("seniority_weights") or target.get("seniority")
    if stored_sw:
        seniority = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        from user_config import compute_seniority_weights

        seniority = compute_seniority_weights(target.get("level", ""), target.get("track", "ic"))

    # Role type from profile; fallback to generic "professional"
    role_type = target.get("role_type", "professional")

    # Geography from profile; fallback: derive from home_locations or "flexible location"
    geography = target.get("geography")
    if not geography:
        home_locs = user.get("home_locations") or []
        if home_locs:
            geography = ", ".join(home_locs) + " or remote"
        else:
            geography = "flexible location"

    top_domains = sorted(domains.items(), key=lambda x: -x[1])
    core_domains = [d for d, s in top_domains if s >= 12]
    adjacent_domains = [d for d, s in top_domains if 6 <= s < 12]
    _penalty_domains = [d for d, s in top_domains if s < 0]  # reserved for future penalty clause
    core_str = ", ".join(core_domains) if core_domains else "tech"

    # Adjacent clause: if adjacent domains exist, list them; otherwise omit
    if adjacent_domains:
        adjacent_clause = "Adjacent domains (" + ", ".join(adjacent_domains) + ")"
    else:
        adjacent_clause = "Tangentially related domains"

    # Graduated penalty clause: two tiers based on weight magnitude.
    # strong (≤ -15): cap domain_fit at 3 — candidate strongly avoids these.
    # mild  (< 0, > -15): cap domain_fit at 10 — candidate deprioritizes but doesn't reject.
    strong_domains = sorted(d for d, s in top_domains if s <= -15)
    mild_domains = sorted(d for d, s in top_domains if -15 < s < 0)

    if strong_domains or mild_domains:
        lines = ["PENALTY — domains the candidate has explicitly deprioritized:"]
        if strong_domains:
            lines.append(
                f"- If the role's PRIMARY domain is {', '.join(strong_domains)}: "
                "cap domain_fit at 3. The candidate strongly avoids these domains."
            )
        if mild_domains:
            lines.append(
                f"- If the role's PRIMARY domain is {', '.join(mild_domains)}: "
                "cap domain_fit at 10. The candidate deprioritizes but does not reject these domains."
            )
        penalty_clause = "\n".join(lines) + "\n"
    else:
        penalty_clause = ""

    top_levels = sorted(seniority.items(), key=lambda x: -x[1])
    target_levels = [lvl for lvl, s in top_levels if s >= 10]
    target_str = "/".join(target_levels) if target_levels else "Senior"

    # Substitute only the known placeholders; leave JSON braces in the rubric untouched.
    rubric = _get_scoring_rubric()
    return (
        rubric.replace("{name}", name)
        .replace("{role_type}", role_type)
        .replace("{core_str}", core_str)
        .replace("{adjacent_clause}", adjacent_clause)
        .replace("{target_str}", target_str)
        .replace("{geography}", geography)
        .replace("{penalty_clause}", penalty_clause)
    )


# ---------------------------------------------------------------------------
# Programmatic story mapping (no RAG, no API calls)
# Story tags loaded from user profile (config/profiles/<id>.yaml → stories: {})
# If no stories defined in profile, returns [] (graceful no-op)
# ---------------------------------------------------------------------------

_TOP_N_STORIES = 4  # max stories to recommend per job


def _map_stories(job, story_tags: dict):
    """Programmatically map job skills/themes to interview stories.

    story_tags: dict of {keyword: [story_id, ...]} from the user profile.
    If empty, returns []. No API calls.
    """
    if not story_tags:
        return []

    parsed = job.get("parsed") or {}

    # Build bag of text to match against
    text_parts = [
        job.get("title", ""),
        parsed.get("domain", ""),
        parsed.get("responsibilities_summary", ""),
        " ".join(parsed.get("truly_required") or parsed.get("must_have_skills") or []),
        " ".join(parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or []),
        " ".join(parsed.get("technical_stack") or []),
        " ".join(parsed.get("key_phrases") or []),
    ]
    text = " ".join(text_parts).lower()

    story_votes = {}
    for keyword, stories in story_tags.items():
        if keyword in text:
            for rank, story in enumerate(stories):
                # Primary story (rank 0) gets more weight than alternatives
                weight = 2 if rank == 0 else 1
                story_votes[story] = story_votes.get(story, 0) + weight

    if not story_votes:
        return []

    # Sort by votes desc, then story ID asc for tie-breaking
    ranked = sorted(story_votes.items(), key=lambda x: (-x[1], x[0]))
    return [s for s, _ in ranked[:_TOP_N_STORIES]]


def _build_scoring_input(job, chunks):
    """Build the user message combining parsed JD and retrieved profile chunks."""

    parsed = job.get("parsed", {})

    jd_summary = f"""## Job Description (parsed)
Title: {job.get("title", "?")}
Company: {job.get("company", "?")}
Location: {job.get("location", "?")} ({parsed.get("location_type", "?")})
Seniority: {parsed.get("seniority", "?")}
Domain: {parsed.get("domain", "?")}
Salary: {parsed.get("salary_mentioned", "not mentioned")}

Must-have skills: {", ".join(parsed.get("truly_required") or parsed.get("must_have_skills") or [])}
Nice-to-have: {", ".join(parsed.get("preferred_skills") or parsed.get("nice_to_have_skills") or [])}
Technical stack: {", ".join(parsed.get("technical_stack") or [])}
Responsibilities: {parsed.get("responsibilities_summary", "")}
Red flags: {", ".join(parsed.get("red_flags") or [])}
Key phrases: {", ".join(parsed.get("key_phrases") or [])}"""

    profile_context = "\n\n---\n\n".join([f"[{c['source']} / {c['section']}]\n{c['text']}" for c in chunks])

    return f"""{jd_summary}

## Candidate profile (relevant excerpts)

{profile_context}"""


def score_job(job, collection, profile: dict, n_chunks=8, knowledge_dir: str = ""):
    """
    Score a single parsed job against the knowledge base.
    Returns the job dict enriched with a 'rag_score' field.
    """
    if not job.get("parsed"):
        job["rag_score"] = None
        job["rag_error"] = "no parsed data"
        return job

    from vectorstore import retrieve_relevant_chunks

    # Build a rich query from the JD for retrieval
    parsed = job["parsed"]
    query_parts = [
        job.get("title", ""),
        " ".join((parsed.get("truly_required") or parsed.get("must_have_skills") or [])[:5]),
        " ".join(parsed.get("technical_stack", [])[:5]),
        parsed.get("responsibilities_summary", "")[:200],
        parsed.get("domain", ""),
    ]
    query = " ".join(p for p in query_parts if p)

    try:
        chunks = retrieve_relevant_chunks(query, collection, n_results=n_chunks)
    except Exception as e:
        job["rag_score"] = None
        job["rag_error"] = f"retrieval error: {e}"
        return job

    user_content = _build_scoring_input(job, chunks)

    if knowledge_dir:
        cv_path = os.path.join(knowledge_dir, "master_cv.json")
        if os.path.exists(cv_path):
            try:
                with open(cv_path) as f:
                    master_cv = json.load(f)
                from shared.master_cv_scoring import build_scoring_context  # noqa: PLC0415

                enriched = build_scoring_context(master_cv, parsed)
                user_content += f"\n\n## Master CV Evidence\n{enriched}"
            except Exception:
                pass  # non-fatal: score without enriched context

    if os.environ.get("POSTHOG_API_KEY"):
        try:
            from posthog.ai.openai import OpenAI as _PhOpenAI  # noqa: PLC0415

            client = _PhOpenAI()
        except Exception:
            from openai import OpenAI  # noqa: PLC0415

            client = OpenAI()
    else:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI()
    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=SCORE_MODEL,
                messages=[
                    {"role": "system", "content": _build_scoring_prompt(profile)},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=800,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

            score_data = json.loads(raw.strip())
            job["rag_score"] = score_data
            job["rag_error"] = None
            return job

        except json.JSONDecodeError as e:
            job["rag_score"] = None
            job["rag_error"] = f"JSON parse error: {e}"
            return job

        except Exception as e:
            err_str = str(e)
            # Retry on rate limit (429) with exponential backoff
            if "429" in err_str and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                time.sleep(wait)
                continue
            job["rag_score"] = None
            job["rag_error"] = f"API error: {e}"
            return job

    return job


def score_all(jobs, collection, profile: dict, max_workers=2, knowledge_dir: str = ""):
    """
    Score all parsed jobs concurrently.
    Uses fewer workers than parser to respect rate limits.
    Returns enriched job list.
    """
    scoreable = [j for j in jobs if j.get("parsed")]
    print(f"\nRAG scoring {len(scoreable)} jobs with {SCORE_MODEL} ({max_workers} concurrent)...")

    scored = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(score_job, job, collection, profile, knowledge_dir=knowledge_dir): job for job in scoreable
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                job = future.result()
                if job.get("rag_score"):
                    scored += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                original_job = futures[future]
                original_job["rag_score"] = None
                original_job["rag_error"] = f"unexpected error: {e}"
            if done % 5 == 0 or done == len(scoreable):
                print(f"   Scored {done}/{len(scoreable)}...")

    print(f"Scoring complete: {scored} OK, {errors} errors")
    if errors > 0:
        # Print first error for diagnostics
        for job in scoreable:
            if job.get("rag_error"):
                print(f"   First score error: {job['rag_error']}")
                break
    return jobs


if __name__ == "__main__":
    import sys
    from user_config import load_profile, list_profiles
    from vectorstore import build_vectorstore

    profile_id = sys.argv[1] if len(sys.argv) > 1 else list_profiles()[0]
    profile = load_profile(profile_id)
    print(f"Testing scorer with profile: {profile_id}")

    # Build/load vectorstore
    collection = build_vectorstore(profile=profile)

    # Test with a synthetic job
    test_job = {
        "id": "test001",
        "title": "Principal Product Manager - Data Platform",
        "company": "Acme Data Co",
        "location": "Remote, Europe",
        "description": "Looking for a Principal PM to own our event tracking and analytics platform...",
        "job_url": "https://example.com",
        "site": "test",
        "parsed": {
            "seniority": "principal",
            "location_type": "remote",
            "domain": "data",
            "must_have_skills": ["data platform", "event tracking", "SQL", "stakeholder management"],
            "nice_to_have_skills": ["Snowplow", "Kafka", "dbt"],
            "technical_stack": ["Snowflake", "Kafka", "dbt", "Python"],
            "responsibilities_summary": "Own the data platform strategy, define event taxonomy, align 5+ engineering teams.",
            "salary_mentioned": "120000-140000 EUR",
            "red_flags": [],
            "key_phrases": ["data platform ownership", "event taxonomy", "real-time pipeline"],
        },
    }

    result = score_job(test_job, collection, profile)
    if result.get("rag_score"):
        s = result["rag_score"]
        print(f"\nScore: {s['score']}/100")
        print(f"Verdict: {s['one_line_verdict']}")
        print(f"Strengths: {[x['claim'] for x in s.get('strengths', [])]}")
        print(f"Gaps: {[x['gap'] for x in s.get('gaps', [])]}")
        print(f"Stories: {s.get('stories_to_prepare', [])}")
    else:
        print(f"Error: {result.get('rag_error')}")
