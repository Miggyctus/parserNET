# actions/chart_engine/html_builder.py

import json

def extract_labels_values(data):
    labels = []
    values = []

    for item in data:
        label_key = [k for k in item.keys() if k not in ("count", "event_count")]
        if not label_key:
            continue

        label = str(item[label_key[0]])
        value = item.get("event_count") or item.get("count") or 0

        labels.append(label[:30])  # truncate for UI
        values.append(value)

    return labels, values


def build_dashboard_chart(chart_id, chart):
    import json

    data = chart.get("data", [])

    labels = []
    values = []

    for item in data:
        key = [k for k in item.keys() if k != "event_count"][0]
        labels.append(str(item[key])[:20])
        values.append(item["event_count"])

    total = sum(values)
    unique = len(values)

    return f"""
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{
                margin: 0;
                background: #020617;
                font-family: 'Segoe UI', sans-serif;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }}

            .container {{
                width: 950px;
                border-radius: 20px;
                padding: 25px;
                background: linear-gradient(180deg, #020617, #020617);
                box-shadow: 0 0 40px rgba(0, 140, 255, 0.15);
                border: 1px solid rgba(0, 140, 255, 0.2);
            }}

            .title {{
                text-align: center;
                font-size: 20px;
                font-weight: 600;
                letter-spacing: 1px;
            }}

            .subtitle {{
                text-align: center;
                font-size: 12px;
                color: #3b82f6;
                margin-bottom: 20px;
            }}

            .metrics {{
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-bottom: 20px;
            }}

            .metric-box {{
                border: 1px solid rgba(59,130,246,0.3);
                padding: 10px 20px;
                border-radius: 10px;
                text-align: center;
                min-width: 150px;
            }}

            .metric-value {{
                font-size: 22px;
                font-weight: bold;
                color: #3b82f6;
            }}

            canvas {{
                height: 350px !important;
            }}
        </style>
    </head>

    <body>
        <div class="container">
            <div class="title">{chart_id.replace("_", " ").upper()}</div>
            <div class="subtitle">DISTRIBUCIÓN POR USUARIO</div>

            <div class="metrics">
                <div class="metric-box">
                    <div>Total de eventos</div>
                    <div class="metric-value">{total}</div>
                </div>

                <div class="metric-box">
                    <div>Usuarios únicos</div>
                    <div class="metric-value">{unique}</div>
                </div>
            </div>

            <canvas id="chart"></canvas>
        </div>

        <script>
            const ctx = document.getElementById('chart');

            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        data: {json.dumps(values)},
                        backgroundColor: [
                            '#3b82f6','#22c55e','#ef4444','#f59e0b'
                        ],
                        borderRadius: 8
                    }}]
                }},
                options: {{
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: 'white' }},
                            grid: {{ color: 'rgba(255,255,255,0.05)' }}
                        }},
                        y: {{
                            ticks: {{ color: 'white' }},
                            grid: {{ color: 'rgba(255,255,255,0.05)' }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """