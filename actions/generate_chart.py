# actions/generate_chart.py
import json
import os

from chart_engine.html_builder import build_dashboard_chart
from chart_engine.renderer import render_html_to_png

JSON_PATH = "output/json/llm_output.json"
OUTPUT_DIR = "output/charts"


def load_json():
    if not os.path.exists(JSON_PATH):
        return None

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_charts(llm_data):
    if "charts" in llm_data:
        return llm_data["charts"]

    if "security_telemetry_summary" in llm_data:
        return llm_data["security_telemetry_summary"].get("chart_data", {})

    return {}


def main():
    llm_data = load_json()

    if not llm_data:
        print(json.dumps({
            "generated_charts": [],
            "error": "JSON not found"
        }))
        return

    charts = extract_charts(llm_data)

    if not charts:
        print(json.dumps({
            "generated_charts": [],
            "warning": "No charts found"
        }))
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = []

    for chart_id, chart in charts.items():
        try:
            html = build_dashboard_chart(chart_id, chart)

            output_path = f"{OUTPUT_DIR}/{chart_id}.png"

            render_html_to_png(html, output_path)

            generated.append(output_path)

        except Exception as e:
            print(f"Error generating {chart_id}: {e}")

    print(json.dumps({
        "generated_charts": generated
    }))


if __name__ == "__main__":
    main()