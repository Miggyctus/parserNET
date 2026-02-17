import requests
from client_charts import main as run_charts
from client_report import generate_report

BACKEND_URL = "http://localhost:8000/execute"


def run():

    # 1️⃣ Generar JSON de charts con LLM
    run_charts()

    # 2️⃣ Generar imágenes
    requests.post(
        BACKEND_URL,
        json={"action": "generate_chart"}
    )

    # 3️⃣ Generar reporte narrativo (analiza CSV + charts)
    generate_report()

    # 4️⃣ Generar documento Word final
    requests.post(
        BACKEND_URL,
        json={"action": "generate_word"}
    )


if __name__ == "__main__":
    run()
