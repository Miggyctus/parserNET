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
MODEL_ID = "openai/gpt-oss-20b"
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


def summarize_csv_data(csv_data, max_samples=5):
    summary = {}

    for filename, rows in csv_data.items():
        columns = []
        sample_values = {}
        numeric_columns = set()

        if rows:
            columns = list(rows[0].keys())
            for row in rows[:max_samples]:
                for key, value in row.items():
                    if key not in sample_values:
                        sample_values[key] = []
                    if len(sample_values[key]) < max_samples:
                        sample_values[key].append(value)
                    if is_numeric_value(value):
                        numeric_columns.add(key)

        summary[filename] = {
            "row_count": len(rows),
            "columns": columns,
            "numeric_columns": sorted(list(numeric_columns)),
            "sample_values": sample_values
        }

    return summary


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

BATCH_SIZE = 10  # procesar N placeholders por llamada al LLM


def ask_llm(placeholders, csv_data):

    chart_prompt = load_chart_prompt()

    # IMPORTANTE: pasar el summary, NO el csv_data completo
    csv_summary = summarize_csv_data(csv_data)

    all_charts = {}

    # procesar en lotes para evitar que el modelo se rinda por contexto largo
    for batch_start in range(0, len(placeholders), BATCH_SIZE):
        batch = placeholders[batch_start:batch_start + BATCH_SIZE]
        batch_result = ask_llm_batch(batch, csv_data, chart_prompt)
        charts = batch_result.get("charts", {})
        all_charts.update(charts)

    return {"charts": all_charts}


def ask_llm_batch(placeholders_batch, csv_summary, chart_prompt):

    placeholder_list = "\n".join(
        [f"{i+1}. {p}" for i, p in enumerate(placeholders_batch)]
    )

    # listar las columnas disponibles de forma explícita para ayudar al modelo
    available_columns_summary = []
    for filename, info in csv_summary.items():
        cols = ", ".join(info.get("columns", []))
        row_count = info.get("row_count", 0)
        numeric_cols = ", ".join(info.get("numeric_columns", []))
        available_columns_summary.append(
            f"- {filename} ({row_count} filas): columnas=[{cols}] | numéricas=[{numeric_cols}]"
        )
    columns_text = "\n".join(available_columns_summary)

    prompt = f"""
TASK: Generate chart JSON for ALL {len(placeholders_batch)} placeholders listed below.

AVAILABLE COLUMNS IN CSV DATA

{columns_text}

REQUESTED CHART PLACEHOLDERS ({len(placeholders_batch)} total — ALL are REQUIRED)

{placeholder_list}

CSV SAMPLE DATA (for value reference)

{json.dumps(csv_summary, indent=2, ensure_ascii=False)}

CRITICAL MAPPING INSTRUCTIONS

- You MUST produce a chart entry for ALL {len(placeholders_batch)} placeholders above.
- "no_data_available" is FORBIDDEN unless no CSV file has any columns at all.
- You MUST use semantic inference: placeholder "top_usuarios" maps to any user/account column.
- You MUST use the sample_values in the summary to generate realistic data points.
- If the placeholder implies a count/group, generate data by counting sample values.
- Approximate mappings with real column data are ALWAYS preferred over no_data_available.
- Do NOT set no_data_available as a shortcut to avoid mapping work.

VALID FALLBACK (when exact match impossible):
  Use any available string column as dimension and any numeric column as event_count.
  Add "status": "approximate_mapping" to that chart object.

OUTPUT: raw JSON only. No explanations. No markdown.
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": chart_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,   # reducido para que el modelo sea más determinista
        top_p=0.9,
        max_tokens=10000,
        n=1
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