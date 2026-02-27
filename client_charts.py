import os
import json
import re
import requests
import httpx
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
OUTPUT_JSON = "output/json/llm_charts.json"

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=600.0)
)

# =========================
# Model Load / Unload
# =========================

MODEL_INSTANCE_ID = None


def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 15000,
        "eval_batch_size": 256,
        "flash_attention": False,
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
    return re.findall(pattern, report_text)


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


# =========================
# LLM CALL
# =========================

def ask_llm(placeholders, summary):

    prompt = f"""
You are a visualization engine.

You are given:

1) A list of chart identifiers requested in a report:
{placeholders}

2) Structured statistical data extracted from CSV:
{json.dumps(summary, separators=(',', ':'))}

Instructions:
- Generate ONLY charts requested in the placeholder list.
- The chart identifier must match EXACTLY the placeholder name.
- Do NOT invent additional charts.
- Use only data present in summary.
- Maximum 10 data points per chart.
- Output VALID JSON only.

Format:
{{
  "charts": {{
      "placeholder_name": {{
          "chart_type": "bar | line | pie | stacked_bar | horizontal_bar",
          "data": [...]
      }}
  }}
}}
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=6000
    )

    return completion.choices[0].message.content


def safe_json_load(text):
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if not match:
        raise ValueError("No valid JSON found")

    return json.loads(match.group(1))


# =========================
# MAIN
# =========================

def main():

    report_text = load_report_text()
    summary = load_summary()

    placeholders = extract_chart_placeholders(report_text)

    if not placeholders:
        print("No chart placeholders found.")
        return

    print("Detected placeholders:", placeholders)

    with model_session():

        raw = ask_llm(placeholders, summary)

        parsed = safe_json_load(raw)

        os.makedirs("output/json", exist_ok=True)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        print("Charts JSON saved")

        # Llamar backend para generar imágenes
        requests.post(
            BACKEND_URL,
            json={
                "action": "generate_chart",
                "json_path": OUTPUT_JSON
            }
        )


if __name__ == "__main__":
    main()