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

PYTHON_EXEC = sys.executable


@app.post("/execute")
def execute(payload: dict):

    action = payload.get("action")

    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="Action not allowed")

    try:

        # Ejecutar acción principal
        process = subprocess.run(
            [PYTHON_EXEC, ACTIONS[action], json.dumps(payload)],
            capture_output=True,
            text=True,
            check=True
        )

        result = process.stdout.strip()

        return {
            "status": "ok",
            "result": result
        }

    except subprocess.CalledProcessError as e:

        return {
            "status": "error",
            "stderr": e.stderr
        }
