"""Convert structured CV selection to markdown for LLM rewrite or direct docx build.

render_cv_markdown(selected) -> str
  Takes the output of select_cv_content() and renders it as work-experience
  markdown compatible with the existing docx_builder pipeline.
"""

from __future__ import annotations


def render_cv_markdown(selected: dict) -> str:
    """Render selected CV content as markdown.

    Args:
        selected: Output of select_cv_content() — dict with "work" list
                  and "skill_intersection" list.

    Returns:
        Markdown string suitable for passing to rewrite_cv_content()
        or directly to build_docx().
    """
    work = selected.get("work") or []
    if not work:
        return ""

    lines: list[str] = []
    lines.append("## Work Experience")

    for entry in work:
        company = entry.get("company", "")
        position = entry.get("position", "")
        start = entry.get("start_date") or ""
        end = entry.get("end_date") or "present"

        lines.append("")
        lines.append(f"### {company}")
        lines.append(f"**{position}** | {start} – {end}")

        for highlight in entry.get("selected_highlights") or []:
            lines.append(f"- {highlight}")

    return "\n".join(lines)
