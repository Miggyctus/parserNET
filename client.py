import requests
import json

LM_URL = "http://localhost:1234/v1/chat/completions"
BACKEND_URL = "http://localhost:8000/execute"
PROMPT_FILE = "prompt.json"


def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["system_prompt"]


def ask_llm(system_prompt, user_input):
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0
    }

    r = requests.post(LM_URL, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main():
    system_prompt = load_system_prompt()

    user_input = (
        "Generate a full audit report using simulated security telemetry. "
        "Produce all mandatory charts and finalize the report."
    )

    response = ask_llm(system_prompt, user_input)

    print("\nLLM RAW RESPONSE:\n")
    print(response)

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        print("\n❌ The model did not return valid JSON")
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
