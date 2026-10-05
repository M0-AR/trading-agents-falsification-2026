"""Render docs/preview.html to PNGs via Playwright (desktop + mobile)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "preview.html").as_uri()
OUT = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(HTML, wait_until="networkidle")
    pg.wait_for_timeout(800)
    pg.screenshot(path=str(OUT / "preview-desktop.png"), full_page=True)
    m = b.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
    m.goto(HTML, wait_until="networkidle")
    m.wait_for_timeout(800)
    m.screenshot(path=str(OUT / "preview-mobile.png"), full_page=True)
    b.close()
print("saved:", sorted(p.name for p in OUT.glob("preview-*.png")))
