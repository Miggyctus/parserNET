import json
import os
import matplotlib.pyplot as plt

# =========================
# Configuración fija
# =========================

JSON_PATH = "output/json/llm_output.json"
OUTPUT_DIR = "output/charts"

# =========================
# Verificar archivo
# =========================

if not os.path.exists(JSON_PATH):
    print(json.dumps({
        "generated_charts": [],
        "error": f"JSON file not found at {JSON_PATH}"
    }))
    exit(1)

# =========================
# Cargar JSON del LLM
# =========================

with open(JSON_PATH, "r", encoding="utf-8") as f:
    llm_data = json.load(f)

# =========================
# Detectar estructura
# =========================

if "charts" in llm_data:
    charts = llm_data["charts"]
elif "security_telemetry_summary" in llm_data:
    charts = llm_data["security_telemetry_summary"].get("chart_data", {})
else:
    charts = {}

if not charts:
    print(json.dumps({
        "generated_charts": [],
        "warning": "No charts found in JSON"
    }))
    exit(0)

# =========================
# Generación de gráficos
# =========================

os.makedirs(OUTPUT_DIR, exist_ok=True)

generated_files = []

for chart_id, chart in charts.items():

    chart_type = chart.get("chart_type", "").lower()
    data = chart.get("data", [])

    if not data:
        continue

    filename = f"{OUTPUT_DIR}/{chart_id}.png"

    plt.figure(figsize=(10, 6))

    labels = []
    values = []

    for item in data:
        # Detectar campo label automáticamente
        label_keys = [k for k in item.keys() if k not in ("count", "event_count")]
        if not label_keys:
            continue

        label_key = label_keys[0]
        value_key = "event_count" if "event_count" in item else "count"

        labels.append(str(item[label_key]))
        values.append(item[value_key])

    if not labels or not values:
        continue

    if chart_type == "bar":
        plt.bar(labels, values)

    elif chart_type == "horizontal_bar":
        plt.barh(labels, values)

    elif chart_type == "pie":
        plt.pie(values, labels=labels, autopct="%1.1f%%")

    else:
        continue

    plt.title(chart_id.replace("_", " ").title())
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    generated_files.append(filename)

print(json.dumps({
    "generated_charts": generated_files
}))
