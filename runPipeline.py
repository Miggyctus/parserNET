import requests

from client_csv import generate_csv_intelligence
from consolidate_findings import consolidate
from client_report import generate_report
from client_charts import main as run_charts

BACKEND_URL = "http://localhost:8000/execute"


def run():

    # =========================
    # 1️⃣ Analyze CSV telemetry
    # =========================

    print("Generating CSV intelligence...")

    generate_csv_intelligence()

    print("CSV intelligence generated.")

    # =========================
    # 1.5️⃣ Consolidate findings
    # =========================

    print("Consolidating and deduplicating findings...")

    consolidate()

    print("Findings consolidated.")

    # =========================
    # 2️⃣ Generate SOC report
    # =========================

    print("Generating SOC report...")

    generate_report()

    print("SOC report generated.")

    # =========================
    # 3️⃣ Generate charts JSON
    # =========================

    print("Generating charts JSON...")

    run_charts()

    print("Charts JSON generated.")

    # =========================
    # 4️⃣ Render chart images
    # =========================

    print("Rendering chart images...")

    requests.post(
        BACKEND_URL,
        json={
            "action": "generate_chart",
            "json_path": "output/json/llm_output.json"
        }
    )

    print("Charts rendered.")

    # =========================
    # 5️⃣ Generate Word report
    # =========================

    print("Generating DOCX report...")

    requests.post(
        BACKEND_URL,
        json={
            "action": "generate_word"
        }
    )

    print("DOCX report generated.")


if __name__ == "__main__":
    run()