import sys
import json
import os
import matplotlib.pyplot as plt

payload = json.loads(sys.argv[1])

json_path = payload.get("json_path")

if not json_path or not os.path.exists(json_path):
    print(json.dumps({
        "generated_charts": [],
        "error": "JSON file not found"
    }))
    sys.exit(1)

# Leer archivo LLM
with open(json_path, "r", encoding="utf-8") as f:
    llm_data = json.load(f)

# Detectar estructura
if "charts" in llm_data:
    charts = llm_data["charts"]
elif "security_telemetry_summary" in llm_data:
    charts = llm_data["security_telemetry_summary"].get("chart_data", {})
else:
    charts = {}

if not charts:
    print(json.dumps({
        "generated_charts": [],
        "warning": "No charts found"
    }))
    sys.exit(0)

output_dir = "output/charts"
os.makedirs(output_dir, exist_ok=True)

generated_files = []

for chart_id, chart in charts.items():

    chart_type = chart.get("chart_type", "").lower()
    data = chart.get("data", [])

    if not data:
        continue

    filename = f"{output_dir}/{chart_id}.png"

    plt.figure(figsize=(10, 6))

    labels = []
    values = []

    for item in data:
        label_key = [k for k in item.keys() if k not in ("count", "event_count")][0]
        value_key = "event_count" if "event_count" in item else "count"

        labels.append(str(item[label_key]))
        values.append(item[value_key])

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
