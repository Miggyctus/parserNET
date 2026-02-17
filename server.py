from fastapi import FastAPI, HTTPException
import subprocess
import json
import sys
import os

app = FastAPI()

ACTIONS = {
    "generate_chart": "actions/generate_chart.py",
    "generate_word": "actions/generate_word.py"
}

# 🔥 Usar el mismo intérprete que corre FastAPI
PYTHON_EXEC = sys.executable


@app.post("/execute")
def execute(payload: dict):
    action = payload.get("action")

    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="Action not allowed")

    try:
        # 1️⃣ Ejecutar acción principal usando el python correcto
        process = subprocess.run(
            [PYTHON_EXEC, ACTIONS[action]],
            capture_output=True,
            text=True,
            check=True
        )

        result_main = process.stdout.strip()

        # 2️⃣ Si fue generate_chart → ejecutar también generate_word
        result_word = None

        if action == "generate_chart":
            process_word = subprocess.run(
                [PYTHON_EXEC, ACTIONS["generate_word"], json.dumps(payload)],
                capture_output=True,
                text=True,
                check=True
            )

            result_word = process_word.stdout.strip()

        return {
            "status": "ok",
            "chart_result": result_main,
            "word_result": result_word
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "stderr": e.stderr
        }
