"""Parse quality metrics — batch analysis of parsed job fields.

Pure functions for computing null rates, error rates, and field coverage
after a parse batch. No I/O, no LLM calls.
"""

_CRITICAL_FIELDS = ("domain", "seniority", "location_type")


def compute_parse_metrics(jobs: list[dict]) -> dict:
    """Compute batch parse quality metrics.

    Args:
        jobs: List of job dicts after parse_all(). Each has ``parsed``
              (dict or None) and optionally ``parse_error``.

    Returns:
        Dict with keys:
            parse_error_rate — fraction of jobs with no parsed data
            total_parsed     — count of successfully parsed jobs
            total_errors     — count of parse failures
            null_field_rates — {field: fraction_null} for critical fields
    """
    if not jobs:
        return {
            "parse_error_rate": 0.0,
            "total_parsed": 0,
            "total_errors": 0,
            "null_field_rates": {},
        }

    parsed_jobs = [j for j in jobs if j.get("parsed")]
    total = len(jobs)
    total_parsed = len(parsed_jobs)
    total_errors = total - total_parsed

    null_field_rates: dict[str, float] = {}
    if parsed_jobs:
        for field in _CRITICAL_FIELDS:
            null_count = sum(1 for j in parsed_jobs if j["parsed"].get(field) is None)
            null_field_rates[field] = round(null_count / total_parsed, 3)

        skills_null = sum(1 for j in parsed_jobs if _skills_empty(j["parsed"]))
        null_field_rates["skills"] = round(skills_null / total_parsed, 3)

    return {
        "parse_error_rate": round(total_errors / total, 3),
        "total_parsed": total_parsed,
        "total_errors": total_errors,
        "null_field_rates": null_field_rates,
    }


def _skills_empty(parsed: dict) -> bool:
    """Check if skills fields are empty (backward compat)."""
    skills = parsed.get("truly_required") or parsed.get("must_have_skills")
    return not skills
