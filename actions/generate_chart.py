import sys
import json
import os
import matplotlib.pyplot as plt

# =========================
# Load payload
# =========================
try:
    payload = json.loads(sys.argv[1])
except Exception as e:
    print(json.dumps({
        "error": f"Invalid JSON payload: {str(e)}"
    }))
    sys.exit(1)

# =========================
# Detect charts structure
# =========================
if "charts" in payload:
    charts = payload["charts"]
elif "security_telemetry_summary" in payload:
    charts = payload["security_telemetry_summary"].get("chart_data", {})
else:
    charts = {}

if not charts:
    print(json.dumps({
        "generated_charts": [],
        "warning": "No charts found in payload"
    }))
    sys.exit(0)

# =========================
# Prepare output directory
# =========================
output_dir = "output/charts"
os.makedirs(output_dir, exist_ok=True)

generated_files = []

# =========================
# Chart generation loop
# =========================
for chart_id, chart in charts.items():

    chart_type = chart.get("chart_type", "").lower()
    data = chart.get("data", [])

    if not data:
        print(f"Skipping {chart_id}: no data")
        continue

    filename = f"{output_dir}/{chart_id}.png"

    try:
        plt.figure(figsize=(10, 6))

        labels = []
        values = []

        for item in data:
            # Detect label field automatically
            label_keys = [k for k in item.keys() if k not in ("count", "event_count")]
            if not label_keys:
                continue

            label_key = label_keys[0]
            value_key = "event_count" if "event_count" in item else "count"

            labels.append(str(item[label_key]))
            values.append(item[value_key])

        if not labels or not values:
            print(f"Skipping {chart_id}: could not extract labels/values")
            continue

        # =========================
        # Chart types
        # =========================
        if chart_type == "bar":
            plt.bar(labels, values)

        elif chart_type == "horizontal_bar":
            plt.barh(labels, values)

        elif chart_type == "stacked_bar":
            # Simple stacked (single metric fallback)
            plt.bar(labels, values)

        elif chart_type == "pie":
            plt.pie(values, labels=labels, autopct="%1.1f%%")

        else:
            print(f"Unsupported chart type: {chart_type}")
            continue

        plt.title(chart_id.replace("_", " ").title())
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()

        generated_files.append(filename)

    except Exception as e:
        print(f"Error generating {chart_id}: {str(e)}")

# =========================
# Return result
# =========================
print(json.dumps({
    "generated_charts": generated_files
}))
