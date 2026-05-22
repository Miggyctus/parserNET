import json
import os
import re
import httpx
import requests
import fitz

from openai import OpenAI
from contextlib import contextmanager
from typing import List, Dict, Any

# =========================================================
# CONFIG
# =========================================================

BASE_URL = "http://localhost:1234/v1"

MODEL_ID = "foundation-sec-8b-reasoning"

PROMPT_FILE = "prompt_report.json"

REPORT_TEXT_PATH = "output/reports/llm_report.txt"

INTELLIGENCE_DIR = "output/intelligence"

REFERENCE_REPORT_PATH = "SOC_Reporte_Modelo_NETLOGIC.pdf"

MAX_CHARTS_PER_SECTION = 2

# =========================================================
# CLIENT
# =========================================================

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=9999.0)
)

# =========================================================
# SECTION CONFIG
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
    "PORTADA E INDICE": 2800,
    "RESUMEN EJECUTIVO": 3000,
    "INTRODUCCIÓN": 2500,
    "EQUIPOS MONITOREADOS A LA FECHA": 7000,
    "RESUMEN DE CASOS": 8000,
    "TOP DE ORIGEN DE ATAQUES": 7000,
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": 8000,
    "TOP LOGIN": 5000,
    "DIRECTORIO ACTIVO": 7000,
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": 5000,
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": 4500,
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS": 9000,
    "REPORTE DE VOLUMEN DE LOGS": 5000,
    "CONCLUSION": 3500
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

MODEL_INSTANCE_ID = None


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
        raise RuntimeError(
            f"Failed to load model: {response.text}"
        )

    data = response.json()

    if data.get("status") != "loaded":
        raise RuntimeError(
            f"Model failed to load: {data}"
        )

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
# FILE LOADERS
# =========================================================

def load_system_prompt():

    with open(
        PROMPT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)["system_prompt"]


def load_reference_style():

    if not os.path.exists(
        REFERENCE_REPORT_PATH
    ):
        return ""

    pages = []

    with fitz.open(
        REFERENCE_REPORT_PATH
    ) as doc:

        for page in doc:

            pages.append(
                page.get_text()
            )

    full_text = "\n".join(pages)

    # =====================================================
    # compact style guide
    # =====================================================

    compact_style = full_text[:12000]

    return compact_style


def load_intelligence_batches():

    intelligence_batches = []

    if not os.path.exists(INTELLIGENCE_DIR):
        return intelligence_batches

    files = sorted(
        os.listdir(INTELLIGENCE_DIR)
    )

    for file in files:

        if not file.endswith(".json"):
            continue

        path = os.path.join(
            INTELLIGENCE_DIR,
            file
        )

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                intelligence_batches.append(
                    json.load(f)
                )

        except Exception as e:

            print(
                f"Failed loading {file}: {e}"
            )

    return intelligence_batches


# =========================================================
# FINDING RETRIEVAL
# =========================================================

def retrieve_findings_for_section(
    section: str,
    intelligence_batches: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    relevant_findings = []

    for batch in intelligence_batches:

        findings = batch.get(
            "findings",
            []
        )

        if not isinstance(findings, list):
            continue

        for finding in findings:

            if not isinstance(finding, dict):
                continue

            recommended_sections = finding.get(
                "recommended_sections",
                []
            )

            if section in recommended_sections:

                relevant_findings.append(
                    finding
                )

    return relevant_findings


# =========================================================
# CHART LIMITER
# =========================================================

def enforce_chart_limits(
    content: str,
    max_charts: int = MAX_CHARTS_PER_SECTION
) -> str:

    pattern = r"\{\{CHART:.*?\}\}"

    matches = list(
        re.finditer(
            pattern,
            content,
            flags=re.DOTALL
        )
    )

    if len(matches) <= max_charts:
        return content

    for match in matches[max_charts:]:

        content = content.replace(
            match.group(0),
            ""
        )

    return content


def remove_all_charts(content: str) -> str:

    pattern = r"\{\{CHART:.*?\}\}"

    return re.sub(
        pattern,
        "",
        content,
        flags=re.DOTALL
    )


# =========================================================
# PROMPT BUILDERS
# =========================================================

def build_section_prompt(
    section: str,
    findings: List[Dict[str, Any]],
    reference_style: str
):

    findings_json = json.dumps(
        findings,
        separators=(",", ":"),
        ensure_ascii=False
    )

    no_chart_instruction = ""

    if section in NO_CHART_SECTIONS:

        no_chart_instruction = """
- DO NOT insert chart placeholders
- DO NOT suggest charts
"""

    return f"""
You are generating a SOC report section.

SECTION:
{section}

STRICT RULES:

- Generate ONLY this section
- Do NOT generate other sections
- Use ONLY provided findings
- Do NOT hallucinate telemetry
- Use professional SOC reporting tone
- Keep narrative concise and analytical
- Avoid repetitive explanations
- Avoid generic cybersecurity filler

CHART RULES:

{no_chart_instruction}

- Insert charts ONLY if they provide real analytical value
- Maximum 2 charts
- Never repeat chart identifiers
- Use chart placeholders only when justified

AVAILABLE FINDINGS:
{findings_json}

STYLE GUIDE:
{reference_style}

OUTPUT:
Generate ONLY the section content.
"""


# =========================================================
# SECTION GENERATION
# =========================================================

def generate_section(
    section: str,
    system_prompt: str,
    findings: List[Dict[str, Any]],
    reference_style: str
):

    prompt = build_section_prompt(
        section,
        findings,
        reference_style
    )

    max_tokens = SECTION_TOKEN_LIMITS.get(
        section,
        3000
    )

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

        raise RuntimeError(
            f"Empty response for section: {section}"
        )

    content = message.content.strip()

    # =====================================================
    # enforce chart rules
    # =====================================================

    if section in NO_CHART_SECTIONS:

        content = remove_all_charts(
            content
        )

    else:

        content = enforce_chart_limits(
            content
        )

    return content


# =========================================================
# REPORT ASSEMBLY
# =========================================================

def assemble_report(
    sections_content: Dict[str, str]
):

    report = []

    for section in SECTIONS:

        content = sections_content.get(
            section,
            ""
        )

        report.append(
            f"\n\n# {section}\n\n{content}"
        )

    return "\n".join(report)


# =========================================================
# REPORT GENERATION
# =========================================================

def generate_report():

    system_prompt = load_system_prompt()

    reference_style = load_reference_style()

    intelligence_batches = load_intelligence_batches()

    sections_content = {}

    with model_session():

        for section in SECTIONS:

            print(
                f"Generating section: {section}"
            )

            # =============================================
            # SECTION-SCOPED CONTEXT
            # =============================================

            findings = retrieve_findings_for_section(
                section,
                intelligence_batches
            )

            print(
                f"Retrieved findings: "
                f"{len(findings)}"
            )

            content = generate_section(
                section=section,
                system_prompt=system_prompt,
                findings=findings,
                reference_style=reference_style
            )

            sections_content[section] = content

    final_report = assemble_report(
        sections_content
    )

    os.makedirs(
        "output/reports",
        exist_ok=True
    )

    with open(
        REPORT_TEXT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(final_report)

    print(
        f"Report saved: {REPORT_TEXT_PATH}"
    )

    return final_report


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "Generating SOC report..."
    )

    generate_report()

    print(
        "SOC report generated successfully."
    )


if __name__ == "__main__":
    main()