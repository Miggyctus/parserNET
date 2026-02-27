import os
import json
import re
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

REPORT_TEXT_PATH = "output/reports/llm_report.txt"
OUTPUT_DIR = "output/reports"
CHARTS_DIR = "output/charts"

os.makedirs(OUTPUT_DIR, exist_ok=True)

filename = f"{OUTPUT_DIR}/security_audit_report.docx"

doc = Document()


# =========================
# Helpers
# =========================

def insert_chart(chart_id):
    chart_path = os.path.join(CHARTS_DIR, f"{chart_id}.png")
    if os.path.exists(chart_path):
        doc.add_picture(chart_path, width=Inches(6))
        doc.add_paragraph(f"Figura: {chart_id.replace('_', ' ').title()}")
        return True
    return False


def is_section_title(line):
    return line.isupper() and len(line) > 3


def is_numbered_section(line):
    return re.match(r"^\d+\.\s", line)


# =========================
# Parse Report
# =========================

if os.path.exists(REPORT_TEXT_PATH):

    with open(REPORT_TEXT_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            continue

        # Detect top banner lines
        if line.startswith("===="):
            p = doc.add_paragraph(line)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            continue

        # Detect uppercase section headers
        if is_section_title(line):
            doc.add_heading(line, level=1)
            continue

        # Detect numbered index sections
        if is_numbered_section(line):
            doc.add_heading(line, level=2)
            continue

        # Detect placeholder
        placeholder_match = re.match(r"\{\{CHART:\s*([a-z0-9_]+)\s*\}\}", line)
        if placeholder_match:
            chart_id = placeholder_match.group(1)
            insert_chart(chart_id)
            continue

        # Ignore dashed separators
        if line.startswith("----"):
            continue

        # Normal paragraph
        doc.add_paragraph(line)

else:
    doc.add_paragraph("Report text not found.")


# =========================
# Save Document
# =========================

doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))