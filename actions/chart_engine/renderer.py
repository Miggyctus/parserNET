# actions/chart_engine/renderer.py

from playwright.sync_api import sync_playwright

def render_html_to_png(html, output_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1050, "height": 800})

        page.set_content(html)

        # Esperar a que Chart.js renderice
        page.wait_for_timeout(1000)

        page.screenshot(path=output_path)
        browser.close()