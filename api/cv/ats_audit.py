"""ATS compliance audit utility.

Post-build safety net that inspects a .docx file for ATS violations.
Called after docx_builder.build_docx() — result exposed via X-ATS-Audit header.
"""
import re
from docx import Document
from docx.oxml.ns import qn

# Standard section headers required by the CV format
_REQUIRED_HEADERS = {
    "Summary",
    "Selected Impact",
    "Core Skills",
    "Work Experience",
    "Education and Certifications",
    "Languages",
}

# Prohibited characters with their violation labels
_PROHIBITED_CHARS = [
    ("\u2014", "prohibited_char:em_dash"),
    ("\u2013", "prohibited_char:en_dash"),
    ("\u2192", "prohibited_char:arrow"),
    ("\u25cf", "prohibited_char:unicode_bullet"),
    ("\u25e6", "prohibited_char:unicode_bullet"),
    ("\u25aa", "prohibited_char:unicode_bullet"),
    ("\u2022", "prohibited_char:unicode_bullet"),
]

# Approximate lines per page for page count heuristic
_LINES_PER_PAGE = 45


def audit_docx(path: str) -> dict:
    """Inspect a .docx file for ATS compliance violations.

    Args:
        path: Absolute path to the .docx file to audit.

    Returns:
        Dict with keys:
          - passed (bool): True if zero violations found.
          - violations (list[str]): Violation codes/descriptions.
          - stats (dict): section_count, bullet_count, paragraph_count,
                         estimated_pages.
    """
    violations: list[str] = []
    doc = Document(path)

    # 1. Zero tables
    if len(doc.tables) > 0:
        violations.append(f"table_found: {len(doc.tables)} table(s) in document")

    # 2. Collect all paragraph text and inspect
    all_paragraphs = doc.paragraphs
    paragraph_count = len(all_paragraphs)

    section_count = 0
    bullet_count = 0
    found_headers: set[str] = set()

    for para in all_paragraphs:
        text = para.text
        stripped = text.strip()

        # Detect section headers: "Heading 2" style (Phase 5) OR exact text match
        # against required headers (Phase 6 uses Normal style with explicit formatting)
        is_section_header = (
            para.style.name == "Heading 2"
            or stripped in _REQUIRED_HEADERS
        )
        if is_section_header:
            section_count += 1
            for required in _REQUIRED_HEADERS:
                if required.lower() in stripped.lower():
                    found_headers.add(required)

        # Count bullets
        if "List" in para.style.name or "Bullet" in para.style.name:
            bullet_count += 1

        # Check for prohibited characters
        for char, label in _PROHIBITED_CHARS:
            if char in text:
                violations.append(f"{label}: found in paragraph: {text[:60]}")
                break  # one violation per paragraph

        # Oxford comma check
        if re.search(r",\s+and\s+\w", text):
            violations.append(f"oxford_comma: found in paragraph: {text[:60]}")

    # 3. Check date format in role lines (MM/YYYY pattern)
    for para in all_paragraphs:
        if para.style.name in ("Normal", "Body Text") and "|" in para.text:
            # Lines like "Role Title | MM/YYYY - MM/YYYY"
            date_part = para.text.split("|", 1)[-1].strip() if "|" in para.text else ""
            if date_part:
                # Accept: MM/YYYY, YYYY, Present, or empty
                if not re.match(
                    r"^(\d{2}/\d{4}|\d{4})\s*[-–]\s*(\d{2}/\d{4}|\d{4}|[Pp]resent)$",
                    date_part.strip(),
                ):
                    # Only flag if it looks date-like but wrong format
                    if re.search(r"\d{4}", date_part):
                        violations.append(
                            f"date_format: unexpected date format: {date_part[:40]}"
                        )

    # 4. Missing required headers
    for required in _REQUIRED_HEADERS:
        if required not in found_headers:
            violations.append(f"missing_header:{required}")

    # 5. Stats
    estimated_pages = max(1, round(paragraph_count / _LINES_PER_PAGE + 0.4))
    stats = {
        "section_count": section_count,
        "bullet_count": bullet_count,
        "paragraph_count": paragraph_count,
        "estimated_pages": estimated_pages,
    }

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "stats": stats,
    }
