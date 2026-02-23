"""Tests for api/cv/docx_builder.py — ATS-compliant .docx builder."""
import pytest
import tempfile
import os
from pathlib import Path


SAMPLE_MARKDOWN = """# Juan Azabal
Senior Product Manager | Data, Personalization & Monetization
Barcelona, Spain | j.azabal@gmail.com | +34 625 588 926 | linkedin.com/in/juanazabal

## Summary

Experienced product manager with 10 years driving data platform and monetization products.
Proven track record of growing revenue and improving user engagement.

## Selected Impact

- Grew ad revenue 40% YoY by redesigning targeting pipeline
- Led migration of legacy data platform serving 50M users
- Reduced time-to-insight from 3 days to 4 hours for analytics team

## Core Skills

**Data Platform**
Deep experience with data warehousing, streaming pipelines, and self-serve analytics.

**Product Strategy**
Strong background in roadmap definition, stakeholder alignment, and OKR frameworks.

## Projects

### JobSeeker
Job search CRM with AI-powered CV tailoring. FastAPI, React, SQLite. github.com/juan/jobseeker

## Work Experience

### Acme Corp, Barcelona, Spain
**Senior Product Manager | 01/2021 - Present**

- Defined 3-year data platform roadmap adopted by engineering leadership
- Increased query performance 60% by migrating to columnar storage

### Previous Company, Madrid, Spain
**Product Manager | 03/2018 - 12/2020**

- Built real-time personalization engine serving 10M daily users

## Education and Certifications

- MBA - IESE Business School, 2017
- BSc Computer Science - UPC, 2013

## Languages

- Spanish - Native
- English - Fluent
- Catalan - Native
"""


def _build(markdown: str) -> Path:
    """Helper: run build_docx and return path."""
    from api.cv.docx_builder import build_docx
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        output_path = f.name
    build_docx(markdown, output_path)
    return Path(output_path)


def test_output_file_exists_and_has_content():
    """build_docx() creates a non-empty .docx file."""
    path = _build(SAMPLE_MARKDOWN)
    try:
        assert path.exists()
        assert path.stat().st_size > 0
    finally:
        path.unlink(missing_ok=True)


def test_zero_tables_in_xml():
    """Generated .docx must have zero <w:tbl> elements (ATS requirement)."""
    from docx import Document
    path = _build(SAMPLE_MARKDOWN)
    try:
        doc = Document(str(path))
        # Check via python-docx tables property
        assert len(doc.tables) == 0, f"Found {len(doc.tables)} table(s) — ATS violation"
    finally:
        path.unlink(missing_ok=True)


def test_heading1_is_candidate_name():
    """First Heading 1 must be the candidate name."""
    from docx import Document
    path = _build(SAMPLE_MARKDOWN)
    try:
        doc = Document(str(path))
        h1_paragraphs = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
        assert len(h1_paragraphs) >= 1
        assert "Juan Azabal" in h1_paragraphs[0].text
    finally:
        path.unlink(missing_ok=True)


def test_heading2_count_matches_sections():
    """Number of Heading 2 elements matches number of ## sections."""
    from docx import Document
    path = _build(SAMPLE_MARKDOWN)
    try:
        doc = Document(str(path))
        h2_paragraphs = [p for p in doc.paragraphs if p.style.name == "Heading 2"]
        # SAMPLE_MARKDOWN has: Summary, Selected Impact, Core Skills, Projects,
        # Work Experience, Education and Certifications, Languages = 7
        assert len(h2_paragraphs) == 7
    finally:
        path.unlink(missing_ok=True)


def test_bullets_use_list_style_not_unicode():
    """Bullet paragraphs must use list style, not unicode bullet characters."""
    from docx import Document
    path = _build(SAMPLE_MARKDOWN)
    try:
        doc = Document(str(path))
        unicode_bullets = {"•", "◦", "▪", "–", "→"}
        for para in doc.paragraphs:
            for char in unicode_bullets:
                assert char not in para.text, (
                    f"Unicode bullet '{char}' found in paragraph: {para.text[:60]}"
                )
        # At least some list-style paragraphs exist
        list_paras = [
            p for p in doc.paragraphs
            if "List" in p.style.name or "Bullet" in p.style.name
        ]
        assert len(list_paras) > 0, "No list-style paragraphs found"
    finally:
        path.unlink(missing_ok=True)


def test_em_dashes_replaced_in_post_processing():
    """Post-processing must replace em dashes with ASCII hyphens."""
    from docx import Document
    markdown_with_em_dash = SAMPLE_MARKDOWN.replace(
        "Grew ad revenue 40% YoY by redesigning targeting pipeline",
        "Grew ad revenue 40% YoY — redesigned targeting pipeline"
    )
    path = _build(markdown_with_em_dash)
    try:
        doc = Document(str(path))
        full_text = " ".join(p.text for p in doc.paragraphs)
        assert "—" not in full_text, "Em dash found in output — should have been replaced"
    finally:
        path.unlink(missing_ok=True)


def test_oxford_comma_replaced_in_post_processing():
    """Post-processing must remove Oxford comma pattern ', and '."""
    from docx import Document
    markdown_with_oxford = SAMPLE_MARKDOWN.replace(
        "Deep experience with data warehousing, streaming pipelines, and self-serve analytics.",
        "Deep experience with data warehousing, streaming pipelines, and self-serve analytics, and more."
    )
    path = _build(markdown_with_oxford)
    try:
        doc = Document(str(path))
        full_text = " ".join(p.text for p in doc.paragraphs)
        # Oxford comma pattern should be gone
        assert ", and " not in full_text, "Oxford comma pattern found in output"
    finally:
        path.unlink(missing_ok=True)


def test_code_fences_stripped():
    """Markdown wrapped in code fences must produce a valid .docx."""
    fenced = "```markdown\n" + SAMPLE_MARKDOWN + "\n```"
    path = _build(fenced)
    try:
        from docx import Document
        doc = Document(str(path))
        h1_paragraphs = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
        assert any("Juan Azabal" in p.text for p in h1_paragraphs)
    finally:
        path.unlink(missing_ok=True)


def test_preamble_stripped():
    """Text before first # heading must be stripped."""
    with_preamble = "Here is your tailored CV:\n\n" + SAMPLE_MARKDOWN
    path = _build(with_preamble)
    try:
        from docx import Document
        doc = Document(str(path))
        h1_paragraphs = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
        assert any("Juan Azabal" in p.text for p in h1_paragraphs)
        # Preamble text should not appear
        full_text = " ".join(p.text for p in doc.paragraphs)
        assert "Here is your tailored CV" not in full_text
    finally:
        path.unlink(missing_ok=True)


def test_empty_markdown_raises_value_error():
    """Empty or whitespace-only markdown must raise ValueError."""
    from api.cv.docx_builder import build_docx
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        output_path = f.name
    try:
        with pytest.raises(ValueError):
            build_docx("   \n\n  ", output_path)
    finally:
        Path(output_path).unlink(missing_ok=True)


def test_malformed_markdown_no_heading_raises_value_error():
    """Markdown with no # heading raises ValueError."""
    from api.cv.docx_builder import build_docx
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        output_path = f.name
    try:
        with pytest.raises(ValueError):
            build_docx("Some random text\nno headings here\njust prose", output_path)
    finally:
        Path(output_path).unlink(missing_ok=True)
