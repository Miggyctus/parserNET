import os
import json
import re
import unicodedata
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


def add_paragraph_with_formatting(text):
    """Add paragraph with support for bold, italic, strikethrough"""
    paragraph = doc.add_paragraph()
    
    # Split by bold **text**, italic *text*, strikethrough ~~text~~
    pattern = r"(\*\*.*?\*\*|~~.*?~~|\*[^*]+\*|_[^_]+_)"
    parts = re.split(pattern, text)
    
    i = 0
    while i < len(parts):
        part = parts[i]
        if not part:
            i += 1
            continue
            
        if part.startswith("**") and part.endswith("**"):
            # Bold
            clean_text = part[2:-2]
            run = paragraph.add_run(clean_text)
            run.bold = True
        elif part.startswith("~~") and part.endswith("~~"):
            # Strikethrough
            clean_text = part[2:-2]
            run = paragraph.add_run(clean_text)
            run.strike = True
        elif (part.startswith("*") and part.endswith("*")) or (part.startswith("_") and part.endswith("_")):
            # Italic (single * or _)
            clean_text = part[1:-1]
            run = paragraph.add_run(clean_text)
            run.italic = True
        else:
            # Inline code: `code`
            code_pattern = r"(`[^`]+`)"
            code_parts = re.split(code_pattern, part)
            for code_part in code_parts:
                if code_part.startswith("`") and code_part.endswith("`"):
                    clean_text = code_part[1:-1]
                    run = paragraph.add_run(clean_text)
                    run.font.name = "Courier New"
                    run.font.size = 90000  # 9pt in twips
                else:
                    paragraph.add_run(code_part)
        i += 1


def add_unordered_list(lines):
    """Add unordered list from markdown lines"""
    for line in lines:
        text = re.sub(r"^[\-\*]\s+", "", line.strip())
        paragraph = doc.add_paragraph(text, style="List Bullet")


def add_ordered_list(lines):
    """Add ordered list from markdown lines"""
    for i, line in enumerate(lines, 1):
        text = re.sub(r"^\d+\.\s+", "", line.strip())
        paragraph = doc.add_paragraph(text, style="List Number")


def add_code_block(lines):
    """Add code block to document"""
    code_text = "".join(lines).strip()
    paragraph = doc.add_paragraph(code_text, style="Normal")
    for run in paragraph.runs:
        run.font.name = "Courier New"
        run.font.size = 90000  # 9pt
    paragraph.paragraph_format.left_indent = Inches(0.5)


def add_blockquote(lines):
    """Add blockquote to document"""
    quote_text = "".join(lines).strip()
    quote_text = re.sub(r"^>\s+", "", quote_text)
    paragraph = doc.add_paragraph(quote_text, style="Normal")
    paragraph.paragraph_format.left_indent = Inches(0.5)
    for run in paragraph.runs:
        run.italic = True


# =========================
# Insert Report Content
# =========================

if os.path.exists(REPORT_TEXT_PATH):

    with open(REPORT_TEXT_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip completely empty lines (but add spacing)
        if not line:
            doc.add_paragraph()  # Adds vertical space
            i += 1
            continue

        # Headings
        if line.startswith("#"):
            add_heading_from_markdown(line)
            i += 1
            continue

        # Code blocks (``` ```)
        if line.startswith("```"):
            code_block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_block.append(lines[i])
                i += 1
            if code_block:
                add_code_block(code_block)
            i += 1  # Skip closing ```
            continue

        # Blockquotes
        if line.startswith(">"):
            blockquote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                blockquote_lines.append(lines[i])
                i += 1
            add_blockquote(blockquote_lines)
            continue

        # Unordered lists
        if re.match(r"^[\-\*]\s+", line):
            list_lines = []
            while i < len(lines) and re.match(r"^[\-\*]\s+", lines[i].strip()):
                list_lines.append(lines[i])
                i += 1
            add_unordered_list(list_lines)
            continue

        # Ordered lists
        if re.match(r"^\d+\.\s+", line):
            list_lines = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                list_lines.append(lines[i])
                i += 1
            add_ordered_list(list_lines)
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
        placeholder_match = re.match(r"\{\{CHART:\s*([a-z0-9_áéíóúñ]+)\s*\}\}", line, re.IGNORECASE)
        if placeholder_match:
            chart_id = placeholder_match.group(1)
            
            # Normalize chart_id: remove accents for file lookup
            chart_id_normalized = ''.join(
                c for c in unicodedata.normalize('NFD', chart_id)
                if unicodedata.category(c) != 'Mn'
            )
            
            chart_path = os.path.join(CHARTS_DIR, f"{chart_id_normalized}.png")

            if os.path.exists(chart_path):
                doc.add_picture(chart_path, width=Inches(6))
                title_text = chart_id.replace("_", " ").title()
                doc.add_paragraph(title_text, style="Caption")
            # If chart not found, skip silently (chart likely empty/unavailable)

            i += 1
            continue

        # Normal paragraph
        if line:
            add_paragraph_with_formatting(line)

        i += 1

else:
    doc.add_paragraph("Report text not found.")


doc.save(filename)

print(json.dumps({
    "generated_report": filename
}))