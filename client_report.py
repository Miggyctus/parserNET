import json
import os
import httpx
import requests
from openai import OpenAI
from contextlib import contextmanager
import fitz

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"
PROMPT_FILE = "prompt_report.json"
CHART_JSON_PATH = "output/json/llm_output.json"
REPORT_TEXT_PATH = "output/reports/llm_report.txt"
CSV_FOLDER = "input_csv"

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=9999.0)
)

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
    "TOP DE ORIGEN DE ATAQUES": 10000,
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": 10000,
    "TOP LOGIN": 5000,
    "DIRECTORIO ACTIVO": 9000,
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": 5000,
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": 4500,
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS": 9000,
    "REPORTE DE VOLUMEN DE LOGS": 6000,
    "CONCLUSION": 3000
}

# =========================
# Model Load / Unload
# =========================

MODEL_INSTANCE_ID = None


def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 48000,
        "eval_batch_size": 256,
        "offload_kv_cache_to_gpu": True,
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


# =========================
# Utils
# =========================

def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def load_chart_json():
    if not os.path.exists(CHART_JSON_PATH):
        return {}
    with open(CHART_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_csv(folder_path: str) -> dict:
    csv_data = {}

    for file in os.listdir(folder_path):
        if not file.lower().endswith(".csv"):
            continue

        file_path = os.path.join(folder_path, file)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            csv_data[file] = content

        except Exception:
            continue

    return csv_data

def load_reference_report():
    path = "FL-OPE-23 V00 Informe de Incidentes SOC CADIEM 01032026 al 31032026.pdf"

    if not os.path.exists(path):
        return ""

    text = []

    with fitz.open(path) as doc:
        for page in doc:
            text.append(page.get_text())

    return "\n".join(text)
    
# =========================
# LLM Call
# =========================

def build_section_prompt(section, csv_data, reference):
    return f"""
    You are generating a SOC report section.

    SECTION: {section}

    STRICT RULES:
    - Only generate THIS section
    - Do NOT generate other sections
    - Use telemetry data strictly
    - Insert chart placeholders only when needed, following the naming rules
    - Maximum 2 charts per section, only if they add value to the section
    - use charts only when they add real analytical value
    - NEVER reuse the same chart_identifier across sections 
    - No repetition of charts across sections

    === DATA ===
    {json.dumps(csv_data, separators=(',', ':'))}

    === STYLE REFERENCE ===
    {reference}

    Generate ONLY the section content.
    """

def generate_section(section, system_prompt, csv_data, reference):
    prompt = build_section_prompt(section, csv_data, reference)
    maxTokens = SECTION_TOKEN_LIMITS.get(section, 2000)
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        top_p=0.85,
        max_tokens=maxTokens,
    )
    message = completion.choices[0].message

    if not message:
        raise RuntimeError(f"LLM returned empty response for section {section}")

    return message.content

def assemble_report(sections_content):
    report = []

    titles = {
    "portada_e_indice": "PORTADA E INDICE",
    "resumen_ejecutivo": "RESUMEN EJECUTIVO",
    "introduccion": "INTRODUCCIÓN",
    "equipos_monitoreados": "EQUIPOS MONITOREADOS A LA FECHA",
    "resumen_casos": "RESUMEN DE CASOS",
    "top_origen_ataques": "TOP DE ORIGEN DE ATAQUES",
    "actividades_sospechosas": "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS",
    "top_login": "TOP LOGIN",
    "directorio_activo": "DIRECTORIO ACTIVO",
    "actividad_admins": "ACTIVIDAD DE USUARIOS ADMINISTRADORES",
    "cambios_comunicaciones": "CAMBIOS EN EQUIPOS DE COMUNICACIONES",
    "reporte_alertas": "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS",
    "reporte_volumen_logs": "REPORTE DE VOLUMEN DE LOGS",
    "conclusion": "CONCLUSION"
}

    for section, content in sections_content.items():

        key = section.lower().replace(" ", "_")

        report.append(f"\n\n {titles.get(key, section)}\n\n{content}")

    return "\n".join(report)


# =========================
# Public Function
# =========================

def generate_report():

    system_prompt = load_system_prompt()
    chart_data = load_chart_json()
    csv_data = load_all_csv(CSV_FOLDER)
    reference = load_reference_report()

    sections_content ={}

    with model_session():
        for section in SECTIONS:
            print(f"Generating {section}...")
            content = generate_section(
                section,
                system_prompt,
                csv_data,
                reference
            )
            sections_content[section] = content
        final_report = assemble_report(sections_content)

        os.makedirs("output/reports", exist_ok=True)

        with open(REPORT_TEXT_PATH, "w", encoding="utf-8") as f:
            f.write(final_report)

        return final_report


def main():
    print("Generating audit report...")
    generate_report()
    print("Report generated successfully.")


if __name__ == "__main__":
    main()