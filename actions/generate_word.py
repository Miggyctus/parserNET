import json
import os
from docx import Document
from docx.shared import Inches
from datetime import datetime

REPORT_JSON = "output/json/llm_report.json"

output_dir = "output/reports"
os.makedirs(output_dir, exist_ok=True)

if not os.path.exists(REPORT_JSON):
    print(json.dumps({"error": "Report JSON not found"}))
    exit(1)

with open(REPORT_JSON, "r", encoding="utf-8") as f:
    report_data = json.load(f)

report_title = report_data.get("report_title", "Security Audit Report")

filename = f"{output_dir}/{report_title.replace(' ', '_').lower()}.docx"

doc = Document()

# =========================
# Cover Page
# =========================

doc.add_heading(report_title, level=0)
doc.add_paragraph(f"Fecha de Emisión: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
doc.add_page_break()

# =========================
# Insert full structured sections
# =========================

for section_key, section_content in report_data.items():

    if section_key == "report_title":
        continue

    doc.add_heading(section_key.replace("_", " ").title(), level=1)
    doc.add_paragraph(section_content)
    doc.add_page_break()

# =========================
# Charts
# =========================

charts_dir = "output/charts"

if os.path.exists(charts_dir):
    chart_files = [f for f in os.listdir(charts_dir) if f.endswith(".png")]

    if chart_files:
        doc.add_heading("Anexos – Evidencia Gráfica", level=1)

        for file in sorted(chart_files):
            chart_path = os.path.join(charts_dir, file)

            doc.add_picture(chart_path, width=Inches(6))
            doc.add_paragraph(
                file.replace(".png", "").replace("_", " "),
                style="Caption"
            )
            doc.add_page_break()

doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))
