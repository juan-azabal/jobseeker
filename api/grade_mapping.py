"""Grade-to-points mapping — re-exports from shared/scoring_core.py.

Single source of truth is shared/scoring_core.GRADE_POINTS and grade_to_points().
This module exists for backward compatibility with existing import sites.
"""

from shared.scoring_core import GRADE_POINTS, grade_to_points

__all__ = ["GRADE_POINTS", "grade_to_points"]
