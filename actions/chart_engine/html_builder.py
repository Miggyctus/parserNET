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

        labels.append(label[:30])
        values.append(value)

    return labels, values


def build_dashboard_chart(chart_id, chart):
    chart_type = chart.get("chart_type", "bar")
    data       = chart.get("data", [])

    labels, values = extract_labels_values(data)

    total     = sum(values)
    unique    = len(values)
    max_value = max(values) if values else 0

    # =====================================================
    # CHART TYPE MAPPING
    # =====================================================

    js_type    = "bar"
    index_axis = "x"

    if chart_type == "horizontal_bar":
        js_type    = "bar"
        index_axis = "y"
    elif chart_type == "pie":
        js_type = "doughnut"
    elif chart_type == "line":
        js_type = "line"

    # =====================================================
    # COLOR PALETTE
    # =====================================================

    colors = [
        "#3b82f6",
        "#06b6d4",
        "#22c55e",
        "#f59e0b",
        "#ef4444",
        "#a855f7",
        "#e11d48",
        "#84cc16",
    ]
    colors_json = json.dumps(colors)

    # =====================================================
    # DATASETS
    # =====================================================

    if js_type == "line":
        dataset_block = f"""
        {{
            label: 'Eventos',
            data: {json.dumps(values)},
            borderColor: '#3b82f6',
            backgroundColor: (ctx) => {{
                const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 360);
                gradient.addColorStop(0, 'rgba(59,130,246,0.30)');
                gradient.addColorStop(1, 'rgba(59,130,246,0.00)');
                return gradient;
            }},
            fill: true,
            tension: 0.38,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: '#60a5fa',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            borderWidth: 3
        }}
        """

    elif js_type == "doughnut":
        # Richer doughnut: thicker ring, glow border on hover, shadow plugin
        dataset_block = f"""
        {{
            data: {json.dumps(values)},
            backgroundColor: {colors_json},
            borderColor: '#0b1628',
            borderWidth: 3,
            hoverOffset: 28,
            hoverBorderColor: '#ffffff',
            hoverBorderWidth: 2,
            spacing: 3,
            cutout: '65%'
        }}
        """

    else:
        dataset_block = f"""
        {{
            label: 'Eventos',
            data: {json.dumps(values)},
            backgroundColor: (ctx) => {{
                const chart = ctx.chart;
                const {{ ctx: c, chartArea }} = chart;
                const palette = {colors_json};
                const color = palette[ctx.dataIndex % palette.length];
                if (!chartArea) return color;
                const hex = color.replace('#','');
                const r = parseInt(hex.slice(0,2),16);
                const g = parseInt(hex.slice(2,4),16);
                const b = parseInt(hex.slice(4,6),16);
                const isHorizontal = '{index_axis}' === 'y';
                const grad = isHorizontal
                    ? c.createLinearGradient(chartArea.left, 0, chartArea.right, 0)
                    : c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                grad.addColorStop(0, `rgba(${{r}},${{g}},${{b}},1)`);
                grad.addColorStop(1, `rgba(${{r}},${{g}},${{b}},0.5)`);
                return grad;
            }},
            borderRadius: 8,
            borderSkipped: false,
            borderWidth: 0
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
                    color: '#94a3b8',
                    font: { size: 12, family: 'Inter, sans-serif' },
                    maxRotation: 30
                },
                grid: { color: 'rgba(255,255,255,0.05)' },
                border: { color: 'rgba(255,255,255,0.08)' }
            },
            y: {
                beginAtZero: true,
                ticks: {
                    color: '#94a3b8',
                    font: { size: 12, family: 'Inter, sans-serif' }
                },
                grid: { color: 'rgba(255,255,255,0.05)' },
                border: { color: 'rgba(255,255,255,0.08)' }
            }
        }
        """

    legend_display  = "true"  if js_type == "doughnut" else "false"
    legend_position = "right" if js_type == "doughnut" else "bottom"

    total_str     = str(total)
    title_display = chart_id.replace("_", " ").title()

    # =====================================================
    # HTML
    # =====================================================

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Inter', sans-serif;
            background:
                radial-gradient(ellipse 55% 45% at 10% 5%,  rgba(59,130,246,0.16) 0%, transparent 55%),
                radial-gradient(ellipse 45% 40% at 88% 90%, rgba(6,182,212,0.10)  0%, transparent 55%),
                #020617;
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            color: #f1f5f9;
        }}

        .container {{
            width: min(95vw, 980px);
            background: rgba(15, 23, 42, 0.80);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            border: 1px solid rgba(59,130,246,0.18);
            box-shadow:
                0 0 30px rgba(59,130,246,0.12),
                0 0 80px rgba(59,130,246,0.06),
                inset 0 1px 0 rgba(255,255,255,0.05);
            padding: 28px 32px 32px;
            animation: fadeUp 0.5s ease both;
        }}

        @keyframes fadeUp {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 18px;
            border-bottom: 1px solid rgba(59,130,246,0.12);
        }}

        .title {{
            font-size: 20px;
            font-weight: 700;
            color: #f1f5f9;
        }}

        .subtitle {{
            margin-top: 4px;
            font-size: 12px;
            color: #64748b;
            font-weight: 400;
        }}

        .badge {{
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(59,130,246,0.12);
            border: 1px solid rgba(59,130,246,0.28);
            color: #60a5fa;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }}

        .badge-dot {{
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #60a5fa;
            box-shadow: 0 0 6px #3b82f6;
            animation: blink 2s ease-in-out infinite;
        }}

        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50%       {{ opacity: 0.3; }}
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }}

        .metric-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 16px 18px;
            position: relative;
            overflow: hidden;
            transition: background 0.2s, border-color 0.2s;
        }}

        .metric-card:hover {{
            background: rgba(59,130,246,0.06);
            border-color: rgba(59,130,246,0.22);
        }}

        .metric-card::after {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, #3b82f6, transparent);
            opacity: 0.55;
        }}

        .metric-label {{
            font-size: 11px;
            font-weight: 500;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            margin-bottom: 8px;
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            color: #f1f5f9;
            line-height: 1;
        }}

        .chart-wrapper {{
            position: relative;
            height: 380px;
            background: rgba(255,255,255,0.015);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 14px;
            padding: 12px;
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
        <div>
            <div class="title">{title_display}</div>
            <div class="subtitle">Telemetría de seguridad &nbsp;·&nbsp; Análisis SOC</div>
        </div>
        <div class="badge">
            <span class="badge-dot"></span>
            En vivo
        </div>
    </div>

    <div class="metrics">
        <div class="metric-card">
            <div class="metric-label">Total de eventos</div>
            <div class="metric-value">{total:,}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Categorías</div>
            <div class="metric-value">{unique}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Valor máximo</div>
            <div class="metric-value">{max_value:,}</div>
        </div>
    </div>

    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>

</div>

<script>
    // ── Glow effect on doughnut segments ─────────────────────────
    const glowPlugin = {{
        id: 'segmentGlow',
        afterDatasetDraw(chart) {{
            if (chart.config.type !== 'doughnut') return;
            const {{ ctx }} = chart;
            const meta = chart.getDatasetMeta(0);
            meta.data.forEach((arc, i) => {{
                if (!arc.active) return;
                const color = chart.data.datasets[0].backgroundColor[i];
                ctx.save();
                ctx.shadowColor  = color;
                ctx.shadowBlur   = 24;
                arc.draw(ctx);
                ctx.restore();
            }});
        }}
    }};

    // ── Center label (solo para gráfico de torta) ─────────────────
    const centerTextPlugin = {{
        id: 'centerText',
        beforeDraw(chart) {{
            if (chart.config.type !== 'doughnut') return;
            const {{ ctx, width, height }} = chart;
            const cx = width  / 2;
            const cy = height / 2;
            ctx.save();
            ctx.textAlign    = 'center';
            ctx.textBaseline = 'middle';

            // small label
            ctx.font      = '500 12px Inter, sans-serif';
            ctx.fillStyle = '#64748b';
            ctx.fillText('Total eventos', cx, cy - 16);

            // big number
            ctx.font      = 'bold 34px Inter, sans-serif';
            ctx.fillStyle = '#f1f5f9';
            ctx.fillText('{total_str}', cx, cy + 16);

            ctx.restore();
        }}
    }};

    new Chart(document.getElementById('chart'), {{
        type: '{js_type}',
        data: {{
            labels: {json.dumps(labels)},
            datasets: [ {dataset_block} ]
        }},
        plugins: [glowPlugin, centerTextPlugin],
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: '{index_axis}',
            animation: {{ duration: 900, easing: 'easeOutQuart' }},
            plugins: {{
                legend: {{
                    display: {legend_display},
                    position: '{legend_position}',
                    labels: {{
                        color: '#94a3b8',
                        padding: 20,
                        boxWidth: 13,
                        boxHeight: 13,
                        borderRadius: 4,
                        useBorderRadius: true,
                        font: {{ size: 12, family: 'Inter, sans-serif' }},
                        generateLabels: (chart) => {{
                            const data = chart.data;
                            if (!data.labels.length) return [];
                            const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                            return data.labels.map((label, i) => {{
                                const value = data.datasets[0].data[i];
                                const pct   = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return {{
                                    text: `${{label}}  ${{pct}}%`,
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    strokeStyle: 'transparent',
                                    index: i
                                }};
                            }});
                        }}
                    }}
                }},
                tooltip: {{
                    backgroundColor: '#0f172a',
                    borderColor: 'rgba(59,130,246,0.35)',
                    borderWidth: 1,
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    padding: 12,
                    cornerRadius: 10,
                    titleFont: {{ size: 13, weight: 'bold', family: 'Inter, sans-serif' }},
                    bodyFont:  {{ size: 12, family: 'Inter, sans-serif' }},
                    callbacks: {{
                        label: (item) => {{
                            const total = item.dataset.data.reduce((a, b) => a + b, 0);
                            const pct   = total > 0 ? ((item.raw / total) * 100).toFixed(1) : 0;
                            return `  ${{item.formattedValue}} eventos (${{pct}}%)`;
                        }}
                    }}
                }}
            }},
            scales: {scales_block}
        }}
    }});
</script>

</body>
</html>
"""