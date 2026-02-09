import sys
import json
import os
import matplotlib.pyplot as plt

payload = json.loads(sys.argv[1])
chart = payload["chart"]

chart_id = chart["chart_id"]
chart_type = chart["chart_type"]
title = chart["title"]

x_values = chart["x_axis"]["values"]
series = chart.get("series", [])

output_dir = "output/charts"
os.makedirs(output_dir, exist_ok=True)

filename = f"{output_dir}/{chart_id}.png"

plt.figure()

if chart_type == "bar":
    for s in series:
        plt.bar(x_values, s["values"], label=s["name"])
    plt.legend()

elif chart_type == "line":
    for s in series:
        plt.plot(x_values, s["values"], label=s["name"])
    plt.legend()

elif chart_type == "pie":
    values = series[0]["values"] if series else []
    plt.pie(values, labels=x_values, autopct="%1.1f%%")

elif chart_type == "stacked_bar":
    bottom = [0] * len(x_values)
    for s in series:
        plt.bar(x_values, s["values"], bottom=bottom, label=s["name"])
        bottom = [b + v for b, v in zip(bottom, s["values"])]
    plt.legend()

else:
    raise ValueError("Unsupported chart type")

plt.title(title)
plt.tight_layout()
plt.savefig(filename)
plt.close()

print(filename)
