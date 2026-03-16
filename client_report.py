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
        "context_length": 30000,
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
    path = "ejemplo.pdf"

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

def ask_llm(system_prompt: str, chart_data: dict, csv_data: dict):

    referenceReport= load_reference_report()
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
You are provided with:

[1] PRIMARY — RAW CSV (analysis, evidence, findings)
Every finding MUST cite: exact field | real value | timestamp
If CSV and charts contradict: CSV prevails — flag the discrepancy

[2] REFERENCE — EXAMPLE REPORT (tone and style only)
PROHIBITED to copy: incidents, IPs, users, hostnames, dates, conclusions

Chart placeholders {{{{CHART: chart_identifier}}}} ARE PART OF THE REPORT.

They must be inserted DURING writing, not appended at the end.

WHEN to insert a placeholder:
Immediately AFTER the paragraph describing a distribution or trend
Whenever you mention: "distribution of...", "top N of...", "trend of...",
"volume of...", "comparison between...", "frequency of..."

Once per unique statistical analysis — never repeat the same one

HOW to name the chart_identifier:

Lowercase, letters/numbers/underscores only
Must reflect EXACTLY the metric analyzed in that paragraph

- Correct examples:

top10_events_by_type
alert_trend_by_hour

      severity_distribution_endpoints

      egress_volume_by_external_destination

      top_users_with_auth_failures

      suspicious_linux_command_distribution

  - Incorrect examples: chart1, graph_1, data_chart

WHERE placeholders go by section:

  Section 6  (Statistical Analysis)  → minimum 3 placeholders

  Section 7  (Findings)              → 1 per finding that warrants it

  Section 8  (Egress)                → minimum 2 placeholders

  Section 9  (Linux Activity)        → minimum 1 placeholder (if data exists)

  Section 10 (Risk Analysis)         → 1 risk matrix placeholder

MINIMUM TOTAL PLACEHOLDERS IN REPORT: 8

MAXIMUM TOTAL: 20

ABSOLUTE RULE: no chart_identifier may ever be repeated in the entire report

Example of correct insertion:

---

During the analyzed period, 4,823 authentication events were recorded,

of which 67% correspond to repeated failures from the 10.10.2.x segment,

with a sharp peak between 02:00 and 04:00 UTC on the 14th.

{{{{CHART: auth_failure_distribution_by_hour}}}}

This activity outside normal business hours suggests automated behavior

consistent with password spraying techniques (MITRE T1110.003)...


You must analyze the raw CSV data directly.

Use the reference report ONLY as a stylistic and structural guide.
Do NOT reuse its incidents, conclusions, or content.

{referenceReport}

=== RAW CSV FILES ===
{json.dumps(csv_data, indent=2)}

Generate the full SOC report using the telemetry data.

Follow the writing style, tone, and structure of the reference report,
but base ALL analysis strictly on the telemetry provided.
"""
            }
        ],
        temperature=0.7,
        top_p=0.95,
        
        max_tokens=30000,
        n=1
    )
    message = completion.choices[0].message

    return message.content


# =========================
# Public Function
# =========================

def generate_report():

    system_prompt = load_system_prompt()
    chart_data = load_chart_json()
    csv_data = load_all_csv(CSV_FOLDER)

    with model_session():
        raw = ask_llm(system_prompt, chart_data, csv_data)

        if not raw or not raw.strip():
            raise RuntimeError("LLM returned empty response")

        os.makedirs("output/reports", exist_ok=True)

        with open(REPORT_TEXT_PATH, "w", encoding="utf-8") as f:
            f.write(raw)

        return raw


def main():
    print("Generating audit report...")
    generate_report()
    print("Report generated successfully.")


if __name__ == "__main__":
    main()