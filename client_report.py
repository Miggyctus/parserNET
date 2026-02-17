import json
import os
import httpx
import re
import pandas as pd
from openai import OpenAI

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"  # Cambialo por tu modelo narrativo
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
# Utils JSON seguros
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
# CSV ANALYSIS CON PANDAS
# =========================

def analyze_csv_with_pandas():

    dfs = []

    for file in os.listdir(CSV_FOLDER):
        if not file.endswith(".csv"):
            continue

        path = os.path.join(CSV_FOLDER, file)

        try:
            df = pd.read_csv(path)
            df["source_file"] = file
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return {}

    df_all = pd.concat(dfs, ignore_index=True)

    analysis = {}

    analysis["total_events"] = int(len(df_all))
    analysis["columns"] = list(df_all.columns)

    # =========================
    # Top categorical distributions
    # =========================

    for col in df_all.columns:
        if df_all[col].dtype == "object":
            top = df_all[col].value_counts().head(5).to_dict()
            if top:
                analysis[f"top_{col}"] = top

    # =========================
    # Numeric statistics
    # =========================

    numeric_cols = df_all.select_dtypes(include=["int64", "float64"]).columns

    for col in numeric_cols:
        analysis[f"stats_{col}"] = {
            "mean": float(df_all[col].mean()),
            "max": float(df_all[col].max()),
            "min": float(df_all[col].min())
        }

    # =========================
    # Temporal trend (si existe)
    # =========================

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
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"""
You are given:

1) Chart data generated from telemetry.
2) Structured statistical analysis derived from original CSV files.

You must correlate both sources.

=== CHART DATA ===
{json.dumps(chart_data, indent=2)}

=== CSV ANALYSIS ===
{json.dumps(csv_analysis, indent=2)}
"""
            }
        ],
        temperature=0.7,
        max_tokens=6000
    )

    return completion.choices[0].message.content


# =========================
# MAIN
# =========================

def main():

    print("🧠 Starting report generation...")

    system_prompt = load_system_prompt()
    chart_data = load_chart_json()
    csv_analysis = analyze_csv_with_pandas()

    raw_response = ask_llm(
        system_prompt,
        chart_data,
        csv_analysis
    )

    print("\n===== REPORT RAW RESPONSE =====\n")
    print(raw_response)

    try:
        parsed = safe_json_load(raw_response)

        os.makedirs("output/json", exist_ok=True)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        print("\n✅ Report JSON saved at:", OUTPUT_JSON)

    except Exception as e:
        print("\n❌ Invalid JSON returned by model")
        print("Error:", e)


if __name__ == "__main__":
    main()
