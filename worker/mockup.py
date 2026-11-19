"""mockup.py - an image mockup of an assembled site: 1440-wide render, top 2000 px, scaled to 720 px webp."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from labio import SERPMAN_SRC

if str(SERPMAN_SRC) not in sys.path:
    sys.path.insert(0, str(SERPMAN_SRC))
import serpman_paths  # noqa: E402,F401  (points Playwright at D:\caches\ms-playwright)

W, H, CROP, OUT_W = 1440, 900, 2000, 720


def screenshot(site_dir: Path) -> bytes:
    """site_dir holds index.html + styles.css + assets/ (assemble.write_local). Needs network for Google Fonts."""
    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1, reduced_motion="reduce")
            pg.goto((site_dir / "index.html").resolve().as_uri(), wait_until="networkidle", timeout=60_000)
            pg.wait_for_timeout(600)
            height = min(CROP, int(pg.evaluate("document.documentElement.scrollHeight")))
            png = pg.screenshot(full_page=True, clip={"x": 0, "y": 0, "width": W, "height": height})
        finally:
            b.close()
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im = im.resize((OUT_W, round(im.height * OUT_W / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=5)
    return buf.getvalue()
