import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import sys

# =========================
# Configuración
# =========================

JSON_PATH = "output/json/llm_output.json"
OUTPUT_DIR = "output/charts"

SUPPORTED_CHARTS = {
    "bar",
    "horizontal_bar",
    "stacked_bar",
    "pie",
    "line",
    "area",
    "boxplot"
}


# =========================
# Utils
# =========================

def safe_load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_chart_structure(chart):
    if "data" not in chart:
        return False

    if not isinstance(chart["data"], list):
        return False

    if not chart["data"]:
        return False

    return True


def get_dimension_column(df):
    cols = list(df.columns)
    if "event_count" not in cols:
        return None

    dimension_cols = [c for c in cols if c != "event_count"]

    if not dimension_cols:
        return None

    return dimension_cols[0]


# =========================
# Render Engine
# =========================

def render_chart(chart_id, chart):

    if not validate_chart_structure(chart):
        return None

    df = pd.DataFrame(chart.get("data", []))

    if df.empty:
        return None

    if "event_count" not in df.columns:
        return None

    dimension_col = get_dimension_column(df)

    if not dimension_col:
        return None

    chart_type = chart.get("chart_type", "bar").lower()

    if chart_type not in SUPPORTED_CHARTS:
        chart_type = "bar"

    # Ordenar si es categórico
    try:
        df = df.sort_values("event_count", ascending=False)
    except Exception:
        pass

    plt.figure(figsize=(10, 6))

    try:

        if chart_type == "bar":
            plt.bar(df[dimension_col], df["event_count"])

        elif chart_type == "horizontal_bar":
            plt.barh(df[dimension_col], df["event_count"])

        elif chart_type == "pie":
            # Evitar pie con demasiadas categorías
            if len(df) <= 6:
                plt.pie(
                    df["event_count"],
                    labels=df[dimension_col],
                    autopct="%1.1f%%"
                )
            else:
                # fallback seguro
                plt.bar(df[dimension_col], df["event_count"])

        elif chart_type == "line":
            plt.plot(
                df[dimension_col],
                df["event_count"],
                marker="o"
            )

        elif chart_type == "area":
            plt.fill_between(
                df[dimension_col],
                df["event_count"]
            )

        elif chart_type == "stacked_bar":
            pivot = df.pivot_table(
                index=dimension_col,
                values="event_count",
                aggfunc="sum"
            )
            pivot.plot(kind="bar", stacked=True)

        elif chart_type == "boxplot":
            plt.boxplot(df["event_count"])

        else:
            plt.bar(df[dimension_col], df["event_count"])

        plt.title(chart_id.replace("_", " ").title())
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        filename = os.path.join(OUTPUT_DIR, f"{chart_id}.png")
        plt.savefig(filename)
        plt.close()

        return filename

    except Exception:
        plt.close()
        return None


# =========================
# Main Execution
# =========================

def main():

    try:

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        llm_data = safe_load_json(JSON_PATH)

        charts = {}

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
            return

        generated_files = []

        for chart_id, chart in charts.items():

            file_path = render_chart(chart_id, chart)

            if file_path:
                generated_files.append(file_path)

        print(json.dumps({
            "generated_charts": generated_files
        }))

    except Exception as e:

        print(json.dumps({
            "generated_charts": [],
            "error": str(e)
        }))


if __name__ == "__main__":
    main()
 