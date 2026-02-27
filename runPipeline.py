import requests
from client_report import generate_report
from client_charts import main as run_charts

BACKEND_URL = "http://localhost:8000/execute"

def run():

    # 1️⃣ Generar reporte (incluye csv_summary + placeholders)
    generate_report()

    # 2️⃣ Generar charts JSON según placeholders
    run_charts()

    # 3️⃣ Renderizar imágenes
    requests.post(
        BACKEND_URL,
        json={
            "action": "generate_chart",
            "json_path": "output/json/llm_charts.json"
        }
    )

    # 4️⃣ Generar Word final
    requests.post(
        BACKEND_URL,
        json={"action": "generate_word"}
    )

if __name__ == "__main__":
    run()