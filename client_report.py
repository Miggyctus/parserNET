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
    "OBJECTIVOS Y ALCANCE",
    "ACTIVOS ANALIZADOS",
    "ANALISIS ESTADISTICO DE EVENTOS",
    "HALLAZGOS DETALLADOS Y MAPEO MITRE ATT&CK",
    "ANALISIS  DE TRAFICO DE SALIDA",
    "ANALISIS DE ACTIVIDAD LINUX Y LINEA DE COMANDOS",
    "ANALISIS DE RIESGO CONSOLIDADOS",
    "ANALISIS DE IDENTIDAD Y ACCESO",
    "ANALISIS DE CUMPLIMIENTO NORMATIVO",
    "OPORTUNIDADES DE MEJORA DE VISIBILIDAD",
    "RECOMENDACIONES Y ACCIONES A CORTO PLAZO",
    "HOJA DE RUTA DE REMEDIACION",
    "CONCLUSION"
]

SECTION_TOKEN_LIMITS = {
    "PORTADA E INDICE": 2800,
    "RESUMEN EJECUTIVO": 3000,
    "OBJECTIVOS Y ALCANCE": 2500,
    "ACTIVOS ANALIZADOS": 7000,
    "ANALISIS ESTADISTICO DE EVENTOS": 8000,
    "HALLAZGOS DETALLADOS Y MAPEO MITRE ATT&CK": 10000,
    "ANALISIS  DE TRAFICO DE SALIDA": 5000,
    "ANALISIS DE ACTIVIDAD LINUX Y LINEA DE COMANDOS": 6000,
    "ANALISIS DE RIESGO CONSOLIDADOS": 6500,
    "ANALISIS DE IDENTIDAD Y ACCESO": 6000,
    "ANALISIS DE CUMPLIMIENTO NORMATIVO": 7000,
    "OPORTUNIDADES DE MEJORA DE VISIBILIDAD": 4500,
    "RECOMENDACIONES Y ACCIONES A CORTO PLAZO": 5000,
    "HOJA DE RUTA DE REMEDIACION": 5000,
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
        "context_length": 40000,
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
        temperature=0.5,
        top_p=0.9,
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
        "objetivos_y_alcance": "OBJECTIVOS Y ALCANCE",
        "activos_analizados": "ACTIVOS ANALIZADOS",
        "analisis_estadistico_eventos": "ANALISIS ESTADISTICO DE EVENTOS",
        "hallazgos_mitre_attack": "HALLAZGOS DETALLADOS Y MAPEO MITRE ATT&CK",
        "analisis_trafico_salida": "ANALISIS  DE TRAFICO DE SALIDA",
        "analisis_linux_linea_comandos": "ANALISIS DE ACTIVIDAD LINUX Y LINEA DE COMANDOS",
        "analisis_riesgo_consolidado": "ANALISIS DE RIESGO CONSOLIDADOS",
        "analisis_identidad_acceso": "ANALISIS DE IDENTIDAD Y ACCESO",
        "analisis_cumplimiento": "ANALISIS DE CUMPLIMIENTO NORMATIVO",
        "oportunidades_mejora_visibilidad": "OPORTUNIDADES DE MEJORA DE VISIBILIDAD",
        "recomendaciones_corto_plazo": "RECOMENDACIONES Y ACCIONES A CORTO PLAZO",
        "hoja_ruta_remediacion": "HOJA DE RUTA DE REMEDIACION",
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