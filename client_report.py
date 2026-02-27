import os
import json
import pandas as pd
import requests
import httpx
from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"

PROMPT_FILE = "prompt_report.json"
CSV_FOLDER = "input_csv"

REPORT_PATH = "output/reports/llm_report.txt"
SUMMARY_PATH = "output/json/csv_summary.json"

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

    data = response.json()
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
# CSV SUMMARY BUILDER
# =========================

def build_csv_summary():

    dfs = []

    for file in os.listdir(CSV_FOLDER):
        if file.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(CSV_FOLDER, file))
                df["source_file"] = file
                dfs.append(df)
            except Exception:
                continue

    if not dfs:
        return {}

    df_all = pd.concat(dfs, ignore_index=True)

    summary = {
        "total_events": int(len(df_all)),
        "columns": list(df_all.columns)
    }

    # Top categorical distributions
    for col in df_all.columns:
        if df_all[col].dtype == "object":
            top = df_all[col].value_counts().head(10).to_dict()
            if top:
                summary[f"{col}_distribution"] = top

    # Numeric statistics
    numeric_cols = df_all.select_dtypes(include=["int64", "float64"]).columns

    for col in numeric_cols:
        summary[f"{col}_stats"] = {
            "mean": float(df_all[col].mean()),
            "max": float(df_all[col].max()),
            "min": float(df_all[col].min())
        }

    # Temporal trend detection
    for col in df_all.columns:
        if "time" in col.lower() or "date" in col.lower():
            try:
                df_all[col] = pd.to_datetime(df_all[col], errors="coerce")
                trend = (
                    df_all.groupby(df_all[col].dt.date)
                    .size()
                    .to_dict()
                )
                summary["temporal_trend"] = trend
                break
            except Exception:
                continue

    return summary


# =========================
# Prompt Loader
# =========================

def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


# =========================
# LLM CALL
# =========================

def ask_llm(system_prompt, summary):

    user_content = f"""
You are given structured statistical data extracted from CSV logs.

Generate a complete professional security audit report in Spanish.

IMPORTANT:
- Whenever a visualization is required, you MUST insert a placeholder in this exact format:
{{{{CHART: chart_identifier}}}}

Rules for chart_identifier:
- lowercase only
- underscores instead of spaces
- descriptive (e.g. severity_distribution, vendor_distribution, temporal_trend)
- placeholder must be on its own line

Structured Data:
{json.dumps(summary, separators=(',', ':'))}
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.4,
        max_tokens=8000
    )

    return completion.choices[0].message.content


# =========================
# MAIN PUBLIC FUNCTION
# =========================

def generate_report():

    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/json", exist_ok=True)

    summary = build_csv_summary()

    # Guardar summary para client_charts
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    system_prompt = load_system_prompt()

    with model_session():
        report_text = ask_llm(system_prompt, summary)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("Report generated successfully")
    return report_text


def main():
    generate_report()


if __name__ == "__main__":
    main()