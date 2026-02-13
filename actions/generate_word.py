import sys
import json
import os
from docx import Document
from docx.shared import Inches
from datetime import datetime

# =========================
# Load payload (si viene)
# =========================

payload = {}

if len(sys.argv) > 1:
    try:
        payload = json.loads(sys.argv[1])
    except Exception:
        payload = {}

report_title = payload.get("report_title", "Security Report")
summary = payload.get("summary", "Automated security telemetry analysis.")
sections = payload.get("sections", "Detailed analysis generated automatically.")

# =========================
# Output setup
# =========================

output_dir = "output/reports"
os.makedirs(output_dir, exist_ok=True)

filename = f"{output_dir}/{report_title.replace(' ', '_').lower()}.docx"

doc = Document()

# =========================
# Cover Page
# =========================

doc.add_heading(report_title, level=0)
doc.add_paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

doc.add_page_break()

# =========================
# Executive Summary
# =========================

doc.add_heading("Executive Summary", level=1)
doc.add_paragraph(summary)

doc.add_page_break()

# =========================
# Detailed Analysis
# =========================

doc.add_heading("Detailed Analysis", level=1)
doc.add_paragraph(sections)

# =========================
# Charts Section
# =========================

charts_dir = "output/charts"

if os.path.exists(charts_dir):
    chart_files = [f for f in os.listdir(charts_dir) if f.endswith(".png")]

    if chart_files:
        doc.add_page_break()
        doc.add_heading("Charts and Visual Evidence", level=1)

        for file in sorted(chart_files):
            chart_path = os.path.join(charts_dir, file)

            doc.add_picture(chart_path, width=Inches(6))
            doc.add_paragraph(
                file.replace(".png", "").replace("_", " "),
                style="Caption"
            )
            doc.add_page_break()

# =========================
# Save Document
# =========================

doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))
