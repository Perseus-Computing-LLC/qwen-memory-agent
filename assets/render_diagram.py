"""Render architecture diagram HTML to PNG using Playwright."""
from playwright.sync_api import sync_playwright
from pathlib import Path

html_path = Path(__file__).resolve().parent.parent / "assets" / "architecture-diagram.html"
png_path = Path(__file__).resolve().parent.parent / "assets" / "architecture-diagram.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 900, "height": 620}, device_scale_factor=2)
    page.goto(f"file://{html_path.absolute()}")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(png_path), full_page=False)
    browser.close()

print(f"Diagram: {png_path} ({png_path.stat().st_size // 1024} KB)")
