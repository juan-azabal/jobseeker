"""ATS-compliant .docx builder.

Parses structured markdown output from the LLM and builds a python-docx
Document that passes ATS parsers (Workday, Greenhouse, Lever).

ATS constraints enforced:
- Zero tables anywhere in the document XML
- Bullets via 'List Bullet' style (never unicode characters)
- Single column layout
- Standard section headers
- Post-processing: replaces em dash, en dash, arrows, Oxford comma
"""
import logging
import re
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT

logger = logging.getLogger(__name__)

# Characters to replace in post-processing
_REPLACEMENTS = [
    ("\u2014", "-"),   # em dash → hyphen
    ("\u2013", "-"),   # en dash → hyphen
    ("\u2192", ""),    # → (arrow) → removed
    ("=>", ""),        # => (arrow) → removed
    ("\u007e", ""),    # tilde
    ("•", ""),         # unicode bullet
    ("\u25e6", ""),    # ◦
    ("\u25aa", ""),    # ▪
]

# Page width minus margins (8.27" - 2 × 1") for right-aligned tab stop
_PAGE_CONTENT_WIDTH = Inches(6.27)


def _clean_text(text: str) -> str:
    """Apply ATS post-processing replacements to a text string."""
    for bad, good in _REPLACEMENTS:
        if bad in text:
            logger.warning("ATS post-processing: replaced %r with %r in: %s", bad, good, text[:60])
            text = text.replace(bad, good)
    # Oxford comma: ", and " → ", "  (only when followed by a word, not at end)
    cleaned = re.sub(r",\s+and\s+(?=\w)", ", ", text)
    if cleaned != text:
        logger.warning("ATS post-processing: removed Oxford comma in: %s", text[:60])
        text = cleaned
    return text


def _strip_fences_and_preamble(markdown: str) -> str:
    """Remove code fences and any text before the first # heading."""
    # Strip code fences
    markdown = re.sub(r"^```[a-zA-Z]*\n?", "", markdown.strip())
    markdown = re.sub(r"\n?```$", "", markdown.strip())

    # Strip preamble before first # heading
    match = re.search(r"^# ", markdown, re.MULTILINE)
    if not match:
        return markdown.strip()
    return markdown[match.start():].strip()


def _set_run_font(run, size_pt: int, bold: bool = False):
    """Set font name and size on a run."""
    run.font.name = "Calibri"
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def _add_name(doc: Document, text: str):
    """Add candidate name as Heading 1."""
    para = doc.add_heading(level=1)
    para.clear()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 14, bold=True)


def _add_contact_line(doc: Document, text: str):
    """Add a contact/title line as a small normal paragraph."""
    para = doc.add_paragraph()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 10)


def _add_section_header(doc: Document, text: str):
    """Add a ## section header as Heading 2."""
    para = doc.add_heading(level=2)
    para.clear()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 12, bold=True)
    para.paragraph_format.space_before = Pt(12)


def _add_subsection_header(doc: Document, text: str):
    """Add a ### subsection header (company/project) as Heading 3."""
    para = doc.add_heading(level=3)
    para.clear()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 11, bold=True)


def _add_role_line(doc: Document, text: str):
    """Add a **Role | Date** line as a normal paragraph with right-aligned date tab."""
    # Parse "Role Title | MM/YYYY - MM/YYYY"
    para = doc.add_paragraph()
    para.paragraph_format.tab_stops.add_tab_stop(
        _PAGE_CONTENT_WIDTH, WD_TAB_ALIGNMENT.RIGHT
    )

    if "|" in text:
        parts = text.split("|", 1)
        role = _clean_text(parts[0].strip())
        date = _clean_text(parts[1].strip())
        run_role = para.add_run(role)
        _set_run_font(run_role, 11, bold=True)
        run_tab = para.add_run("\t")
        run_tab.font.size = Pt(11)
        run_date = para.add_run(date)
        _set_run_font(run_date, 11)
    else:
        run = para.add_run(_clean_text(text))
        _set_run_font(run, 11, bold=True)


def _add_bullet(doc: Document, text: str):
    """Add a bullet item using List Bullet style (ATS-safe)."""
    para = doc.add_paragraph(style="List Bullet")
    para.clear()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 11)
    para.paragraph_format.left_indent = Inches(0.25)
    para.paragraph_format.first_line_indent = Inches(-0.25)


def _add_prose(doc: Document, text: str):
    """Add a regular prose paragraph."""
    para = doc.add_paragraph()
    run = para.add_run(_clean_text(text))
    _set_run_font(run, 11)


def _add_skills_theme(doc: Document, theme: str, prose: str):
    """Add a Core Skills theme block: bold theme name + prose."""
    para = doc.add_paragraph()
    run_theme = para.add_run(_clean_text(theme) + "\n")
    _set_run_font(run_theme, 11, bold=True)
    if prose:
        run_prose = para.add_run(_clean_text(prose))
        _set_run_font(run_prose, 11)


def _parse_work_experience(doc: Document, lines: list[str]):
    """Parse and render Work Experience section lines."""
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("### "):
            _add_subsection_header(doc, line[4:])
        elif line.startswith("**") and line.endswith("**") and "|" in line:
            _add_role_line(doc, line.strip("*").strip())
        elif line.startswith("- "):
            _add_bullet(doc, line[2:])
        elif line.strip():
            _add_prose(doc, line)
        i += 1


def _parse_projects(doc: Document, lines: list[str]):
    """Parse and render Projects section lines."""
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("### "):
            _add_subsection_header(doc, line[4:])
        elif line.startswith("- "):
            _add_bullet(doc, line[2:])
        elif line.strip():
            _add_prose(doc, line)
        i += 1


def _parse_core_skills(doc: Document, lines: list[str]):
    """Parse and render Core Skills: **Theme** blocks + prose."""
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # Bold theme: **Theme Name**
        if line.startswith("**") and line.endswith("**"):
            theme = line.strip("*").strip()
            # Collect following prose paragraph
            prose_lines = []
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith("**"):
                prose_lines.append(lines[j].strip())
                j += 1
            _add_skills_theme(doc, theme, " ".join(prose_lines))
            i = j
            continue
        elif line.startswith("- "):
            _add_bullet(doc, line[2:])
        elif line.strip():
            _add_prose(doc, line)
        i += 1


def _parse_bullets_section(doc: Document, lines: list[str]):
    """Parse a section that is primarily bullet lists."""
    for line in lines:
        line = line.rstrip()
        if line.startswith("- "):
            _add_bullet(doc, line[2:])
        elif line.strip():
            _add_prose(doc, line)


def _parse_prose_section(doc: Document, lines: list[str]):
    """Parse a section with prose paragraphs."""
    for line in lines:
        line = line.rstrip()
        if line.startswith("- "):
            _add_bullet(doc, line[2:])
        elif line.strip():
            _add_prose(doc, line)


def build_docx(markdown: str, output_path: str) -> str:
    """Parse structured LLM markdown and build an ATS-compliant .docx file.

    Args:
        markdown: Structured CV markdown string from the LLM.
        output_path: Absolute path where the .docx file will be written.

    Returns:
        The output_path on success.

    Raises:
        ValueError: If markdown is empty or has no # heading.
    """
    if not markdown or not markdown.strip():
        raise ValueError("Cannot build .docx from empty markdown.")

    markdown = _strip_fences_and_preamble(markdown)

    if not re.search(r"^# ", markdown, re.MULTILINE):
        raise ValueError(
            "Malformed CV markdown: no '# Name' heading found. "
            "The LLM output must start with a level-1 heading."
        )

    doc = Document()

    # Page setup: A4, 1-inch margins
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    # Default paragraph font
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Split markdown into lines
    lines = markdown.split("\n")

    # Extract header block (name + lines before first ## section)
    header_lines = []
    section_start = 0
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            section_start = idx
            break
        header_lines.append(line)

    # Parse header: first line = name, rest = title/contact
    name_written = False
    for line in header_lines:
        line = line.strip()
        if not line:
            continue
        if not name_written:
            _add_name(doc, line.lstrip("# "))
            name_written = True
        else:
            _add_contact_line(doc, line)

    # Split remaining lines into ## sections
    sections: list[tuple[str, list[str]]] = []
    current_section_name = ""
    current_section_lines: list[str] = []

    for line in lines[section_start:]:
        if line.startswith("## "):
            if current_section_name:
                sections.append((current_section_name, current_section_lines))
            current_section_name = line[3:].strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)
    if current_section_name:
        sections.append((current_section_name, current_section_lines))

    # Render each section
    for sec_name, sec_lines in sections:
        _add_section_header(doc, sec_name)
        # Strip leading/trailing blank lines
        while sec_lines and not sec_lines[0].strip():
            sec_lines.pop(0)
        while sec_lines and not sec_lines[-1].strip():
            sec_lines.pop()

        sec_lower = sec_name.lower()

        if "work experience" in sec_lower:
            _parse_work_experience(doc, sec_lines)
        elif "project" in sec_lower:
            _parse_projects(doc, sec_lines)
        elif "core skills" in sec_lower or "skills" in sec_lower:
            _parse_core_skills(doc, sec_lines)
        elif any(k in sec_lower for k in ("impact", "education", "language", "certification")):
            _parse_bullets_section(doc, sec_lines)
        else:
            _parse_prose_section(doc, sec_lines)

    doc.save(output_path)
    return output_path
