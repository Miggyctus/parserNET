import json
import requests
from openai import OpenAI
import os
import csv
import httpx
import re

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
def safe_json_load(text: str):
    cleaned = extract_json(text)

    # Reparaciones comunes del LLM
    cleaned = cleaned.replace(")", "}")
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    return json.loads(cleaned)

def extract_json(text: str) -> str:
    """
    Extrae el primer objeto JSON válido dentro del texto,
    incluso si viene envuelto en markdown o con texto extra.
    """
    # Caso ```json ... ```
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    # Caso JSON sin markdown
    brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if brace_match:
        return brace_match.group(1)

    return text.strip()

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
        temperature=0.5,
        top_p=1.0,
        max_tokens=25000,
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
        parsed = safe_json_load(response)
        os.makedirs("output/json", exist_ok=True)

        json_path = "output/json/llm_output.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        print("JSON guardado en:", json_path)

        print("\n✅ Valid JSON received")
        try:
            backend_response = requests.post(
            BACKEND_URL,
            json={
                "action": "generate_chart",
                "json_path": json_path
            }
        )


            print("\n📡 Backend status:", backend_response.status_code)
            print("📨 Backend response:", backend_response.text)

        except Exception as e:
            print("\n❌ Error communicating with backend:")
            print(e)

    except Exception as e:
            print("\n❌ Response is not valid JSON")
            print("Error:", e)



if __name__ == "__main__":
    main()