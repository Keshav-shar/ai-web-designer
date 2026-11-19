"""shoot.py - screenshots for visual checks (desktop 1440 + phone 375), full page.

    python tools/shoot.py <url-or-file> <out-prefix> [--wait 1500]
"""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\Keshav Sharma\Downloads\serpman")
import serpman_paths  # noqa: F401,E402  (points Playwright at D:\caches\ms-playwright)
from playwright.sync_api import sync_playwright  # noqa: E402

target, prefix = sys.argv[1], sys.argv[2]
wait = int(sys.argv[sys.argv.index("--wait") + 1]) if "--wait" in sys.argv else 1500
url = target if "://" in target else Path(target).resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h in (("desktop", 1440, 900), ("phone", 375, 812)):
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto(url, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(wait)
        over = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        out = f"{prefix}-{name}.png"
        pg.screenshot(path=out, full_page=True)
        print(out, "horizontal-overflow" if over else "no-overflow")
        pg.close()
    b.close()
