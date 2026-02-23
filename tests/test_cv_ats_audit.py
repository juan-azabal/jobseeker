"""Tests for api/cv/ats_audit.py — ATS audit utility."""
import tempfile
import pytest
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from lxml import etree


def _make_clean_docx(tmp_path) -> str:
    """Create a minimal ATS-compliant .docx for testing."""
    from tests.test_cv_docx_builder import SAMPLE_MARKDOWN
    from api.cv.docx_builder import build_docx
    path = tmp_path / "clean.docx"
    build_docx(SAMPLE_MARKDOWN, str(path))
    return str(path)


def _make_docx_with_table(tmp_path) -> str:
    """Create a .docx that contains a table element."""
    doc = Document()
    doc.add_heading("Test Name", level=1)
    doc.add_paragraph("## Summary")
    doc.add_paragraph("A summary paragraph here.")
    doc.add_paragraph("## Work Experience")
    doc.add_paragraph("## Education and Certifications")
    doc.add_paragraph("## Languages")
    # Add a table (ATS violation)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Company"
    table.cell(0, 1).text = "Role"
    path = tmp_path / "with_table.docx"
    doc.save(str(path))
    return str(path)


def _make_docx_with_em_dash(tmp_path) -> str:
    """Create a .docx with an em dash in body text."""
    doc = Document()
    doc.add_heading("Test Name", level=1)
    doc.add_paragraph("Contact info here")
    h = doc.add_heading(level=2)
    h.clear()
    h.add_run("Summary")
    doc.add_paragraph("Experience — with em dash.")
    h2 = doc.add_heading(level=2)
    h2.clear()
    h2.add_run("Work Experience")
    h3 = doc.add_heading(level=2)
    h3.clear()
    h3.add_run("Education and Certifications")
    h4 = doc.add_heading(level=2)
    h4.clear()
    h4.add_run("Languages")
    h5 = doc.add_heading(level=2)
    h5.clear()
    h5.add_run("Selected Impact")
    h6 = doc.add_heading(level=2)
    h6.clear()
    h6.add_run("Core Skills")
    path = tmp_path / "with_em_dash.docx"
    doc.save(str(path))
    return str(path)


def _make_docx_missing_header(tmp_path) -> str:
    """Create a .docx missing the Summary standard header."""
    doc = Document()
    doc.add_heading("Test Name", level=1)
    doc.add_paragraph("Contact line")
    # Has most headers but not "Summary"
    for h in ["Selected Impact", "Core Skills", "Work Experience",
              "Education and Certifications", "Languages"]:
        hpara = doc.add_heading(level=2)
        hpara.clear()
        hpara.add_run(h)
        doc.add_paragraph(f"Content for {h}")
    path = tmp_path / "missing_header.docx"
    doc.save(str(path))
    return str(path)


# --- Tests ---

def test_clean_docx_passes(tmp_path):
    """A properly built ATS-compliant .docx must pass the audit."""
    from api.cv.ats_audit import audit_docx
    path = _make_clean_docx(tmp_path)
    result = audit_docx(path)
    assert result["passed"] is True
    assert result["violations"] == []


def test_audit_returns_required_keys(tmp_path):
    """audit_docx() must return passed, violations, and stats."""
    from api.cv.ats_audit import audit_docx
    path = _make_clean_docx(tmp_path)
    result = audit_docx(path)
    assert "passed" in result
    assert "violations" in result
    assert "stats" in result
    assert isinstance(result["violations"], list)
    assert isinstance(result["stats"], dict)


def test_table_detected_as_violation(tmp_path):
    """A .docx with a table must report table_found violation."""
    from api.cv.ats_audit import audit_docx
    path = _make_docx_with_table(tmp_path)
    result = audit_docx(path)
    assert result["passed"] is False
    assert any("table" in v for v in result["violations"])


def test_em_dash_detected_as_violation(tmp_path):
    """A .docx with an em dash must report prohibited_char violation."""
    from api.cv.ats_audit import audit_docx
    path = _make_docx_with_em_dash(tmp_path)
    result = audit_docx(path)
    assert result["passed"] is False
    assert any("em_dash" in v or "prohibited_char" in v for v in result["violations"])


def test_missing_header_detected_as_violation(tmp_path):
    """A .docx missing 'Summary' header must report missing_header violation."""
    from api.cv.ats_audit import audit_docx
    path = _make_docx_missing_header(tmp_path)
    result = audit_docx(path)
    assert result["passed"] is False
    assert any("Summary" in v for v in result["violations"])


def test_stats_contain_expected_keys(tmp_path):
    """Stats dict must include section_count, bullet_count, paragraph_count, estimated_pages."""
    from api.cv.ats_audit import audit_docx
    path = _make_clean_docx(tmp_path)
    result = audit_docx(path)
    stats = result["stats"]
    assert "section_count" in stats
    assert "bullet_count" in stats
    assert "paragraph_count" in stats
    assert "estimated_pages" in stats
    assert stats["section_count"] >= 6
    assert stats["bullet_count"] > 0
    assert stats["paragraph_count"] > 0
    assert stats["estimated_pages"] >= 1
