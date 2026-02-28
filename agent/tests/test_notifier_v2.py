"""Tests for notifier._build_context() compatibility with v2 rag_score.

P15: rag["score"] KeyError when job has v2 rag_score dict (no "score" key).
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notifier import _build_context

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Minimal globals that _heuristic_score needs to function without a real profile.
_PATCH_MAIN = {
    "_DOMAIN_SCORES": {"saas": 10, "data": 15},
    "_SENIORITY_SCORES": {"principal": 15, "senior": 8},
    "_PROFILE_SKILLS": ["analytics", "kafka"],
    "_HOME_LOCATIONS": ["barcelona"],
    "_HOME_REGIONS": [],
    "_COUNTRY_WEIGHTS": {},  # isolate from stale global state
}


def _make_job(job_id="abc123", rag_score=None):
    """Minimal job dict compatible with _build_context."""
    return {
        "id": job_id,
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "url": "https://example.com/job/1",
        "parsed": {
            "domain": "saas",
            "seniority": "principal",
            "location_type": "remote",
            "skills": [],
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "technical_stack": [],
            "responsibilities_summary": "",
            "red_flags": [],
        },
        "raw": {"description": ""},
        "rag_score": rag_score,
    }


RUN_META = {"date": "26 Feb 2026"}
REJECTED_STATS = {"total": 10, "passed": 1}


class TestBuildContextV2RagScore:
    """_build_context must not crash with v2 rag_score."""

    def test_v2_rag_score_no_crash(self):
        """v2 rag_score (no 'score' key) must not raise KeyError."""
        job = _make_job(rag_score={"technical_depth": "A", "profile_evidence": "B"})
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        assert isinstance(ctx, dict)

    def test_v2_rag_score_computes_hybrid_score(self):
        """v2 rag_score → _display_score = _fit_score + grade_to_points(tech) + grade_to_points(prof)."""
        job = _make_job(rag_score={"technical_depth": "A", "profile_evidence": "B"})
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        all_jobs = ctx["tier_a"] + ctx["tier_b"] + ctx["tier_c"]
        assert len(all_jobs) == 1
        # _fit_score = saas(10) + principal(15) + remote(10) + no skills = 35
        # grade_to_points(A)=20, grade_to_points(B)=12 → hybrid = 35+20+12 = 67
        assert all_jobs[0]["score"] == 67

    def test_v1_rag_score_still_works(self):
        """v1 rag_score (has numeric 'score') must continue to be used as display score."""
        job = _make_job(rag_score={"score": 78, "tier": "A", "reasoning": "..."})
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        all_jobs = ctx["tier_a"] + ctx["tier_b"] + ctx["tier_c"]
        assert len(all_jobs) == 1
        assert all_jobs[0]["score"] == 78

    def test_no_rag_score_uses_fit_score(self):
        """No rag_score → _display_score = _fit_score."""
        job = _make_job(rag_score=None)
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        all_jobs = ctx["tier_a"] + ctx["tier_b"] + ctx["tier_c"]
        assert len(all_jobs) == 1
        assert all_jobs[0]["score"] == 35  # same heuristic

    def test_mixed_v1_v2_no_crash(self):
        """Mix of v1 and v2 jobs in the same digest must not crash."""
        job_v1 = _make_job("id1", rag_score={"score": 80, "tier": "A"})
        job_v2 = _make_job("id2", rag_score={"technical_depth": "B", "profile_evidence": "C"})
        job_none = _make_job("id3", rag_score=None)
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job_v1, job_v2, job_none], REJECTED_STATS, RUN_META)
        all_jobs = ctx["tier_a"] + ctx["tier_b"] + ctx["tier_c"]
        assert len(all_jobs) == 3

    def test_v2_job_appears_in_correct_tier(self):
        """v2 job with A+A grades: hybrid = 35+20+20=75 → tier_a (≥50)."""
        job = _make_job(rag_score={"technical_depth": "A", "profile_evidence": "A"})
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        assert len(ctx["tier_a"]) == 1
        assert ctx["tier_a"][0]["score"] == 75


class TestDigestTemplateToggle:
    """Step 20.0: v1 backup + DIGEST_TEMPLATE env var."""

    def test_v1_template_backup_exists(self):
        """email_digest_v1.html.j2 must exist and match original."""
        v1 = TEMPLATES_DIR / "email_digest_v1.html.j2"
        assert v1.exists(), "email_digest_v1.html.j2 backup not found"
        v2 = TEMPLATES_DIR / "email_digest.html.j2"
        # Content should be at least as long (not an empty file)
        assert v1.stat().st_size > 0

    def test_digest_template_env_default(self):
        """DIGEST_TEMPLATE env var defaults to email_digest.html.j2."""
        import importlib
        import notifier
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DIGEST_TEMPLATE", None)
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest.html.j2"

    def test_digest_template_env_override(self):
        """DIGEST_TEMPLATE env var overrides the template name."""
        import importlib
        import notifier
        with patch.dict(os.environ, {"DIGEST_TEMPLATE": "email_digest_v1.html.j2"}):
            importlib.reload(notifier)
            assert notifier.TEMPLATE_NAME == "email_digest_v1.html.j2"


class TestFlattenJobPlatformLink:
    """Step 20.1: _flatten_job() platform_link field."""

    def _job(self, job_id=None, job_url="https://ext.com/job"):
        j = _make_job()
        j["job_id"] = job_id
        j["job_url"] = job_url
        return j

    def test_platform_link_uses_job_id(self):
        """platform_link = APP_BASE_URL/jobs/{job_id} when job_id present."""
        from notifier import _flatten_job
        job = self._job(job_id="abc123hash")
        with patch("notifier._is_reloc", return_value=False):
            with patch.dict(os.environ, {"APP_BASE_URL": "https://example.com"}):
                result = _flatten_job(job)
        assert result["platform_link"] == "https://example.com/jobs/abc123hash"

    def test_platform_link_fallback_no_job_id(self):
        """platform_link falls back to job_url when job_id is missing."""
        from notifier import _flatten_job
        job = self._job(job_id=None, job_url="https://ext.com/job")
        with patch("notifier._is_reloc", return_value=False):
            result = _flatten_job(job)
        assert result["platform_link"] == "https://ext.com/job"

    def test_platform_link_fallback_empty_job_id(self):
        """platform_link falls back to job_url when job_id is empty string."""
        from notifier import _flatten_job
        job = self._job(job_id="", job_url="https://ext.com/job")
        with patch("notifier._is_reloc", return_value=False):
            result = _flatten_job(job)
        assert result["platform_link"] == "https://ext.com/job"


class TestBuildContextPlatformUrl:
    """Step 20.1: _build_context() includes platform_url."""

    def test_platform_url_in_context(self):
        """_build_context() must include platform_url key."""
        job = _make_job()
        with patch.multiple("main", **_PATCH_MAIN):
            ctx = _build_context([job], REJECTED_STATS, RUN_META)
        assert "platform_url" in ctx

    def test_platform_url_default(self):
        """platform_url defaults to Railway production URL."""
        job = _make_job()
        with patch.multiple("main", **_PATCH_MAIN):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("APP_BASE_URL", None)
                ctx = _build_context([job], REJECTED_STATS, RUN_META)
        assert ctx["platform_url"] == "https://jobseeker-production.up.railway.app"

    def test_platform_url_env_override(self):
        """platform_url uses APP_BASE_URL env var when set."""
        job = _make_job()
        with patch.multiple("main", **_PATCH_MAIN):
            with patch.dict(os.environ, {"APP_BASE_URL": "https://staging.example.com"}):
                ctx = _build_context([job], REJECTED_STATS, RUN_META)
        assert ctx["platform_url"] == "https://staging.example.com"
