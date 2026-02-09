import sys
import json
import os
from docx import Document
from docx.shared import Inches

payload = json.loads(sys.argv[1])

report_title = payload["report_title"]
summary = payload["summary"]
sections = payload["sections"]
charts_used = payload.get("charts_used", [])

output_dir = "output/reports"
os.makedirs(output_dir, exist_ok=True)

filename = f"{output_dir}/{report_title.replace(' ', '_').lower()}.docx"

doc = Document()

# Cover
doc.add_heading(report_title, level=0)

# Executive Summary
doc.add_heading("Executive Summary", level=1)
doc.add_paragraph(summary)

# Body Sections
doc.add_page_break()
doc.add_heading("Detailed Analysis", level=1)
doc.add_paragraph(sections)

# Charts
if charts_used:
    doc.add_page_break()
    doc.add_heading("Charts and Visual Evidence", level=1)

    for chart_id in charts_used:
        chart_path = f"output/charts/{chart_id}.png"
        if os.path.exists(chart_path):
            doc.add_picture(chart_path, width=Inches(6))
            doc.add_paragraph(f"Figure: {chart_id}")

doc.save(filename)

print(filename)
