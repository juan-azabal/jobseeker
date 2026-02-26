"""Tests for scoring rubric v2.0 file structure."""

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class TestScoringRubricV2:
    def test_rubric_v2_file_exists(self):
        """scoring-rubric-v2.md must exist."""
        path = PROMPTS_DIR / "scoring-rubric-v2.md"
        assert path.exists(), f"Missing: {path}"

    def test_rubric_v2_has_technical_depth_grade(self):
        """Rubric v2 must define technical_depth A/B/C grades."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert "technical_depth" in content
        # Accept any common format: "A:", **A**, "A"|B|C, A/B/C, etc.
        assert any(marker in content for marker in ('"A"', "'A'", "A:", "**A**", "A|B|C", "A/B/C"))

    def test_rubric_v2_has_profile_evidence_grade(self):
        """Rubric v2 must define profile_evidence A/B/C grades."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert "profile_evidence" in content

    def test_rubric_v2_output_format_has_grades(self):
        """Rubric v2 output JSON must include technical_depth and profile_evidence keys."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert '"technical_depth"' in content
        assert '"profile_evidence"' in content

    def test_rubric_v2_has_no_score_breakdown(self):
        """Rubric v2 must NOT contain score_breakdown (numerical sub-scores removed)."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert "score_breakdown" not in content

    def test_rubric_v2_has_no_numerical_composite(self):
        """Rubric v2 must NOT ask for a top-level score integer."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        # Top-level "score" key in JSON output removed; only grades
        assert '"score":' not in content

    def test_rubric_v2_has_strengths_gaps_verdict(self):
        """Rubric v2 must retain strengths, gaps, talking_points, one_line_verdict."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert "strengths" in content
        assert "gaps" in content
        assert "one_line_verdict" in content
        assert "talking_points" in content

    def test_rubric_v2_has_deal_breakers(self):
        """Rubric v2 must include deal_breakers field."""
        content = (PROMPTS_DIR / "scoring-rubric-v2.md").read_text()
        assert "deal_breakers" in content
