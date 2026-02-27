import os
import json
import re
from docx import Document
from docx.shared import Inches
from datetime import datetime

REPORT_TEXT_PATH = "output/reports/llm_report.txt"
OUTPUT_DIR = "output/reports"
CHARTS_DIR = "output/charts"

os.makedirs(OUTPUT_DIR, exist_ok=True)

filename = f"{OUTPUT_DIR}/security_audit_report.docx"

doc = Document()


# =========================
# Markdown Parsing Helpers
# =========================

def add_heading_from_markdown(line):
    level = line.count("#")
    text = line.replace("#", "").strip()
    doc.add_heading(text, level=min(level, 3))


def add_table_from_markdown(table_lines):
    rows = []
    for line in table_lines:
        if not line.strip():
            continue
        if line.strip().startswith("|") and not "---" in line:
            parts = [cell.strip() for cell in line.strip("|").split("|")]
            rows.append(parts)

    if not rows:
        return

    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"

    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            table.rows[row_idx].cells[col_idx].text = cell


def add_paragraph_with_bold(text):
    paragraph = doc.add_paragraph()
    parts = re.split(r"(\*\*.*?\*\*)", text)

    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            clean_text = part[2:-2]
            run = paragraph.add_run(clean_text)
            run.bold = True
        else:
            paragraph.add_run(part)


# =========================
# Insert Report Content
# =========================

if os.path.exists(REPORT_TEXT_PATH):

    with open(REPORT_TEXT_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Headings
        if line.startswith("#"):
            add_heading_from_markdown(line)
            i += 1
            continue

        # Tables
        if line.startswith("|"):
            table_block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_block.append(lines[i])
                i += 1
            add_table_from_markdown(table_block)
            continue

        # Horizontal rule
        if line.startswith("---"):
            i += 1
            continue

        # Placeholder {{CHART: id}}
        placeholder_match = re.match(r"\{\{CHART:\s*([a-z0-9_]+)\s*\}\}", line)
        if placeholder_match:
            chart_id = placeholder_match.group(1)
            chart_path = os.path.join(CHARTS_DIR, f"{chart_id}.png")

            if os.path.exists(chart_path):
                doc.add_picture(chart_path, width=Inches(6))
                doc.add_paragraph(chart_id.replace("_", " ").title())

            i += 1
            continue

        # Normal paragraph
        if line:
            add_paragraph_with_bold(line)

        i += 1

else:
    doc.add_paragraph("Report text not found.")


doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))