"""Tests for shared/file_extract.py — PDF and DOCX text extraction."""

import io

import pytest

# Minimal valid PDF containing "Hello PDF World\nSecond line".
# Generated once with reportlab, embedded here to avoid the test-only dependency.
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R\n"
    b"   /MediaBox [0 0 612 792]\n"
    b"   /Resources << /Font << /F1 4 0 R >> >>\n"
    b"   /Contents 5 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"5 0 obj\n<< /Length 80 >>\nstream\n"
    b"BT /F1 12 Tf 72 720 Td (Hello PDF World) Tj 0 -20 Td (Second line) Tj ET\n"
    b"endstream\nendobj\n"
    b"xref\n0 6\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000266 00000 n \n"
    b"0000000341 00000 n \n"
    b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n474\n%%EOF\n"
)

_MINIMAL_PDF_P2 = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R\n"
    b"   /MediaBox [0 0 612 792]\n"
    b"   /Resources << /Font << /F1 4 0 R >> >>\n"
    b"   /Contents 5 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"5 0 obj\n<< /Length 52 >>\nstream\n"
    b"BT /F1 12 Tf 72 720 Td (Page one content) Tj ET\n"
    b"endstream\nendobj\n"
    b"6 0 obj\n<< /Type /Page /Parent 2 0 R\n"
    b"   /MediaBox [0 0 612 792]\n"
    b"   /Resources << /Font << /F1 4 0 R >> >>\n"
    b"   /Contents 7 0 R >>\nendobj\n"
    b"7 0 obj\n<< /Length 52 >>\nstream\n"
    b"BT /F1 12 Tf 72 720 Td (Page two content) Tj ET\n"
    b"endstream\nendobj\n"
    b"xref\n0 8\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000120 00000 n \n"
    b"0000000271 00000 n \n"
    b"0000000346 00000 n \n"
    b"0000000451 00000 n \n"
    b"0000000602 00000 n \n"
    b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n707\n%%EOF\n"
)


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

        result = extract_text_from_file(_MINIMAL_PDF, "cv.pdf")
        assert isinstance(result, str)
        assert len(result) > 0

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
        from shared.file_extract import extract_text_from_file

        result = extract_text_from_file(_MINIMAL_PDF_P2, "multi.pdf")
        assert isinstance(result, str)
        assert len(result) > 0
