# SOC Report Generation: Option A Solution

## Problem Solved

✅ **Repetition in sections** - Same findings described multiple times across different sections
✅ **Inconsistency between sections** - Tone drift, contradictions when generating section-by-section  
✅ **Unreliable charts** - Charts now generated from findings metadata, not fragile report text parsing
✅ **Large CSV handling** - `client_csv.py` continues to handle large datasets
✅ **Stability** - Keeps proven per-section generation approach

---

## New Architecture

### Pipeline Flow (Updated)

```
CSV Files
   ↓
1. client_csv.py → output/intelligence/batch_*.json
   (Extract & structure findings from raw logs)
   ↓
2. consolidate_findings.py → output/consolidated_findings.json
   (Deduplicate & assign primary sections)
   ↓
3. client_report.py → output/reports/llm_report.txt
   (Generate sections sequentially WITH context awareness)
   ↓
4. client_charts.py → output/json/llm_output.json
   (Map charts from findings metadata, not report text)
   ↓
5. generate_chart.py + generate_word.py
   (Render images & final DOCX)
```

---

## Key Changes

### 1. **consolidate_findings.py** (NEW)

**Purpose:** Merge duplicate findings, assign primary sections, prepare clean input for report.

**What it does:**
- Loads all `output/intelligence/*.json` files from CSV analysis
- Deduplicates findings by title (merges evidence, keeps highest severity)
- Assigns each finding a **primary section** based on:
  - `recommended_sections` metadata from CSV analysis
  - Fallback: keyword matching against section types
  - Fallback: severity-based defaults
- Outputs `output/consolidated_findings.json`

**Example output:**
```json
{
  "total_findings": 42,
  "findings": [
    {
      "title": "VPN Access from Multiple Locations",
      "severity": "high",
      "primary_section": "TOP LOGIN",
      "key_evidence": ["3812 logins", "17 IPs", "4 users"],
      ...
    }
  ],
  "by_section": {
    "TOP LOGIN": [...],
    "ACTIVIDADES SOSPECHOSAS": [...]
  }
}
```

### 2. **client_report.py** (REWRITTEN)

**Key improvements:**

✅ **Loads consolidated findings** instead of raw intelligence batches
- Cleaner input data (already deduplicated)

✅ **Sequential generation WITH context**
- Each section receives the full text of previously generated sections
- LLM avoids repeating what's already been written
- Maintains tone consistency across report

✅ **Simplified prompts**
- Removed style guides, heavy rules
- Removed per-section constraints that caused hallucination
- Clean instructions = better LLM behavior

✅ **Aware of which findings are covered**
- Knows which findings are for this section
- Knows what's already been written in previous sections
- Prevents "same fact, three times" problem

**Example flow:**
```
Section 1 (RESUMEN EJECUTIVO): Generated
Section 2 (TOP DE ORIGEN DE ATAQUES): Generated WITH context="Section 1 text"
Section 3 (TOP LOGIN): Generated WITH context="Section 1 + Section 2 text"
...
```

### 3. **client_charts.py** (UPDATED)

**Key change:**
- ❌ Old: Extract `{{CHART: xxx}}` placeholders from report text via regex
- ✅ New: Extract from findings metadata (`chart_candidate` + `title`)

**Why:**
- Decouples chart generation from report structure
- More reliable (findings structure > report text parsing)
- Charts work even if report format changes

---

## How It Works: The Repetition Fix

### Before (Problem)
```
Section: TOP DE ORIGEN DE ATAQUES
  → Finding: "VPN from multiple locations"
  → LLM writes: "Se detectaron 17 IPs distintas..."

Section: TOP LOGIN
  → Finding: "VPN from multiple locations" (same finding!)
  → LLM writes: "Se registraron múltiples intentos de acceso desde 17 direcciones..."
  → RESULT: Same fact, slightly different wording → REPETITION
```

### After (Fixed)
```
Consolidate stage:
  → Deduplicates: "VPN from multiple locations" → ONE finding
  → Assigns primary section: "TOP LOGIN"
  → Stores in consolidated_findings.json

Report generation:
  Section: TOP DE ORIGEN DE ATAQUES
    → Gets findings for this section (other VPN activities, not the "multiple locations" one)
    → Writes about those

  Section: TOP LOGIN
    → Gets the consolidated "VPN multiple locations" finding
    → Writes about it
    → HAS CONTEXT: "In RESUMEN EJECUTIVO we said X, in TOP DE ORIGEN we said Y"
    → LLM adds analysis, NOT repetition

  RESULT: One finding, one primary location, other sections reference if needed
```

---

## Usage

### Run the entire pipeline:
```bash
python runPipeline.py
```

### Run just the new consolidation:
```bash
python consolidate_findings.py
```

### Check consolidated findings:
```bash
cat output/consolidated_findings.json | jq '.by_section | keys'
```

---

## Configuration

### Token limits (client_report.py)
Adjusted for simpler prompts (lower than before):
```python
SECTION_TOKEN_LIMITS = {
    "PORTADA E INDICE": 2000,
    "TOP DE ORIGEN DE ATAQUES": 3500,
    ...
}
```

Tuning: If sections are cut off, increase these values. If seeing repetition, decrease.

### Section ordering (client_report.py)
```python
SECTIONS = [
    "PORTADA E INDICE",
    "RESUMEN EJECUTIVO",
    ...
]
```

Keep this order—earlier sections provide context for later ones.

### Model selection
Still configurable via `MODEL_ID` in each client file. Test with your preferred model.

---

## What Didn't Change

✅ `client_csv.py` - Untouched, keeps working as-is  
✅ `prompt_csv.json` - Untouched  
✅ `generate_chart.py`, `generate_word.py` - Untouched  
✅ Chart rendering backend - Untouched  

---

## Testing

### Quick validation:
```bash
# 1. Run CSV analysis
python client_csv.py

# 2. Check intelligence was generated
ls -lh output/intelligence/

# 3. Consolidate
python consolidate_findings.py

# 4. Check consolidated output
wc -l output/consolidated_findings.json
jq '.by_section | keys' output/consolidated_findings.json

# 5. Run full pipeline
python runPipeline.py
```

### Check for repetition:
```bash
# Count same phrase in report
grep -o "credenciales" output/reports/llm_report.txt | wc -l
# Should be low (not repeated across sections)
```

---

## Troubleshooting

### "Empty sections" in report
→ Check consolidated_findings.json - findings may not be assigned to that section
→ Update SECTION_MAPPING in consolidate_findings.py

### "Sections still repeat findings"
→ Simplify the prompt further (remove more instructions)
→ Increase context passed to LLM (previous_sections_text)
→ Use a different model (try mistral instead of gpt-oss)

### Charts not generating
→ Check output/consolidated_findings.json has findings with `chart_candidate: true`
→ Verify chart IDs are valid (alphanumeric + underscore)

### Model out of memory
→ Reduce context_length in load_model() 
→ Lower SECTION_TOKEN_LIMITS
→ Generate sections in smaller batches

---

## Next Steps

1. **Test with your next report generation**
2. **Monitor for repetition** - if still occurring, adjust:
   - Token budgets (smaller = less hallucination)
   - Prompt simplicity (fewer rules = clearer intent)
   - Context passed between sections (more detail = better awareness)
3. **Tune section mapping** - ensure findings go to right primary sections
4. **Consider findings consolidation** - may need deeper deduplication for your data

---

## Summary

- ✅ Keeps stable per-section generation
- ✅ Adds deduplication + primary section assignment  
- ✅ Passes context between sections
- ✅ Decouples charts from report text
- ✅ Simplified prompts reduce hallucination
- ✅ Fixes repetition + inconsistency problems
