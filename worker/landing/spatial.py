"""spatial.py - geometry by intent, boxes by code: groups, the scene map, free areas, space adjustments, overlay laws.

Agents place things on a 12-column grid inside bands (columns 0 and 13 are the outer page margins). Nothing here
decides style; it keeps every decision legible and every element where its owner put it:

  content   items belong to groups (nav, hero_text, hero_media, intro, cards); a group reads as one panel with one
            surface, and every item's text colour is checked against that surface (WCAG). Elements are optional:
            only one h1 is required.
  scene     an estimate of where every element lands at 1440 px (content-driven heights), the list A4 sees, and the
            free areas: empty columns beside or around elements, outer wings, the gaps between bands, A2's planned
            negative space (only where it is still empty).
  adjust    A4's bounded edits to undecided space: pad a band, open a gap after a band, align a group, reserve an area.
  laws      a motif never covers text or an image except an explicit behind/edge relation to its target, z20 accents
            sit on container corners and differ from them in geometry and contrast, linear patterns never overlap,
            at most 6 motifs (3 on z20).
The browser QA (qa.py) measures the real page; this module is the plan it is measured against. Every change is
logged as {token, from, to, why}.
"""
from __future__ import annotations

import math

import guardrails as g

from . import schemas as sc

W = 1440
PAD = {"tight": 32, "regular": 64, "loose": 96}
H_RANGE = {"nav": (56, 120), "hero": (360, 860), "intro": (120, 560), "cards": (200, 860)}
HERO_MIN_CAP = 720
MEDIA_MIN = 360
GAP = 16
TEXT_KINDS = {"logo", "nav_link", "cta", "eyebrow", "h1", "subheading", "intro_heading", "intro_body", "card"}
CAPS = {"h1": 90, "subheading": 200, "nav_link": 22, "cta": 30, "eyebrow": 48, "logo": 32, "intro_heading": 90,
        "intro_body": 320, "centerpiece": 120, "card": 0}
LEVEL_OF = {"logo": "wordmark", "nav_link": "subheading", "cta": "subheading", "eyebrow": "accent", "h1": "display",
            "subheading": "body", "centerpiece": "body", "intro_heading": "display", "intro_body": "body",
            "card": "display"}
GROUP_OF = {"logo": "nav", "nav_link": "nav", "eyebrow": "hero_text", "h1": "hero_text", "subheading": "hero_text",
            "centerpiece": "hero_media", "intro_heading": "intro", "intro_body": "intro", "card": "cards"}
NEED = {"wordmark": 3.0, "display": 3.0}               # large text; everything else 4.5
GEOM = {"badge": "round", "star": "round", "sunburst": "round", "blob": "round", "dots": "round", "arch": "round",
        "ribbon": "linear", "tape": "linear", "stripe_band": "linear", "squiggle": "linear", "frame": "rect",
        "perspective_grid": "rect"}
WIDE_ONLY = {"perspective_grid": "stripe_band", "frame": "dots"}
CARD_PAD = 28
WORDMARK_TOKEN = {"s": "--fs-2", "m": "--fs-3", "l": "--fs-4", "xl": "--fs-5"}
KIND_TOKEN = {"nav_link": "--fs-1", "cta": "--fs-1", "eyebrow": "--fs-1", "h1": "--fs-8", "subheading": "--fs-2",
              "intro_heading": "--fs-6", "intro_body": "--fs-2"}


def clamp(v, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def hit(a, b, pad: float = 0) -> bool:
    return a[0] + pad < b[0] + b[2] and b[0] + pad < a[0] + a[2] and a[1] + pad < b[1] + b[3] and b[1] + pad < a[1] + a[3]


def inset(r, d):
    return (r[0] + d, r[1] + d, max(0, r[2] - 2 * d), max(0, r[3] - 2 * d))


def rotated(r, deg):
    """Axis-aligned bounds of box r rotated about its centre (what the browser's getBoundingClientRect reports)."""
    a = math.radians(float(deg or 0))
    c, s = abs(math.cos(a)), abs(math.sin(a))
    w, h = r[2] * c + r[3] * s, r[2] * s + r[3] * c
    return (r[0] + r[2] / 2 - w / 2, r[1] + r[3] / 2 - h / 2, w, h)


def px(v, default=16.0) -> float:
    try:
        return float(str(v).replace("px", ""))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- wireframe
def normalize_wireframe(wg: dict, fallback: dict, bg_image_used: bool = False) -> tuple[dict, list]:
    """Bands are A2's choice (hero is the one band every page has). Heights become minimum hints, safe boxes are
    kept inside the grid, A1's use of the background image is guaranteed an image layer."""
    log = []
    w = {**wg}
    have = {b["band_id"]: b for b in w.get("bands", []) if b.get("band_id") in sc.BANDS}
    fb = {b["band_id"]: b for b in fallback["bands"]}
    if "hero" not in have:
        have["hero"] = fb["hero"]
        log.append({"token": "band:hero", "from": None, "to": "default", "why": "every page needs its main band"})
    bands = []
    for bid in sc.BANDS:                                # page order; bands A2 left out stay out
        if bid not in have:
            continue
        b = dict(have[bid])
        lo, hi = H_RANGE[bid]
        hpx = int(clamp(b.get("height_px"), lo, hi))
        if hpx != b.get("height_px"):
            log.append({"token": f"band:{bid}.height_px", "from": b.get("height_px"), "to": hpx, "why": f"kept in {lo}-{hi}"})
        sb = b.get("safe_box") or {}
        cs = int(clamp(sb.get("col_start"), 1, 12))
        bands.append({**b, "height_px": hpx, "rows": int(clamp(b.get("rows"), 1, 8)),
                      "padding": b.get("padding") if b.get("padding") in PAD else "regular",
                      "surface_role": b.get("surface_role") if b.get("surface_role") in ["transparent"] + sc.PALETTE_ROLES
                      else "transparent",
                      "safe_box": {"col_start": cs, "col_span": int(clamp(sb.get("col_span"), 1, 13 - cs))},
                      "pad_extra": {"top": 0, "bottom": 0}, "gap_after": 0})
    w["bands"] = bands
    seen, regions = set(), []
    for r in w.get("negative_space", []):
        if r.get("band_id") not in have or not r.get("region_id") or r["region_id"] in seen:
            continue
        seen.add(r["region_id"])
        cs = int(clamp(r.get("col_start"), 0, 13))
        y0, y1 = sorted((clamp(r.get("y0"), 0, 1), clamp(r.get("y1"), 0, 1)))
        regions.append({**r, "col_start": cs, "col_span": int(clamp(r.get("col_span"), 1, 14 - cs)),
                        "y0": y0, "y1": max(y1, y0 + 0.05)})
    w["negative_space"] = regions
    layers = [dict(L) for L in w.get("background_layers", []) if L.get("kind") in sc.BG_LAYER_KINDS][:6]
    if not any(L["kind"] == "solid" for L in layers):
        layers.insert(0, {"kind": "solid", "roles": ["bg_primary"], "opacity": 1, "angle_deg": 0, "position": "full",
                          "blend": "normal", "scale": "medium"})
    if bg_image_used and not any(L["kind"] == "image" for L in layers):
        layers.insert(1, {"kind": "image", "roles": ["bg_primary"], "opacity": 1, "angle_deg": 0, "position": "full",
                          "blend": "normal", "scale": "medium"})
        log.append({"token": "background.image", "from": None, "to": "layer",
                    "why": "A1 chose to use the background-image; the z-0 stack had no image layer for it"})
    if not bg_image_used and any(L["kind"] == "image" for L in layers):
        layers = [L for L in layers if L["kind"] != "image"]
        log.append({"token": "background.image", "from": "layer", "to": None,
                    "why": "A1 chose not to use the background-image (nuance_extract or treatment none)"})
    for L in layers:
        L["opacity"] = round(clamp(L.get("opacity"), 0, 1), 3)
        L["roles"] = [r for r in L.get("roles", []) if r in sc.PALETTE_ROLES] or ["bg_primary"]
    w["background_layers"] = layers
    return w, log


def busy_bands(wg: dict, has_bg_image: bool) -> set[str]:
    busy = set()
    for L in wg["background_layers"]:
        if (L["kind"] == "image" and has_bg_image) or (
                L["kind"] in ("stripes", "perspective_grid", "halftone", "dots", "mesh", "grid") and L["opacity"] >= 0.3):
            busy |= {"nav", "hero", "intro", "cards"} if L["kind"] == "image" or L["position"] in (
                "full", "center", "top", "left", "right") else {"hero"}
    return busy


# --------------------------------------------------------------------------- content
def band_surface(bands: dict, band_id: str) -> str:
    s = bands.get(band_id, {}).get("surface_role", "transparent")
    return "bg_primary" if s == "transparent" else s


def group_surface(group: dict, bands: dict) -> str:
    if group.get("backing", "none") != "none":
        return group["pair"].split("/")[1]
    return band_surface(bands, sc.GROUP_BAND[group["group_id"]])


def best_text(pairs: dict, surface: str, need: float, prefer: str) -> str:
    if pairs.get(f"{prefer}/{surface}", 0) >= need:
        return prefer
    ok = [(pairs.get(f"{t}/{surface}", 0), t) for t in sc.TEXT_ROLES]
    good = [x for x in ok if x[0] >= need]
    return max(good or ok)[1]


def hero_arrangement(items: list[dict], hero_style: str) -> str:
    """How the hero's text block and image relate, from A3's columns (+ A1's hero style for a full-bleed image)."""
    ht = [x for x in items if x["group"] == "hero_text"]
    hm = [x for x in items if x["group"] == "hero_media"]
    if not hm:
        return "text_only" if ht else "none"
    if not ht:
        return "media_only"
    t0 = min(x["col_start"] for x in ht)
    t1 = max(x["col_start"] + x["col_span"] - 1 for x in ht)
    m0, m1 = hm[0]["col_start"], hm[0]["col_start"] + hm[0]["col_span"] - 1
    if hero_style == "full_bleed" and m1 - m0 + 1 >= 10:
        return "bleed"
    if m1 < t0 or m0 > t1:
        return "side"
    return "stack_media_first" if hm[0]["row"] < min(x["row"] for x in ht) else "stack"


def normalize_content(cl: dict, wg: dict, pairs: dict, fallback: dict, *, has_centerpiece: bool,
                      has_bg_image: bool, card_ids: list[str], fb_wireframe: dict | None = None,
                      hero_style: str = "", nav_style: str = "") -> tuple[dict, list]:
    """Keep A3's choices (which elements exist is A3's call: only one h1 is required); repair what breaks a contract."""
    log = []
    bands = {b["band_id"]: b for b in wg["bands"]}
    fb_bands = {b["band_id"]: b for b in (fb_wireframe or {}).get("bands", [])}
    items, ids = [], set()
    for it in cl.get("items", []):
        if it.get("kind") not in sc.ITEM_KINDS:
            continue
        it = dict(it)
        grp = it.get("group")
        want = GROUP_OF.get(it["kind"]) or {"nav": "nav", "intro": "intro"}.get(it.get("band_id"), "hero_text")
        if it["kind"] == "cta":
            want = grp if grp in ("nav", "hero_text", "intro") else want
        if grp != want and not (it["kind"] == "cta" and grp in ("nav", "hero_text", "intro")):
            if grp is not None:
                log.append({"token": f"{it.get('item_id')}.group", "from": grp, "to": want,
                            "why": f"a {it['kind']} belongs to the {want} group"})
            grp = want
        it["group"] = grp
        it["band_id"] = sc.GROUP_BAND[grp]
        if it["band_id"] not in bands:
            src = fb_bands.get(it["band_id"])
            if not src:
                continue
            nb = {**src, "pad_extra": {"top": 0, "bottom": 0}, "gap_after": 0}
            bands[it["band_id"]] = nb
            wg["bands"] = [b for b in [bands.get(x) for x in sc.BANDS] if b]
            log.append({"token": f"band:{it['band_id']}", "from": None, "to": "default",
                        "why": f"A3 placed {it['kind']} in a band the wireframe didn't have"})
        if not it.get("item_id") or it["item_id"] in ids:
            it["item_id"] = f"{it['kind']}_{len(items) + 1}"
        ids.add(it["item_id"])
        sb = bands[it["band_id"]]["safe_box"]
        lo, hi = (1, 12) if it["kind"] in ("centerpiece", "card") or grp == "nav" else \
            (sb["col_start"], sb["col_start"] + sb["col_span"] - 1)
        cs = int(clamp(it.get("col_start"), lo, hi))
        span = int(clamp(it.get("col_span"), 1, hi - cs + 1))
        if (cs, span) != (it.get("col_start"), it.get("col_span")):
            log.append({"token": f"{it['item_id']}.cols", "from": [it.get("col_start"), it.get("col_span")],
                        "to": [cs, span], "why": f"kept inside the {it['band_id']} area for it (cols {lo}-{hi})"})
        it.update(col_start=cs, col_span=span, row=int(clamp(it.get("row"), 1, 12)),
                  row_span=int(clamp(it.get("row_span"), 1, 6)))
        if it.get("level") not in sc.LEVELS:
            it["level"] = LEVEL_OF[it["kind"]]
        if it.get("text_role") not in sc.TEXT_ROLES:
            it["text_role"] = "text_body"
        if it.get("align") not in sc.ALIGN:
            it["align"] = "left"
        cap = CAPS.get(it["kind"], 200)
        if cap and len(it.get("text") or "") > cap:
            it["text"] = it["text"][:cap].rsplit(" ", 1)[0]
        if it["kind"] == "card":
            if it.get("card_id") not in card_ids or any(x["kind"] == "card" and x["card_id"] == it["card_id"] for x in items):
                log.append({"token": it["item_id"], "from": it.get("card_id"), "to": None,
                            "why": "no strategic card with that id (A1 owns the cards)"})
                continue
            it["text"] = ""
        items.append(it)
    # the one structural requirement: exactly one h1
    h1s = [x for x in items if x["kind"] == "h1"]
    for x in h1s[1:]:
        x["kind"] = "subheading"
        log.append({"token": x["item_id"], "from": "h1", "to": "subheading", "why": "only one h1 per page"})
    if not h1s:
        fb_h1 = next((x for x in fallback["content_layer"]["items"] if x["kind"] == "h1"), None)
        if fb_h1:
            items.append(dict(fb_h1))
            log.append({"token": "h1", "from": None, "to": "default", "why": "a page needs one h1 (document structure)"})
    for x in [x for x in items if x["kind"] == "centerpiece"][(1 if has_centerpiece else 0):]:
        items.remove(x)
        log.append({"token": x["item_id"], "from": "centerpiece", "to": None,
                    "why": "no text-free central graphic" if not has_centerpiece else "one centerpiece per page"})
    for x in [x for x in items if x["kind"] == "nav_link"][5:]:
        items.remove(x)
    # groups: one panel per group, one surface, every text checked against it
    given = {}
    for gp in cl.get("groups", []):
        if gp.get("group_id") in sc.GROUPS and gp["group_id"] not in given:
            given[gp["group_id"]] = dict(gp)
    groups = []
    arrangement = hero_arrangement(items, hero_style)
    busy = busy_bands(wg, has_bg_image) | ({"hero"} if arrangement == "bleed" else set())
    for gid in sc.GROUPS:
        members = [x for x in items if x["group"] == gid]
        if not members:
            continue
        gp = given.get(gid) or {"group_id": gid, "backing": "solid" if gid == "cards" else "none", "align": "start",
                                "pair": None}
        if gid not in given:
            log.append({"token": f"group:{gid}", "from": None, "to": "default", "why": "items without a group entry"})
        if gp.get("backing") not in sc.BACKING:
            gp["backing"] = "none"
        if gp.get("align") not in sc.GALIGN:
            gp["align"] = "start"
        if gp.get("pair") not in pairs:
            s = band_surface(bands, sc.GROUP_BAND[gid]) if gp["backing"] == "none" else "bg_secondary"
            gp["pair"] = f"{best_text(pairs, s, 4.5, 'text_body')}/{s}"
        if gid == "hero_media":
            gp["backing"] = "none"
        elif gp["backing"] == "none" and gp["pair"].split("/")[1] != band_surface(bands, sc.GROUP_BAND[gid]):
            gp["backing"] = "solid"
            log.append({"token": f"group:{gid}.backing", "from": "none", "to": "solid",
                        "why": f"its pair assumes {gp['pair'].split('/')[1]}, but the band is "
                               f"{band_surface(bands, sc.GROUP_BAND[gid])}: the panel carries that surface"})
        elif gp["backing"] == "none" and (sc.GROUP_BAND[gid] in busy or (gid == "nav" and nav_style == "pill_floating")):
            gp["backing"] = "frosted"
            log.append({"token": f"group:{gid}.backing", "from": "none", "to": "frosted",
                        "why": "a floating pill nav is a panel" if gid == "nav" and sc.GROUP_BAND[gid] not in busy else
                        "this text block sits on a busy background: one plate for the whole block"})
        surf = group_surface(gp, bands)
        for x in members:
            if x["kind"] in ("centerpiece",):
                continue
            need = NEED.get(x["level"], 4.5)
            s = "cta_fill" if x["kind"] == "cta" else surf
            if pairs.get(f"{x['text_role']}/{s}", 0) < need:
                new = best_text(pairs, s, need, x["text_role"])
                log.append({"token": f"{x['item_id']}.text_role", "from": x["text_role"], "to": new,
                            "why": f"needs >= {need}:1 on {s}"})
                x["text_role"] = new
        groups.append(gp)
    return {**cl, "groups": groups, "items": items, "hero_arrangement": arrangement}, log


# --------------------------------------------------------------------------- scene + free areas
class Geo:
    """Column geometry of the 12-column grid at 1440 px."""

    def __init__(self, wg: dict):
        c = wg.get("canvas") or {}
        self.cw = c.get("content_width_px", 1200)
        self.gut = c.get("gutter_px", 24)
        self.margin = (W - self.cw) / 2
        self.col_w = (self.cw - 11 * self.gut) / 12

    def col_x(self, c: int) -> float:
        if c <= 0:
            return 0
        if c >= 13:
            return self.margin + self.cw
        return self.margin + (c - 1) * (self.col_w + self.gut)

    def span_w(self, c: int, s: int) -> float:
        end = c + s - 1
        if c <= 0 or end >= 13:
            right = W if end >= 13 else self.col_x(end) + self.col_w
            return max(8, right - self.col_x(c))
        return s * self.col_w + (s - 1) * self.gut


def text_h(text: str, size: float, width: float, lh: float = 1.35) -> float:
    chars_per_line = max(8, width / (size * 0.55))
    lines = max(1, math.ceil(len(text or "x") / chars_per_line))
    return lines * size * lh


def item_h(x: dict, scale: dict, typo: dict, width: float, card: dict | None = None) -> float:
    if x["kind"] == "card":
        c = card or {}
        inner = width - 2 * CARD_PAD
        return 2 * CARD_PAD + 22 + 12 + text_h(c.get("heading", ""), px(scale.get("--fs-4"), 31), inner, 1.15) + 12 + \
            text_h(c.get("body", ""), px(scale.get("--fs-1"), 16), inner, 1.6)
    if x["kind"] == "centerpiece":
        return MEDIA_MIN
    if x["kind"] == "logo":
        size = px(scale.get(WORDMARK_TOKEN.get((typo.get("wordmark_font") or {}).get("scale", "m"), "--fs-3")), 25)
    else:
        size = px(scale.get(KIND_TOKEN.get(x["kind"], "--fs-1")), 16)
        if x["kind"] == "h1":
            size = min(size, 76)
    h = text_h(x.get("text", ""), size, width, 1.1 if x["level"] in ("display", "wordmark") else 1.55)
    return h + (24 if x["kind"] == "cta" else 0)


def scene(wg: dict, content: dict, scale: dict, typo: dict, cards: dict) -> dict:
    """Estimated layout at 1440 px: bands, elements (items, group panels, the image), text and image boxes,
    and the free areas left in each band. Heights are content-driven, as compile_spec renders them."""
    geo = Geo(wg)
    items = content["items"]
    groups = {gp["group_id"]: gp for gp in content["groups"]}
    out_bands, elements, y = {}, [], 0.0
    for b in wg["bands"]:
        bid = b["band_id"]
        pt = (20 if bid == "nav" else PAD[b["padding"]]) + b.get("pad_extra", {}).get("top", 0)
        pb = (20 if bid == "nav" else PAD[b["padding"]]) + b.get("pad_extra", {}).get("bottom", 0)
        members = [x for x in items if x["band_id"] == bid]
        boxes = {}                                      # item_id -> box
        content_h = 0.0
        if bid == "nav":
            content_h = 56.0
            xcur = geo.margin
            for x in sorted(members, key=lambda x: ({"logo": 0, "nav_link": 1, "cta": 2}.get(x["kind"], 1), x["col_start"])):
                size = 25 if x["kind"] == "logo" else 16
                wdt = len(x.get("text", "")) * size * 0.55 + (48 if x["kind"] == "cta" else 0)
                boxes[x["item_id"]] = (xcur, y + pt + 8, wdt, 40)
                xcur += wdt + 28
        elif bid == "cards":
            cards_items = sorted(members, key=lambda x: (x["row"], x["col_start"]))
            rows, cur, used = [], [], 0
            for x in cards_items:
                if used + x["col_span"] > 12 and cur:
                    rows.append(cur)
                    cur, used = [], 0
                cur.append(x)
                used += x["col_span"]
            if cur:
                rows.append(cur)
            yy = 0.0
            for r in rows:
                hs = [item_h(x, scale, typo, geo.span_w(x["col_start"], x["col_span"]), cards.get(x.get("card_id"))) for x in r]
                rh = max(hs)
                col = 1
                for x in r:
                    boxes[x["item_id"]] = (geo.col_x(col), y + pt + yy, geo.span_w(col, x["col_span"]), rh)
                    col += x["col_span"]
                yy += rh + 24
            content_h = max(0.0, yy - 24)
        else:
            text_members = sorted([x for x in members if x["kind"] != "centerpiece"], key=lambda x: (x["row"], x["col_start"]))
            media = [x for x in members if x["kind"] == "centerpiece"]
            arr = content.get("hero_arrangement", "stack") if bid == "hero" else "text_only"
            if text_members:
                c0 = min(x["col_start"] for x in text_members)
                c1 = max(x["col_start"] + x["col_span"] - 1 for x in text_members)
            else:
                c0, c1 = 1, 0
            pw = geo.span_w(c0, c1 - c0 + 1) if text_members else 0
            gp = groups.get(text_members[0]["group"]) if text_members else None
            plate = 64 if gp and gp.get("backing", "none") != "none" else 0
            rows = {}
            for x in text_members:                       # items sharing a row sit side by side in the panel
                rows.setdefault(x["row"], []).append(x)
            row_h = {r: max(item_h(x, scale, typo, geo.span_w(x["col_start"], x["col_span"])) for x in xs)
                     for r, xs in rows.items()}
            th = sum(row_h.values()) + GAP * max(0, len(rows) - 1) + plate
            mw = geo.span_w(media[0]["col_start"], media[0]["col_span"]) if media else 0
            if arr == "side":
                content_h = max(th, MEDIA_MIN)
            elif arr in ("stack", "stack_media_first"):
                content_h = th + 32 + mw * 9 / 16
            elif arr == "media_only":
                content_h = mw * 9 / 16
            else:                                         # text only, or text over a full-bleed image
                content_h = th
            if bid == "hero":
                content_h = max(content_h, min(b["height_px"], HERO_MIN_CAP) - pt - pb)
            cy = y + pt
            ty = {"side": cy + (content_h - th) / 2, "stack": cy, "stack_media_first": cy + content_h - th,
                  "bleed": cy + (content_h - th) / 2, "text_only": cy + (content_h - th) / 2}.get(arr, cy)
            if text_members:
                yy = ty + plate / 2
                for r in sorted(rows):
                    for x in rows[r]:
                        boxes[x["item_id"]] = (geo.col_x(x["col_start"]) + (plate / 2 if x["col_start"] == c0 else 0), yy,
                                               min(geo.span_w(x["col_start"], x["col_span"]), pw - plate), row_h[r])
                    yy += row_h[r] + GAP
                gid = text_members[0]["group"]
                elements.append({"id": f"group:{gid}", "kind": "panel", "group": gid, "band": bid,
                                 "box": (geo.col_x(c0), ty, pw, th), "is_text": False, "is_image": False,
                                 "plate": bool(plate)})
            if media:
                m = media[0]
                if arr == "bleed":
                    mb = (0, y, W, pt + content_h + pb)
                elif arr == "side":
                    mb = (geo.col_x(m["col_start"]), cy, mw, content_h)
                elif arr == "stack_media_first":
                    mb = (geo.col_x(m["col_start"]), cy, mw, mw * 9 / 16)
                else:
                    mb = (geo.col_x(m["col_start"]), cy + (th + 32 if text_members else 0), mw, mw * 9 / 16)
                boxes[m["item_id"]] = mb
        bh = pt + content_h + pb
        out_bands[bid] = {"y": y, "h": bh, "pt": pt, "pb": pb, "content": (y + pt, content_h)}
        for x in members:
            if x["item_id"] in boxes:
                bx = boxes[x["item_id"]]
                tb = inset(bx, CARD_PAD) if x["kind"] == "card" else bx
                elements.append({"id": x["item_id"], "kind": x["kind"], "group": x["group"], "band": bid, "box": bx,
                                 "text_box": tb if x["kind"] in TEXT_KINDS else None,
                                 "is_text": x["kind"] in TEXT_KINDS, "is_image": x["kind"] == "centerpiece",
                                 "plate": x["kind"] == "card" and groups.get("cards", {}).get("backing", "solid") != "none"})
        y += bh + b.get("gap_after", 0)
    sc_ = {"geo": geo, "bands": out_bands, "elements": elements, "height": y}
    sc_["areas"] = free_areas(wg, sc_)
    return sc_


def free_areas(wg: dict, sc_: dict) -> list[dict]:
    geo, bands, els = sc_["geo"], sc_["bands"], sc_["elements"]
    blockers = [e["box"] for e in els if e["is_text"] or e["is_image"] or e["kind"] == "panel"]
    out = []

    def add(aid, band, kind, box, note):
        x, y, w, h = box
        if w < 48 or h < 40:
            return
        if any(hit(box, b, 2) for b in blockers):
            return
        out.append({"area_id": aid, "band_id": band, "kind": kind, "box_px": [round(x), round(y), round(w), round(h)],
                    "note": note})
    for bid, b in bands.items():
        cy, ch = b["content"]
        if ch <= 0:
            continue
        mine = [e for e in els if e["band"] == bid and (e["is_text"] or e["is_image"] or e["kind"] == "panel")]
        covered = set()
        for e in mine:
            x0, x1 = e["box"][0], e["box"][0] + e["box"][2]
            for c in range(1, 13):
                cx = geo.col_x(c)
                if cx + geo.col_w > x0 + 1 and cx < x1 - 1:
                    covered.add(c)
        run, n = [], 0
        for c in list(range(1, 13)) + [99]:
            if c <= 12 and c not in covered:
                run.append(c)
                continue
            if len(run) >= 2:
                n += 1
                add(f"{bid}.side{n}", bid, "side", (geo.col_x(run[0]), cy, geo.span_w(run[0], len(run)), ch),
                    f"empty columns {run[0]}-{run[-1]} beside the {bid} content")
            run = []
        for e in mine:                                 # space above / below an element that is shorter than the band
            x, ey, w, h = e["box"]
            if ey - cy > 60:
                add(f"{bid}.above_{e['id']}", bid, "above", (x, cy, w, ey - cy - 8), f"empty space above {e['id']}")
            if cy + ch - (ey + h) > 60:
                add(f"{bid}.below_{e['id']}", bid, "below", (x, ey + h + 8, w, cy + ch - (ey + h) - 8),
                    f"empty space below {e['id']}")
        if geo.margin >= 60:
            add(f"{bid}.wing_left", bid, "wing", (0, b["y"], geo.margin - 8, b["h"]), "outer page margin, left")
            add(f"{bid}.wing_right", bid, "wing", (geo.margin + geo.cw + 8, b["y"], geo.margin - 8, b["h"]),
                "outer page margin, right")
        if b["pt"] >= 48 and b["y"] > 0:
            add(f"{bid}.gap_above", bid, "gap", (geo.margin, b["y"], geo.cw, b["pt"] - 8), f"the gap before the {bid} band")
    for r in wg.get("negative_space", []):           # A2's plan, where it is still empty
        b = bands.get(r["band_id"])
        if not b:
            continue
        add(f"planned.{r['region_id']}", r["band_id"], "planned",
            (geo.col_x(r["col_start"]), b["y"] + r["y0"] * b["h"], geo.span_w(r["col_start"], r["col_span"]),
             (r["y1"] - r["y0"]) * b["h"]), f"A2's negative space {r['region_id']}")
    return out


MAX_AREAS = 14


def scene_table(sc_: dict) -> dict:
    """The scene + free areas as compact lines for A4 (its request must fit Qwen's free-tier minute window)."""
    def box(b):
        return ",".join(str(round(v)) for v in b)
    rows = []
    for e in sc_["elements"]:
        flags = "+".join(f for f, on in (("text", e["is_text"]), ("image", e["is_image"]), ("plate", e.get("plate"))) if on)
        rows.append(f"{e['id']} | {e['kind']} | {e['group']} | {e['band']} | {box(e['box'])} | {flags or '-'}")
    areas = sorted(sc_["areas"], key=lambda a: (a["kind"] != "planned", -a["box_px"][2] * a["box_px"][3]))[:MAX_AREAS]
    return {"scene": {"format": "id | kind | group | band | x,y,w,h px | flags", "elements": rows},
            "free_areas": {"format": "area_id | band | kind | x,y,w,h px",
                           "areas": [f"{a['area_id']} | {a['band_id']} | {a['kind']} | {box(a['box_px'])}" for a in areas]}}


def agent_areas(sc_: dict) -> list[dict]:
    """The free areas A4 is shown (and may name)."""
    keep = {line.split(" | ")[0] for line in scene_table(sc_)["free_areas"]["areas"]}
    return [a for a in sc_["areas"] if a["area_id"] in keep]


def scene_for_agent(sc_: dict) -> list[dict]:
    """What A4 sees: every element with its kind, group, band and estimated px box."""
    return [{"id": e["id"], "kind": e["kind"], "group": e["group"], "band": e["band"],
             "box_px": [round(v) for v in e["box"]], "is_text": e["is_text"], "is_image": e["is_image"],
             "has_plate": bool(e.get("plate"))} for e in sc_["elements"]]


# --------------------------------------------------------------------------- A4's adjustments to undecided space
def apply_adjustments(adj: list[dict], wg: dict, content: dict, areas: list[dict]) -> tuple[list[str], list]:
    """pad_band / band_gap / align_group / reserve_area, bounded; -> (reserved area ids, log)."""
    log, reserved = [], []
    bands = {b["band_id"]: b for b in wg["bands"]}
    groups = {gp["group_id"]: gp for gp in content["groups"]}
    area_ids = {a["area_id"] for a in areas}
    for a in (adj or [])[:6]:
        op = a.get("op")
        if op == "pad_band" and a.get("band_id") in bands and a.get("side") in ("top", "bottom"):
            v = int(clamp(a.get("px"), 0, 120))
            bands[a["band_id"]]["pad_extra"][a["side"]] = v
            log.append({"token": f"adjust:{a['band_id']}.pad_{a['side']}", "from": 0, "to": v, "why": "A4: room for decoration"})
        elif op == "band_gap" and a.get("band_id") in bands:
            v = int(clamp(a.get("px"), 0, 160))
            bands[a["band_id"]]["gap_after"] = v
            log.append({"token": f"adjust:{a['band_id']}.gap_after", "from": 0, "to": v, "why": "A4: breathing room"})
        elif op == "align_group" and a.get("group_id") in groups and a.get("align") in sc.GALIGN:
            old = groups[a["group_id"]]["align"]
            groups[a["group_id"]]["align"] = a["align"]
            log.append({"token": f"adjust:{a['group_id']}.align", "from": old, "to": a["align"], "why": "A4: integration"})
        elif op == "reserve_area" and a.get("area_id") in area_ids:
            reserved.append(a["area_id"])
            log.append({"token": f"adjust:reserve {a['area_id']}", "from": None, "to": "kept empty", "why": "A4"})
        else:
            log.append({"token": f"adjust:{op}", "from": a, "to": None, "why": "not a valid edit of undecided space"})
    return reserved, log


# --------------------------------------------------------------------------- overlay laws
def motif_box(m: dict, sc_: dict, areas: dict, els: dict):
    rel = m["relation"]
    if rel == "in_free_area":
        r = areas[m["area_id"]]["box_px"]
        x, y = clamp(m.get("x"), 0, 0.9), clamp(m.get("y"), 0, 0.9)
        w, h = clamp(m.get("w") or 1, 0.1, 1 - x), clamp(m.get("h") or 1, 0.1, 1 - y)
        return (r[0] + x * r[2], r[1] + y * r[3], w * r[2], h * r[3])
    t = els[m["target"]]["box"]
    if rel == "behind_element":                       # offset (x, y) and scale (w, h) relative to the target
        dx, dy = clamp(m.get("x"), -0.3, 0.3), clamp(m.get("y"), -0.3, 0.3)
        sw, sh = clamp(m.get("w") or 1, 0.6, 1.3), clamp(m.get("h") or 1, 0.6, 1.3)
        w, h = t[2] * sw, t[3] * sh
        return (t[0] + (t[2] - w) / 2 + dx * t[2], t[1] + (t[3] - h) / 2 + dy * t[3], w, h)
    if rel == "edge_of_element":
        th = clamp(m.get("size_px") or 24, 8, 80)
        ln = clamp(m.get("w") or 0.6, 0.2, 1.0)
        off = clamp(m.get("x"), 0, 1 - ln)
        e = m.get("edge") if m.get("edge") in ("top", "bottom", "left", "right") else "top"
        if e in ("top", "bottom"):
            y = t[1] - th - 6 if e == "top" else t[1] + t[3] + 6
            return (t[0] + off * t[2], y, ln * t[2], th)
        x = t[0] - th - 6 if e == "left" else t[0] + t[2] + 6
        return (x, t[1] + off * t[3], th, ln * t[3])
    s = clamp(m.get("size_px") or 96, 40, 140)        # corner_of_container
    out = s * float(m.get("_out", 0.2))
    c = m.get("corner") if m.get("corner") in ("tl", "tr", "bl", "br") else "tr"
    cx = t[0] + (t[2] if c in ("tr", "br") else 0) + (out if c in ("tr", "br") else -out)
    cy = t[1] + (t[3] if c in ("bl", "br") else 0) + (out if c in ("bl", "br") else -out)
    return (cx - s / 2, cy - s / 2, s, s)


def enforce_overlays(ol: dict, sc_: dict, palette: dict, content: dict, wg: dict,
                     reserved: list[str] | None = None) -> tuple[dict, list, dict]:
    """-> (overlay with kept motifs, log, placements {motif_id: {relation, box, target, band}})."""
    log = []
    areas = {a["area_id"]: a for a in sc_["areas"] if a["area_id"] not in (reserved or [])}
    els = {e["id"]: e for e in sc_["elements"]}
    bands = {b["band_id"]: b for b in wg["bands"]}
    groups = {gp["group_id"]: gp for gp in content["groups"]}
    texts = [(e["id"], e["text_box"] or e["box"], e.get("group")) for e in sc_["elements"]
             if e["is_text"] and e["kind"] != "panel"]
    images = [(e["id"], e["box"]) for e in sc_["elements"] if e["is_image"]]
    kept, boxes = [], {}
    for m in (ol.get("motifs") or [])[:8]:
        m = {**m}
        mid = m.get("motif_id") or f"m{len(kept) + 1}"
        if mid in boxes:
            mid = f"{mid}_{len(kept)}"
        m["motif_id"] = mid
        rel = m.get("relation")
        if m.get("primitive") not in sc.PRIMITIVES or rel not in sc.RELATIONS:
            log.append({"token": mid, "from": m.get("primitive"), "to": None, "why": "unknown primitive or relation"})
            continue
        if rel == "in_free_area" and m.get("area_id") not in areas:
            log.append({"token": mid, "from": m.get("area_id"), "to": None, "why": "not a free (or unreserved) area"})
            continue
        if rel != "in_free_area" and m.get("target") not in els:
            log.append({"token": mid, "from": m.get("target"), "to": None, "why": "relation needs a target element"})
            continue
        m["layer"] = "z20" if rel == "corner_of_container" else "z5"
        tgt = els.get(m.get("target"))
        if rel == "corner_of_container":
            if tgt["kind"] not in ("card", "centerpiece") and not (tgt["kind"] == "panel" and tgt.get("plate")):
                log.append({"token": mid, "from": m["target"], "to": None,
                            "why": "a corner accent needs a container (card, image or a plated panel)"})
                continue
            cls = GEOM[m["primitive"]]
            if cls == "rect":
                log.append({"token": mid, "from": m["primitive"], "to": None, "why": "a rectangle on a rectangle's corner"})
                continue
            if cls == "linear" and abs(clamp(m.get("rotation_deg"), -180, 180)) < 8:
                log.append({"token": f"{mid}.rotation", "from": m.get("rotation_deg"), "to": -12,
                            "why": "a linear corner accent is rotated to differ from the container's edges"})
                m["rotation_deg"] = -12
            if tgt["kind"] == "card":
                surf = group_surface(groups["cards"], bands) if "cards" in groups else "bg_primary"
            elif tgt["kind"] == "panel":
                surf = group_surface(groups[tgt["group"]], bands)
            else:
                surf = "bg_primary"
            fill = m.get("fill_role") if m.get("fill_role") in palette else None
            if not fill or g.contrast(palette[fill], palette[surf]) < 3.0:
                best = max(sc.PALETTE_ROLES, key=lambda r: g.contrast(palette[r], palette[surf]))
                if (m.get("stroke_role") not in palette or g.contrast(palette[m["stroke_role"]], palette[surf]) < 3.0
                        or float(m.get("stroke_width") or 0) < 3):
                    log.append({"token": f"{mid}.stroke", "from": m.get("stroke_role"), "to": best,
                                "why": f"an accent needs >= 3:1 against {surf}: die-cut outline added"})
                    m["stroke_role"], m["stroke_width"] = best, max(4.0, float(m.get("stroke_width") or 0))
        for k, lo, hi in (("opacity", 0.15, 1), ("stroke_width", 0, 16), ("rotation_deg", -180, 180)):
            m[k] = round(clamp(m.get(k), lo, hi), 2)
        m["count"] = int(clamp(m.get("count"), 2, 24))
        box = motif_box(m, sc_, areas, els)
        if m["primitive"] in WIDE_ONLY and box[2] < 0.8 * box[3]:
            new = WIDE_ONLY[m["primitive"]]
            log.append({"token": f"{mid}.primitive", "from": m["primitive"], "to": new,
                        "why": f"a {m['primitive']} needs a wide box; this one is {round(box[2])}x{round(box[3])}px"})
            m["primitive"] = new

        def conflicts(bx):
            rb = rotated(bx, m["rotation_deg"])
            own = m.get("target")
            own_group = (tgt or {}).get("group") if (tgt or {}).get("kind") == "panel" else None
            bad = []
            for tid, tb, grp in texts:
                if rel == "behind_element" and (tid == own or (own_group and grp == own_group)) and (tgt or {}).get("plate"):
                    continue                            # behind a plated block: under the plate, not under its text
                if rel == "corner_of_container" and tid == own:
                    if hit(rb, tb):
                        bad.append(tid)
                    continue
                if hit(rb, tb):
                    bad.append(tid)
            for iid, ib in images:
                if iid == own and rel in ("behind_element", "edge_of_element", "corner_of_container"):
                    continue
                inter = max(0, min(rb[0] + rb[2], ib[0] + ib[2]) - max(rb[0], ib[0])) * \
                    max(0, min(rb[1] + rb[3], ib[1] + ib[3]) - max(rb[1], ib[1]))
                if inter > 0.05 * rb[2] * rb[3]:
                    bad.append(iid)
            return bad
        bad, tries = conflicts(box), 0
        while bad and tries < 2:                       # nudge: shrink, pull behind shapes in, push corners out
            tries += 1
            if rel == "in_free_area":
                m["w"], m["h"] = round((m.get("w") or 1) * 0.7, 3), round((m.get("h") or 1) * 0.7, 3)
            elif rel == "behind_element":
                m["x"], m["y"] = round(float(m.get("x") or 0) / 2, 3), round(float(m.get("y") or 0) / 2, 3)
                m["w"], m["h"] = min(1.1, float(m.get("w") or 1)), min(1.1, float(m.get("h") or 1))
            elif rel == "corner_of_container":
                m["_out"] = 0.5 if tries == 1 else 0.75
            else:
                m["w"] = round(float(m.get("w") or 0.6) * 0.6, 3)
            box = motif_box(m, sc_, areas, els)
            bad = conflicts(box)
        if bad:
            log.append({"token": mid, "from": m["primitive"], "to": None,
                        "why": f"would cover {', '.join(dict.fromkeys(bad))[:80]}"})
            continue
        rb = rotated(box, m["rotation_deg"])
        if GEOM[m["primitive"]] == "linear" and any(GEOM[k["primitive"]] == "linear" and hit(rb, boxes[k["motif_id"]])
                                                     for k in kept):
            log.append({"token": mid, "from": m["primitive"], "to": None, "why": "two linear patterns would overlap"})
            continue
        if m["layer"] == "z20" and sum(k["layer"] == "z20" for k in kept) >= 3:
            log.append({"token": mid, "from": m["primitive"], "to": None, "why": "at most 3 foreground accents"})
            continue
        if len(kept) >= 6:
            log.append({"token": mid, "from": m["primitive"], "to": None, "why": "at most 6 motifs"})
            continue
        boxes[mid] = [round(v, 1) for v in rb]
        kept.append(m)
    placements = {}
    for m in kept:
        box = motif_box(m, sc_, areas, els)
        band = areas[m["area_id"]]["band_id"] if m["relation"] == "in_free_area" else els[m["target"]]["band"]
        placements[m["motif_id"]] = {"relation": m["relation"], "box": [round(v, 1) for v in box],
                                     "target": m.get("target") or "", "band_id": band}
    return {**ol, "motifs": kept}, log, placements
