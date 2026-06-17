# Quick Start: Option A Pipeline

## What Was Changed?

Three things:

1. **NEW: `consolidate_findings.py`** — Deduplicates findings before report
2. **UPDATED: `client_report.py`** — Simpler, with context awareness to prevent repetition  
3. **UPDATED: `client_charts.py`** — Charts from findings metadata, not report text
4. **UPDATED: `runPipeline.py`** — Consolidation step added

## Run Your First Report

```bash
python runPipeline.py
```

That's it. It will:
1. Analyze CSVs → `output/intelligence/batch_*.json`
2. Consolidate findings → `output/consolidated_findings.json`
3. Generate report → `output/reports/llm_report.txt`
4. Generate charts → `output/json/llm_output.json`
5. Render images → `output/charts/*.png`
6. Create DOCX → `output/reports/security_audit_report.docx`

---

## What to Expect (vs. Before)

### ✅ Improvements

| Problem | Before | After |
|---------|--------|-------|
| **Repetition** | "Failed logins" mentioned 3x in different sections | Consolidated—each finding appears once in primary section |
| **Inconsistency** | VPN activity described differently in different sections | Context-aware generation—consistent narrative |
| **Garbled chars** | Model gets confused, inserts random chars | Simpler prompts → better output quality |
| **Chart reliability** | Sometimes charts reference placeholders that don't exist | Charts mapped from findings metadata |
| **Large CSVs** | Works but slow | Still works, now cleaner consolidation |

### 🔧 Tuneable Parameters

If you want to adjust behavior, edit:

**consolidate_findings.py:**
```python
SECTION_MAPPING = {
    "TOP DE ORIGEN DE ATAQUES": ["origin", "source", ...],
    # Add keywords to assign findings to correct sections
}
```

**client_report.py:**
```python
SECTION_TOKEN_LIMITS = {
    "TOP DE ORIGEN DE ATAQUES": 3500,  # Increase if sections cut off
}
```

---

## Verify It Works

### 1. Check consolidated findings created:
```bash
ls -lh output/consolidated_findings.json
```

### 2. Preview what findings go where:
```bash
python -c "
import json
with open('output/consolidated_findings.json') as f:
    data = json.load(f)
for section, findings in data.get('by_section', {}).items():
    print(f'{section}: {len(findings)} findings')
"
```

### 3. Check report generated:
```bash
wc -l output/reports/llm_report.txt
```

Should be 500+ lines for a full report.

### 4. Scan for repetition (quick check):
```bash
# Count occurrences of common phrases
grep -io "credenciales" output/reports/llm_report.txt | wc -l
# Should be < 5 (low repetition)
```

---

## If Repetition Still Happens

### Quick fixes (try in order):

**1. Reduce token limits** (forces conciseness):
```python
# client_report.py
SECTION_TOKEN_LIMITS = {
    "TOP DE ORIGEN DE ATAQUES": 2500,  # Was 3500
    "TOP LOGIN": 1800,  # Was 2500
}
```

**2. Further simplify the prompt** (client_report.py, `build_section_prompt()`):
```python
# Remove or simplify instructions, especially the detailed ones
# Keep only: "write this section, use provided findings, avoid repeating previous sections"
```

**3. Increase context** (client_report.py, line ~180):
```python
# Pass more previous sections to give LLM better awareness
previous_sections_text=accumulated_text  # Currently does this
```

**4. Switch model:**
```python
# client_report.py, line 19
MODEL_ID = "mistralai/ministral-3-14b-reasoning"  # Try this instead of gpt-oss-20b
```

---

## Integration with Your Workflow

### If you already have CSV files ready:
```bash
# Just run the pipeline
python runPipeline.py
```

### If you want to debug consolidation:
```bash
python consolidate_findings.py
# Produces: output/consolidated_findings.json

# Then check what findings were merged:
cat output/consolidated_findings.json | python -m json.tool | head -100
```

### If you want to regenerate just the report:
```bash
python client_report.py
# (Assumes consolidated_findings.json already exists)
```

---

## What the Consolidated Findings Look Like

```json
{
  "total_findings": 42,
  "findings": [
    {
      "title": "VPN Access from Multiple Locations",
      "summary": "17 external IPs, 4 users, Paraguay and Argentina",
      "severity": "high",
      "primary_section": "TOP LOGIN",
      "key_evidence": [
        "3812 failed logins",
        "17 external IPs",
        "Paraguay and Argentina only"
      ],
      "tags": ["vpn", "authentication", "geographic-anomaly"],
      "recommended_sections": ["TOP LOGIN", "TOP DE ORIGEN DE ATAQUES"],
      "chart_candidate": true,
      "chart_priority": 85
    }
  ],
  "by_section": {
    "TOP LOGIN": [/* findings for this section only */],
    "TOP DE ORIGEN DE ATAQUES": [/* findings for this section only */],
    ...
  }
}
```

---

## Real Example Flow

```
INPUT: input_csv/*.csv (large LogRhythm exports)
  ↓
client_csv.py analyzes each CSV → finds: VPN anomaly, Tor traffic, failed logins
  ↓
OUTPUT: output/intelligence/batch_1.json, batch_2.json, ...
{
  "findings": [
    {"title": "VPN from Paraguay", "recommended_sections": ["TOP LOGIN"], ...},
    {"title": "Tor traffic detected", "recommended_sections": ["TOP DE ORIGEN"], ...},
    ...
  ]
}
  ↓
consolidate_findings.py deduplicates + assigns primary sections
  ↓
OUTPUT: output/consolidated_findings.json
{
  "findings": [/* 42 unique findings */],
  "by_section": {
    "TOP LOGIN": [/* 8 findings for this section */],
    "TOP DE ORIGEN DE ATAQUES": [/* 12 findings for this section */],
    ...
  }
}
  ↓
client_report.py generates sections sequentially
  For each section:
    - Load findings for THIS section
    - Load text from PREVIOUS sections
    - Ask LLM: "Write TOP LOGIN section, don't repeat what we already said"
  ↓
OUTPUT: output/reports/llm_report.txt
"# TOP LOGIN\n\n...[section content, no repetition]..."
  ↓
Rest of pipeline continues (charts, Word doc, etc.)
```

---

## Success Criteria

✅ Report generates successfully
✅ No "same fact repeated in different sections" 
✅ Section tone is consistent throughout
✅ No garbled characters or strange repetition
✅ Charts generate without errors
✅ DOCX includes all sections + charts

If all ✅, you're done!

---

## Support

See `SOLUTION_NOTES.md` for detailed explanation of what changed and why.

For issues with the pipeline itself, check:
- `output/consolidated_findings.json` exists
- `output/intelligence/batch_*.json` exists  
- Model loading succeeds (check logs)
- LM Studio is running on localhost:1234
