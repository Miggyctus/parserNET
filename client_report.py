import json
import os
import re
import httpx
import requests
from openai import OpenAI
from contextlib import contextmanager
import fitz

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
#foundation-sec-8b-reasoning
#glm-4.7-flash-claude-opus-4.5-high-reasoning-distill
MODEL_ID = "foundation-sec-8b-reasoning"
PROMPT_FILE = "prompt_report.json"
CHART_JSON_PATH = "output/json/llm_output.json"
REPORT_TEXT_PATH = "output/reports/llm_report.txt"
INTELLIGENCE_DIR = "output/intelligence"

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
    "RESUMEN DE CASOS": 3500,
    "TOP DE ORIGEN DE ATAQUES": 10000,
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": 10000,
    "TOP LOGIN": 5000,
    "DIRECTORIO ACTIVO": 9000,
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": 5000,
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": 4500,
    "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS": 6000,
    "REPORTE DE VOLUMEN DE LOGS": 6000,
    "CONCLUSION": 4000
}

# =========================
# Model Load / Unload
# =========================

MODEL_INSTANCE_ID = None


def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 49000,
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

REFERENCE_MAX_CHARS = 6000


def load_reference_report():
    path = "SOC_Reporte_Modelo_NETLOGIC.pdf"

    if not os.path.exists(path):
        return ""

    text = []

    with fitz.open(path) as doc:
        for page in doc:
            text.append(page.get_text())

    # Truncated on purpose: the full reference is another client's complete
    # report. Passing it whole leads the model to reproduce entire sections
    # of it (structure, findings, tables) instead of only imitating tone.
    return "\n".join(text)[:REFERENCE_MAX_CHARS]
    
# =========================
# LLM Call
# =========================

def build_section_prompt(section, intelligence_batches, reference):
    return f"""
    You are generating a SOC report section.

    SECTION: {section}

    STRICT RULES:
    - Only generate THIS section
    - Do NOT generate other sections
    - Use telemetry data strictly
    - Insert chart placeholders only when needed, following the naming rules
    - NO charts for the "PORTADA E INDICE", "INTRODUCCIÓN" "RESUMEN EJECUTIVO" and "CONCLUSION" sections
    - MAXIMUM 2 charts per section, only if they add value to the section
    - use charts only when they add real analytical value
    - NEVER reuse the same chart_identifier across sections
    - No repetition of charts across sections
    - NEVER generate two HALLAZGO entries with the same or substantially similar Evidencia Directa. Prefer fewer, distinct findings over padding.

    === DATA (real telemetry intelligence — the only source for IPs, usernames, hosts, event counts, and dates of events) ===
    {json.dumps(intelligence_batches, separators=(',', ':'))}

    === STYLE REFERENCE (excerpt from a DIFFERENT client's past report — imitate ONLY its tone, structure and formatting. NEVER copy a placeholder like [NOMBRE_EMPRESA]/[IP]/[DD/MM/AAAA], or any company name, IP, date, hostname or number from this section into your output) ===
    {reference}

    Generate ONLY the section content.
    """

def generate_section(section, system_prompt, intelligence_batches, reference):
    prompt = build_section_prompt(section, intelligence_batches, reference)
    maxTokens = SECTION_TOKEN_LIMITS.get(section, 2000)
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        top_p=0.7,
        max_tokens=maxTokens,
    )
    message = completion.choices[0].message

    if not message:
        raise RuntimeError(f"LLM returned empty response for section {section}")

    return message.content

FINDING_HEADER_RE = re.compile(r'^(?:HALLAZGO[-\s]?\d+|HAL-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b', re.IGNORECASE)


def strip_leaked_index_preamble(section, content):
    """The local model sometimes prefixes a section with a leaked copy of the
    report index (PORTADA E INDICE + numbered list of all 14 sections) before
    finally writing this section's own content. If a later line is just this
    section's own title, cut everything before it."""

    if section == "PORTADA E INDICE" or not content:
        return content

    lines = content.split("\n")
    title_lower = section.strip().lower()

    last_match = None
    for i, line in enumerate(lines):
        candidate = re.sub(r'^\d+\.\s*', '', line.strip()).strip().lower()
        if candidate == title_lower:
            last_match = i

    if last_match is None or last_match == 0:
        return content

    return "\n".join(lines[last_match:]).strip()


def dedupe_and_cap_findings(content, max_findings=6):
    """The local model does not reliably obey the prompt's numeric cap on
    HALLAZGO entries per section, sometimes repeating the same finding
    dozens of times. Enforce it in code: drop near-duplicate finding blocks
    and hard-cap the count."""

    if not content:
        return content

    lines = content.split("\n")
    header_positions = [
        i for i, line in enumerate(lines)
        if FINDING_HEADER_RE.match(line.strip().lstrip('#').lstrip('*').strip())
    ]

    if len(header_positions) < 2:
        return content

    preamble = "\n".join(lines[:header_positions[0]]).strip()

    blocks = []
    for idx, start in enumerate(header_positions):
        end = header_positions[idx + 1] if idx + 1 < len(header_positions) else len(lines)
        blocks.append("\n".join(lines[start:end]).strip())

    def fingerprint(block):
        # Strip the leading HALLAZGO-N / HAL-XXX-NN identifier before
        # fingerprinting, since two blocks with identical bodies but
        # different sequence numbers are still the same duplicated finding.
        first_line, _, rest = block.partition("\n")
        first_line = FINDING_HEADER_RE.sub("", first_line).lstrip(":| ").strip()
        normalized = re.sub(r'\s+', ' ', f"{first_line} {rest}").strip().lower()
        return normalized[:400]

    seen = set()
    kept = []

    for block in blocks:
        key = fingerprint(block)
        if key in seen:
            continue
        seen.add(key)
        kept.append(block)
        if len(kept) >= max_findings:
            break

    result = f"{preamble}\n\n" if preamble else ""
    result += "\n\n".join(kept)

    return result


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
    intelligence_batches = load_intelligence_batches()
    reference = load_reference_report()

    sections_content ={}

    with model_session():
        for section in SECTIONS:
            print(f"Generating {section}...")
            content = generate_section(
                section,
                system_prompt,
                intelligence_batches,
                reference
            )
            content = strip_leaked_index_preamble(section, content)
            content = dedupe_and_cap_findings(content)
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