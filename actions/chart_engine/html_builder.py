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

    chart_type = chart.get("chart_type", "bar")
    data = chart.get("data", [])

    labels = []
    values = []

    for item in data:
        key = [k for k in item.keys() if k != "event_count"][0]

        if key == "timestamp":
            labels.append(item[key])
        else:
            labels.append(str(item[key])[:20])

        values.append(item.get("event_count", 0))

    total = sum(values)
    unique = len(values)

    # ===== DETECT TYPE =====
    js_type = "bar"
    index_axis = "x"
    extra_options = ""

    if chart_type == "horizontal_bar":
        js_type = "bar"
        index_axis = "y"

    elif chart_type == "pie":
        js_type = "pie"

    elif chart_type == "line":
        js_type = "line"
        extra_options = """
        tension: 0.3,
        fill: true,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.2)',
        pointRadius: 3
        """

    # ===== COLORS =====
    colors = [
        '#3b82f6','#22c55e','#ef4444','#f59e0b',
        '#a855f7','#06b6d4','#e11d48','#84cc16'
    ]

    # ===== SCALES FIX =====
    if js_type == "pie":
        scales_block = "{}"
    else:
        scales_block = """
        {
            x: {
                ticks: { color: 'white' },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: {
                ticks: { color: 'white' },
                grid: { color: 'rgba(255,255,255,0.05)' }
            }
        }
        """

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
                background: #020617;
                box-shadow: 0 0 40px rgba(0, 140, 255, 0.15);
                border: 1px solid rgba(0, 140, 255, 0.2);
            }}

            .title {{
                text-align: center;
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 10px;
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

            <div class="metrics">
                <div class="metric-box">
                    <div>Total</div>
                    <div class="metric-value">{total}</div>
                </div>

                <div class="metric-box">
                    <div>Categorías</div>
                    <div class="metric-value">{unique}</div>
                </div>
            </div>

            <canvas id="chart"></canvas>
        </div>

        <script>
            const ctx = document.getElementById('chart');

            new Chart(ctx, {{
                type: '{js_type}',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        data: {json.dumps(values)},
                        backgroundColor: {json.dumps(colors)},
                        borderRadius: 8,
                        {extra_options}
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: '{index_axis}',

                    plugins: {{
                        legend: {{
                            display: {str(chart_type == "pie").lower()},
                            labels: {{ color: 'white' }}
                        }}
                    }},

                    scales: {scales_block}
                }}
            }});
        </script>
    </body>
    </html>
    """