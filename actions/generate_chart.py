import sys
import json
import os
import matplotlib.pyplot as plt

payload = json.loads(sys.argv[1])
charts = payload.get("charts", {})

output_dir = "output/charts"
os.makedirs(output_dir, exist_ok=True)

generated_files = []

for chart_id, chart in charts.items():
    chart_type = chart.get("chart_type")
    title = chart_id.replace("_", " ").title()
    data = chart.get("data", [])

    filename = f"{output_dir}/{chart_id}.png"

    plt.figure()

    if chart_type == "bar":
        labels = [list(item.values())[0] for item in data]
        values = [item["count"] for item in data]
        plt.bar(labels, values)

    elif chart_type == "stacked_bar":
        labels = [item.get("vendor_device", "Unknown") for item in data]
        values = [item["count"] for item in data]
        plt.bar(labels, values)

    elif chart_type == "pie":
        labels = [list(item.values())[0] for item in data]
        values = [item["count"] for item in data]
        plt.pie(values, labels=labels, autopct="%1.1f%%")

    else:
        continue

    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    generated_files.append(filename)

print(json.dumps({
    "generated_charts": generated_files
}))
