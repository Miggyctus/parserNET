import json
import os
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List

JSON_PATH = "output/json/llm_output.json"
OUTPUT_DIR = "output/charts"


class ChartEngine:

    def __init__(self, json_path: str):
        self.json_path = json_path
        self.data = self._load_json()

    def _load_json(self) -> Dict:
        if not os.path.exists(self.json_path):
            raise FileNotFoundError("LLM JSON not found")
        with open(self.json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate(self) -> List[str]:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        charts = self.data.get("charts", {})
        generated = []

        for chart_id, chart in charts.items():
            df = pd.DataFrame(chart.get("data", []))

            if df.empty:
                continue

            filename = self._render_chart(chart_id, chart, df)
            if filename:
                generated.append(filename)

        return generated

    def _render_chart(self, chart_id: str, chart: Dict, df: pd.DataFrame):

        chart_type = chart.get("chart_type", "bar")

        if "event_count" not in df.columns:
            return None

        dimension_col = [c for c in df.columns if c != "event_count"][0]

        df = df.sort_values("event_count", ascending=False)

        plt.figure(figsize=(10, 6))

        if chart_type == "bar":
            plt.bar(df[dimension_col], df["event_count"])

        elif chart_type == "horizontal_bar":
            plt.barh(df[dimension_col], df["event_count"])

        elif chart_type == "pie":
            plt.pie(df["event_count"], labels=df[dimension_col], autopct="%1.1f%%")

        elif chart_type == "stacked_bar":
            # soporte básico stacked
            df_pivot = df.pivot_table(
                index=dimension_col,
                values="event_count",
                aggfunc="sum"
            )
            df_pivot.plot(kind="bar", stacked=True)

        else:
            return None

        plt.title(chart_id.replace("_", " ").title())
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        filename = os.path.join(OUTPUT_DIR, f"{chart_id}.png")
        plt.savefig(filename)
        plt.close()

        return filename


if __name__ == "__main__":

    try:
        engine = ChartEngine(JSON_PATH)
        files = engine.generate()

        print(json.dumps({"generated_charts": files}))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
