import json
import os
import httpx
import re
import pandas as pd
import requests
from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"
PROMPT_FILE = "prompt_report.json"
CHART_JSON_PATH = "output/json/llm_output.json"
OUTPUT_JSON = "output/json/llm_report.json"
CSV_FOLDER = "input_csv"

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=900.0)
)

# =========================
# Model Load / Unload
# =========================

MODEL_INSTANCE_ID = None


def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 20000,
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

def extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    brace = re.search(r"(\{.*\})", text, re.DOTALL)
    if brace:
        return brace.group(1)

    return text.strip()


def safe_json_load(text: str):
    cleaned = extract_json(text)
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)
    return json.loads(cleaned)


def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def load_chart_json():
    if not os.path.exists(CHART_JSON_PATH):
        return {}
    with open(CHART_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# CSV ANALYSIS
# =========================

def analyze_csv_with_pandas():

    dfs = []

    for file in os.listdir(CSV_FOLDER):
        if not file.endswith(".csv"):
            continue

        try:
            df = pd.read_csv(os.path.join(CSV_FOLDER, file))
            df["source_file"] = file
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return {}

    df_all = pd.concat(dfs, ignore_index=True)

    analysis = {
        "total_events": int(len(df_all)),
        "columns": list(df_all.columns)
    }

    # Top categorical
    for col in df_all.columns:
        if df_all[col].dtype == "object":
            top = df_all[col].value_counts().head(5).to_dict()
            if top:
                analysis[f"top_{col}"] = top

    # Numeric stats
    numeric_cols = df_all.select_dtypes(include=["int64", "float64"]).columns

    for col in numeric_cols:
        analysis[f"stats_{col}"] = {
            "mean": float(df_all[col].mean()),
            "max": float(df_all[col].max()),
            "min": float(df_all[col].min())
        }

    # Temporal trend
    for col in df_all.columns:
        if "time" in col.lower() or "date" in col.lower():
            try:
                df_all[col] = pd.to_datetime(df_all[col], errors="coerce")
                trend = (
                    df_all.groupby(df_all[col].dt.date)
                    .size()
                    .to_dict()
                )
                analysis["daily_trend"] = trend
                break
            except Exception:
                continue

    return analysis


# =========================
# LLM CALL
# =========================

def ask_llm(system_prompt: str, chart_data: dict, csv_analysis: dict):

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
You are given:

1) Chart data generated from telemetry.
2) Statistical analysis derived directly from CSV files.

Correlate both sources.

=== CHART DATA ===
{json.dumps(chart_data, indent=2)}

=== CSV ANALYSIS ===
{json.dumps(csv_analysis, indent=2)}
"""
            }
        ],
        temperature=0.7,
        top_p=1.0,
        max_tokens=20000
    )

    return completion.choices[0].message.content


# =========================
# PUBLIC FUNCTION FOR PIPELINE
# =========================

def generate_report():

    system_prompt = load_system_prompt()
    chart_data = load_chart_json()
    csv_analysis = analyze_csv_with_pandas()

    with model_session():
        raw = ask_llm(system_prompt, chart_data, csv_analysis)
        parsed = safe_json_load(raw)

        os.makedirs("output/json", exist_ok=True)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        return parsed


def main():
    print("Starting report generation...")
    generate_report()
    print("Report completed.")


if __name__ == "__main__":
    main()
