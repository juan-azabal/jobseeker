"""Grade-to-points conversion for hybrid scoring.

LLM grades (A/B/C) map to fixed point values used by hybrid_score().
Default of 10 (midpoint) is used for unscored jobs.
"""

GRADE_POINTS: dict[str, int] = {"A": 20, "B": 12, "C": 5}


def grade_to_points(grade: str | None, default: int = 10) -> int:
    """Convert a categorical grade (A/B/C) to integer points.

    Args:
        grade: Grade string ("A", "B", or "C"). Case-insensitive.
        default: Points to return when grade is None or unrecognised.

    Returns:
        Integer point value.
    """
    if grade is None:
        return default
    return GRADE_POINTS.get(grade.upper(), default)
