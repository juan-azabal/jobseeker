"""Golden CV pipeline regression tests — deterministic, no LLM calls.

Validates that build_cv_plan(), build_cv_prompts(), and validate_cv()
produce consistent, expected output for known input scenarios.
Runs in CI without LLM env vars.
"""

import importlib
import json

import pytest

from api.cv.plan import build_cv_plan
from api.cv.validator import validate_cv
from api.cv.content_checks import check_company_hallucination, check_length_bounds

from tests.fixtures.cv_golden import (
    SCENARIO_A_CV,
    SCENARIO_A_JOB,
    SCENARIO_A_PROFILE,
    SCENARIO_B_CV,
    SCENARIO_B_JOB,
    SCENARIO_B_PROFILE,
    SCENARIO_C_JOB,
)


# ═══════════════════════════════════════════════════════════════════════════
# Golden Plan Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenPlan:
    """Verify build_cv_plan produces expected structure for golden scenarios."""

    @pytest.mark.parametrize(
        "job,cv",
        [
            (SCENARIO_A_JOB, SCENARIO_A_CV),
            (SCENARIO_B_JOB, SCENARIO_B_CV),
            (SCENARIO_C_JOB, SCENARIO_A_CV),
        ],
        ids=["data_pm_consultancy", "saas_pm_sparse", "eng_role_mismatch"],
    )
    def test_plan_has_required_keys(self, job, cv):
        plan = build_cv_plan(job, cv)
        assert "source_facts" in plan
        assert "jd_context" in plan
        assert "bullet_allocation" in plan

    def test_plan_extracts_title_from_cv(self):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        title = plan["source_facts"].get("title", "")
        assert "Product Manager" in title

    def test_plan_detects_consultancy(self):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        assert plan["jd_context"]["company_type"] == "consultancy"

    def test_plan_bullet_budget_within_limit(self):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        total = sum(v.get("budget", 0) for v in plan["bullet_allocation"].values())
        assert total <= 12

    def test_sparse_job_produces_valid_plan(self):
        """Scenario B has no scored data — plan should still build."""
        plan = build_cv_plan(SCENARIO_B_JOB, SCENARIO_B_CV)
        assert plan["source_facts"]["title"] != ""
        assert isinstance(plan["bullet_allocation"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# Golden Prompt Tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def mock_references_dir(tmp_path):
    """Create minimal reference files for prompt builder."""
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "generate-cv.md").write_text("Generate a CV for the candidate.")
    (refs / "ats-rules.md").write_text("ATS compliance rules.")
    return refs


class TestGoldenPrompts:
    """Verify build_cv_prompts produces expected content."""

    def _build(self, job, cv, plan, profile, monkeypatch, mock_references_dir):
        monkeypatch.setenv("CV_REFERENCES_DIR", str(mock_references_dir))
        import api.cv.prompt as prompt_mod

        importlib.reload(prompt_mod)
        return prompt_mod.build_cv_prompts(job, cv, plan, profile)

    def test_prompt_contains_job_title(self, monkeypatch, mock_references_dir):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        sys_p, usr_p = self._build(
            SCENARIO_A_JOB, SCENARIO_A_CV, plan, SCENARIO_A_PROFILE, monkeypatch, mock_references_dir
        )
        assert "Senior Product Manager" in sys_p or "Senior Product Manager" in usr_p

    def test_prompt_contains_skills(self, monkeypatch, mock_references_dir):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        sys_p, usr_p = self._build(
            SCENARIO_A_JOB, SCENARIO_A_CV, plan, SCENARIO_A_PROFILE, monkeypatch, mock_references_dir
        )
        combined = sys_p + usr_p
        assert "SQL" in combined or "Python" in combined or "dbt" in combined

    def test_plan_aware_no_full_jd(self, monkeypatch, mock_references_dir):
        """Plan-aware path should use parsed distillation, not raw JD."""
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        parsed = json.loads(SCENARIO_A_JOB["parsed"])
        full_desc = parsed["description"]
        _, usr_p = self._build(
            SCENARIO_A_JOB, SCENARIO_A_CV, plan, SCENARIO_A_PROFILE, monkeypatch, mock_references_dir
        )
        # Plan-aware path should NOT contain the full raw JD text
        assert full_desc not in usr_p

    def test_no_plan_includes_jd(self, monkeypatch, mock_references_dir):
        """Legacy path (no plan) should include the JD."""
        sys_p, usr_p = self._build(
            SCENARIO_A_JOB, SCENARIO_A_CV, None, SCENARIO_A_PROFILE, monkeypatch, mock_references_dir
        )
        combined = sys_p + usr_p
        assert "DataConsult" in combined


# ═══════════════════════════════════════════════════════════════════════════
# Validator Regression Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestValidatorRegression:
    """Verify validate_cv + content_checks catch known issues."""

    def test_slop_detected(self):
        bad_cv = "# Test User\n## Summary\nA strong track record of delivery.\n" + "\n".join(
            f"Line {i}" for i in range(35)
        )
        plan = {"source_facts": {}, "jd_context": {}, "bullet_allocation": {}}
        result = validate_cv(bad_cv, plan)
        codes = [e["code"] for e in result["errors"]]
        assert "slop_detected" in codes

    def test_hallucinated_company(self):
        bad_cv = "# User\n## Work Experience\n### FakeCompany, Berlin\n- Did things\n" + "\n".join(
            f"Line {i}" for i in range(35)
        )
        errors = check_company_hallucination(bad_cv, ["Acme Corp", "Beta Inc"])
        codes = [e["code"] for e in errors]
        assert "company_hallucinated" in codes

    def test_gerund_warning(self):
        cv = "# User\nSenior PM\n## Summary\nExperienced PM.\n## Work\n### Acme, BCN\n- Leading the team\n" + "\n".join(
            f"- Built thing {i}" for i in range(30)
        )
        plan = {"source_facts": {}, "jd_context": {}, "bullet_allocation": {}}
        result = validate_cv(cv, plan)
        codes = [w["code"] for w in result["warnings"]]
        assert "gerund_start" in codes

    def test_clean_cv_passes(self):
        plan = build_cv_plan(SCENARIO_A_JOB, SCENARIO_A_CV)
        result = validate_cv(SCENARIO_A_CV, plan)
        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_too_long_cv(self):
        long_cv = "\n".join(f"Line {i}" for i in range(130))
        warnings = check_length_bounds(long_cv)
        codes = [w["code"] for w in warnings]
        assert "cv_too_long" in codes

    def test_too_short_cv(self):
        short_cv = "\n".join(f"Line {i}" for i in range(15))
        warnings = check_length_bounds(short_cv)
        codes = [w["code"] for w in warnings]
        assert "cv_too_short" in codes
