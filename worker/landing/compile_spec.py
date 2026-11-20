"""compile_spec.py - the deterministic compiler: landing_spec -> HTML + CSS (A5's fallback and reference rendering).

It makes no design decision of its own: colours are the spec's role variables, type its five levels, layout its
groups and columns, decoration its pre-rendered SVGs placed by relation. What it does own is composition:

  flow      bands are content-driven (padding from the spec; only the hero has a minimum height)
  panels    every group is one block: a flex column with one gap rhythm; items sharing a row sit side by side;
            a group's backing is one plate for the whole block
  hero      text panel beside the image: the image stretches to the row, the text is centred against it;
            stacked: text then image (or the reverse); full-bleed: the image fills the hero behind a plated panel
  cards     content-sized, equal heights per row (or top-aligned when the measurements ask for it)
  z-0       a fixed backdrop behind everything: the spec's layers, the background image with A1's treatment
  decor     free-area motifs in the band's z-5 layer (% of the band), behind/edge motifs in a z-5 layer just under
            their target (% of the target), corner accents pinned to their container on z-20
Below 1024 px every grid collapses to one column and the decor layers are hidden (validate_page's GUARD as well).
Output goes through validate_page.check and the browser measurements like any model-written page.
"""
from __future__ import annotations

from html import escape

POS = {"full": "50% 50%", "top": "50% 0%", "center": "50% 50%", "bottom": "50% 100%", "left": "0% 50%",
       "right": "100% 50%", "top_left": "0% 0%", "top_right": "100% 0%", "bottom_left": "0% 100%",
       "bottom_right": "100% 100%"}
SCALE = {"fine": 0.5, "medium": 1.0, "bold": 2.0}
SHADOW = {"none": "none", "soft_drop": "0 8px 28px color-mix(in srgb, var(--bg-primary) 70%, transparent)",
          "hard_offset": "4px 4px 0 var(--overlay-secondary)",
          "neon_glow": "0 0 10px var(--overlay-primary), 0 0 34px var(--overlay-primary)",
          "outline": "none"}
SIZE = {"nav_link": "var(--fs-1)", "cta": "var(--fs-1)", "eyebrow": "var(--fs-1)",
        "h1": "clamp(2.4rem,5.2vw,var(--fs-8))", "subheading": "var(--fs-2)",
        "intro_heading": "clamp(1.9rem,3.6vw,var(--fs-6))", "intro_body": "var(--fs-2)"}
NAV_RANK = {"logo": 0, "nav_link": 1, "cta": 2}


def v(role: str) -> str:
    return "transparent" if role in (None, "", "transparent", "none") else f"var(--{role.replace('_', '-')})"


def plate_style(backing: str, surface: str) -> str:
    if backing == "solid":
        return f"background:{v(surface)};"
    if backing == "frosted":
        return f"background:color-mix(in srgb,{v(surface)} 74%,transparent);backdrop-filter:blur(12px);"
    return ""


# --------------------------------------------------------------------------- z0
def layer_css(L: dict, i: int, bg: dict) -> tuple[str, str]:
    """-> (css rule, inner html) for one z0 background layer."""
    r = [v(x) for x in L["roles"]] or ["var(--bg-primary)"]
    r0, r1, r2 = r[0], r[1 % len(r)], r[2 % len(r)]
    s = SCALE.get(L.get("scale"), 1.0)
    pos = POS.get(L.get("position"), "50% 50%")
    a = float(L.get("angle_deg") or 0)
    k, css, extra = L["kind"], "", ""
    if k == "solid":
        css = f"background:{r0}"
    elif k == "linear_gradient":
        css = f"background:linear-gradient({a:.0f}deg,{r0},{r1})"
    elif k == "radial_glow":
        css = f"background:radial-gradient(circle at {pos},color-mix(in srgb,{r0} 75%,transparent) 0,transparent {int(30 + 18 * s)}%)"
    elif k == "stripes":
        w = int(10 * s)
        css = f"background:repeating-linear-gradient({a:.0f}deg,{r0} 0 {w}px,transparent {w}px {2 * w}px)"
    elif k == "grid":
        w = int(48 * s)
        css = (f"background-image:linear-gradient({r0} 1px,transparent 1px),linear-gradient(90deg,{r0} 1px,transparent 1px);"
               f"background-size:{w}px {w}px")
    elif k == "dots":
        w = int(22 * s)
        css = f"background-image:radial-gradient({r0} 1.6px,transparent 1.8px);background-size:{w}px {w}px"
    elif k == "halftone":
        w = int(14 * s)
        css = (f"background-image:radial-gradient({r0} 32%,transparent 34%);background-size:{w}px {w}px;"
               f"-webkit-mask-image:linear-gradient(to bottom,var(--bg-primary),transparent);"
               f"mask-image:linear-gradient(to bottom,var(--bg-primary),transparent)")
    elif k == "scanlines":
        css = f"background:repeating-linear-gradient(0deg,color-mix(in srgb,{r0} 40%,transparent) 0 1px,transparent 1px 3px)"
    elif k == "mesh":
        css = (f"background:radial-gradient(40% 35% at 20% 25%,{r0},transparent 70%),"
               f"radial-gradient(35% 40% at 80% 20%,{r1},transparent 70%),radial-gradient(45% 40% at 60% 85%,{r2},transparent 70%);"
               f"filter:blur(60px)")
    elif k == "paper":
        css = f"background:radial-gradient(120% 90% at 50% 40%,transparent 60%,color-mix(in srgb,{r0} 35%,transparent))"
    elif k == "perspective_grid":
        from .primitives import render
        extra = render({"motif_id": f"bg{i}", "primitive": "perspective_grid", "count": int(5 * s) + 2,
                        "fill_role": L["roles"][0], "stroke_role": L["roles"][-1], "stroke_width": 3}, 1440, 420)
        css = "top:auto;height:46%;" + ("bottom:0" if L.get("position") != "top" else "top:0")
    elif k == "image" and bg.get("image"):
        t = bg.get("treatment", "photo_fill")
        mask = ("-webkit-mask-image:radial-gradient(ellipse at 50% 38%,var(--bg-primary) 28%,transparent 76%);"
                "mask-image:radial-gradient(ellipse at 50% 38%,var(--bg-primary) 28%,transparent 76%)"
                if t == "masked_radial" else "")
        extra = f'<img src="{escape(bg["image"])}" alt="" class="bg-img" style="{mask}">'
        if t == "tinted" or bg.get("abstract"):
            extra += '<div class="bg-tint"></div>'
    elif k == "grain":
        return "", ""                                  # the z50 layer (validate_page GUARD) draws grain
    rule = (f'.bg-l{i}{{position:absolute;inset:0;{css};opacity:{float(L.get("opacity", 1)):.3g};'
            f'mix-blend-mode:{L.get("blend", "normal")}}}')
    return rule, extra


def level_css(spec: dict) -> str:
    out = []
    for lvl, L in spec["levels"].items():
        r = [f"font-family:{L['stack']}", f"font-weight:{L['weight']}", f"letter-spacing:{L['letter_spacing']}",
             f"text-transform:{L['case']}", f"font-style:{'italic' if L['italic'] else 'normal'}"]
        if lvl == "display":
            r.append(f"text-shadow:{SHADOW.get(L.get('shadow_treatment'), 'none')};line-height:1.06")
            if L.get("shadow_treatment") == "outline":
                r.append("-webkit-text-stroke:1.5px currentColor;color:transparent!important")
        if lvl == "wordmark":
            r.append(f"font-size:var({L.get('size_token', '--fs-3')});line-height:1")
        out.append(f".lv-{lvl}{{{';'.join(r)}}}")
    return "".join(out)


# --------------------------------------------------------------------------- decoration
def pins(spec: dict, kind: str, target: str) -> str:
    return "".join(
        f'<div data-layer="z20" class="pin pin-{m["corner"]}" data-relation="corner_of_container" '
        f'data-target="{escape(target)}" style="width:{m["size_px"]}px;height:{m["size_px"]}px;'
        f'--o:-{m["size_px"] // 2 + m["offset_px"]}px;transform:rotate({m["rotation_deg"]}deg);opacity:{m["opacity"]}">'
        f'{m["svg"]}</div>'
        for m in spec["motifs"] if m["relation"] == "corner_of_container" and m.get("target_kind") == kind
        and m.get("target") == target)


def unders(spec: dict, kind: str, target: str) -> str:
    ms = [m for m in spec["motifs"] if m["relation"] in ("behind_element", "edge_of_element")
          and m.get("target_kind") == kind and m.get("target") == target]
    if not ms:
        return ""
    return "".join(
        f'<div data-layer="z5" class="under" data-relation="{m["relation"]}" data-target="{escape(target)}" aria-hidden="true">'
        f'<div class="m" style="left:{m["left_pct"]}%;top:{m["top_pct"]}%;width:{m["width_pct"]}%;height:{m["height_pct"]}%;'
        f'transform:rotate({m["rotation_deg"]}deg);opacity:{m["opacity"]}">{m["svg"]}</div></div>' for m in ms)


def slot(inner: str, place: str, spec: dict, kind: str, target: str, cls: str = "") -> str:
    """A grid cell holding one host (panel, image, card) with its under-layer (z5, behind it) and pins (z20)."""
    return f'<div class="slot {cls}" style="{place}">{unders(spec, kind, target)}{inner}</div>'


# --------------------------------------------------------------------------- items + panels
def item_html(it: dict, in_row: bool = False) -> str:
    k = it["kind"]
    cls = f'it k-{k} lv-{it["level"]}'
    style = f'color:{v(it["text_role"])};text-align:{it["align"]};'
    if k in SIZE:
        style += f"font-size:{SIZE[k]};"
    if k not in ("logo", "nav_link", "cta") and it.get("width_pct", 100) < 99:
        style += f'{"flex:0 1 " if in_row else "max-width:"}{it["width_pct"]}%;'
    t = escape(it.get("text") or "")
    a = f'data-item="{escape(it["item_id"])}"'
    if k == "logo":
        return f'<a href="#top" {a} class="{cls}" style="{style}">{t}</a>'
    if k == "nav_link":
        return f'<a href="{escape(it["href"])}" {a} class="{cls}" style="{style}">{t}</a>'
    if k == "cta":
        return (f'<a href="{escape(it["href"])}" {a} class="{cls} cta" style="{style}background:{v(it["surface_role"])};">'
                f'{t}</a>')
    if k == "h1":
        return f'<h1 {a} class="{cls}" style="{style}">{t}</h1>'
    if k == "intro_heading":
        return f'<h2 {a} class="{cls}" style="{style}">{t}</h2>'
    if k in ("eyebrow", "subheading", "intro_body"):
        return f'<p {a} class="{cls}" style="{style}">{t}</p>'
    return ""


def panel_rows(items: list[dict], align: str) -> str:
    rows: dict[int, list] = {}
    for it in items:
        rows.setdefault(it["row"], []).append(it)
    out = []
    for r in sorted(rows):
        xs = sorted(rows[r], key=lambda x: x["col_start"])
        if len(xs) == 1:
            out.append(item_html(xs[0]))
        else:
            out.append(f'<div class="row row-{align}">{"".join(item_html(x, True) for x in xs)}</div>')
    return "".join(out)


def panel(spec: dict, gp: dict, items: list[dict], extra_cls: str = "", tag: str = "div") -> str:
    plated = gp["backing"] != "none"
    style = plate_style(gp["backing"], gp["surface_role"])
    return (f'<{tag} class="panel host al-{gp["align"]}{" plated" if plated else ""}{extra_cls}" '
            f'data-group="{gp["group_id"]}"{" data-opaque=\"1\"" if plated else ""} style="{style}">'
            f'{panel_rows(items, gp["align"])}{pins(spec, "group", gp["group_id"])}</{tag}>')


def col(gp_or_it: dict) -> str:
    return f'grid-column:{gp_or_it["col_start"]} / span {gp_or_it["col_span"]};'


def card_html(spec: dict, it: dict) -> str:
    c = it.get("card") or {}
    gp = next(g for g in spec["groups"] if g["group_id"] == "cards")
    style = plate_style(gp["backing"], gp["surface_role"]) + f'color:{v(it["text_role"])};'
    tag = (f'<span class="tag lv-accent" style="background:{v(c.get("tag_fill_role"))};color:{v(c.get("tag_text_role"))}">'
           f'{escape(c.get("tag", ""))}</span>') if c.get("tag") else ""
    return (f'<article data-item="{escape(it["item_id"])}" class="it k-card host{" plated" if gp["backing"] != "none" else ""}"'
            f'{" data-opaque=\"1\"" if gp["backing"] != "none" else ""} style="{style}">{tag}'
            f'<h3 class="lv-display">{escape(c.get("heading", ""))}</h3><p class="lv-body">{escape(c.get("body", ""))}</p>'
            f'{pins(spec, "item", it["item_id"])}</article>')


def media_html(spec: dict, it: dict, cls: str = "") -> str:
    return (f'<figure data-item="{escape(it["item_id"])}" data-group="hero_media" data-opaque="1" class="media host {cls}">'
            f'<img src="{escape(it["src"])}" alt="{escape(it.get("alt") or "")}" loading="eager">'
            f'{pins(spec, "item", it["item_id"])}</figure>')


# --------------------------------------------------------------------------- bands
def band_inner(spec: dict, band: dict) -> tuple[str, str]:
    """-> (html inside the band, an html block placed before the grid, e.g. a full-bleed image)."""
    bid = band["band_id"]
    groups = {g["group_id"]: g for g in spec["groups"] if g["band_id"] == bid}
    items = [it for it in spec["items"] if it["band_id"] == bid]
    by_group = {gid: [it for it in items if it["group"] == gid] for gid in groups}
    L = spec["layout"]
    if bid == "nav":
        gp = groups.get("nav")
        if not gp:
            return "", ""
        its = sorted(by_group["nav"], key=lambda x: (NAV_RANK.get(x["kind"], 1), x["col_start"]))
        style = L.get("nav", "bar_left_logo")
        if style == "centered_logo" and its and its[0]["kind"] == "logo":
            body = item_html(its[0]) + (f'<div class="row row-center">{"".join(item_html(x, True) for x in its[1:])}</div>'
                                        if its[1:] else "")
            gp = {**gp, "align": "center"}
        else:
            body = "".join(item_html(x, True) for x in its)
        plated = gp["backing"] != "none"
        return (f'<div class="wrap"><nav class="panel nav nav-{style}{" plated" if plated else ""} host" data-group="nav"'
                f'{" data-opaque=\"1\"" if plated else ""} style="{plate_style(gp["backing"], gp["surface_role"])}">'
                f'{body}{pins(spec, "group", "nav")}</nav></div>'), ""
    if bid == "cards":
        gp = groups.get("cards")
        if not gp:
            return "", ""
        cards = sorted(by_group["cards"], key=lambda x: (x["row"], x["col_start"]))
        align = "start" if L.get("cards_align") == "start" or L.get("cards") == "staggered" else "stretch"
        cells = "".join(slot(card_html(spec, it), col(it), spec, "item", it["item_id"],
                             "stagger" if L.get("cards") == "staggered" and i % 2 else "")
                        for i, it in enumerate(cards))
        return f'<div class="grid cards cards-{align}" data-group="cards">{cells}</div>', ""
    if bid == "hero":
        arr = L.get("hero_arrangement", "stack")
        tg, mg = groups.get("hero_text"), groups.get("hero_media")
        media = next((it for it in by_group.get("hero_media", []) if it.get("src")), None)
        text = slot(panel(spec, tg, by_group["hero_text"]), col(tg), spec, "group", "hero_text", "s-text") if tg else ""
        if media and arr == "bleed":
            return f'<div class="grid hero-grid arr-text_only">{text}</div>', \
                f'<div class="bleed">{unders(spec, "item", media["item_id"])}{media_html(spec, media)}</div>'
        img = slot(media_html(spec, media), col(media), spec, "item", media["item_id"], "s-media") if media and mg else ""
        parts = [img, text] if arr == "stack_media_first" else [text, img]
        return f'<div class="grid hero-grid arr-{arr}">{"".join(parts)}</div>', ""
    out = []
    for gid, gp in groups.items():
        out.append(slot(panel(spec, gp, by_group[gid]), col(gp), spec, "group", gid))
    return f'<div class="grid">{"".join(out)}</div>', ""


def band_decor(spec: dict, bid: str) -> str:
    ms = [m for m in spec["motifs"] if m["relation"] == "in_free_area" and m["band_id"] == bid]
    if not ms:
        return ""
    return '<div data-layer="z5" class="decor" aria-hidden="true">' + "".join(
        f'<div class="m" data-relation="in_free_area" style="left:{m["left_pct"]}%;top:{m["top_pct"]}%;'
        f'width:{m["width_pct"]}%;height:{m["height_pct"]}%;transform:rotate({m["rotation_deg"]}deg);'
        f'opacity:{m["opacity"]}">{m["svg"]}</div>' for m in ms) + "</div>"


BASE = """*{box-sizing:border-box}html,body{margin:0}
.lp{position:relative;max-width:1440px;margin:0 auto;overflow-x:hidden;isolation:isolate}
[data-layer="z0"]{position:fixed;inset:0;z-index:0;overflow:hidden}
.bg-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.bg-tint{position:absolute;inset:0;background:color-mix(in srgb,var(--bg-primary) 55%,transparent)}
.band{position:relative;z-index:10;display:flex;flex-direction:column}
.decor{position:absolute;inset:0;z-index:5;overflow:visible}.m{position:absolute}
.wrap,.grid{position:relative;z-index:10;width:100%;max-width:var(--cw);margin:0 auto;padding-inline:24px}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:var(--gut);row-gap:32px;flex:1}
.slot{position:relative;display:flex;flex-direction:column;min-width:0}
.slot>.host{position:relative;z-index:10;flex:1}
.under{position:absolute;inset:0;z-index:5;overflow:visible}
.panel{display:flex;flex-direction:column;gap:18px;min-width:0}
.panel.plated{padding:32px 36px;border-radius:22px}
.al-start{align-items:flex-start}.al-center{align-items:center}.al-end{align-items:flex-end}
.row{display:flex;flex-wrap:wrap;gap:14px 18px;align-items:center;width:100%}
.row-start{justify-content:flex-start}.row-center{justify-content:center}.row-end{justify-content:flex-end}
.it{margin:0;min-width:0;overflow-wrap:break-word}
.nav{flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px 28px}
.nav-bar_left_logo .k-logo,.nav-minimal_split .k-logo{margin-right:auto}
.nav-centered_logo{flex-direction:column;gap:12px}
.nav-pill_floating{width:fit-content;max-width:100%;margin-inline:auto;border-radius:999px;padding:12px 28px}
.nav-pill_floating .k-logo{margin-right:16px}
.k-logo,.k-nav_link{text-decoration:none}.k-nav_link{white-space:nowrap}
.k-nav_link:hover{text-decoration:underline}
.cta{display:inline-flex;align-items:center;justify-content:center;padding:14px 28px;border-radius:999px;
text-decoration:none;font-weight:600;white-space:nowrap;flex:0 0 auto}
.cta:focus-visible,.k-nav_link:focus-visible,.k-logo:focus-visible{outline:3px solid var(--overlay-secondary);outline-offset:3px}
.media{margin:0;display:flex}.media img{display:block;width:100%;border-radius:24px;object-fit:cover}
.arr-side{align-items:center}.arr-side>.s-media{align-self:stretch}.arr-side .media img{height:100%;min-height:360px}
.arr-stack,.arr-stack_media_first,.arr-text_only,.arr-media_only{align-content:center}
.arr-stack .media img,.arr-stack_media_first .media img,.arr-media_only .media img{aspect-ratio:16/9}
.bleed{position:absolute;inset:0;z-index:0}.bleed .media{position:absolute;inset:0;z-index:10}
.bleed .media img{height:100%;border-radius:0}
.cards{row-gap:24px}.cards-stretch{align-items:stretch}.cards-start{align-items:start}.stagger{margin-top:48px}
.k-card{border-radius:22px;padding:28px;display:flex;flex-direction:column;gap:12px}
.k-card h3{margin:0;font-size:var(--fs-4)}.k-card p{margin:0}
.tag{align-self:flex-start;padding:4px 12px;border-radius:999px;font-size:.78rem}
.pin{position:absolute;z-index:20}.pin-tl{top:var(--o);left:var(--o)}.pin-tr{top:var(--o);right:var(--o)}
.pin-bl{bottom:var(--o);left:var(--o)}.pin-br{bottom:var(--o);right:var(--o)}
@media (max-width:1023px){.grid{grid-template-columns:1fr;padding-inline:20px;row-gap:24px}
.grid>*{grid-column:1 / -1!important}.wrap{padding-inline:20px}.band{min-height:0!important}
#nav .k-nav_link,#nav .k-cta{display:none}.panel.plated{padding:24px}.stagger{margin-top:0}
.arr-side .media img{min-height:240px;aspect-ratio:16/10}.cta{white-space:normal}}"""


def render(spec: dict) -> str:
    """-> a raw document (<style> + <body>) for validate_page.check."""
    css_vars = ";".join(f"{k}:{h}" for k, h in spec["css_vars"].items())
    fs = ";".join(f"{k}:{val}" for k, val in spec["type_scale"].items())
    cv = spec["canvas"]
    bg = spec["background"]
    rules, z0 = [], []
    for i, L in enumerate(bg["layers"]):
        rule, extra = layer_css(L, i, bg)
        if rule:
            rules.append(rule)
            z0.append(f'<div class="bg-l{i}">{extra}</div>')
    body_lv = spec["levels"]["body"]
    css = [f":root{{{css_vars};{fs};--cw:{cv['content_width_px']}px;--gut:{cv['gutter_px']}px}}", BASE,
           f"body{{background:var(--bg-primary);color:var(--text-body);font-family:{body_lv['stack']};"
           f"font-size:var(--fs-1);line-height:{body_lv.get('line_height', '1.6')}}}", level_css(spec)]
    small = []
    for b in spec["bands"]:
        css.append(f'#{b["band_id"]}{{padding:{b["padding_top_px"]}px 0 {b["padding_bottom_px"]}px;'
                   f'background:{v(b["surface_role"])};margin-bottom:{b["gap_after_px"]}px'
                   + (f';min-height:{b["min_height_px"]}px' if b.get("min_height_px") else "") + "}")
        small.append(f'#{b["band_id"]}{{padding:{max(16, round(b["padding_top_px"] * 0.45))}px 0 '
                     f'{max(16, round(b["padding_bottom_px"] * 0.45))}px;margin-bottom:{round(b["gap_after_px"] * 0.4)}px}}')
    css.append("@media (max-width:1023px){" + "".join(small) + "}")       # the same rhythm, tightened
    css += rules
    parts = ['<div class="lp" id="top">', f'<div data-layer="z0" aria-hidden="true">{"".join(z0)}</div>']
    main_open = False
    for b in spec["bands"]:
        bid = b["band_id"]
        if bid != "nav" and not main_open:
            parts.append("<main>")
            main_open = True
        inner, before = band_inner(spec, b)
        tag = "header" if bid == "nav" else "section"
        parts.append(f'<{tag} class="band" id="{bid}">{before}{band_decor(spec, bid)}{inner}</{tag}>')
    parts.append("</main>" if main_open else "")
    if bg.get("grain"):
        parts.append('<div data-layer="z50" aria-hidden="true"></div>')
    parts.append("</div>")
    return f"<html><head><style>{''.join(css)}</style></head><body>{''.join(parts)}</body></html>"
