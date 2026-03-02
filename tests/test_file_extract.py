"""Tests for shared/file_extract.py — PDF and DOCX text extraction."""

import io
import tempfile

import pytest


def _make_pdf_bytes(text: str = "Hello PDF World\nSecond line") -> bytes:
    """Create a minimal PDF with text using pdfplumber-compatible format."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i, line in enumerate(text.split("\n")):
        c.drawString(72, 720 - i * 20, line)
    c.save()
    return buf.getvalue()


def _make_docx_bytes(text: str = "Hello DOCX World") -> bytes:
    """Create a minimal .docx file with one paragraph."""
    from docx import Document

    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestExtractTextFromFile:
    def test_pdf_returns_non_empty_string(self):
        from shared.file_extract import extract_text_from_file

        pdf_bytes = _make_pdf_bytes()
        result = extract_text_from_file(pdf_bytes, "cv.pdf")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello PDF World" in result

    def test_docx_returns_non_empty_string(self):
        from shared.file_extract import extract_text_from_file

        docx_bytes = _make_docx_bytes()
        result = extract_text_from_file(docx_bytes, "cv.docx")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello DOCX World" in result

    def test_unknown_extension_raises_value_error(self):
        from shared.file_extract import extract_text_from_file

        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text_from_file(b"some content", "document.txt")

    def test_pdf_multipage(self):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        from shared.file_extract import extract_text_from_file

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 720, "Page one content")
        c.showPage()
        c.drawString(72, 720, "Page two content")
        c.save()
        result = extract_text_from_file(buf.getvalue(), "multi.pdf")
        assert "Page one content" in result
        assert "Page two content" in result
