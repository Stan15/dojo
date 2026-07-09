"""Syllabus-markdown → styled PDF, for `dojo campaign export --format pdf`.

Optional surface: importing this module requires the `dojo[pdf]` extra
(fpdf2); callers guard the import and offer markdown export instead. The
renderer handles the syllabus subset of markdown (#/##/### headings, bullets,
**bold**, *italic*) — it is not a general markdown engine.
"""

from __future__ import annotations

import re
from pathlib import Path
from fpdf import FPDF

class SyllabusPDF(FPDF):
    """FPDF with the dojo syllabus chrome: branded header rule + page-number
    footer, applied automatically on every page."""

    def header(self) -> None:
        """Draws the top-of-page banner and separator line."""
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "DOJO STUDY SYLLABUS", border=0, new_x="LMARGIN", new_y="NEXT", align="R")
        self.set_draw_color(200, 200, 200)
        self.line(15, 18, 195, 18)
        self.ln(4)

    def footer(self) -> None:
        """Draws the centered page number."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", border=0, align="C")


def write_styled_text(pdf: SyllabusPDF, text: str, line_height: float = 5.0) -> None:
    """Writes one line, honoring inline `**bold**` and `*italic*` spans."""
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', text)
    current_family = pdf.font_family
    current_size = pdf.font_size_pt

    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            pdf.set_font(current_family, "B", current_size)
            pdf.write(line_height, part[2:-2])
        elif part.startswith('*') and part.endswith('*'):
            pdf.set_font(current_family, "I", current_size)
            pdf.write(line_height, part[1:-1])
        else:
            pdf.set_font(current_family, "", current_size)
            pdf.write(line_height, part)


def render_markdown_to_pdf(markdown_text: str, output_path: str | Path) -> None:
    """Renders syllabus markdown to a PDF file at `output_path`. Unicode
    outside latin-1 is transliterated or replaced (fpdf2 core-font
    limitation) — content survives, exotic glyphs may not."""
    replacements = {
        "\u2014": " - ",   # em-dash
        "\u2013": "-",     # en-dash
        "\u201c": '"',     # smart double quote left
        "\u201d": '"',     # smart double quote right
        "\u2018": "'",     # smart single quote left
        "\u2019": "'",     # smart single quote right
        "\u2022": "*",     # bullet point
        "\u2026": "...",   # ellipsis
    }
    for old, new in replacements.items():
        markdown_text = markdown_text.replace(old, new)

    markdown_text = markdown_text.encode("latin-1", "replace").decode("latin-1")

    pdf = SyllabusPDF()
    pdf.add_page()
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=15)

    lines = markdown_text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue

        h1_match = re.match(r'^#\s+(.+)$', stripped)
        if h1_match:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(20, 120, 60)  # Dojo Green
            pdf.multi_cell(0, 8, h1_match.group(1), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue

        h2_match = re.match(r'^##\s+(.+)$', stripped)
        if h2_match:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(30, 100, 150)  # Cyan/Blue
            pdf.multi_cell(0, 6, h2_match.group(1), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        h3_match = re.match(r'^###\s+(.+)$', stripped)
        if h3_match:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(60, 60, 60)  # Dark Grey
            pdf.multi_cell(0, 5, h3_match.group(1), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(40, 40, 40)
            pdf.set_x(20)
            pdf.write(5, "\x95 ")
            write_styled_text(pdf, bullet_match.group(1), line_height=5.0)
            pdf.ln(5)
            continue

        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(40, 40, 40)
        write_styled_text(pdf, stripped, line_height=5.0)
        pdf.ln(5)

    pdf.output(str(output_path))
