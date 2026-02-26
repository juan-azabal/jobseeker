"""Tests for P17: gap_tracker stores meaningful score for v2 rag_score jobs."""

import sys
import os
import json
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gap_tracker import append_gap_history

PROFILE = {"user": {"id": "test_user"}}


def _make_job(job_id="j1", rag_score=None):
    return {
        "id": job_id,
        "title": "Head of Product",
        "company": "Acme",
        "location": "Remote",
        "job_url": "https://example.com",
        "parsed": {"domain": "saas", "seniority": "principal", "location_type": "remote"},
        "_salary_eur": 120000,
        "rag_score": rag_score,
    }


def _read_entries(history_dir, user_id="test_user"):
    filepath = os.path.join(history_dir, f"{user_id}.jsonl")
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestGapTrackerV2Score:
    """append_gap_history must record non-zero scores for v2 jobs (P17)."""

    def test_v1_score_stored_as_is(self):
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score={"score": 78, "strengths": [], "gaps": []})
            append_gap_history([job], PROFILE, history_dir=d)
            entries = _read_entries(d)
        assert len(entries) == 1
        assert entries[0]["score"] == 78

    def test_v2_score_non_zero(self):
        """v2 rag_score must produce a non-zero score (not 0 as in the bug)."""
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score={
                "technical_depth": "A", "profile_evidence": "B",
                "strengths": [], "gaps": [],
            })
            append_gap_history([job], PROFILE, history_dir=d)
            entries = _read_entries(d)
        assert len(entries) == 1
        assert entries[0]["score"] > 0

    def test_v2_a_a_scores_40(self):
        """v2 A+A → 20+20=40 points."""
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score={
                "technical_depth": "A", "profile_evidence": "A",
                "strengths": [], "gaps": [],
            })
            append_gap_history([job], PROFILE, history_dir=d)
            entries = _read_entries(d)
        assert entries[0]["score"] == 40

    def test_v2_b_c_scores_17(self):
        """v2 B+C → 12+5=17 points."""
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score={
                "technical_depth": "B", "profile_evidence": "C",
                "strengths": [], "gaps": [],
            })
            append_gap_history([job], PROFILE, history_dir=d)
            entries = _read_entries(d)
        assert entries[0]["score"] == 17

    def test_v2_unknown_grades_use_default(self):
        """Unknown/None grades use default of 10 each → score = 20."""
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score={
                "technical_depth": None, "profile_evidence": None,
                "strengths": [], "gaps": [],
            })
            append_gap_history([job], PROFILE, history_dir=d)
            entries = _read_entries(d)
        assert entries[0]["score"] == 20

    def test_no_rag_score_not_stored(self):
        """Jobs without rag_score are skipped by gap_tracker."""
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(rag_score=None)
            n = append_gap_history([job], PROFILE, history_dir=d)
        assert n == 0
