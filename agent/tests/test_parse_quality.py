"""Tests for parse_quality — batch parse metrics computation."""

import pytest

from parse_quality import compute_parse_metrics


# ── Fixtures ─────────────────────────────────────────────────────────────


def _job(parsed=None, parse_error=None):
    """Build a minimal job dict for testing."""
    j = {"id": "test-job"}
    if parsed is not None:
        j["parsed"] = parsed
    if parse_error is not None:
        j["parse_error"] = parse_error
    return j


_FULL_PARSED = {
    "domain": "fintech",
    "seniority": "senior",
    "location_type": "remote",
    "truly_required": ["SQL", "Python"],
}

_SPARSE_PARSED = {
    "domain": None,
    "seniority": "mid",
    "location_type": None,
    "truly_required": [],
}


# ── Tests ────────────────────────────────────────────────────────────────


class TestComputeParseMetrics:
    def test_all_parsed_ok(self):
        jobs = [_job(parsed=_FULL_PARSED) for _ in range(3)]
        m = compute_parse_metrics(jobs)
        assert m["parse_error_rate"] == 0.0
        assert m["total_parsed"] == 3
        assert m["total_errors"] == 0
        assert m["null_field_rates"]["domain"] == 0.0
        assert m["null_field_rates"]["seniority"] == 0.0

    def test_mixed_errors(self):
        jobs = [
            _job(parsed=_FULL_PARSED),
            _job(parsed=_FULL_PARSED),
            _job(parse_error="JSON parse error"),
        ]
        m = compute_parse_metrics(jobs)
        assert abs(m["parse_error_rate"] - 1 / 3) < 0.01
        assert m["total_parsed"] == 2
        assert m["total_errors"] == 1

    def test_null_field_rates(self):
        jobs = [
            _job(parsed=_FULL_PARSED),
            _job(parsed=_SPARSE_PARSED),
        ]
        m = compute_parse_metrics(jobs)
        assert m["null_field_rates"]["domain"] == 0.5
        assert m["null_field_rates"]["seniority"] == 0.0
        assert m["null_field_rates"]["location_type"] == 0.5

    def test_empty_skills_counted_as_null(self):
        """Empty list for skills should count as null."""
        jobs = [_job(parsed=_SPARSE_PARSED)]
        m = compute_parse_metrics(jobs)
        assert m["null_field_rates"]["skills"] == 1.0

    def test_skills_backward_compat(self):
        """must_have_skills used when truly_required absent."""
        parsed = {"domain": "saas", "seniority": "senior", "location_type": "hybrid", "must_have_skills": ["React"]}
        jobs = [_job(parsed=parsed)]
        m = compute_parse_metrics(jobs)
        assert m["null_field_rates"]["skills"] == 0.0

    def test_empty_input(self):
        m = compute_parse_metrics([])
        assert m["parse_error_rate"] == 0.0
        assert m["total_parsed"] == 0
        assert m["total_errors"] == 0
        assert m["null_field_rates"] == {}

    def test_all_errors(self):
        jobs = [_job(parse_error="err") for _ in range(3)]
        m = compute_parse_metrics(jobs)
        assert m["parse_error_rate"] == 1.0
        assert m["total_parsed"] == 0
        assert m["total_errors"] == 3
        assert m["null_field_rates"] == {}
