import os
import json
import re
import requests
import httpx
import csv
from collections import Counter
from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "mistralai/ministral-3-14b-reasoning"
BACKEND_URL = "http://localhost:8000/execute"

REPORT_PATH = "output/reports/llm_report.txt"
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
        "context_length": 47000,
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


def load_chart_prompt():
    if not os.path.exists(PROMPT_CHART_FILE):
        raise RuntimeError("Chart prompt file not found")

    with open(PROMPT_CHART_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def load_all_csv(folder="input_csv", max_rows_per_file=None):
    data = {}
    for file in os.listdir(folder):
        if not file.endswith(".csv"):
            continue
        path = os.path.join(folder, file)
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):
                if max_rows_per_file is not None and i >= max_rows_per_file:
                    break
                rows.append(row)
        data[file] = rows
    return data


# =========================
# Vocabulario semántico (mismo usado en la etapa de análisis de CSV)
# =========================

SEMANTIC_FIELDS = [
    "source_ip", "destination_ip", "username", "hostname", "domain", "url",
    "process_name", "command_line", "hash", "sha256", "md5", "timestamp",
    "event_id", "severity", "protocol", "action", "bytes", "country", "port",
    "status", "vendor", "product", "authentication_type", "logon_type",
    "parent_process", "registry_key", "service_name", "scheduled_task",
    "dns_query", "file_path",
]

FIELD_MAPPING_SYSTEM_PROMPT = """You are a deterministic column-mapping engine for heterogeneous SOC telemetry CSVs.

Your ONLY job is to map original CSV column names to a fixed semantic vocabulary. You are NOT asked to count, aggregate, or analyze any data — sample rows are provided only so you can judge the meaning of each column.

RULES
- Output ONLY valid raw JSON, parseable by json.loads() with zero preprocessing.
- Do NOT output markdown, prose, explanations, or <think> blocks.
- Map a column only if you are reasonably confident. Omit columns that don't match anything in the vocabulary — do NOT force a mapping.
- Never invent a column name that isn't in the input.
- Use each semantic field at most once per file.

OUTPUT SCHEMA
{"files": {"<filename>": {"<original_column>": "<semantic_field>"}}}
"""


# =========================
# Paso 1: mapeo semántico de columnas (LLM, sin filas masivas)
# =========================

def build_field_mapping_payload(csv_data, sample_rows=2):
    payload = {}
    for filename, rows in csv_data.items():
        columns = list(rows[0].keys()) if rows else []
        payload[filename] = {
            "columns": columns,
            "sample_rows": rows[:sample_rows],
        }
    return payload


def ask_llm_field_mapping(csv_data):
    if not csv_data:
        return {}

    payload = build_field_mapping_payload(csv_data)

    prompt = f"""
Map ORIGINAL column names to semantic fields for each file below.

ALLOWED SEMANTIC FIELDS
{", ".join(SEMANTIC_FIELDS)}

FILES (columns + up to 2 sample rows each — for context only, do NOT count or aggregate anything)

{json.dumps(payload, separators=(",", ":"), ensure_ascii=False)}

OUTPUT: raw JSON only, matching the schema from the system prompt.
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": FIELD_MAPPING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        top_p=0.7,
        max_tokens=1500,
    )

    raw = completion.choices[0].message.content
    return clean_field_mapping_json(raw, list(csv_data.keys()))


def clean_field_mapping_json(raw, filenames):
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
    cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
    cleaned = cleaned.replace('```', '').strip()

    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not json_match:
        return {f: {} for f in filenames}

    try:
        parsed = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {f: {} for f in filenames}

    files = parsed.get("files")
    if not isinstance(files, dict):
        return {f: {} for f in filenames}

    result = {}
    for f in filenames:
        mapping = files.get(f)
        result[f] = mapping if isinstance(mapping, dict) else {}
    return result


def validate_field_mapping(mapping, rows):
    """Descarta cualquier columna/campo inventado que no exista realmente en el CSV o el vocabulario."""
    if not rows or not isinstance(mapping, dict):
        return {}
    real_columns = set(rows[0].keys())
    return {
        column: field
        for column, field in mapping.items()
        if column in real_columns and field in SEMANTIC_FIELDS
    }


# =========================
# Paso 2: catálogo semántico (100% Python, sin LLM)
# =========================

def build_semantic_catalog(csv_data, field_mappings, sample_limit=5, scan_limit=500):
    catalog = {}
    for filename, rows in csv_data.items():
        mapping = field_mappings.get(filename, {})
        fields = {}
        for column, semantic_field in mapping.items():
            seen = []
            seen_set = set()
            for row in rows[:scan_limit]:
                value = (row.get(column) or "").strip()
                if value and value not in seen_set:
                    seen_set.add(value)
                    seen.append(value)
                if len(seen) >= sample_limit:
                    break
            fields[semantic_field] = {"column": column, "sample_values": seen}
        catalog[filename] = fields
    return catalog


# =========================
# Paso 3: decisión de intención por placeholder (LLM, sin datos crudos)
# =========================

BATCH_SIZE = 8  # placeholders por llamada al LLM


def ask_llm_intents(placeholders, catalog):
    chart_prompt = load_chart_prompt()
    all_charts = {}

    for batch_start in range(0, len(placeholders), BATCH_SIZE):
        batch = placeholders[batch_start:batch_start + BATCH_SIZE]

        batch_result = ask_llm_intent_batch(batch, catalog, chart_prompt)
        all_charts.update(batch_result.get("charts", {}))

    return {"charts": all_charts}


def ask_llm_intent_batch(placeholders_batch, catalog, chart_prompt):

    placeholder_list = "\n".join(
        [f"{i+1}. {p}" for i, p in enumerate(placeholders_batch)]
    )

    prompt = f"""
Decide chart intent for ALL {len(placeholders_batch)} placeholders listed below.

REQUESTED CHART PLACEHOLDERS

{placeholder_list}

SEMANTIC CATALOG (fields available per file, with a few REAL sample values — for context only, do NOT count anything)

{json.dumps(catalog, separators=(",", ":"), ensure_ascii=False)}

OUTPUT: raw JSON only, following the EXACT OUTPUT SCHEMA from the system prompt.
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": chart_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        top_p=0.7,
        max_tokens=1500,
    )

    raw = completion.choices[0].message.content

    return clean_intent_json(raw, placeholders_batch)


def empty_intent(placeholder, status):
    return {
        "chart_type": None,
        "title": placeholder,
        "x_label": "",
        "y_label": "Cantidad de Eventos",
        "source_file": None,
        "group_by": None,
        "filter": [],
        "top_n": 10,
        "status": status,
    }


def clean_intent_json(raw: str, placeholders: list):

    # eliminar bloques <think> y markdown
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
    cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
    cleaned = cleaned.replace('```', '').strip()

    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)

    if not json_match:
        return {"charts": {p: empty_intent(p, "parse_error") for p in placeholders}}

    candidate = json_match.group(0)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {"charts": {p: empty_intent(p, "json_decode_error") for p in placeholders}}

    charts = parsed.get("charts")

    # si charts vino como lista
    if isinstance(charts, list):
        charts_dict = {}
        for i, chart in enumerate(charts):
            if isinstance(chart, dict):
                identifier = chart.get("chart_identifier")
                charts_dict[identifier or f"chart_{i}"] = chart
        charts = charts_dict

    if not isinstance(charts, dict):
        charts = {}

    # asegurar placeholders y campos mínimos
    for p in placeholders:
        intent = charts.get(p)

        if not isinstance(intent, dict):
            status = "invalid_chart_structure" if p in charts else "missing_in_model_output"
            charts[p] = empty_intent(p, status)
            continue

        intent.setdefault("chart_type", None)
        intent.setdefault("title", p)
        intent.setdefault("x_label", "")
        intent.setdefault("y_label", "Cantidad de Eventos")
        intent.setdefault("source_file", None)
        intent.setdefault("group_by", None)
        intent.setdefault("filter", [])
        intent.setdefault("top_n", 10)

        if not isinstance(intent.get("filter"), list):
            intent["filter"] = []

    return {"charts": charts}


# =========================
# Paso 4: motor de agregación determinístico (100% Python, sin LLM)
# =========================

ALLOWED_CHART_TYPES = {"bar", "horizontal_bar", "pie", "line", "stacked_bar", "area"}
ALLOWED_FILTER_OPS = {"eq", "neq", "contains", "in"}
MAX_ITEMS = 10
MIN_ITEMS = 2


def resolve_column(file_mapping, semantic_field):
    if not semantic_field:
        return None
    for column, field in file_mapping.items():
        if field == semantic_field:
            return column
    return None


def matches_filter(row, column, op, value):
    cell = (row.get(column) or "").strip().lower()

    if op == "eq":
        return cell == str(value).strip().lower()
    if op == "neq":
        return cell != str(value).strip().lower()
    if op == "contains":
        return str(value).strip().lower() in cell
    if op == "in":
        options = value if isinstance(value, list) else [value]
        return cell in {str(v).strip().lower() for v in options}
    return False


def apply_filters(rows, filters, file_mapping):
    if not filters:
        return rows

    valid_filters = []
    for f in filters:
        if not isinstance(f, dict):
            continue
        op = f.get("op")
        field = f.get("field")
        value = f.get("value")
        if op not in ALLOWED_FILTER_OPS or value is None:
            continue
        column = resolve_column(file_mapping, field)
        if not column:
            continue
        valid_filters.append((column, op, value))

    if not valid_filters:
        return rows

    return [
        row for row in rows
        if all(matches_filter(row, column, op, value) for column, op, value in valid_filters)
    ]


def decide_chart_type_fallback(placeholder, n_categories):
    name = placeholder.lower()

    if any(k in name for k in ("trend", "timeline", "time", "hora", "temporal", "diario", "historico")):
        return "line"
    if any(k in name for k in ("distribucion", "severidad", "tipo", "categoria", "top")):
        return "pie" if n_categories <= 5 else "horizontal_bar"
    if any(k in name for k in ("volumen", "conteo", "eventos", "count")):
        return "bar"
    if any(k in name for k in ("stacked", "apilado", "breakdown")):
        return "stacked_bar"
    return "bar"


def empty_chart(intent, placeholder, status):
    chart_type = intent.get("chart_type")
    return {
        "chart_type": chart_type if chart_type in ALLOWED_CHART_TYPES else "bar",
        "title": intent.get("title") or placeholder,
        "x_label": intent.get("x_label") or "",
        "y_label": intent.get("y_label") or "Cantidad de Eventos",
        "data": [],
        "status": status,
    }


def aggregate_placeholder(placeholder, intent, csv_data, field_mappings):
    """Agrega los datos reales del CSV en Python — el LLM ya no cuenta ni calcula nada."""

    source_file = intent.get("source_file")
    group_by = intent.get("group_by")

    if intent.get("status") == "no_data_available" or not group_by:
        return empty_chart(intent, placeholder, "no_data_available")

    candidate_files = [source_file] if source_file in csv_data else list(csv_data.keys())

    rows = []
    resolved_column = None
    resolved_file_mapping = {}

    for filename in candidate_files:
        file_mapping = field_mappings.get(filename, {})
        column = resolve_column(file_mapping, group_by)
        if not column:
            continue
        resolved_column = column
        resolved_file_mapping = file_mapping
        rows.extend(csv_data.get(filename, []))

    if not resolved_column:
        return empty_chart(intent, placeholder, "no_data_available")

    filtered_rows = apply_filters(rows, intent.get("filter"), resolved_file_mapping)

    values = [
        (row.get(resolved_column) or "").strip()
        for row in filtered_rows
    ]
    values = [v for v in values if v]

    if not values:
        return empty_chart(intent, placeholder, "no_data_available")

    try:
        top_n = min(int(intent.get("top_n") or MAX_ITEMS), MAX_ITEMS)
    except (TypeError, ValueError):
        top_n = MAX_ITEMS

    counter = Counter(values)

    if group_by == "timestamp":
        items = sorted(counter.items(), key=lambda kv: kv[0])[:top_n]
    else:
        items = counter.most_common(top_n)

    if len(items) < MIN_ITEMS:
        return empty_chart(intent, placeholder, "no_data_available")

    data = [
        {"value": value, group_by: value, "event_count": count}
        for value, count in items
    ]

    chart_type = intent.get("chart_type")
    if chart_type not in ALLOWED_CHART_TYPES:
        chart_type = decide_chart_type_fallback(placeholder, len(items))

    return {
        "chart_type": chart_type,
        "title": intent.get("title") or placeholder,
        "x_label": intent.get("x_label") or "",
        "y_label": intent.get("y_label") or "Cantidad de Eventos",
        "data": data,
    }


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

        raw_mapping = ask_llm_field_mapping(csv_data)
        field_mappings = {
            filename: validate_field_mapping(raw_mapping.get(filename, {}), rows)
            for filename, rows in csv_data.items()
        }

        catalog = build_semantic_catalog(csv_data, field_mappings)

        intents = ask_llm_intents(placeholders, catalog)

        charts = {
            p: aggregate_placeholder(p, intent, csv_data, field_mappings)
            for p, intent in intents["charts"].items()
        }
        parsed = {"charts": charts}

        os.makedirs("output/json", exist_ok=True)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)

        # reporte de resultados
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
