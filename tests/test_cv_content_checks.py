"""Tests for api.cv.content_checks — company hallucination + length bounds."""

import pytest

from api.cv.content_checks import (
    check_company_hallucination,
    check_length_bounds,
    extract_cv_companies,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

_CV_WITH_KNOWN = """\
# Juan Azabal
Senior Product Manager | Data & Analytics

## Work Experience

### Acme Corp, Barcelona
- Built data platform serving 2M users

### Beta Analytics, Madrid
- Led product team of 5
"""

_CV_WITH_HALLUCINATION = """\
# Juan Azabal
Senior Product Manager

## Work Experience

### Acme Corp, Barcelona
- Built data platform

### FakeCompany, Berlin
- Invented role at invented company

### Beta Analytics, Madrid
- Led product team
"""

_KNOWN_COMPANIES = ["Acme Corp", "Beta Analytics"]


# ── extract_cv_companies ─────────────────────────────────────────────────


class TestExtractCompanies:
    def test_extracts_from_h3_headers(self):
        result = extract_cv_companies(_CV_WITH_KNOWN)
        assert result == ["Acme Corp", "Beta Analytics"]

    def test_handles_parentheses_in_company(self):
        cv = "### Grupo Godo (LaVanguardia.com), Barcelona\n- Did things"
        result = extract_cv_companies(cv)
        assert result == ["Grupo Godo (LaVanguardia.com)"]

    def test_empty_cv(self):
        assert extract_cv_companies("") == []

    def test_no_h3_headers(self):
        assert extract_cv_companies("# Name\n## Section\nSome text") == []


# ── check_company_hallucination ──────────────────────────────────────────


class TestCompanyHallucination:
    def test_no_hallucination_when_all_known(self):
        errors = check_company_hallucination(_CV_WITH_KNOWN, _KNOWN_COMPANIES)
        assert errors == []

    def test_hallucination_detected(self):
        errors = check_company_hallucination(_CV_WITH_HALLUCINATION, _KNOWN_COMPANIES)
        assert len(errors) == 1
        assert errors[0]["code"] == "company_hallucinated"
        assert "FakeCompany" in errors[0]["detail"]

    def test_case_insensitive(self):
        errors = check_company_hallucination(_CV_WITH_KNOWN, ["acme corp", "beta analytics"])
        assert errors == []

    def test_skipped_when_no_known(self):
        errors = check_company_hallucination(_CV_WITH_HALLUCINATION, [])
        assert errors == []


# ── check_length_bounds ──────────────────────────────────────────────────


class TestLengthBounds:
    def test_ok_length(self):
        cv = "\n".join(f"Line {i}" for i in range(60))
        warnings = check_length_bounds(cv)
        assert warnings == []

    def test_too_long(self):
        cv = "\n".join(f"Line {i}" for i in range(130))
        warnings = check_length_bounds(cv)
        assert len(warnings) == 1
        assert warnings[0]["code"] == "cv_too_long"

    def test_too_short(self):
        cv = "\n".join(f"Line {i}" for i in range(20))
        warnings = check_length_bounds(cv)
        assert len(warnings) == 1
        assert warnings[0]["code"] == "cv_too_short"

    def test_empty_string(self):
        warnings = check_length_bounds("")
        assert len(warnings) == 1
        assert warnings[0]["code"] == "cv_too_short"

    def test_blank_lines_not_counted(self):
        cv = "\n".join(["Line"] * 25 + [""] * 50 + ["Line"] * 4)
        warnings = check_length_bounds(cv)
        assert len(warnings) == 1
        assert warnings[0]["code"] == "cv_too_short"
