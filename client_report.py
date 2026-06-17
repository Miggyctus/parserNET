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
    "PORTADA E INDICE": 2000,
    "RESUMEN EJECUTIVO": 2500,
    "INTRODUCCIÓN": 2000,
    "EQUIPOS MONITOREADOS A LA FECHA": 3000,
    "RESUMEN DE CASOS": 3000,
    "TOP DE ORIGEN DE ATAQUES": 3500,
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": 4000,
    "TOP LOGIN": 2500,
    "DIRECTORIO ACTIVO": 2500,
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": 2500,
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": 2000,
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS": 3500,
    "REPORTE DE VOLUMEN DE LOGS": 2000,
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
    Simplified prompt that avoids complexity and repetition.
    Key: provide context from previous sections to avoid repeating them.
    """

    findings_json = json.dumps(
        findings,
        separators=(",", ":"),
        ensure_ascii=False
    )

    context_instruction = ""
    if previous_sections_text:
        context_instruction = f"""
CONTEXT FROM PREVIOUS SECTIONS:
(Use this to avoid repeating what's already been written. Reference earlier sections if needed, don't duplicate.)

{previous_sections_text[:2000]}

---
"""

    no_chart_instruction = ""
    if section in NO_CHART_SECTIONS:
        no_chart_instruction = "Do NOT insert chart placeholders in this section."

    return f"""Generate the "{section}" section for a formal SOC monthly report.

FINDINGS FOR THIS SECTION:
{findings_json}

{context_instruction}

INSTRUCTIONS:
1. Write ONLY this section ({section})
2. Use formal, professional SOC language (Spanish)
3. Focus on findings relevant to this section
4. Do NOT repeat information from previous sections
5. Keep narrative concise and analytical
6. Each statement must be data-driven (use findings provided)
7. Maximum 2 chart placeholders per section (format: {{{{CHART: chart_id}}}})
{no_chart_instruction}

OUTPUT:
Generate only the section content. No headers, no section title—just the body.
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
