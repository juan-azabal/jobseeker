# MANUAL: run after Phase 3.1-3.3 to validate quality
"""CV A/B test: compare old (raw JD) vs new (parsed distillation) prompt.

Usage:
    python scripts/cv_ab_test.py [--db data/jobseeker.db] [--limit 5]

Requires ANTHROPIC_API_KEY or OPENAI_API_KEY in environment.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _count_tokens_approx(text: str) -> int:
    """Rough token count: ~4 chars/token."""
    return len(text) // 4


def _phrase_coverage(cv_text: str, verbatim: list[str]) -> tuple[int, int]:
    """Return (matched, total) verbatim phrases found in the CV."""
    if not verbatim:
        return 0, 0
    cv_lower = cv_text.lower()
    matched = sum(1 for p in verbatim if p.lower() in cv_lower)
    return matched, len(verbatim)


def _fetch_candidate_jobs(db_path: str, limit: int) -> list[dict]:
    """Fetch jobs that have both raw JD and v1.5 fields."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT job_id, title, company, parsed
            FROM jobs
            WHERE parsed IS NOT NULL
              AND json_extract(parsed, '$.description') IS NOT NULL
              AND json_extract(parsed, '$.role_in_plain_english') IS NOT NULL
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _build_old_prompt(parsed: dict) -> str:
    """Legacy user prompt: raw JD as ## Job Description."""
    jd = parsed.get("description") or parsed.get("full_text") or "(no JD)"
    return f"## Job Description\n\n{jd}"


def _build_new_prompt(parsed: dict) -> str:
    """Plan-aware user prompt: parsed distillation via _format_job_summary."""
    from api.cv.prompt import _format_job_summary

    return _format_job_summary(parsed)


def _run_ab_test(jobs: list[dict], call_llm: bool) -> None:
    headers = ["Job", "Old tokens", "New tokens", "Savings", "Phrase cov (new)"]
    rows = []

    for job in jobs:
        parsed = json.loads(job["parsed"]) if isinstance(job["parsed"], str) else job["parsed"]

        old_prompt = _build_old_prompt(parsed)
        new_prompt = _build_new_prompt(parsed)

        old_tokens = _count_tokens_approx(old_prompt)
        new_tokens = _count_tokens_approx(new_prompt)
        savings_pct = round((old_tokens - new_tokens) / max(old_tokens, 1) * 100)

        verbatim = parsed.get("verbatim_for_cv") or []
        phrase_cov = "N/A (dry run)"

        if call_llm:
            from api.cv.llm import generate_cv

            try:
                cv_text = generate_cv(
                    system_prompt="Generate a brief CV. Output only CV markdown.",
                    user_prompt=new_prompt,
                )
                matched, total = _phrase_coverage(cv_text, verbatim)
                phrase_cov = f"{matched}/{total}" if total else "no phrases"
            except Exception as exc:
                phrase_cov = f"ERROR: {exc}"

        label = f"{job['company']} / {job['title'][:25]}"
        rows.append([label, old_tokens, new_tokens, f"{savings_pct}%", phrase_cov])

    col_widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    sep = "  ".join("-" * w for w in col_widths)

    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*row))


def main() -> None:
    parser = argparse.ArgumentParser(description="CV prompt A/B comparison")
    parser.add_argument("--db", default="data/jobseeker.db", help="SQLite DB path")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to test")
    parser.add_argument("--llm", action="store_true", help="Actually call the LLM (costs money)")
    args = parser.parse_args()

    db_path = args.db
    if not Path(db_path).exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    jobs = _fetch_candidate_jobs(db_path, args.limit)
    if not jobs:
        print("No jobs with both raw JD and v1.5 fields found.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(jobs)} candidate job(s). call_llm={args.llm}\n")
    _run_ab_test(jobs, call_llm=args.llm)


if __name__ == "__main__":
    main()
