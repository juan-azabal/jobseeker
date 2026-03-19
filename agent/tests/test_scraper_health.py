"""Tests for scraper_health — collection, evaluation, GHA annotations, serialisation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from models import RawJob
from scraper_health import (
    CRITICAL,
    OK,
    WARNING,
    HealthReport,
    ScraperMeta,
    SourceHealth,
    collect_source_meta,
    evaluate_health,
    format_gha_annotations,
    health_report_to_dict,
    _evaluate_source,
    _compute_meta_for_source,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _raw(
    source="indeed",
    description="A proper job description with enough text",
    location="Barcelona, Spain",
    company="Acme Corp",
    title="Product Manager",
    id=None,
):
    return RawJob(
        id=id or f"{source}-{title}-{company}",
        title=title,
        company=company,
        source=source,
        description=description,
        location=location,
    )


# ── collect_source_meta ───────────────────────────────────────────────────────


class TestCollectSourceMeta:
    def test_single_source(self):
        jobs = [_raw("indeed"), _raw("indeed")]
        metas = collect_source_meta(jobs, {})
        assert len(metas) == 1
        assert metas[0].source == "indeed"
        assert metas[0].job_count == 2

    def test_multiple_sources(self):
        jobs = [_raw("indeed"), _raw("linkedin"), _raw("wttj")]
        metas = collect_source_meta(jobs, {})
        sources = {m.source for m in metas}
        assert sources == {"indeed", "linkedin", "wttj"}

    def test_error_source_with_no_jobs(self):
        metas = collect_source_meta([], {"wttj": "Connection timeout"})
        assert len(metas) == 1
        assert metas[0].source == "wttj"
        assert metas[0].job_count == 0
        assert metas[0].error == "Connection timeout"

    def test_error_recorded_on_source_with_jobs(self):
        jobs = [_raw("ats")]
        metas = collect_source_meta(jobs, {"ats": "partial failure"})
        m = next(m for m in metas if m.source == "ats")
        assert m.error == "partial failure"

    def test_empty_input(self):
        metas = collect_source_meta([], {})
        assert metas == []

    def test_description_completeness(self):
        jobs = [
            _raw("indeed", description="Long enough description here"),
            _raw("indeed", description=None),
            _raw("indeed", description=""),
        ]
        metas = collect_source_meta(jobs, {})
        m = metas[0]
        assert abs(m.has_description_pct - 1 / 3) < 0.01

    def test_median_desc_length(self):
        jobs = [
            _raw("linkedin", description="short"),  # len 5
            _raw("linkedin", description="medium text"),  # len 11
            _raw("linkedin", description="a" * 500),  # len 500
        ]
        metas = collect_source_meta(jobs, {})
        m = metas[0]
        assert m.median_desc_length == 11  # median of [5, 11, 500]

    def test_median_desc_length_all_none(self):
        jobs = [_raw("indeed", description=None), _raw("indeed", description="")]
        metas = collect_source_meta(jobs, {})
        assert metas[0].median_desc_length == 0

    def test_location_completeness(self):
        jobs = [_raw("wttj", location="Paris"), _raw("wttj", location=None)]
        metas = collect_source_meta(jobs, {})
        assert metas[0].has_location_pct == 0.5

    def test_company_completeness(self):
        jobs = [_raw("greenhouse", company=""), _raw("greenhouse", company="Acme")]
        metas = collect_source_meta(jobs, {})
        assert metas[0].has_company_pct == 0.5


# ── _evaluate_source ──────────────────────────────────────────────────────────


class TestEvaluateSource:
    def _meta(
        self, source="indeed", job_count=10, error=None, desc_pct=0.9, desc_len=300, loc_pct=0.9, company_pct=0.9
    ):
        return ScraperMeta(
            source=source,
            job_count=job_count,
            error=error,
            has_description_pct=desc_pct,
            median_desc_length=desc_len,
            has_location_pct=loc_pct,
            has_company_pct=company_pct,
        )

    def test_ok_above_all_thresholds(self):
        sh = _evaluate_source(self._meta())
        assert sh.verdict == OK
        assert sh.reasons == []

    def test_error_is_critical(self):
        sh = _evaluate_source(self._meta(error="HTTP 503"))
        assert sh.verdict == CRITICAL
        assert any("scraper_error" in r for r in sh.reasons)

    def test_zero_jobs_is_critical(self):
        sh = _evaluate_source(self._meta(job_count=0))
        assert sh.verdict == CRITICAL
        assert "zero_results" in sh.reasons

    def test_low_count_is_warning(self):
        sh = _evaluate_source(self._meta(job_count=1))  # indeed min=3
        assert sh.verdict == WARNING
        assert any("low_count" in r for r in sh.reasons)

    def test_low_desc_pct_is_warning(self):
        sh = _evaluate_source(self._meta(desc_pct=0.3))  # indeed min=0.5
        assert sh.verdict == WARNING
        assert any("schema_drift" in r for r in sh.reasons)

    def test_low_desc_len_is_warning(self):
        sh = _evaluate_source(self._meta(desc_len=50))  # indeed min=100
        assert sh.verdict == WARNING
        assert any("schema_drift" in r for r in sh.reasons)

    def test_two_warnings_escalate_to_critical(self):
        # Both low_count and low desc_pct → 2 warnings → CRITICAL
        sh = _evaluate_source(self._meta(job_count=1, desc_pct=0.3))
        assert sh.verdict == CRITICAL
        assert len(sh.reasons) == 2

    def test_unknown_source_uses_defaults(self):
        meta = self._meta(source="glassdoor", job_count=5, desc_pct=0.6, desc_len=150)
        sh = _evaluate_source(meta)
        assert sh.verdict == OK

    def test_verdict_carries_job_count(self):
        sh = _evaluate_source(self._meta(job_count=7))
        assert sh.job_count == 7


# ── evaluate_health ───────────────────────────────────────────────────────────


class TestEvaluateHealth:
    def _meta(self, source, verdict_target="ok"):
        if verdict_target == "ok":
            return ScraperMeta(source, 10, None, 0.9, 300, 0.9, 0.9)
        if verdict_target == "warning":
            return ScraperMeta(source, 1, None, 0.9, 300, 0.9, 0.9)  # low_count only
        return ScraperMeta(source, 0, None, 0.0, 0, 0.0, 0.0)  # critical

    def test_all_ok(self):
        report = evaluate_health([self._meta("indeed"), self._meta("wttj")])
        assert report.overall == OK

    def test_one_critical_makes_overall_critical(self):
        report = evaluate_health([self._meta("indeed"), self._meta("wttj", "critical")])
        assert report.overall == CRITICAL

    def test_warning_without_critical(self):
        report = evaluate_health([self._meta("indeed"), self._meta("wttj", "warning")])
        assert report.overall == WARNING

    def test_empty_metas(self):
        report = evaluate_health([])
        assert report.overall == OK
        assert report.sources == []

    def test_timestamp_is_iso(self):
        report = evaluate_health([])
        assert "T" in report.timestamp  # ISO format


# ── format_gha_annotations ────────────────────────────────────────────────────


class TestFormatGhaAnnotations:
    def _report(self, verdicts: dict[str, str]) -> HealthReport:
        sources = [
            SourceHealth(src, v, 5 if v != CRITICAL else 0, ["reason"] if v != OK else [])
            for src, v in verdicts.items()
        ]
        overall = max(verdicts.values(), key=lambda v: {"ok": 0, "warning": 1, "critical": 2}[v])
        return HealthReport(sources=sources, overall=overall, timestamp="2026-01-01T00:00:00+00:00")

    def test_ok_produces_no_lines(self):
        report = self._report({"indeed": OK, "wttj": OK})
        assert format_gha_annotations(report) == []

    def test_warning_produces_warning_annotation(self):
        lines = format_gha_annotations(self._report({"indeed": WARNING}))
        assert len(lines) == 1
        assert lines[0].startswith("::warning::")
        assert "indeed" in lines[0]

    def test_critical_produces_error_annotation(self):
        lines = format_gha_annotations(self._report({"wttj": CRITICAL}))
        assert len(lines) == 1
        assert lines[0].startswith("::error::")

    def test_mixed_produces_correct_levels(self):
        lines = format_gha_annotations(self._report({"indeed": WARNING, "wttj": CRITICAL, "linkedin": OK}))
        assert len(lines) == 2
        levels = {line.split("::")[1] for line in lines}
        assert levels == {"warning", "error"}


# ── health_report_to_dict ─────────────────────────────────────────────────────


class TestHealthReportToDict:
    def test_serialises_correctly(self):
        report = HealthReport(
            sources=[
                SourceHealth("indeed", OK, 10, []),
                SourceHealth("wttj", WARNING, 2, ["low_count: 2"]),
            ],
            overall=WARNING,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        d = health_report_to_dict(report)
        assert d["overall"] == WARNING
        assert d["n_ok"] == 1
        assert d["n_warning"] == 1
        assert d["n_critical"] == 0
        assert len(d["sources"]) == 2
        assert d["sources"][1]["source"] == "wttj"
        assert d["sources"][1]["reasons"] == ["low_count: 2"]


# ── send_health_alert ─────────────────────────────────────────────────────────


class TestSendHealthAlert:
    def _report(self, overall="warning"):
        sh = SourceHealth("wttj", overall, 1, ["low_count: 1"])
        return HealthReport(sources=[sh], overall=overall, timestamp="2026-01-01T00:00:00+00:00")

    def test_skips_when_all_ok(self):
        from scraper_health import send_health_alert

        report = HealthReport(
            sources=[SourceHealth("indeed", OK, 10, [])],
            overall=OK,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert send_health_alert(report) is False

    def test_returns_false_when_no_recipient(self, monkeypatch):
        from scraper_health import send_health_alert

        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        monkeypatch.delenv("NOTIFY_EMAIL", raising=False)
        assert send_health_alert(self._report()) is False

    def test_calls_send_smtp_with_subject(self, monkeypatch):
        from scraper_health import send_health_alert

        monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
        monkeypatch.setenv("GMAIL_ADDRESS", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        with patch("notifier.send_smtp", return_value=True) as mock_smtp:
            result = send_health_alert(self._report())

        assert result is True
        mock_smtp.assert_called_once()
        to, subject, _ = mock_smtp.call_args[0]
        assert to == "admin@example.com"
        assert "critical" in subject.lower() or "warning" in subject.lower()

    def test_falls_back_to_notify_email(self, monkeypatch):
        from scraper_health import send_health_alert

        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        monkeypatch.setenv("NOTIFY_EMAIL", "fallback@example.com")
        monkeypatch.setenv("GMAIL_ADDRESS", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        with patch("notifier.send_smtp", return_value=True) as mock_smtp:
            send_health_alert(self._report())

        to, _, _ = mock_smtp.call_args[0]
        assert to == "fallback@example.com"
