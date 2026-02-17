import os
from docx import Document
from docx.shared import Inches
from datetime import datetime
import json

REPORT_TEXT_PATH = "output/reports/llm_report.txt"
OUTPUT_DIR = "output/reports"

os.makedirs(OUTPUT_DIR, exist_ok=True)

filename = f"{OUTPUT_DIR}/security_audit_report.docx"

doc = Document()

# =========================
# Insert Report Text
# =========================

if os.path.exists(REPORT_TEXT_PATH):

    with open(REPORT_TEXT_PATH, "r", encoding="utf-8") as f:
        report_content = f.read()

    doc.add_paragraph(report_content)

else:
    doc.add_paragraph("Report text not found.")

# =========================
# Charts Section
# =========================

charts_dir = "output/charts"

if os.path.exists(charts_dir):

    chart_files = [f for f in os.listdir(charts_dir) if f.endswith(".png")]

    if chart_files:
        doc.add_page_break()
        doc.add_heading("Anexos – Evidencia Gráfica", level=1)

        for file in sorted(chart_files):
            chart_path = os.path.join(charts_dir, file)
            doc.add_picture(chart_path, width=Inches(6))
            doc.add_paragraph(file.replace(".png", "").replace("_", " "))
            doc.add_page_break()

doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))
