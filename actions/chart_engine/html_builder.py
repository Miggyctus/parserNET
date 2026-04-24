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


def build_chart_html(chart_id, chart):
    import json

    chart_type = chart.get("chart_type", "bar").lower()
    data = chart.get("data", [])

    labels = []
    values = []

    for item in data:
        key = [k for k in item.keys() if k != "event_count"][0]
        labels.append(str(item[key])[:20])
        values.append(item["event_count"])

    js_type = "bar"
    index_axis = "x"

    if chart_type == "horizontal_bar":
        index_axis = "y"
    elif chart_type == "pie":
        js_type = "pie"

    return f"""
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{
                margin: 0;
                background: linear-gradient(135deg, #020617, #0f172a);
                font-family: 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                color: white;
            }}

            .card {{
                width: 900px;
                padding: 25px;
                border-radius: 16px;
                background: rgba(15, 23, 42, 0.9);
                box-shadow: 0 10px 40px rgba(0,0,0,0.6);
                backdrop-filter: blur(10px);
            }}

            .title {{
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 15px;
                text-align: center;
                letter-spacing: 0.5px;
            }}

            canvas {{
                max-height: 400px;
            }}
        </style>
    </head>

    <body>
        <div class="card">
            <div class="title">{chart_id.replace("_", " ").title()}</div>
            <canvas id="chart"></canvas>
        </div>

        <script>
            const ctx = document.getElementById('chart').getContext('2d');

            new Chart(ctx, {{
                type: '{js_type}',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        label: 'Eventos',
                        data: {json.dumps(values)},
                        backgroundColor: [
                            '#3b82f6','#22c55e','#ef4444','#f59e0b',
                            '#a855f7','#06b6d4','#e11d48','#84cc16'
                        ],
                        borderRadius: 6,
                        borderSkipped: false
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: '{index_axis}',

                    plugins: {{
                        legend: {{
                            display: {str(js_type == "pie").lower()},
                            labels: {{
                                color: 'white',
                                font: {{ size: 12 }}
                            }}
                        }}
                    }},

                    scales: {{
                        x: {{
                            ticks: {{
                                color: 'white',
                                font: {{ size: 11 }}
                            }},
                            grid: {{
                                color: 'rgba(255,255,255,0.05)'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: 'white',
                                font: {{ size: 11 }}
                            }},
                            grid: {{
                                color: 'rgba(255,255,255,0.05)'
                            }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """