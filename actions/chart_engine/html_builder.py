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
    chart_type = chart.get("chart_type", "bar").lower()
    data = chart.get("data", [])

    labels, values = extract_labels_values(data)

    # Map types
    js_type = "bar"
    index_axis = "x"

    if chart_type == "horizontal_bar":
        js_type = "bar"
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
                background: #0f172a;
                font-family: Arial;
                color: white;
            }}

            .container {{
                width: 900px;
                height: 500px;
                padding: 20px;
            }}

            h2 {{
                text-align: center;
                font-size: 18px;
                margin-bottom: 10px;
            }}
        </style>
    </head>

    <body>
        <div class="container">
            <h2>{chart_id.replace("_", " ").title()}</h2>
            <canvas id="chart"></canvas>
        </div>

        <script>
            const ctx = document.getElementById('chart');

            new Chart(ctx, {{
                type: '{js_type}',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        label: '{chart_id}',
                        data: {json.dumps(values)},
                        backgroundColor: [
                            '#3b82f6','#22c55e','#ef4444','#f59e0b',
                            '#a855f7','#14b8a6','#e11d48','#84cc16'
                        ]
                    }}]
                }},
                options: {{
                    responsive: false,
                    indexAxis: '{index_axis}',
                    plugins: {{
                        legend: {{
                            labels: {{ color: 'white' }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: 'white' }}
                        }},
                        y: {{
                            ticks: {{ color: 'white' }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """