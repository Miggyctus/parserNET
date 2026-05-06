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
            labels.append(str(item[key])[:28])

        values.append(item.get("event_count", 0))

    total = sum(values)
    unique = len(values)
    max_value = max(values) if values else 0

    # =====================================================
    # CHART TYPE
    # =====================================================

    js_type = "bar"
    index_axis = "x"

    if chart_type == "horizontal_bar":
        js_type = "bar"
        index_axis = "y"

    elif chart_type == "pie":
        js_type = "doughnut"

    elif chart_type == "line":
        js_type = "line"

    # =====================================================
    # DATASET OPTIONS
    # =====================================================

    if js_type == "line":

        dataset_block = f"""
        {{
            label: 'Eventos',
            data: {json.dumps(values)},
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59,130,246,0.18)',
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: '#60a5fa',
            borderWidth: 3
        }}
        """

    elif js_type == "doughnut":

        dataset_block = f"""
        {{
            data: {json.dumps(values)},

            backgroundColor: [
                '#3b82f6',
                '#06b6d4',
                '#22c55e',
                '#f59e0b',
                '#ef4444',
                '#a855f7',
                '#e11d48'
            ],

            borderColor: '#0f172a',
            borderWidth: 4,

            spacing: 3,

            hoverOffset: 18,

            cutout: '72%'
        }}
        """

    else:

        dataset_block = f"""
        {{
            label: 'Eventos',
            data: {json.dumps(values)},
            backgroundColor: [
                '#3b82f6',
                '#06b6d4',
                '#22c55e',
                '#f59e0b',
                '#ef4444',
                '#a855f7',
                '#e11d48',
                '#84cc16'
            ],
            borderRadius: 10,
            borderSkipped: false
        }}
        """

    # =====================================================
    # SCALES
    # =====================================================

    if js_type == "doughnut":

        scales_block = "{}"

    else:

        scales_block = """
        {
            x: {
                ticks: {
                    color: '#cbd5e1',
                    font: {
                        size: 11
                    }
                },
                grid: {
                    color: 'rgba(255,255,255,0.04)'
                }
            },
            y: {
                beginAtZero: true,
                ticks: {
                    color: '#cbd5e1',
                    font: {
                        size: 11
                    }
                },
                grid: {
                    color: 'rgba(255,255,255,0.04)'
                }
            }
        }
        """

    # =====================================================
    # HTML
    # =====================================================

    return f"""
    <html>
    <head>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                font-family: 'Inter', sans-serif;
                background:
                    radial-gradient(circle at top left, rgba(59,130,246,0.18), transparent 30%),
                    radial-gradient(circle at bottom right, rgba(6,182,212,0.12), transparent 30%),
                    #020617;

                color: white;

                width: 100vw;
                height: 100vh;

                display: flex;
                justify-content: center;
                align-items: center;

                overflow: hidden;
            }}

            .container {{

                width: 980px;

                background: rgba(15,23,42,0.78);

                backdrop-filter: blur(18px);

                border-radius: 24px;

                border: 1px solid rgba(59,130,246,0.18);

                box-shadow:
                    0 0 25px rgba(59,130,246,0.15),
                    0 0 80px rgba(59,130,246,0.08);

                padding: 28px;
            }}

            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
            }}

            .title-block {{
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}

            .title {{
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}

            .subtitle {{
                color: #94a3b8;
                font-size: 13px;
            }}

            .badge {{
                background: rgba(59,130,246,0.15);
                border: 1px solid rgba(59,130,246,0.3);
                color: #60a5fa;

                padding: 8px 14px;

                border-radius: 999px;

                font-size: 12px;
                font-weight: 600;
            }}

            .metrics {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 18px;

                margin-bottom: 28px;
            }}

            .metric-card {{

                background: rgba(255,255,255,0.03);

                border: 1px solid rgba(255,255,255,0.06);

                border-radius: 16px;

                padding: 18px;
            }}

            .metric-label {{
                color: #94a3b8;
                font-size: 13px;
                margin-bottom: 8px;
            }}

            .metric-value {{
                font-size: 30px;
                font-weight: 700;
            }}

            .chart-wrapper {{
                height: 420px;
                position: relative;
            }}

            canvas {{
                width: 100% !important;
                height: 100% !important;
            }}

        </style>
    </head>

    <body>

        <div class="container">

            <div class="header">

                <div class="title-block">

                    <div class="title">
                        {chart_id.replace("_", " ").upper()}
                    </div>

                    <div class="subtitle">
                        Security Telemetry Visualization
                    </div>

                </div>

                <div class="badge">
                    SOC ANALYTICS
                </div>

            </div>

            <div class="metrics">

                <div class="metric-card">
                    <div class="metric-label">TOTAL EVENTOS</div>
                    <div class="metric-value">{total}</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">CATEGORÍAS</div>
                    <div class="metric-value">{unique}</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">VALOR MÁXIMO</div>
                    <div class="metric-value">{max_value}</div>
                </div>

            </div>

            <div class="chart-wrapper">
                <canvas id="chart"></canvas>
            </div>

        </div>

        <script>

            const ctx = document.getElementById('chart');

            new Chart(ctx, {{

                type: '{js_type}',

                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [
                        {dataset_block}
                    ]
                }},

                options: {{

                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: '{index_axis}',

                    animation: {{
                        duration: 1200
                    }},

                    plugins: {{

                        legend: {{
                            display: {str(js_type == "doughnut").lower()},
                            position: 'bottom',

                            labels: {{
                                color: '#e2e8f0',
                                padding: 18,
                                font: {{
                                    size: 12
                                }}
                            }}
                        }},

                        tooltip: {{
                            backgroundColor: '#0f172a',
                            borderColor: 'rgba(59,130,246,0.4)',
                            borderWidth: 1,
                            titleColor: '#fff',
                            bodyColor: '#cbd5e1'
                        }}

                    }},

                    scales: {scales_block}

                }}

            }});

        </script>

    </body>
    </html>
    """