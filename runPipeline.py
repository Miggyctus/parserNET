import requests
import json
from client_charts import main as run_charts
from client_report import generate_report_text

BACKEND_URL = "http://localhost:8000/execute"

def run():

    # 1️⃣ Generar charts JSON
    charts_json = run_charts()

    # 2️⃣ Generar imágenes
    requests.post(
        BACKEND_URL,
        json={
            "action": "generate_chart"
        }
    )

    # 3️⃣ Generar texto del informe
    report_text = generate_report_text(charts_json)

    # 4️⃣ Generar Word
    requests.post(
        BACKEND_URL,
        json={
            "action": "generate_word",
            "report_title": "SOC Analysis Report",
            "summary": report_text,
            "sections": report_text
        }
    )

if __name__ == "__main__":
    run()
