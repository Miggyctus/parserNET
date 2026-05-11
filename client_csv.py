import json
import os
import httpx
import re
import requests
from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"

MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"

PROMPT_FILE = "prompt_csv.json"

CSV_FOLDER = "input_csv"

OUTPUT_PATH = "output/json/csv_intelligence.json"

CSV_BATCH_SIZE = 3

client = OpenAI(
    base_url=BASE_URL,
    api_key="lm-studio",
    http_client=httpx.Client(timeout=9999.0)
)

MODEL_INSTANCE_ID = None


# =========================
# Model Load / Unload
# =========================

def load_model():
    global MODEL_INSTANCE_ID

    payload = {
        "model": MODEL_ID,
        "context_length": 60000,
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

    print("CSV Analysis model loaded")


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

    print("CSV Analysis model unloaded")


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


def batch_csv_files(csv_data, batch_size=1):

    items = list(csv_data.items())

    batches = []

    for i in range(0, len(items), batch_size):

        batch = dict(items[i:i + batch_size])

        batches.append(batch)

    return batches


# =========================
# Prompt Builder
# =========================

def build_analysis_prompt(csv_data):

    return f"""
Analyze the following heterogeneous SOC telemetry CSV datasets.

OBJECTIVE:
Generate structured telemetry intelligence JSON.

IMPORTANT:
- Detect semantic meaning of fields dynamically
- Infer security-relevant entities
- Reduce redundant information
- Generate high-value summaries
- Detect anomalies and patterns
- Recommend useful visualizations
- Identify high-signal fields
- Detect security-relevant dimensions
- Generate useful aggregated metrics

STRICT RULES:
- Output JSON ONLY
- NO markdown
- NO explanations
- NO narrative report
- NO hallucinations
- Use ONLY provided data

CSV DATA:
{json.dumps(csv_data, separators=(",", ":"), ensure_ascii=False)}

OUTPUT:
Raw JSON only.
"""


# =========================
# JSON Cleaner
# =========================

def clean_json(raw: str):

    # =========================
    # remove think blocks
    # =========================

    raw = re.sub(
        r"<think>.*?</think>",
        "",
        raw,
        flags=re.DOTALL
    )

    # =========================
    # remove markdown fences
    # =========================

    raw = raw.replace("```json", "")
    raw = raw.replace("```", "")

    raw = raw.strip()

    # =========================
    # extract json object
    # =========================

    match = re.search(
        r"\{.*\}",
        raw,
        re.DOTALL
    )

    if not match:
        raise RuntimeError(
            "No JSON object found in model output"
        )

    candidate = match.group(0)

    # =========================
    # common repairs
    # =========================

    # remove trailing commas
    candidate = re.sub(
        r",\s*([}\]])",
        r"\1",
        candidate
    )

    # replace invalid control chars
    candidate = candidate.replace("\x00", "")

    # =========================
    # parse
    # =========================

    try:
        return json.loads(candidate)

    except json.JSONDecodeError as e:

        print("\n========= INVALID JSON =========")
        print(candidate[:4000])
        print("================================\n")

        raise RuntimeError(
            f"Failed parsing JSON: {e}"
        )

# =========================
# Merge Results
# =========================

def merge_analysis_results(results):

    merged = {
        "datasets": [],
        "detected_entities": [],
        "high_signal_fields": [],
        "top_metrics": [],
        "anomalies": [],
        "recommended_charts": []
    }

    for result in results:

        merged["datasets"].extend(
            result.get("datasets", [])
        )

        merged["detected_entities"].extend(
            result.get("detected_entities", [])
        )

        merged["high_signal_fields"].extend(
            result.get("high_signal_fields", [])
        )

        merged["top_metrics"].extend(
            result.get("top_metrics", [])
        )

        merged["anomalies"].extend(
            result.get("anomalies", [])
        )

        merged["recommended_charts"].extend(
            result.get("recommended_charts", [])
        )

    # remove duplicates

    merged["detected_entities"] = list(
        set(merged["detected_entities"])
    )

    merged["high_signal_fields"] = list(
        set(merged["high_signal_fields"])
    )

    return merged


# =========================
# Batch LLM Analysis
# =========================

def analyze_csv_batches(system_prompt, csv_batches):

    all_results = []

    total_batches = len(csv_batches)

    for idx, batch in enumerate(csv_batches):

        print(
            f"Analyzing CSV batch "
            f"{idx + 1}/{total_batches}"
        )

        prompt = build_analysis_prompt(batch)

        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            top_p=0.8,
            max_tokens=12000
        )

        response = completion.choices[0].message.content

        parsed = clean_json(response)

        all_results.append(parsed)

    return merge_analysis_results(all_results)


# =========================
# Main Pipeline
# =========================

def generate_csv_intelligence():

    system_prompt = load_system_prompt()

    csv_data = load_all_csv(CSV_FOLDER)

    csv_batches = batch_csv_files(
        csv_data,
        batch_size=CSV_BATCH_SIZE
    )

    with model_session():

        intelligence = analyze_csv_batches(
            system_prompt,
            csv_batches
        )

    os.makedirs("output/json", exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:

        json.dump(
            intelligence,
            f,
            indent=2,
            ensure_ascii=False
        )

    return intelligence


def main():

    print("Generating CSV intelligence...")

    generate_csv_intelligence()

    print("CSV intelligence generated.")


if __name__ == "__main__":
    main()