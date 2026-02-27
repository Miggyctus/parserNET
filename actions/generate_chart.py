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

    if df.empty or "event_count" not in df.columns:
        return None

    dimension_col = get_dimension_column(df)
    if not dimension_col:
        return None

    chart_type = chart.get("chart_type", "bar").lower()
    if chart_type not in SUPPORTED_CHARTS:
        chart_type = "bar"

    # Orden descendente
    try:
        df = df.sort_values("event_count", ascending=False)
    except Exception:
        pass

    # =========================
    # 🎨 ENTERPRISE DARK THEME
    # =========================
    plt.style.use("dark_background")

    fig, ax = plt.subplots(figsize=(14, 8))

    fig.patch.set_facecolor("#0B1220")     # Fondo general
    ax.set_facecolor("#111827")            # Panel

    # Quitar bordes feos
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Grid sutil
    ax.grid(True, color="#1F2937", linestyle="--", linewidth=0.5, alpha=0.6)

    # Paleta
    palette = [
        "#3B82F6",  # azul
        "#22D3EE",  # cyan
        "#A78BFA",  # violeta
        "#F97316",  # naranja
        "#22C55E",  # verde
        "#EF4444"   # rojo
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
        # 🏷 Title & Labels
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
 