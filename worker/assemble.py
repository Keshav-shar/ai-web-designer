"""assemble.py - the page frame (L0 background, L1 nav/footer, L2 sections, L3 overlay) + compiled CSS.

Tailwind: the worker compiles only the classes the page uses, with the web project's own @tailwindcss/cli
(web/node_modules/.bin/tailwindcss), or TAILWIND_BIN if set. The result is a static site: no runtime scripts.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path

from agent import content_sections, title_of
from assets import page_assets

ROOT = Path(__file__).resolve().parents[1]


def tailwind_bin() -> list[str]:
    env = os.getenv("TAILWIND_BIN")
    if env:
        return [env]
    for name in ("tailwindcss.cmd", "tailwindcss"):
        p = ROOT / "web" / "node_modules" / ".bin" / name
        if p.exists():
            return [str(p)]
    raise RuntimeError("Tailwind CLI not found: run `npm install` in D:\\serpman-studio\\web (it provides "
                       "@tailwindcss/cli) or set TAILWIND_BIN")


def overlay_kind(effect: str) -> list[str]:
    e = effect.lower()
    kinds = []
    if re.search(r"grain|noise|film|photocopy|paper|letterpress", e):
        kinds.append("grain")
    if re.search(r"scanline|crt", e):
        kinds.append("scanlines")
    if re.search(r"glow|neon|aurora|blur|gradient", e):
        kinds.append("glow")
    return kinds or ["grain"]


GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/>"
         "</filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.55'/></svg>\")")


def input_css(brief: dict) -> str:
    t, f = brief["tokens"], brief["fonts"]
    visuals = brief["typography"].get("visuals", [])
    roots = {**t["color"], **t["derived"], **{f"--visual-{i + 1}": v for i, v in enumerate(visuals)}, **t["type"]}
    v1, v2, v3 = (f"var(--visual-{i})" if len(visuals) >= i else "var(--accent-soft)" for i in (1, 2, 3))
    kinds = overlay_kind(brief["vibe"]["effect"])
    h_it = "italic" if f.get("pairing", {}).get("heading_italic") else "normal"
    return f"""@import "tailwindcss" source(none);
@source "./index.html";

@theme {{
  --font-heading: "{f['heading']['family']}", ui-serif, Georgia, serif;
  --font-body: "{f['body']['family']}", ui-sans-serif, system-ui, sans-serif;
}}

:root {{
{chr(10).join(f'  {k}: {v};' for k, v in roots.items())}
}}

@layer base {{
  html {{ scroll-behavior: smooth; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-body); font-size: var(--fs-1);
         line-height: var(--lh-body); -webkit-font-smoothing: antialiased; }}
  h1, h2, h3 {{ font-family: var(--font-heading); line-height: var(--lh-heading); letter-spacing: var(--tracking-display);
               text-transform: var(--case-display); font-weight: 500; }}
  h1, h2 {{ font-style: {h_it}; }}
  a {{ color: inherit; }}
  :focus-visible {{ outline: 2px solid var(--focus-ring); outline-offset: 3px; border-radius: 6px; }}
  img {{ max-width: 100%; height: auto; }}
}}

@layer components {{
  .container-x {{ width: min(100% - 2.5rem, 72rem); margin-inline: auto; }}
  .glass {{ background: color-mix(in oklab, var(--surface) 62%, transparent); border: 1px solid
           color-mix(in oklab, var(--border) 70%, transparent); border-radius: 1.75rem;
           backdrop-filter: blur(18px) saturate(1.2); box-shadow: 0 20px 60px -30px color-mix(in oklab, var(--text) 35%, transparent); }}
  .eyebrow {{ font-size: var(--fs-1); text-transform: uppercase; letter-spacing: .14em; color: var(--text-muted);
             margin-bottom: .75rem; }}
  .btn {{ display: inline-flex; align-items: center; gap: .5rem; border-radius: 999px; padding: .85rem 1.6rem;
         font-weight: 500; transition: transform .4s ease, background-color .4s ease; }}
  .btn-primary {{ background: var(--accent); color: var(--on-accent); }}
  .btn-primary:hover {{ background: var(--accent-hover); transform: translateY(-2px); }}
  .btn-ghost {{ border: 1px solid var(--border); color: var(--text); background: color-mix(in oklab, var(--surface) 40%, transparent); }}
  .btn-ghost:hover {{ transform: translateY(-2px); }}
  .soft-glow {{ position: absolute; inset: 10% 5%; border-radius: 50%; filter: blur(60px); opacity: .7; z-index: -1;
               background: radial-gradient(circle at 30% 30%, {v1}, transparent 60%), radial-gradient(circle at 70% 60%, {v2}, transparent 60%); }}
  .float {{ animation: float 9s ease-in-out infinite; }}
  .fade-up {{ animation: fade-up 1.1s cubic-bezier(.2,.7,.2,1) both; }}
}}

.l0 {{ position: fixed; inset: 0; z-index: -2; overflow: hidden; background: var(--bg); }}
.l0 .mesh {{ position: absolute; inset: -20%; filter: blur(70px); opacity: .85; animation: drift 48s ease-in-out infinite alternate;
            background: radial-gradient(40% 35% at 20% 25%, {v1}, transparent 70%),
                        radial-gradient(35% 40% at 80% 20%, {v2}, transparent 70%),
                        radial-gradient(45% 40% at 60% 85%, {v3}, transparent 70%); }}
.l0 img {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: .28; mix-blend-mode: soft-light; }}
.l3 {{ position: fixed; inset: 0; z-index: 50; pointer-events: none; }}
{'.l3 .grain { position: absolute; inset: 0; opacity: .08; background-image: ' + GRAIN + '; mix-blend-mode: multiply; }' if 'grain' in kinds else ''}
{'.l3 .scanlines { position: absolute; inset: 0; opacity: .12; background: repeating-linear-gradient(0deg, color-mix(in oklab, var(--text) 40%, transparent) 0 1px, transparent 1px 3px); }' if 'scanlines' in kinds else ''}

@keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-8px); }} }}
@keyframes fade-up {{ from {{ opacity: 0; transform: translateY(18px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes drift {{ from {{ transform: translate3d(-3%, -2%, 0) rotate(0deg); }} to {{ transform: translate3d(3%, 2%, 0) rotate(8deg); }} }}
@media (prefers-reduced-motion: reduce) {{
  .float, .fade-up, .l0 .mesh {{ animation: none !important; }}
  html {{ scroll-behavior: auto; }}
}}
"""


def nav(brief: dict, split: dict) -> str:
    brand = escape(split.get("brand_name") or split["full_query"].split(" website")[0][:40])
    links = [s["id"] for s in content_sections(brief) if s["id"] not in ("hero", "announce_bar", "cta_band")][:5]
    items = "".join(f'<li><a class="hover:text-[var(--text)]" href="#{sid}">{title_of(sid)}</a></li>' for sid in links)
    return (f'<header class="sticky top-0 z-40"><nav class="container-x mt-4 flex items-center justify-between gap-6 '
            f'rounded-full px-6 py-3 glass" aria-label="Main"><a href="#hero" class="font-heading text-[length:var(--fs-3)]">'
            f'{brand}</a><ul class="hidden gap-6 text-[var(--text-muted)] md:flex">{items}</ul>'
            f'<a class="btn btn-primary" href="#cta_band">Get started</a></nav></header>')


def footer(brief: dict, split: dict) -> str:
    brand = escape(split.get("brand_name") or "")
    return (f'<footer class="container-x mt-24 border-t border-[var(--border)] py-12 text-[var(--text-muted)]">'
            f'<div class="flex flex-col justify-between gap-6 md:flex-row"><p class="font-heading text-[length:var(--fs-3)] '
            f'text-[var(--text)]">{brand or escape(split["full_query"][:60])}</p><p>Concept site generated by serpman Studio '
            f'from the {escape(brief["vibe"]["name"])} family. Images are research references.</p></div></footer>')


def html_page(brief: dict, split: dict, sections: list[dict]) -> str:
    f = brief["fonts"]
    bg = next((a for a in page_assets(brief) if a["role"] == "background"), None)
    title = escape(split.get("brand_name") or split["full_query"][:70])
    body = "\n".join(s["html"] for s in sections if s["id"] != "announce_bar")
    announce = next((s["html"] for s in sections if s["id"] == "announce_bar"), "")
    csp = ("default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
           "font-src https://fonts.gstatic.com")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>{title}</title>
<meta name="generator" content="serpman Studio / {escape(brief['meta']['routed_family'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{escape(f['heading']['google_css'])}">
<link rel="stylesheet" href="{escape(f['body']['google_css'])}">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="l0" aria-hidden="true"><div class="mesh"></div>{f'<img src="{bg["path"]}" alt="">' if bg else ''}</div>
{announce}
{nav(brief, split)}
<main>
{body}
</main>
{footer(brief, split)}
<div class="l3" aria-hidden="true"><div class="grain"></div><div class="scanlines"></div></div>
</body>
</html>
"""


def build(brief: dict, split: dict, sections: list[dict]) -> tuple[str, str]:
    """-> (index.html, styles.css)."""
    page = html_page(brief, split, sections)
    # Build inside web/ so `@import "tailwindcss"` resolves against web/node_modules.
    build_root = ROOT / "web" / ".site-build"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_root) as d:
        dp = Path(d)
        (dp / "index.html").write_text(page, encoding="utf-8")
        (dp / "input.css").write_text(input_css(brief), encoding="utf-8")
        cmd = tailwind_bin() + ["-i", str(dp / "input.css"), "-o", str(dp / "styles.css"), "--minify"]
        r = subprocess.run(cmd, cwd=dp, capture_output=True, text=True, timeout=120, shell=cmd[0].endswith(".cmd"))
        if r.returncode != 0 or not (dp / "styles.css").exists():
            raise RuntimeError(f"tailwind failed ({r.returncode}): {(r.stderr or r.stdout)[-800:]}")
        css = (dp / "styles.css").read_text(encoding="utf-8")
    return page, css


def write_local(out_dir: Path, page: str, css: str, files: dict[str, bytes]) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / "styles.css").write_text(css, encoding="utf-8")
    for rel, data in files.items():
        (out_dir / rel).write_bytes(data)
