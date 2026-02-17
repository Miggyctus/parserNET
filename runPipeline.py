import requests
from client_charts import main as run_charts
from client_report import generate_report

BACKEND_URL = "http://localhost:8000/execute"

def run():

    # 1️⃣ Generar charts JSON
    run_charts()

    # 2️⃣ Renderizar imágenes
    requests.post(
        BACKEND_URL,
        json={"action": "generate_chart"}
    )

    # 3️⃣ Generar reporte narrativo
    generate_report()

    # 4️⃣ Generar Word final
    requests.post(
        BACKEND_URL,
        json={"action": "generate_word"}
    )

if __name__ == "__main__":
    run()
