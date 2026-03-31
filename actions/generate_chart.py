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


def normalize_chart_data(chart):
    """
    Normalizes chart data regardless of whether the model used
    'data' or 'data_points' as the key, and regardless of whether
    the value field is called 'event_count' or 'value'.
    Returns the chart dict with a guaranteed 'data' key.
    """

    # prefer 'data' if it's already populated
    data = chart.get("data")

    # fall back to data_points if data is missing or empty
    if not data:
        data = chart.get("data_points")

    if not isinstance(data, list) or not data:
        chart["data"] = []
        return chart

    # normalize value field: accept 'event_count' or 'value'
    normalized = []
    for row in data:
        if not isinstance(row, dict):
            continue

        label = row.get("label") or row.get("name") or row.get("category") or ""
        value = row.get("event_count") or row.get("value") or row.get("count") or 0

        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0

        normalized.append({"label": str(label), "event_count": value})

    chart["data"] = normalized
    return chart


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

    # normalize before anything else
    chart = normalize_chart_data(chart)

    if not validate_chart_structure(chart):
        print(f"[SKIP] {chart_id}: empty or invalid data after normalization")
        return None

    df = pd.DataFrame(chart.get("data", []))

    if df.empty or "event_count" not in df.columns:
        print(f"[SKIP] {chart_id}: DataFrame is empty or missing event_count")
        return None

    dimension_col = get_dimension_column(df)
    if not dimension_col:
        print(f"[SKIP] {chart_id}: no dimension column found")
        return None

    chart_type = chart.get("chart_type", "bar").lower()
    if chart_type not in SUPPORTED_CHARTS:
        chart_type = "bar"

    # sort descending
    try:
        df = df.sort_values("event_count", ascending=False)
    except Exception:
        pass

    # =========================
    # ENTERPRISE DARK THEME
    # =========================
    plt.style.use("dark_background")

    fig, ax = plt.subplots(figsize=(14, 8))

    fig.patch.set_facecolor("#0B1220")
    ax.set_facecolor("#111827")

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.grid(True, color="#1F2937", linestyle="--", linewidth=0.5, alpha=0.6)

    palette = [
        "#3B82F6",  # blue
        "#22D3EE",  # cyan
        "#A78BFA",  # violet
        "#F97316",  # orange
        "#22C55E",  # green
        "#EF4444"   # red
    ]

    colors = palette * (len(df) // len(palette) + 1)

    try:

        if chart_type == "bar":
            ax.bar(df[dimension_col], df["event_count"], color=colors[:len(df)])

        elif chart_type == "horizontal_bar":
            ax.barh(df[dimension_col], df["event_count"], color=colors[:len(df)])

        elif chart_type == "pie":
            if len(df) <= 6:
                ax.pie(
                    df["event_count"],
                    labels=df[dimension_col],
                    autopct="%1.1f%%",
                    colors=colors[:len(df)],
                    textprops={"color": "white"}
                )
            else:
                ax.bar(df[dimension_col], df["event_count"], color=colors[:len(df)])

        elif chart_type == "line":
            ax.plot(
                df[dimension_col],
                df["event_count"],
                marker="o",
                linewidth=2.5,
                color="#22D3EE"
            )
            ax.fill_between(
                df[dimension_col],
                df["event_count"],
                alpha=0.2,
                color="#22D3EE"
            )

        elif chart_type == "area":
            ax.fill_between(
                df[dimension_col],
                df["event_count"],
                color="#3B82F6",
                alpha=0.4
            )

        elif chart_type == "stacked_bar":
            df.plot(
                kind="bar",
                stacked=True,
                ax=ax,
                color=colors[:len(df.columns)]
            )

        elif chart_type == "boxplot":
            ax.boxplot(
                df["event_count"],
                patch_artist=True,
                boxprops=dict(facecolor="#3B82F6")
            )

        else:
            ax.bar(df[dimension_col], df["event_count"], color=colors[:len(df)])

        # =========================
        # Title & Labels
        # =========================
        ax.set_title(
            chart_id.replace("_", " ").title(),
            fontsize=16,
            color="white",
            pad=20,
            weight="bold"
        )

        ax.tick_params(axis="x", colors="white", rotation=45)
        ax.tick_params(axis="y", colors="white")

        plt.tight_layout()

        filename = os.path.join(OUTPUT_DIR, f"{chart_id}.png")
        plt.savefig(filename, dpi=300, facecolor=fig.get_facecolor())
        plt.close()

        print(f"[OK] {chart_id} -> {filename}")
        return filename

    except Exception as e:
        plt.close()
        print(f"[ERROR] {chart_id}: {e}")
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
        skipped = []

        for chart_id, chart in charts.items():

            file_path = render_chart(chart_id, chart)

            if file_path:
                generated_files.append(file_path)
            else:
                skipped.append(chart_id)

        print(json.dumps({
            "generated_charts": generated_files,
            "skipped_charts": skipped
        }))

    except Exception as e:

        print(json.dumps({
            "generated_charts": [],
            "error": str(e)
        }))


if __name__ == "__main__":
    main()