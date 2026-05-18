import json
import os
import httpx
import re
import requests
import csv

from openai import OpenAI
from contextlib import contextmanager

# =========================
# Configuración
# =========================

BASE_URL = "http://localhost:1234/v1"

MODEL_ID = "mistralai/ministral-3-14b-reasoning"

PROMPT_FILE = "prompt_csv.json"

CSV_FOLDER = "input_csv"

OUTPUT_DIR = "output/intelligence"

CSV_BATCH_SIZE = 1

MAX_ROWS_PER_CHUNK = 400

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
        "context_length": 72000,
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
        raise RuntimeError(
            f"Failed to load model: {response.text}"
        )

    data = response.json()

    if data.get("status") != "loaded":
        raise RuntimeError(
            f"Model failed to load: {data}"
        )

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

    with open(
        PROMPT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)["system_prompt"]


def load_all_csv(
    folder_path: str,
    max_rows_per_chunk: int = MAX_ROWS_PER_CHUNK
) -> dict:

    csv_data = {}

    for file in os.listdir(folder_path):

        if not file.lower().endswith(".csv"):
            continue

        file_path = os.path.join(
            folder_path,
            file
        )

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                reader = csv.DictReader(f)

                rows = list(reader)

            # =========================
            # Small CSV
            # =========================

            if len(rows) <= max_rows_per_chunk:

                csv_data[file] = rows

                continue

            # =========================
            # Chunk Large CSV
            # =========================

            chunk_index = 1

            for i in range(
                0,
                len(rows),
                max_rows_per_chunk
            ):

                chunk = rows[
                    i:i + max_rows_per_chunk
                ]

                chunk_name = (
                    f"{file}"
                    f"__part_{chunk_index}"
                    f"__rows_{i}_{i + len(chunk)}"
                )

                csv_data[chunk_name] = chunk

                chunk_index += 1

        except Exception as e:

            print(
                f"Failed loading {file}: {e}"
            )

    return csv_data


def batch_csv_files(
    csv_data,
    batch_size=2
):

    items = list(csv_data.items())

    batches = []

    for i in range(
        0,
        len(items),
        batch_size
    ):

        batch = dict(
            items[i:i + batch_size]
        )

        batches.append(batch)

    return batches


# =========================
# Prompt Builder
# =========================

def build_analysis_prompt(csv_data):

    return f"""
Analyze the following heterogeneous SOC telemetry datasets.

OBJECTIVE:
Generate structured telemetry intelligence JSON.

IMPORTANT:
- Detect semantic meaning dynamically
- Detect anomalies
- Reduce repetitive telemetry
- Generate high-value summaries
- Detect high-signal entities
- Recommend useful visualizations
- Preserve security context
- Use ONLY provided telemetry

STRICT RULES:
- Output JSON ONLY
- NO markdown
- NO explanations
- NO prose
- NO hallucinations

TELEMETRY DATA:
{json.dumps(csv_data, separators=(",", ":"), ensure_ascii=False)}

OUTPUT:
Raw JSON only.
"""


# =========================
# JSON Cleaner
# =========================

def clean_json(raw: str):

    raw = re.sub(
        r"<think>.*?</think>",
        "",
        raw,
        flags=re.DOTALL
    )

    raw = raw.replace(
        "```json",
        ""
    )

    raw = raw.replace(
        "```",
        ""
    )

    raw = raw.strip()

    match = re.search(
        r"\{.*\}",
        raw,
        re.DOTALL
    )

    if not match:

        raise RuntimeError(
            "No JSON object found"
        )

    candidate = match.group(0)

    # remove trailing commas

    candidate = re.sub(
        r",\s*([}\]])",
        r"\1",
        candidate
    )

    candidate = candidate.replace(
        "\x00",
        ""
    )

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
# Save Batch Intelligence
# =========================

def save_batch_intelligence(
    batch_index,
    intelligence
):

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"batch_{batch_index + 1}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            intelligence,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Saved intelligence: {output_path}"
    )


# =========================
# Batch LLM Analysis
# =========================

def analyze_csv_batches(
    system_prompt,
    csv_batches
):

    total_batches = len(csv_batches)

    for idx, batch in enumerate(csv_batches):

        print(
            f"Analyzing CSV batch "
            f"{idx + 1}/{total_batches}"
        )

        prompt = build_analysis_prompt(
            batch
        )

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
            temperature=0,
            top_p=0.8,
            max_tokens=12000
        )

        response = (
            completion
            .choices[0]
            .message
            .content
        )

        parsed = clean_json(response)

        save_batch_intelligence(
            idx,
            parsed
        )


# =========================
# Main Pipeline
# =========================

def generate_csv_intelligence():

    system_prompt = load_system_prompt()

    csv_data = load_all_csv(
        CSV_FOLDER
    )

    csv_batches = batch_csv_files(
        csv_data,
        batch_size=CSV_BATCH_SIZE
    )

    with model_session():

        analyze_csv_batches(
            system_prompt,
            csv_batches
        )

    return True


def main():

    print(
        "Generating CSV intelligence..."
    )

    generate_csv_intelligence()

    print(
        "CSV intelligence generated."
    )


if __name__ == "__main__":
    main()