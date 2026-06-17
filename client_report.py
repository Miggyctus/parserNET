import json
import os
import re
import httpx
import requests

from openai import OpenAI
from contextlib import contextmanager
from typing import Dict, Any

# =========================================================
# CONFIG
# =========================================================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "gpt-oss-20b"
PROMPT_FILE = "prompt_report.json"
REPORT_TEXT_PATH = "output/reports/llm_report.txt"
CONSOLIDATED_FINDINGS_PATH = "output/consolidated_findings.json"

# =========================================================
# CLIENT
# =========================================================

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=9999.0)
)

MODEL_INSTANCE_ID = None

# =========================================================
# SECTIONS (IN ORDER)
# =========================================================

SECTIONS = [
    "PORTADA E INDICE",
    "RESUMEN EJECUTIVO",
    "INTRODUCCIÓN",
    "EQUIPOS MONITOREADOS A LA FECHA",
    "RESUMEN DE CASOS",
    "TOP DE ORIGEN DE ATAQUES",
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS",
    "TOP LOGIN",
    "DIRECTORIO ACTIVO",
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES",
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES",
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS",
    "REPORTE DE VOLUMEN DE LOGS",
    "CONCLUSION"
]

SECTION_TOKEN_LIMITS = {
    "PORTADA E INDICE": 1500,
    "RESUMEN EJECUTIVO": 2000,
    "INTRODUCCIÓN": 1500,
    "EQUIPOS MONITOREADOS A LA FECHA": 2000,
    "RESUMEN DE CASOS": 2500,
    "TOP DE ORIGEN DE ATAQUES": 5000,
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": 5500,
    "TOP LOGIN": 6000,
    "DIRECTORIO ACTIVO": 5500,
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": 6000,
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": 2500,
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS": 6000,
    "REPORTE DE VOLUMEN DE LOGS": 2500,
    "CONCLUSION": 2000
}

NO_CHART_SECTIONS = {
    "PORTADA E INDICE",
    "INTRODUCCIÓN",
    "RESUMEN EJECUTIVO",
    "CONCLUSION"
}

# =========================================================
# MODEL SESSION
# =========================================================

def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 49000,
        "eval_batch_size": 256,
        "offload_kv_cache_to_gpu": True,
        "flash_attention": True,
        "echo_load_config": True
    }

    response = requests.post(
        "http://localhost:1234/api/v1/models/load",
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        raise RuntimeError(f"Failed to load model: {response.text}")

    data = response.json()
    if data.get("status") != "loaded":
        raise RuntimeError(f"Model failed to load: {data}")

    MODEL_INSTANCE_ID = data.get("instance_id")
    print("Report model loaded")

def unload_model():
    global MODEL_INSTANCE_ID

    if not MODEL_INSTANCE_ID:
        return

    requests.post(
        "http://localhost:1234/api/v1/models/unload",
        json={"instance_id": MODEL_INSTANCE_ID},
        timeout=60
    )

    MODEL_INSTANCE_ID = None
    print("Report model unloaded")

@contextmanager
def model_session():
    load_model()
    try:
        yield
    finally:
        unload_model()

# =========================================================
# LOADERS
# =========================================================

def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]

def load_consolidated_findings() -> Dict[str, Any]:
    if not os.path.exists(CONSOLIDATED_FINDINGS_PATH):
        return {"findings": [], "by_section": {}}

    with open(CONSOLIDATED_FINDINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# =========================================================
# FINDING RETRIEVAL
# =========================================================

def get_findings_for_section(section: str, consolidated: Dict[str, Any]):
    """Get findings assigned to this section."""
    by_section = consolidated.get("by_section", {})
    return by_section.get(section, [])

# =========================================================
# CHART LIMITER
# =========================================================

def remove_all_charts(content: str) -> str:
    pattern = r"\{\{CHART:.*?\}\}"
    return re.sub(pattern, "", content, flags=re.DOTALL)

# =========================================================
# PROMPT BUILDERS (SIMPLIFIED)
# =========================================================

def build_section_prompt(
    section: str,
    findings: list,
    previous_sections_text: str = ""
) -> str:
    """
    Structured prompt that guides substantive analysis from findings.
    Key: force the LLM to actually analyze and structure findings content.
    """

    findings_json = json.dumps(
        findings,
        separators=(",", ":"),
        ensure_ascii=False
    )

    context_instruction = ""
    if previous_sections_text:
        context_instruction = f"""
PREVIOUSLY COVERED (don't repeat):
{previous_sections_text[:1500]}

---
AVOID REPEATING the above. Focus only on findings NOT yet discussed.
"""

    no_chart_instruction = ""
    if section in NO_CHART_SECTIONS:
        no_chart_instruction = "\n\nDo NOT insert any chart placeholders {{{{CHART:...}}}} in this section."

    return f"""Generate ONLY the "{section}" section for a formal SOC audit report.

FINDINGS TO ANALYZE ({len(findings)} findings):
{findings_json}

{context_instruction}

STRUCTURE (mandatory):
1. INTRO: 1-2 sentences summarizing the key findings/themes for this section
2. FINDINGS ANALYSIS: For EACH finding (in order), write 2-3 sentences covering:
   - What was detected (from title + summary)
   - The evidence (from key_evidence)
   - The significance/implication
3. PATTERNS: If multiple findings share a theme, identify the pattern
4. RECOMMENDATIONS: 2-3 bulleted action items specific to these findings

STYLE:
- Professional SOC language (Spanish, formal)
- Data-driven (cite numbers from key_evidence)
- Analytical (explain implications, not just facts)
- Concise (total section ~400-600 words)
- USE BOLD for emphasis: **important terms**, **numbers**, **findings titles**

FORMATTING:
- Use **bold text** (with asterisks) for emphasis, key metrics, and finding titles
- Use numbered lists for recommendations: 1. item, 2. item, 3. item
- Use bullet points for evidence details: - item, - item

OUTPUT:
Raw section content only. No section header, no title—just the body text starting with the intro.
Maximum 2 chart placeholders total (format: {{{{CHART: chart_id}}}})
{no_chart_instruction}
"""

# =========================================================
# SECTION GENERATION
# =========================================================

def generate_section(
    section: str,
    system_prompt: str,
    findings: list,
    previous_sections_text: str = ""
) -> str:
    """
    Generate a single section with context awareness.
    Previous sections passed in to prevent repetition.
    """

    prompt = build_section_prompt(section, findings, previous_sections_text)
    max_tokens = SECTION_TOKEN_LIMITS.get(section, 2000)

    try:
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.05,
            top_p=0.35,
            max_tokens=max_tokens
        )

        message = completion.choices[0].message
        if not message or not message.content:
            raise RuntimeError(f"Empty response for section: {section}")

        content = message.content.strip()

        # Enforce chart rules
        if section in NO_CHART_SECTIONS:
            content = remove_all_charts(content)
        else:
            # Limit to max 2 charts
            charts = re.findall(r"\{\{CHART:.*?\}\}", content, flags=re.DOTALL)
            if len(charts) > 2:
                content = re.sub(r"\{\{CHART:.*?\}\}", "", content, flags=re.DOTALL, count=len(charts) - 2)

        return content

    except Exception as e:
        print(f"Error generating {section}: {e}")
        return ""

# =========================================================
# REPORT ASSEMBLY
# =========================================================

def assemble_report(sections_content: Dict[str, str]) -> str:
    """Assemble final report from section contents."""
    report = []

    for section in SECTIONS:
        content = sections_content.get(section, "")
        if content.strip():
            report.append(f"\n# {section}\n\n{content}")

    return "\n".join(report)

# =========================================================
# MAIN GENERATION
# =========================================================

def generate_report():
    """
    Sequential section generation with context awareness.
    Each section knows about previous sections to prevent repetition.
    """

    print("Loading consolidated findings...")
    consolidated = load_consolidated_findings()
    total_findings = consolidated.get("total_findings", 0)
    print(f"  Loaded {total_findings} consolidated findings")

    system_prompt = load_system_prompt()
    sections_content = {}
    accumulated_text = ""

    with model_session():

        for section in SECTIONS:

            print(f"Generating: {section}")

            # Get findings for this section
            findings = get_findings_for_section(section, consolidated)
            finding_count = len(findings)
            print(f"  {finding_count} findings for this section")

            # Generate with context from previous sections
            content = generate_section(
                section=section,
                system_prompt=system_prompt,
                findings=findings,
                previous_sections_text=accumulated_text
            )

            sections_content[section] = content
            accumulated_text += f"\n# {section}\n{content}"

            if not content.strip():
                print(f"  WARNING: Empty content for {section}")

    # Assemble final report
    final_report = assemble_report(sections_content)

    # Save
    os.makedirs("output/reports", exist_ok=True)
    with open(REPORT_TEXT_PATH, "w", encoding="utf-8") as f:
        f.write(final_report)

    print(f"\nReport saved: {REPORT_TEXT_PATH}")
    return final_report

# =========================================================
# MAIN
# =========================================================

def main():
    print("=" * 60)
    print("SOC REPORT GENERATION")
    print("=" * 60)
    print()

    generate_report()

    print()
    print("=" * 60)
    print("Report generation complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
