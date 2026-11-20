"""validate_page.py - sanitize a compiled landing page, re-wrap it, and check it invents nothing.

Any page (A5's Gemini output or compile_spec's) goes through here:
  sanitize   keep <style> + <body>; drop <head>, scripts, frames, links, metas, forms, event handlers, external
             URLs (href: '#...' / mailto only; src / url(): the asset manifest only; CSS @import dropped)
  wrap       our own <head>: charset, viewport, CSP, title, the spec's Google Fonts links, plus GUARD css that
             *enforces* decor rules (pointer-events:none on z0/z5/z20/z50, decor hidden below 1024 px, grain)
  conform    blocking errors: a colour literal outside the spec palette, a font outside the spec, z-index outside
             0-50, not exactly one <h1>, spec copy / data-item / data-section (or data-group) missing.
             advisories (fed back once, never a reason to discard): a decor element or type face the spec has
             but the page doesn't use, no z0 layer.
  fix        code repairs on a model page: drop given motifs (they covered text or an image in the browser) and
             inject the background image the design asked for when the page left it out
clean_svg / clean_css make A4's free decorations safe (allowed SVG elements only, palette colours only).
"""
from __future__ import annotations

import html as H
import re
from html.parser import HTMLParser

BANNED = {"script", "iframe", "object", "embed", "link", "meta", "base", "frame", "frameset", "applet", "noscript",
          "template", "portal", "form", "input", "button", "select", "textarea", "audio", "video", "source", "track",
          "canvas", "head", "title", "foreignobject", "use", "image", "animate", "set", "animatemotion"}
VOID = {"img", "br", "hr", "wbr", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "stop"}
COLOR_LIT = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)|"
                       r"\b(?:oklch|oklab|lab|lch|hwb)\([^)]*\)", re.I)
NAMED = {"white": "#FFFFFF", "black": "#000000", "red": "#FF0000", "blue": "#0000FF", "green": "#008000",
         "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080", "pink": "#FFC0CB", "gray": "#808080",
         "grey": "#808080", "cyan": "#00FFFF", "magenta": "#FF00FF"}
try:                                               # every CSS named colour (tomato, gold, ...), from Pillow's table
    from PIL import ImageColor
    NAMED = {**{k: v.upper() for k, v in ImageColor.colormap.items() if v.startswith("#") and len(v) == 7}, **NAMED}
except ImportError:  # pragma: no cover
    pass
_NAMES = "|".join(sorted(NAMED, key=len, reverse=True))
NAMED_RE = re.compile(r"(?:color|background(?:-color)?|fill|stroke|border(?:-[a-z]+)?|outline|stop-color|"
                      r"text-shadow|box-shadow)\s*:[^;{}]*\b(" + _NAMES + r")\b", re.I)
URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)
FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;}{]+)", re.I)
ZINDEX = re.compile(r"z-index\s*:\s*(-?\d+)", re.I)
GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
           "ui-monospace", "ui-rounded", "emoji", "math", "fangsong", "inherit", "initial", "unset"}
Z_MIN, Z_MAX = 0, 50

GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/>"
         "</filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.55'/></svg>\")")
GUARD = """[data-layer="z0"],[data-layer="z5"],[data-layer="z20"],[data-layer="z50"]{pointer-events:none}
[data-layer="z50"]{position:fixed;inset:0;z-index:50;opacity:.07;mix-blend-mode:overlay;background-image:""" + GRAIN + """}
@media (max-width:1023px){[data-layer="z5"],[data-layer="z20"]{display:none!important}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
img{max-width:100%;height:auto}"""


def strip_fences(text: str) -> str:
    t = (text or "").strip()
    m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", t, re.S)
    return m.group(1) if m else t


def _hex6(lit: str) -> str | None:
    s = lit.strip().lower()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h[:6].upper()
    m = re.match(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)", s)
    if m:
        return "#" + "".join(f"{min(255, int(v)):02X}" for v in m.groups())
    return None


class _San(HTMLParser):
    def __init__(self, assets: set[str], drop_motifs=()):
        super().__init__(convert_charrefs=True)
        self.assets, self.out, self.skip, self.stack = assets, [], 0, []
        self.drop = set(drop_motifs)
        self.sections: set[str] = set()
        self.dropped: list[str] = []
        self.text: list[str] = []
        self.items, self.motifs, self.layers, self.groups = set(), set(), set(), set()
        self.layer_stack: list[str | None] = []
        self.z0_srcs: set[str] = set()
        self.h1 = 0
        self.inline_styles: list[str] = []
        self.svg_colors: list[str] = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if self.skip or t in BANNED or t == "style" or (self.drop and dict(attrs).get("data-motif") in self.drop):
            if not self.skip:
                self.dropped.append(f"<{t}>" if not self.drop or dict(attrs).get("data-motif") not in self.drop
                                    else f"motif {dict(attrs).get('data-motif')}")
            if t not in VOID:
                self.skip += 1
            return
        keep = []
        for k, v in attrs:
            k, v = k.lower(), v or ""
            if k.startswith("on") or k in ("srcset", "formaction", "xlink:href", "ping", "background", "poster", "action"):
                self.dropped.append(f"{t}[{k}]")
                continue
            if k == "href" and not (v.startswith("#") or v.startswith("mailto:")):
                self.dropped.append(f"href={v[:40]}")
                v = "#"
            if k == "src" and v not in self.assets:
                self.dropped.append(f"src={v[:40]}")
                continue
            if k == "style":
                if re.search(r"expression\(|javascript:|@import|behavior\s*:", v, re.I):
                    self.dropped.append("style[unsafe]")
                    continue
                v = URL.sub(lambda mm: mm.group(0) if mm.group(1) in self.assets or mm.group(1).startswith("#")
                            else "none", v)
                self.inline_styles.append(v)
            if k in ("fill", "stroke", "stop-color", "color", "flood-color", "lighting-color"):
                self.svg_colors.append(v)
            if k == "data-item":
                self.items.add(v)
            if k == "data-motif":
                self.motifs.add(v)
            if k == "data-layer":
                self.layers.add(v)
            if k == "data-group":
                self.groups.add(v)
            if k == "data-section":
                self.sections.add(v)
            keep.append((k, v))
        layer = dict(keep).get("data-layer")
        if t == "img" and "z0" in self.layer_stack + [layer] and dict(keep).get("src"):
            self.z0_srcs.add(dict(keep)["src"])
        if t == "h1":
            self.h1 += 1
        self.out.append(f"<{t}" + "".join(f' {k}="{H.escape(v, quote=True)}"' for k, v in keep) + (">"))
        if t not in VOID:
            self.stack.append(t)
            self.layer_stack.append(layer)
        else:
            self.out[-1] = self.out[-1][:-1] + "/>" if t in VOID - {"img", "br", "hr", "wbr"} else self.out[-1]

    def handle_startendtag(self, tag, attrs):
        before = self.skip
        self.handle_starttag(tag, attrs)
        t = tag.lower()
        if self.skip > before:                     # a dropped self-closing element (<use/>, <image/>) has no children
            self.skip = before
            return
        if t not in VOID and not self.skip and self.stack and self.stack[-1] == t:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        t = tag.lower()
        if self.skip:
            if t not in VOID:
                self.skip -= 1
            return
        if t in VOID or t not in self.stack:
            return
        while self.stack:
            x = self.stack.pop()
            self.layer_stack.pop()
            self.out.append(f"</{x}>")
            if x == t:
                break

    def handle_data(self, data):
        if self.skip:
            return
        self.text.append(data)
        self.out.append(H.escape(data, quote=False))


def split_doc(raw: str) -> tuple[str, str]:
    """-> (css, body_inner) from a full document or a fragment."""
    t = strip_fences(raw)
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", t, re.S | re.I))
    m = re.search(r"<body[^>]*>(.*)</body>", t, re.S | re.I)
    body = m.group(1) if m else re.sub(r"(?is)<!doctype[^>]*>|<head>.*?</head>|</?html[^>]*>", "", t)
    body = re.sub(r"(?is)<style[^>]*>.*?</style>", "", body)
    return css, body


def sanitize_css(css: str, assets: set[str]) -> tuple[str, list[str]]:
    dropped = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"@import", css, re.I):
        dropped.append("@import")
        css = re.sub(r"@import[^;]+;", "", css, flags=re.I)
    if re.search(r"expression\(|javascript:|behavior\s*:", css, re.I):
        dropped.append("css[unsafe]")
        css = re.sub(r"expression\([^)]*\)|javascript:[^;]*|behavior\s*:[^;]*", "", css, flags=re.I)

    def u(mm):
        if mm.group(1) in assets or mm.group(1).startswith("data:image/svg+xml") or mm.group(1).startswith("#"):
            return mm.group(0)
        dropped.append(f"url({mm.group(1)[:40]})")
        return "none"
    return URL.sub(u, css), dropped


def wrap(css: str, body: str, spec: dict) -> str:
    fonts = "\n".join(f'<link rel="stylesheet" href="{H.escape(u)}">' for u in spec.get("fonts_css", []))
    title = H.escape(spec.get("title") or "Landing page")
    csp = ("default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline' https://fonts.googleapis.com; "
           "font-src https://fonts.gstatic.com")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>{title}</title>
<meta name="generator" content="serpman landing / {H.escape(spec.get('family', ''))}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{fonts}
<style>
{css}
{GUARD}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(s or "")).strip().lower()


def backdrop_html(spec: dict) -> tuple[str, str]:
    """The fixed z0 backdrop for the spec's background image (injected when a page left it out) -> (css, html)."""
    bg = spec.get("background") or {}
    tint = ('<div style="position:absolute;inset:0;background:color-mix(in srgb,var(--bg-primary) 55%,transparent)">'
            '</div>') if bg.get("treatment") == "tinted" or bg.get("abstract") else ""
    css = ('body{isolation:isolate}[data-injected="backdrop"]{position:fixed;inset:0;z-index:-1;overflow:hidden;'
           'pointer-events:none}[data-injected="backdrop"] img{width:100%;height:100%;object-fit:cover;max-width:none}')
    return css, (f'<div data-layer="z0" data-injected="backdrop" aria-hidden="true">'
                 f'<img src="{H.escape(bg["image"])}" alt="">{tint}</div>')


def check(raw: str, spec: dict, *, drop_motifs=(), inject_backdrop: bool = False, fix_colors_: bool = False) -> dict:
    """-> {html, errors (blocking), advisories, fixes, warnings, dropped}.
    errors = the page is unsafe, invents something or loses content; advisories = taste / completeness notes."""
    assets = {a["path"] for a in spec.get("assets", [])}
    css, body = split_doc(raw)
    css, dropped = sanitize_css(css, assets)
    snapped = 0
    if fix_colors_:                                   # code fix: stray colours -> the nearest palette colour
        css, body, snapped = fix_page_colors(css, body, [h for h in spec["palette"].values()])
    p = _San(assets, drop_motifs)
    p.feed(body)
    p.close()
    while p.stack:
        p.out.append(f"</{p.stack.pop()}>")
    body = "".join(p.out)
    dropped += p.dropped
    errors, advisories, fixes, warnings = [], [], [], []
    allowed = {h.upper() for h in spec["palette"].values()}
    decls = " ; ".join(re.findall(r"\{([^{}]*)\}", css))     # declarations only: '#hero {' is a selector, not a colour
    lits = COLOR_LIT.findall(decls) + [x for s in p.inline_styles for x in COLOR_LIT.findall(s)] + \
        [x for s in p.svg_colors for x in COLOR_LIT.findall(s)]
    foreign = sorted({lit for lit in lits if _hex6(lit) not in allowed})
    if foreign:
        errors.append(f"colours not in the spec palette: {', '.join(foreign[:8])}")
    named = sorted({m.group(1).lower() for m in NAMED_RE.finditer(decls + ";".join(p.inline_styles))
                    if NAMED[m.group(1).lower()] not in allowed})
    named += sorted({v.lower() for v in p.svg_colors if v.lower() in NAMED and NAMED[v.lower()] not in allowed})
    if named:
        errors.append(f"named colours not in the spec palette: {', '.join(dict.fromkeys(named))}")
    fonts = {f.lower() for f in spec.get("fonts", [])}
    declared = set()
    for m in FONT_FAMILY.finditer(css + ";" + ";".join(p.inline_styles)):
        for fam in m.group(1).split(","):
            f = fam.strip().strip("'\"").lower()
            declared.add(f)
            if f and not f.startswith("var(") and f not in GENERIC and f not in fonts:
                errors.append(f"font '{fam.strip()}' is not a spec font")
    for lvl, L in (spec.get("levels") or {}).items():
        if L.get("used") and L["family"].lower() not in declared:
            advisories.append(f"type level {lvl} ({L['family']}) is in the design but its face is never declared")
    zs = {int(z) for z in ZINDEX.findall(css + ";" + ";".join(p.inline_styles))}
    bad_z = sorted(z for z in zs if not Z_MIN <= z <= Z_MAX)
    if bad_z:
        errors.append(f"z-index values outside {Z_MIN}-{Z_MAX}: {bad_z}")
    if p.h1 != 1:
        errors.append(f"expected exactly one <h1>, found {p.h1}")
    text = _norm(" ".join(p.text))
    missing = [s for s in spec.get("copy", []) if s and _norm(s) not in text]
    if missing:
        errors.append(f"spec copy missing: {'; '.join(x[:40] for x in missing[:5])}")
    miss_items = sorted(set(spec.get("item_ids", [])) - p.items)
    if miss_items:
        errors.append(f"data-item missing: {', '.join(miss_items[:8])}")
    miss_groups = sorted(set(spec.get("group_ids", [])) - p.groups)
    if miss_groups:
        errors.append(f"data-group missing: {', '.join(miss_groups)}")
    miss_sections = sorted(set(spec.get("section_ids", [])) - p.sections)
    if miss_sections:
        errors.append(f"data-section missing: {', '.join(miss_sections)}")
    bg_img = (spec.get("background") or {}).get("image")
    if bg_img and bg_img not in p.z0_srcs and bg_img not in css:
        if inject_backdrop:
            add_css, add_html = backdrop_html(spec)
            css += "\n" + add_css
            body = add_html + body
            fixes.append(f"injected the background image {bg_img} as a fixed backdrop (the page left it out)")
        else:
            errors.append(f"the background image {bg_img} (A1: {spec['background'].get('treatment')}) is not in "
                          f"the z0 layer")
    miss_motifs = sorted(set(spec.get("motif_ids", [])) - p.motifs - set(drop_motifs))
    if miss_motifs:
        advisories.append(f"decor not on the page (data-motif missing): {', '.join(miss_motifs[:8])}")
    if "z0" not in p.layers and not fixes:
        advisories.append('no data-layer="z0" backdrop layer')
    if drop_motifs:
        fixes.append(f"removed decor that covered text or an image: {', '.join(sorted(drop_motifs))}")
    if snapped:
        fixes.append(f"snapped {snapped} stray colour(s) to the nearest palette colour")
    if dropped:
        warnings.append(f"sanitized: {', '.join(dict.fromkeys(dropped))[:300]}")
    return {"html": wrap(css, body, spec), "errors": list(dict.fromkeys(errors)),
            "advisories": list(dict.fromkeys(advisories)), "fixes": fixes, "warnings": warnings,
            "dropped": list(dict.fromkeys(dropped))}


# --------------------------------------------------------------------------- A4's free decorations
SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient",
            "radialgradient", "stop", "clippath", "mask", "pattern", "text", "tspan", "title", "desc", "filter",
            "fegaussianblur", "feturbulence", "fecolormatrix", "feblend", "feoffset", "femerge", "femergenode",
            "fecomposite", "feflood", "fedisplacementmap"}
SVG_MAX = 9000


def _rgb(hx: str) -> tuple[int, int, int]:
    return tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))


def nearest_hex(hx: str, allowed: list[str]) -> str:
    r = _rgb(hx)
    return min(allowed, key=lambda a: sum((x - y) ** 2 for x, y in zip(r, _rgb(a))))


COLOR_PROPS = (r"(?:color|background(?:-color|-image)?|fill|stroke|border(?:-[a-z]+)*|outline(?:-color)?|stop-color|"
               r"flood-color|text-shadow|box-shadow|caret-color|text-decoration(?:-color)?|column-rule(?:-color)?)")


def fix_colors(text: str, allowed: list[str]) -> tuple[str, int]:
    """Every colour literal / named colour outside the palette -> its nearest palette colour, keeping alpha
    (rgba(0,0,0,.6) -> color-mix(in srgb, <nearest> 60%, transparent)). -> (text, how many)."""
    ok = {x.upper() for x in allowed}
    pal = sorted(ok)
    n = 0

    def lit(m):
        nonlocal n
        raw = m.group(0)
        h6 = _hex6(raw)
        alpha = None
        am = re.match(r"(?i)rgba?\(\s*\d+[ ,]+\d+[ ,]+\d+\s*[,/]\s*([\d.]+%?)", raw)
        if am:
            v = am.group(1)
            alpha = float(v[:-1]) / 100 if v.endswith("%") else float(v)
        elif re.fullmatch(r"#[0-9a-fA-F]{8}", raw):
            alpha = int(raw[7:9], 16) / 255
        if h6 and h6 in ok and (alpha is None or alpha >= 0.999):
            return raw
        if not h6:                                    # hsl()/oklch(): can't map reliably -> the palette's mid grey
            h6 = "#808080"
        n += 1
        hx = h6 if h6 in ok else nearest_hex(h6, pal)
        if alpha is not None and alpha < 0.999:
            return f"color-mix(in srgb,{hx} {round(alpha * 100)}%,transparent)"
        return hx
    text = COLOR_LIT.sub(lit, text)

    def decl(m):
        nonlocal n

        def name(mm):
            nonlocal n
            hx = NAMED.get(mm.group(0).lower())
            if not hx or hx in ok:
                return mm.group(0)
            n += 1
            return nearest_hex(hx, pal)
        return m.group(1) + re.sub(r"\b(" + _NAMES + r")\b", name, m.group(2), flags=re.I)
    text = re.sub(r"(" + COLOR_PROPS + r"\s*[:=]\s*[\"']?)([^;{}\"'<>]*)", decl, text, flags=re.I)
    return text, n


def fix_page_colors(css: str, body: str, allowed: list[str]) -> tuple[str, str, int]:
    """A model page's stray colours -> the palette: in the stylesheet and inside tags (styles, SVG attributes),
    never in the visible text."""
    css, n1 = fix_colors(css, allowed)
    count = n1

    def tag(m):
        nonlocal count
        t, k = fix_colors(m.group(0), allowed)
        count += k
        return t
    body = re.sub(r"<[^>]+>", tag, body)
    return css, body, count


class _Svg(_San):
    def handle_starttag(self, tag, attrs):
        if not self.skip and tag.lower() not in SVG_TAGS:
            self.dropped.append(f"<{tag.lower()}>")
            if tag.lower() not in VOID:
                self.skip += 1
            return
        if tag.lower() == "svg" and not self.stack:          # the root: our sizing and hooks
            a = dict(attrs)
            vb = a.get("viewbox") or a.get("viewBox")
            if not vb:
                try:
                    vb = f"0 0 {float(a.get('width', 100))} {float(a.get('height', 100))}"
                except ValueError:
                    vb = "0 0 100 100"
            attrs = [(k, v) for k, v in attrs if k.lower() not in ("width", "height", "viewbox", "data-motif",
                                                                   "aria-hidden", "focusable", "id")]
            attrs += [("viewBox", vb), ("width", "100%"), ("height", "100%"), ("data-motif", self.motif_id),
                      ("aria-hidden", "true"), ("focusable", "false")]
        super().handle_starttag(tag, attrs)


def clean_svg(svg: str, allowed: list[str], motif_id: str) -> tuple[str, list[str]]:
    """A4's SVG -> a safe <svg> with data-motif, palette colours only. -> ('' if unusable, notes)."""
    notes = []
    t = (svg or "").strip()
    t = re.sub(r"(?is)<\?xml.*?\?>|<!doctype.*?>|<!--.*?-->", "", t).strip()
    if not t.lower().startswith("<svg") or len(t) > SVG_MAX:
        return "", ["not a single <svg> element" if not t.lower().startswith("<svg") else f"longer than {SVG_MAX} chars"]
    p = _Svg(set())
    p.motif_id = motif_id
    p.feed(t)
    p.close()
    while p.stack:
        p.out.append(f"</{p.stack.pop()}>")
    out = "".join(p.out)
    if p.dropped:
        notes.append(f"removed {', '.join(dict.fromkeys(p.dropped))[:120]}")
    out = re.sub(r'viewbox="', 'viewBox="', out)
    out, n = fix_colors(out, allowed)
    if n:
        notes.append(f"{n} colour(s) snapped to the palette")
    if not re.search(r"<(path|circle|ellipse|rect|line|polyline|polygon|text)\b", out):
        return "", notes + ["no visible shape"]
    return out, notes


def clean_css(css: str, allowed: list[str]) -> tuple[str, list[str]]:
    """A4's CSS recipe (declarations only, e.g. 'background: radial-gradient(...)') -> safe declarations."""
    notes = []
    t = re.sub(r"/\*.*?\*/", "", css or "", flags=re.S)
    t = re.sub(r"[{}@<>]", "", t)
    t, dropped = sanitize_css(t, set())
    if dropped:
        notes.append(f"removed {', '.join(dropped)[:80]}")
    t = re.sub(r"(?i)z-index\s*:[^;]*;?|position\s*:[^;]*;?", "", t)
    t, n = fix_colors(t, allowed)
    if n:
        notes.append(f"{n} colour(s) snapped to the palette")
    return t.strip()[:1500], notes
