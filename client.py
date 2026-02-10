import json
import requests
from openai import OpenAI
import os
import csv
import httpx

# =========================
# LM Studio client
# =========================
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
    http_client=httpx.Client(timeout=99999.0)
)

MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"  # <-- usa EXACTAMENTE el ID de /v1/models
BACKEND_URL = "http://localhost:8000/execute"
PROMPT_FILE = "prompt.json"
CSV_FOLDER = "input_csv"
MAX_ROWS_PER_CSV = 5000              # protección contra CSV gigantes


# =========================
# Utils
# =========================
def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def sanitize_text(text: str) -> str:
    return (
        text.replace("─", "-")
            .replace("–", "-")
            .replace("—", "-")
    )


def load_all_csv(folder_path: str) -> dict:
    telemetry = {}

    for file in os.listdir(folder_path):
        if not file.lower().endswith(".csv"):
            continue

        file_path = os.path.join(folder_path, file)
        rows = []

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= MAX_ROWS_PER_CSV:
                    break
                rows.append(row)

        telemetry[file] = rows

    return telemetry


# =========================
# LLM Call
# =========================
def ask_llm(system_prompt: str, telemetry: dict) -> str:
    telemetry_json = json.dumps(telemetry, indent=2)

    user_input = f"""
The following section contains structured security telemetry collected from multiple vendors.
Each CSV file has been converted to JSON and grouped by filename.

Analyze this data strictly according to your instructions.

=== BEGIN TELEMETRY ===
{telemetry_json}
=== END TELEMETRY ===

Generate ONLY the required JSON chart definitions.
Do NOT generate the final report yet.
"""

    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": sanitize_text(system_prompt)
            },
            {
                "role": "user",
                "content": user_input
            }
        ],
        temperature=0.4,
        top_p=1.0,
        max_tokens=12000,
        n=1
    )

    return completion.choices[0].message.content


# =========================
# Main
# =========================
def main():
    system_prompt = load_system_prompt()
    telemetry = load_all_csv(CSV_FOLDER)

    if not telemetry:
        print("❌ No CSV files found in input folder")
        return

    response = ask_llm(system_prompt, telemetry)

    print("\n===== LLM RAW RESPONSE =====\n")
    print(response)

    try:
        json.loads(response)
        print("\n✅ Valid JSON received")
    except json.JSONDecodeError:
        print("\n❌ Response is not valid JSON")


if __name__ == "__main__":
    main()