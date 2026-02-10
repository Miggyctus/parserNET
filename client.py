import json
import requests
from openai import OpenAI

# =========================
# LM Studio client
# =========================
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

MODEL_ID = "glm-4.7-flash-claude-opus-4.5-high-reasoning-distill"  # <-- usa EXACTAMENTE el ID de /v1/models
BACKEND_URL = "http://localhost:8000/execute"
PROMPT_FILE = "prompt.json"


# =========================
# Utils
# =========================
def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["system_prompt"]


def sanitize_prompt(text: str) -> str:
    # Elimina caracteres problemáticos (como en tus screenshots)
    return (
        text
        .replace("─", "-")
        .replace("–", "-")
        .replace("—", "-")
    )


# =========================
# LLM call (MATCH UI 1:1)
# =========================
def ask_llm(system_prompt: str, user_input: str) -> str:
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": user_input
            },
            {
                "role": "user",
                "content": sanitize_prompt(system_prompt)
            }
        ],
        temperature=0.4,
        top_p=1.0,
        max_tokens=12000,
        n=1
    )

    return completion.choices[0].message.content


# =========================
# Main pipeline
# =========================
def main():
    system_prompt = load_system_prompt()

    user_input = (
        "Generate a full audit report using simulated security telemetry. "
        "Produce all mandatory charts and finalize the report."
    )

    response = ask_llm(system_prompt, user_input)

    print("\n===== LLM RAW RESPONSE =====\n")
    print(response)

    # STRICT JSON ONLY
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        print("\n❌ ERROR: Model did not return valid JSON")
        return

    if "action" in data:
        print(f"\n▶ Action detected: {data['action']}")
        r = requests.post(BACKEND_URL, json=data)
        print("Backend response:")
        print(r.json())
    else:
        print("\nℹ No action detected")


if __name__ == "__main__":
    main()
