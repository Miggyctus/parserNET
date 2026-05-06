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
    data = chart.get("data", [])

    # Reuse shared helper instead of duplicating logic
    labels, values = extract_labels_values(data)

    total = sum(values)
    unique = len(values)
    max_value = max(values) if values else 0

    # =====================================================
    # CHART TYPE MAPPING
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
    # COLOR PALETTE
    # =====================================================

    colors = [
        "#38bdf8",  # sky blue
        "#34d399",  # emerald
        "#fb923c",  # orange
        "#a78bfa",  # violet
        "#f472b6",  # pink
        "#facc15",  # yellow
        "#f87171",  # red
        "#4ade80",  # green
    ]
    colors_json = json.dumps(colors)

    # =====================================================
    # DATASETS
    # =====================================================

    if js_type == "line":
        dataset_block = f"""
        {{
            label: 'Events',
            data: {json.dumps(values)},
            borderColor: '#38bdf8',
            backgroundColor: (ctx) => {{
                const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 380);
                gradient.addColorStop(0, 'rgba(56,189,248,0.28)');
                gradient.addColorStop(1, 'rgba(56,189,248,0.00)');
                return gradient;
            }},
            fill: true,
            tension: 0.42,
            pointRadius: 5,
            pointHoverRadius: 9,
            pointBackgroundColor: '#0ea5e9',
            pointBorderColor: '#e0f2fe',
            pointBorderWidth: 2,
            borderWidth: 3
        }}
        """

    elif js_type == "doughnut":
        dataset_block = f"""
        {{
            data: {json.dumps(values)},
            backgroundColor: {colors_json},
            borderColor: '#03091a',
            borderWidth: 5,
            hoverOffset: 22,
            spacing: 5,
            cutout: '74%'
        }}
        """

    else:
        dataset_block = f"""
        {{
            label: 'Events',
            data: {json.dumps(values)},
            backgroundColor: (ctx) => {{
                const chart = ctx.chart;
                const {{ ctx: c, chartArea }} = chart;
                if (!chartArea) return {colors_json}[ctx.dataIndex % {len(colors)}];
                const palette = {colors_json};
                const color = palette[ctx.dataIndex % palette.length];
                const hex = color.replace('#','');
                const r = parseInt(hex.slice(0,2),16);
                const g = parseInt(hex.slice(2,4),16);
                const b = parseInt(hex.slice(4,6),16);
                const grad = {'x' if index_axis == 'x' else 'y'} === 'x'
                    ? c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
                    : c.createLinearGradient(chartArea.left, 0, chartArea.right, 0);
                grad.addColorStop(0, `rgba(${{r}},${{g}},${{b}},0.95)`);
                grad.addColorStop(1, `rgba(${{r}},${{g}},${{b}},0.45)`);
                return grad;
            }},
            borderRadius: 10,
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
                    font: { size: 11, family: 'DM Mono, monospace' },
                    maxRotation: 35
                },
                grid: { color: 'rgba(148,163,184,0.07)' },
                border: { color: 'rgba(148,163,184,0.12)' }
            },
            y: {
                beginAtZero: true,
                ticks: {
                    color: '#94a3b8',
                    font: { size: 11, family: 'DM Mono, monospace' }
                },
                grid: { color: 'rgba(148,163,184,0.07)' },
                border: { color: 'rgba(148,163,184,0.12)' }
            }
        }
        """

    # =====================================================
    # LEGEND POSITION
    # =====================================================

    legend_display = "true" if js_type == "doughnut" else "false"
    legend_position = "right" if js_type == "doughnut" else "bottom"

    # Fix: total value embedded in Python, not as an unresolved JS string
    total_str = str(total)
    title_display = chart_id.replace("_", " ").upper()

    # =====================================================
    # HTML OUTPUT
    # =====================================================

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg-deep:    #03091a;
            --bg-card:    rgba(8, 20, 45, 0.82);
            --border:     rgba(56, 189, 248, 0.14);
            --accent:     #38bdf8;
            --accent-dim: rgba(56, 189, 248, 0.18);
            --text-hi:    #f0f9ff;
            --text-mid:   #94a3b8;
            --text-lo:    #475569;
            --glow:       0 0 40px rgba(56,189,248,0.12), 0 0 100px rgba(56,189,248,0.06);
            --radius-lg:  20px;
            --radius-md:  14px;
        }}

        html, body {{
            width: 100%; height: 100%;
            background: var(--bg-deep);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}

        /* Subtle animated background mesh */
        body::before {{
            content: '';
            position: fixed;
            inset: 0;
            background:
                radial-gradient(ellipse 60% 40% at 15% 10%, rgba(56,189,248,0.12) 0%, transparent 60%),
                radial-gradient(ellipse 50% 35% at 85% 85%, rgba(52,211,153,0.08) 0%, transparent 55%),
                radial-gradient(ellipse 40% 30% at 60% 50%, rgba(167,139,250,0.06) 0%, transparent 60%);
            pointer-events: none;
            z-index: 0;
        }}

        .container {{
            position: relative;
            z-index: 1;
            width: min(96vw, 1020px);
            background: var(--bg-card);
            backdrop-filter: blur(24px) saturate(140%);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: var(--glow), inset 0 1px 0 rgba(255,255,255,0.05);
            padding: 32px 36px 36px;
            animation: fadeUp 0.6s cubic-bezier(0.22,1,0.36,1) both;
        }}

        @keyframes fadeUp {{
            from {{ opacity: 0; transform: translateY(18px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ── HEADER ── */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}

        .title {{
            font-family: 'Syne', sans-serif;
            font-size: 22px;
            font-weight: 800;
            color: var(--text-hi);
            letter-spacing: 0.04em;
            line-height: 1.2;
        }}

        .subtitle {{
            margin-top: 6px;
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            color: var(--text-lo);
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }}

        .badge {{
            display: flex;
            align-items: center;
            gap: 7px;
            background: var(--accent-dim);
            border: 1px solid rgba(56,189,248,0.28);
            color: var(--accent);
            padding: 7px 14px;
            border-radius: 999px;
            font-family: 'DM Mono', monospace;
            font-size: 10px;
            font-weight: 500;
            letter-spacing: 0.1em;
            white-space: nowrap;
        }}

        .badge::before {{
            content: '';
            width: 7px; height: 7px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 8px var(--accent);
            animation: pulse 2s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50%        {{ opacity: 0.4; }}
        }}

        /* ── METRICS ── */
        .metrics {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 28px;
        }}

        .metric-card {{
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
            transition: border-color 0.25s, background 0.25s;
        }}

        .metric-card:hover {{
            border-color: var(--border);
            background: rgba(56,189,248,0.04);
        }}

        /* Accent bar on top */
        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--accent), transparent);
            opacity: 0.6;
        }}

        .metric-label {{
            font-family: 'DM Mono', monospace;
            font-size: 10px;
            color: var(--text-lo);
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}

        .metric-value {{
            font-family: 'Syne', sans-serif;
            font-size: 32px;
            font-weight: 700;
            color: var(--text-hi);
            line-height: 1;
        }}

        /* ── CHART ── */
        .chart-wrapper {{
            position: relative;
            height: 400px;
            border-radius: var(--radius-md);
            background: rgba(255,255,255,0.015);
            border: 1px solid rgba(255,255,255,0.04);
            padding: 16px;
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
            <div class="subtitle">Security Telemetry &nbsp;/&nbsp; SOC Analytics</div>
        </div>
        <div class="badge">LIVE FEED</div>
    </div>

    <div class="metrics">
        <div class="metric-card">
            <div class="metric-label">Total Events</div>
            <div class="metric-value">{total:,}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Categories</div>
            <div class="metric-value">{unique}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Peak Value</div>
            <div class="metric-value">{max_value:,}</div>
        </div>
    </div>

    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>

</div>

<script>
    // ─── CENTER TEXT PLUGIN (doughnut only) ───────────────────────
    const centerTextPlugin = {{
        id: 'centerText',
        beforeDraw(chart) {{
            if (chart.config.type !== 'doughnut') return;
            const {{ ctx, width, height }} = chart;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const cx = width / 2, cy = height / 2;

            ctx.font = '500 11px "DM Mono", monospace';
            ctx.fillStyle = '#475569';
            ctx.letterSpacing = '0.12em';
            ctx.fillText('TOTAL EVENTS', cx, cy - 18);

            ctx.font = 'bold 36px "Syne", sans-serif';
            ctx.fillStyle = '#f0f9ff';
            ctx.fillText('{total_str}', cx, cy + 16);
            ctx.restore();
        }}
    }};

    // ─── CHART INIT ───────────────────────────────────────────────
    const ctx = document.getElementById('chart');

    new Chart(ctx, {{
        type: '{js_type}',
        data: {{
            labels: {json.dumps(labels)},
            datasets: [ {dataset_block} ]
        }},
        plugins: [centerTextPlugin],
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
                        boxWidth: 12,
                        boxHeight: 12,
                        borderRadius: 4,
                        font: {{ size: 12, family: '"DM Mono", monospace' }}
                    }}
                }},
                tooltip: {{
                    backgroundColor: '#060f24',
                    borderColor: 'rgba(56,189,248,0.35)',
                    borderWidth: 1,
                    titleColor: '#f0f9ff',
                    bodyColor: '#94a3b8',
                    padding: 12,
                    cornerRadius: 10,
                    titleFont: {{ family: '"Syne", sans-serif', size: 13, weight: 'bold' }},
                    bodyFont: {{ family: '"DM Mono", monospace', size: 11 }},
                    callbacks: {{
                        label: (item) => ` ${{item.formattedValue}} events`
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