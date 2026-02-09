from fastapi import FastAPI, HTTPException
import subprocess
import json

app = FastAPI()

ACTIONS = {
    "generate_chart": "actions/generate_chart.py",
    "generate_word": "actions/generate_word.py"
}

@app.post("/execute")
def execute(payload: dict):
    action = payload.get("action")

    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="Action not allowed")

    try:
        process = subprocess.run(
            ["python", ACTIONS[action], json.dumps(payload)],
            capture_output=True,
            text=True,
            check=True
        )

        return {
            "status": "ok",
            "result": process.stdout.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "stderr": e.stderr
        }
