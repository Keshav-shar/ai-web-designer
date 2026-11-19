"""assets.py - turn the brief's picked corpus images into web-ready files (webp, <= 1600 px wide).

Only `background` and `central` assets appear on the page. `layout`, `hero` and `palette` are references: they
are screenshots / boards of other people's sites, so they guide structure (via the layout note) and are shown in
the private recipe view, but never embedded in a generated site.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

MAX_W = 1600
PAGE_ROLES = ("background", "central")


def web_image(src: Path, max_w: int = MAX_W, quality: int = 82) -> bytes:
    with Image.open(src) as im:
        im.seek(0)
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        if im.height > 3 * im.width:                      # full-page captures: keep the top (landing) part
            im = im.crop((0, 0, im.width, 3 * im.width))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=quality, method=5)
        return buf.getvalue()


def prepare(brief: dict, files: dict[str, Path]) -> dict[str, bytes]:
    """{brief asset path: webp bytes} for every asset (references too: the recipe view shows them)."""
    out = {}
    for a in brief["assets"]:
        src = files.get(a["ref_id"])
        if src is not None:
            out[a["path"]] = web_image(src)
    return out


def page_assets(brief: dict) -> list[dict]:
    return [a for a in brief["assets"] if a["role"] in PAGE_ROLES]
