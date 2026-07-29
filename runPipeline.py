import time

import requests

from client_csv import generate_csv_intelligence
from consolidate_findings import consolidate
from client_report import generate_report
from client_charts import main as run_charts

BACKEND_URL = "http://localhost:8000/execute"


def run_stage(label, func):
    print(f"{label}...")

    start = time.perf_counter()
    func()
    elapsed = time.perf_counter() - start

    print(f"{label} done ({elapsed:.1f}s)")

    return elapsed


def run():

    total_start = time.perf_counter()

    # =========================
    # 2️⃣ Generate SOC report
    # =========================

    run_stage("Generating SOC report", generate_report)

    # =========================
    # 3️⃣ Generate charts JSON
    # =========================

    run_stage("Generating charts JSON", run_charts)

    # =========================
    # 4️⃣ Render chart images
    # =========================

    run_stage(
        "Rendering chart images",
        lambda: requests.post(
            BACKEND_URL,
            json={
                "action": "generate_chart",
                "json_path": "output/json/llm_output.json"
            }
        )
    )

    # =========================
    # 5️⃣ Generate Word report
    # =========================

    run_stage(
        "Generating DOCX report",
        lambda: requests.post(
            BACKEND_URL,
            json={"action": "generate_word"}
        )
    )

    total_elapsed = time.perf_counter() - total_start
    print(f"Pipeline completed in {total_elapsed:.1f}s")


if __name__ == "__main__":
    run()
