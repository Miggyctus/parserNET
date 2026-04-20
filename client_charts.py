import os
import json
import re
import requests
import httpx
import csv
from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "qwen/qwq-32b"
BACKEND_URL = "http://localhost:8000/execute"

REPORT_PATH = "output/reports/llm_report.txt"
SUMMARY_PATH = "output/json/csv_summary.json"
OUTPUT_JSON = "output/json/llm_output.json"
PROMPT_CHART_FILE = "prompt_chart.json"

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=3600.0)
)

# =========================
# Model Load / Unload
# =========================

MODEL_INSTANCE_ID = None


def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 50000,
        "eval_batch_size": 256,
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
        "echo_load_config": True
    }

    response = requests.post(
        "http://localhost:1234/api/v1/models/load",
        json=payload,
        timeout=120
    )

    data = response.json()
    MODEL_INSTANCE_ID = data.get("instance_id")

    print("Charts model loaded")


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
    print("Charts model unloaded")


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

def extract_chart_placeholders(report_text):
    pattern = r"\{\{CHART:\s*([a-z0-9_]+)\s*\}\}"
    matches = re.findall(pattern, report_text)

    # eliminar duplicados
    return list(dict.fromkeys(matches))


def load_report_text():
    if not os.path.exists(REPORT_PATH):
        raise RuntimeError("Report file not found")

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def load_summary():
    if not os.path.exists(SUMMARY_PATH):
        raise RuntimeError("CSV summary not found")

    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_chart_prompt():
    if not os.path.exists(PROMPT_CHART_FILE):
        raise RuntimeError("Chart prompt file not found")

    with open(PROMPT_CHART_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def is_numeric_value(value):
    if value is None:
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def load_all_csv(folder = "input_csv", max_rows_per_file = 5000):
    data = {}
    for file in os.listdir(folder):
        if not file.endswith(".csv"):
            continue    
        path = os.path.join(folder, file)
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):
                if i >= max_rows_per_file:
                    break
                rows.append(row)
        data[file] = rows
    return data


# =========================
# LLM CALL — procesado en lotes para evitar saturar el contexto
# =========================

BATCH_SIZE = 5  # procesar N placeholders por llamada al LLM


def ask_llm(placeholders, csv_data):

    chart_prompt = load_chart_prompt()
    all_charts = {}

    for batch_start in range(0, len(placeholders), BATCH_SIZE):
        batch = placeholders[batch_start:batch_start + BATCH_SIZE]

        batch_result = ask_llm_batch(batch, csv_data, chart_prompt)
        charts = batch_result.get("charts", {})
        all_charts.update(charts)

    return {"charts": all_charts}


def ask_llm_batch(placeholders_batch, csv_data, chart_prompt):

    placeholder_list = "\n".join(
        [f"{i+1}. {p}" for i, p in enumerate(placeholders_batch)]
    )

    prompt = f"""
TASK: Generate chart JSON for ALL {len(placeholders_batch)} placeholders listed below.

══════════════════════════════════
REQUESTED CHART PLACEHOLDERS
══════════════════════════════════
{placeholder_list}

══════════════════════════════════
FULL CSV DATA (USE THIS DATA)
══════════════════════════════════
{json.dumps(csv_data, separators=(",", ":"), ensure_ascii=False)}

══════════════════════════════════
CRITICAL INSTRUCTIONS
══════════════════════════════════
- You MUST use the CSV data above.
- You MUST extract, group, count, and transform data as needed.
- You MUST map placeholders using semantic similarity.
- You MUST parse structured fields if needed (e.g. "Object Name").
- You MUST generate REAL data.
- Do NOT try to SAVE time, go DEEP into the data and generate as much REAL data as possible.

- "no_data_available" is FORBIDDEN unless absolutely impossible.

OUTPUT: raw JSON only.
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": chart_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        top_p=0.9,
        max_tokens=2000,
        #reasoning={"effort" : "low"}
    )

    raw = completion.choices[0].message.content

    return clean_json_output(raw, placeholders_batch)

# =========================
# Output Cleaning
# =========================

def clean_json_output(raw: str, placeholders: list):

    # =========================
    # limpiar ruido del modelo
    # =========================

    # eliminar bloques <think>
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)

    # eliminar markdown
    cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
    cleaned = cleaned.replace('```', '')

    # =========================
    # extraer JSON
    # =========================

    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)

    if not json_match:

        return {
            "charts": {
                p: {
                    "chart_type": "bar",
                    "title": p,
                    "data": [],
                    "status": "parse_error"
                }
                for p in placeholders
            }
        }

    candidate = json_match.group(0)

    try:

        parsed = json.loads(candidate)

    except json.JSONDecodeError:

        return {
            "charts": {
                p: {
                    "chart_type": "bar",
                    "title": p,
                    "data": [],
                    "status": "json_decode_error"
                }
                for p in placeholders
            }
        }

    # =========================
    # normalizar charts
    # =========================

    charts = parsed.get("charts")

    # si charts vino como lista
    if isinstance(charts, list):

        charts_dict = {}

        for i, chart in enumerate(charts):

            if isinstance(chart, dict):

                # intentar usar chart_identifier si existe
                identifier = chart.get("chart_identifier")

                if identifier:
                    charts_dict[identifier] = chart
                else:
                    charts_dict[f"chart_{i}"] = chart

        charts = charts_dict

    # si charts no existe o es inválido
    if not isinstance(charts, dict):
        charts = {}

    parsed["charts"] = charts

    # =========================
    # asegurar placeholders
    # =========================

    for p in placeholders:

        if p not in charts:

            charts[p] = {
                "chart_type": "bar",
                "title": p,
                "data": [],
                "status": "missing_in_model_output"
            }

        else:

            chart = charts[p]

            if not isinstance(chart, dict):
                charts[p] = {
                    "chart_type": "bar",
                    "title": p,
                    "data": [],
                    "status": "invalid_chart_structure"
                }
                continue

            # asegurar campos mínimos
            chart.setdefault("chart_type", "bar")
            chart.setdefault("title", p)

            data = chart.get("data")

            if not isinstance(data, list):
                chart["data"] = []

    return parsed

# =========================
# MAIN
# =========================

def main():

    report_text = load_report_text()
    csv_data = load_all_csv()

    placeholders = extract_chart_placeholders(report_text)

    if not placeholders:
        print("No chart placeholders found.")
        return

    print(f"Detected {len(placeholders)} placeholders:", placeholders)

    with model_session():

        parsed = ask_llm(placeholders, csv_data)

        os.makedirs("output/json", exist_ok=True)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        # reporte de resultados
        charts = parsed.get("charts", {})
        with_data = sum(1 for c in charts.values() if isinstance(c.get("data"), list) and len(c.get("data", [])) > 0)
        no_data = len(charts) - with_data
        print(f"Charts JSON saved — {with_data} with data, {no_data} empty")

        # llamar backend para generar imágenes
        requests.post(
            BACKEND_URL,
            json={
                "action": "generate_chart",
                "json_path": OUTPUT_JSON
            }
        )


if __name__ == "__main__":
    main()