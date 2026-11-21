"""state.py - the blackboard: declared read/write sets, slices, single-writer merge, the merged landing spec.

The agents write one design document together, each adding its own section (descriptive JSON, modelled on a
designer's brief); code normalizes each section before the next agent reads it:

    a1 -> design_doc      code -> doc (hexes / fonts / ids checked), palette_final, pairs, type_system + the
                                  legacy keys the deterministic fallback page is built from
    a2 -> layout_plan     code -> plan (ids checked)
    a3 -> copy            code -> copy_final (one h1, kinds, every section's text / surface contrast checked)
    a4 -> decor           code -> decor_final (SVG / CSS sanitized, palette colours only)
    code -> landing_spec  a5 -> page_raw      code -> page (sanitized, fixed, checked, measured)
Agents never see each other's raw output, only code's normalized version, sliced to what they need (and trimmed to
fit Groq's free-tier minute window). A key written by one writer can't be written by another.
"""
from __future__ import annotations

import json
import re

import guardrails as g

from . import primitives, schemas as sc
from .handoff import font_info
from .spatial import PAD, WORDMARK_TOKEN

CONTRACT = {
    "a1": {"reads": ["meta", "facts", "enums", "font_pool", "images", "assets"], "writes": ["design_doc"]},
    "a2": {"reads": ["digest", "doc", "assets"], "writes": ["layout_plan"]},
    "a3": {"reads": ["digest", "meta", "doc", "plan", "assets"], "writes": ["copy"]},
    "a4": {"reads": ["digest", "doc", "plan"], "writes": ["decor"]},
    "a5": {"reads": ["landing_spec"], "writes": ["page_raw"]},
}
LEVEL_ROLE = {"wordmark": "wordmark_font", "display": "display_font", "subheading": "subheading_font",
              "accent": "accent_font", "body": "body_font"}


class WriteConflict(RuntimeError):
    pass


class State:
    def __init__(self, handoff: dict):
        self.d: dict = {}
        self.writer: dict[str, str] = {}
        for k in ("meta", "facts", "enums", "images", "assets", "brief"):
            self.put("handoff", k, handoff[k])
        self.put("handoff", "font_pool", handoff.get("font_pool") or {f: font_info(f) for f in handoff["enums"]["fonts"]})

    def put(self, who: str, key: str, value) -> None:
        if who.startswith("a") and who in CONTRACT and key not in CONTRACT[who]["writes"]:
            raise WriteConflict(f"{who} may not write {key!r}")
        if key in self.writer and self.writer[key] != who:
            raise WriteConflict(f"{key!r} belongs to {self.writer[key]}, not {who}")
        self.d[key], self.writer[key] = value, who

    def merge(self, who: str, out: dict) -> None:
        for k, v in out.items():
            self.put(who, k, v)

    def __getitem__(self, k):
        return self.d[k]

    def get(self, k, default=None):
        return self.d.get(k, default)


def compact(obj) -> str:
    """Minified JSON with nulls / empty strings / empty lists dropped and floats rounded."""
    def prune(x):
        if isinstance(x, dict):
            return {k: prune(v) for k, v in x.items() if v not in (None, "", [], {})}
        if isinstance(x, list):
            return [prune(v) for v in x if v not in (None, "", [], {})]
        if isinstance(x, float):
            return round(x, 3)
        return x
    return json.dumps(prune(obj), separators=(",", ":"), ensure_ascii=False)


def cut(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def trim(obj, cap: int):
    """Every string longer than cap -> cut at a word boundary (slices that must fit a token budget)."""
    if isinstance(obj, dict):
        return {k: trim(v, cap) for k, v in obj.items()}
    if isinstance(obj, list):
        return [trim(v, cap) for v in obj]
    return cut(obj, cap) if isinstance(obj, str) and len(obj) > cap else obj


def tone(hexv: str) -> str:
    """Coarse words for a colour, so text-only agents can reason about it without seeing it."""
    L = g.luminance(hexv)
    c = g.chroma(hexv)
    return ("dark" if L < 0.12 else "light" if L > 0.55 else "mid") + (" vivid" if c > 0.12 else " muted" if c < 0.04 else "")


def uses_bg_image(bs: dict, assets: list[dict]) -> bool:
    """A1's call: the background image is on the page when A1 gave it a treatment (in either alignment mode: an
    off-subject photo is rendered abstracted, see backdrop())."""
    return bs.get("treatment", "none") != "none" and any(a["role"] == "background" for a in assets)


def backdrop(st) -> dict | None:
    """The background asset as the page uses it: as-is, or (off-subject) a blurred 'soft' derivative."""
    bs = st["background_spec"]
    if not uses_bg_image(bs, st["assets"]):
        return None
    a = next(a for a in st["assets"] if a["role"] == "background")
    if bs.get("alignment_mode") == "nuance_extract":
        return {"path": a["path"].replace(".webp", "-soft.webp"), "role": "background", "alt": "", "from": a["path"],
                "blur": 22, "abstract": True}
    return {"path": a["path"], "role": "background", "alt": "", "abstract": False}


def centerpiece_asset(assets: list[dict]) -> dict | None:
    return next((a for a in assets if a["role"] == "central" and not a["text"] and "primary" in (a.get("note") or "")),
                None) or next((a for a in assets if a["role"] == "central" and not a["text"]), None)


# --------------------------------------------------------------------------- slices
def digest(st: State) -> dict:
    """What A2, A3 and A4 all need, sent first and byte-identical so Groq can cache it as a shared prefix."""
    d = st["doc"]
    rules = d["composition_and_overlap_rules"]
    return {"design_system": d["design_system_name"], "aesthetic_direction": cut(d["aesthetic_direction"], 500),
            "query_context": cut(d["query_context"], 500),
            "palette": [f"{c['name']} {c['hex']} ({c['group'].replace('_color', '').replace('_', ' ')}): "
                        f"{cut(c['usage'], 70)}" for c in d["colors"]],
            "type": {lvl: f"{v['family']} {v['weight']} · {cut(v['classification'], 50)}"
                     for lvl, v in d["typography"].items() if lvl in sc.LEVELS},
            "composition": {"grid": cut(rules["alignment_grid"], 160),
                            "permitted_overlaps": [f"{o['a']} over {o['b']}: {cut(o['why'], 90)}"
                                                   for o in rules["permitted_overlaps"][:6]],
                            "prohibited_overlaps": [cut(x, 120) for x in rules["prohibited_overlaps"][:6]]}}


def image_roles(images: dict) -> dict:
    """role -> {image, label, position, present, cluster, baked_in_text, use}, in the order the images are sent.
    position = the n in the '[IMAGE n · role: role-image · LABEL]' header before that image; a missing reference
    is listed with present: false so the agent never looks for it."""
    out, n = {}, 0
    for role, label, image, use in sc.IMAGE_ROLES:
        im = images.get(label)
        if im:
            n += 1
            out[role] = {"image": image, "label": label, "position": n, "present": True, "cluster": im["cluster"],
                         "baked_in_text": im["text"], "use": use}
        else:
            out[role] = {"image": image, "label": label, "present": False, "use": use}
    return out


def present_images(images: dict) -> list[tuple[int, str, dict]]:
    """[(position, label, image)] in send order (the same numbering as image_roles)."""
    labels = [label for _, label, _, _ in sc.IMAGE_ROLES if label in images]
    return [(i + 1, label, images[label]) for i, label in enumerate(labels)]


def font_pool_slice(st: State) -> dict:
    f = st["facts"]["fonts"]
    out = {}
    for n, info in st["font_pool"].items():
        src = "lab heading face" if n == f["heading"] else "lab body face" if n == f["body"] else "buffer"
        out[n] = {"source": src, "category": info["category"], "weights": info["weights"], "italic": info["italic"],
                  "tags": info["tags"]}
    return out


def layer_of(doc: dict) -> dict[str, tuple[str, int]]:
    return {e["id"]: (k, z) for k, z in (("background", 0), ("midground", 5), ("foreground", 20))
            for e in doc["elements"][k]}


def slice_for(st: State, agent: str) -> dict:
    if agent == "a1":
        m, f, e = st["meta"], st["facts"], st["enums"]
        lab_names = {}
        for k, v in f["lab_tokens"].items():
            lab_names.setdefault(v.upper(), k)
        return {"user_query": m["full_query"], "vibe_query": m["vibe_query"], "brand": m.get("brand"),
                "audience": m.get("audience"), "family": m["family"], "niche": m.get("niche"),
                "niche_cues": m.get("niche_cues"), "avoid": m.get("avoid", [])[:6], "vibe": m["vibe"],
                "measured": {"alignment": f["alignment"],
                             "type_roles": {r: {k: v for k, v in d.items() if k in ("size_token", "text_transform",
                                                                                    "letter_spacing", "weight")}
                                            for r, d in f["type_roles"].items()},
                             "lab_font_pair": f["fonts"]},
                "allowed_hexes": {h: lab_names.get(h, "measured from palette-image") for h in e["hex"]},
                "font_pool": font_pool_slice(st),
                "page_assets": {"central_graphic_available": any(a["role"] == "central" and not a["text"]
                                                                 for a in st["assets"]),
                                "background_image_available": any(a["role"] == "background" for a in st["assets"])},
                "image_roles": image_roles(st["images"])}
    d = st.get("doc")
    if agent == "a2":
        bl = d["background_layer"]
        return {"content_sections": d["content_sections"], "centerpiece": d["centerpiece"],
                "background_layer": {"use_background_image": bl["use_background_image"], "treatment": bl["treatment"],
                                     "rendered_abstract": bl["abstract"], "base_surface": bl["base_surface"],
                                     "elements": bl["elements"]},
                "midground_decor": d["elements"]["midground"], "foreground_overlays": d["elements"]["foreground"],
                "layout_hints": d["layout_spec"], "strategic_cards": len(d["strategic_cards"]),
                "canvas": "desktop 1440 px wide, content about 1200 px, 12 columns; one column under 1024 px"}
    if agent == "a3":
        m, plan = st["meta"], st["plan"]
        lay = {s["section_id"]: s["layout"] for s in plan["sections"]}
        return {"brand": m.get("brand"), "audience": m.get("audience"), "niche": m.get("niche"),
                "sections": [{"section_id": s["section_id"], "role": s["role"], "what": s["what"],
                              "layout": lay.get(s["section_id"], "")} for s in d["content_sections"]],
                "cards": [{"card_id": c["card_id"], "heading": c["heading"]} for c in d["strategic_cards"]],
                "has_centerpiece": d["centerpiece"]["use"]}
    if agent == "a4":
        plan, lay = st["plan"], layer_of(d)
        placed = {L["element_id"]: L for L in plan["layers"]}
        els = []
        for k in ("background", "midground", "foreground"):
            for e in d["elements"][k]:
                L = placed.get(e["id"], {})
                els.append({"element_id": e["id"], "z": L.get("z", lay[e["id"]][1]), "what": e["what"],
                            "geometry": e.get("geometry", ""), "where": e["where"], "placement": L.get("placement", ""),
                            "anchor": L.get("anchor", "")})
        return {"decor_elements": els,
                "palette_vars": [f"var({c['var']}) = {c['name']} {c['hex']}" for c in d["colors"]],
                "limits": "one asset per element; svg up to ~2500 characters each, viewBox-based; colours only "
                          "from palette_vars (or their hexes); no text that repeats the page copy"}
    if agent == "a5":
        return st["landing_spec"]
    raise KeyError(agent)


# --------------------------------------------------------------------------- the fallback page's spec (compile_spec)
GENERIC = {"Sans Serif": "sans-serif", "Serif": "serif", "Display": "sans-serif", "Handwriting": "cursive",
           "Monospace": "monospace"}


def font_stack(family: str) -> str:
    cat = g.font_catalog().get(family, {}).get("category", "Sans Serif")
    return f'"{family}", {GENERIC.get(cat, "sans-serif")}'


def _rel(box, tb) -> dict:
    """box as percentages of the target box tb (so it follows the target in the real layout)."""
    return {"left_pct": round((box[0] - tb[0]) / max(1, tb[2]) * 100, 2),
            "top_pct": round((box[1] - tb[1]) / max(1, tb[3]) * 100, 2),
            "width_pct": round(box[2] / max(1, tb[2]) * 100, 2), "height_pct": round(box[3] / max(1, tb[3]) * 100, 2)}


def assemble_spec(st: State, *, wireframe=None, content=None, overlay=None, placements=None, scene=None) -> dict:
    pal = st["palette_final"]
    T = st["type_system"]
    wg = wireframe or st["wireframe"]
    cl = content or st["content"]
    ol = overlay if overlay is not None else st.get("overlay", {"motifs": []})
    plc = placements if placements is not None else st.get("placements", {})
    scn = scene or st.get("scene_final") or st["scene"]
    items = cl["items"]
    cards = {c["card_id"]: c for c in st["strategic_cards"]}
    assets = st["assets"]
    bs = st["background_spec"]
    centre = next((a for a in assets if a["role"] == "central" and not a["text"] and "primary" in (a.get("note") or "")),
                  None) or next((a for a in assets if a["role"] == "central" and not a["text"]), None)
    bg_img = backdrop(st)
    used_levels = {x["level"] for x in items} | ({"display", "accent", "body"} if any(x["kind"] == "card" for x in items)
                                                 else set())
    levels = {}
    for lvl, role in LEVEL_ROLE.items():
        v = T[role]
        levels[lvl] = {"family": v["family"], "stack": font_stack(v["family"]), "weight": v["weight"],
                       "letter_spacing": v.get("letter_spacing", "0em"), "case": v.get("case", "none"),
                       "italic": bool(v.get("italic")), "used": lvl in used_levels}
    levels["display"]["shadow_treatment"] = T["display_font"].get("shadow_treatment", "none")
    levels["body"]["line_height"] = T["body_font"].get("line_height", "1.6")
    levels["wordmark"]["scale"] = T["wordmark_font"].get("scale", "m")
    levels["wordmark"]["size_token"] = WORDMARK_TOKEN[levels["wordmark"]["scale"]]
    fams = list(dict.fromkeys(levels[lvl]["family"] for lvl in LEVEL_ROLE if levels[lvl]["used"] or lvl == "body"))
    italic_fams = {levels[lvl]["family"] for lvl in LEVEL_ROLE if levels[lvl]["italic"] and levels[lvl]["used"]}
    groups = {gp["group_id"]: gp for gp in cl["groups"]}
    bands_by = {b["band_id"]: b for b in wg["bands"]}
    spec_groups = []
    for gid, gp in groups.items():
        members = [x for x in items if x["group"] == gid]
        tr, sr = gp["pair"].split("/")
        band = bands_by[sc.GROUP_BAND[gid]]
        spec_groups.append({"group_id": gid, "band_id": sc.GROUP_BAND[gid], "backing": gp["backing"],
                            "surface_role": sr if gp["backing"] != "none" else
                            ("bg_primary" if band["surface_role"] == "transparent" else band["surface_role"]),
                            "align": gp["align"], "col_start": min(x["col_start"] for x in members),
                            "col_span": max(x["col_start"] + x["col_span"] for x in members) - min(x["col_start"] for x in members)})
    spec_items = []
    for x in sorted(items, key=lambda x: (sc.GROUPS.index(x["group"]), x["row"], x["col_start"])):
        gspec = next(g_ for g_ in spec_groups if g_["group_id"] == x["group"])
        it = {k: x[k] for k in ("item_id", "group", "band_id", "kind", "level", "text_role", "align", "text", "href",
                                "row", "col_start", "col_span")}
        it["surface_role"] = "cta_fill" if x["kind"] == "cta" else gspec["surface_role"]
        it["width_pct"] = round(min(100, x["col_span"] / max(1, gspec["col_span"]) * 100), 1)
        if x["kind"] == "card":
            c = cards.get(x.get("card_id")) or {}
            acc = c.get("accent_color_key", "overlay_primary")
            it["card"] = {"tag": c.get("tag", ""), "heading": c.get("heading", ""), "body": c.get("body", ""),
                          "tag_fill_role": acc,
                          "tag_text_role": max(sc.TEXT_ROLES, key=lambda r: g.contrast(pal[r], pal[acc]))}
            it["text"] = ""
        if x["kind"] == "centerpiece":
            if not centre:
                continue
            it.update(src=centre["path"], alt=(x.get("text") or f"{st['meta']['vibe']['name']} artwork")[:120])
        spec_items.append(it)
    els = {e["id"]: e for e in scn["elements"]}
    bands_est = scn["bands"]
    motifs = []
    for m in ol.get("motifs", []):
        p = plc.get(m["motif_id"])
        if not p:
            continue
        bx = p["box"]
        base = {"motif_id": m["motif_id"], "relation": m["relation"], "layer": m["layer"], "primitive": m["primitive"],
                "rotation_deg": m["rotation_deg"], "opacity": m["opacity"], "band_id": p["band_id"],
                "svg": primitives.render(m, bx[2], bx[3])}
        if m["relation"] == "in_free_area":
            b = bands_est[p["band_id"]]
            base.update(left_pct=round(bx[0] / 1440 * 100, 2), top_pct=round((bx[1] - b["y"]) / max(1, b["h"]) * 100, 2),
                        width_pct=round(bx[2] / 1440 * 100, 2), height_pct=round(bx[3] / max(1, b["h"]) * 100, 2))
        else:
            tgt = p["target"]
            kind = "group" if tgt.startswith("group:") else "item"
            base.update(target=tgt.split(":", 1)[1] if kind == "group" else tgt, target_kind=kind)
            if m["relation"] == "corner_of_container":
                c = m.get("corner") if m.get("corner") in ("tl", "tr", "bl", "br") else "tr"
                base.update(corner=c, size_px=round(bx[2]), offset_px=round(bx[2] * float(m.get("_out", 0.2))))
            else:
                base.update(edge=m.get("edge", "none"), **_rel(bx, els[tgt]["box"]))
        motifs.append(base)
    copy = [x["text"] for x in spec_items if x["kind"] not in ("centerpiece", "card") and x["text"]]
    copy += [v for x in spec_items if x.get("card") for v in (x["card"]["heading"], x["card"]["body"]) if v]
    bands = []
    for b in wg["bands"]:
        if not any(x["band_id"] == b["band_id"] for x in spec_items):
            continue
        pad = 20 if b["band_id"] == "nav" else PAD.get(b["padding"], 64)
        bands.append({"band_id": b["band_id"], "padding_top_px": pad + b.get("pad_extra", {}).get("top", 0),
                      "padding_bottom_px": pad + b.get("pad_extra", {}).get("bottom", 0),
                      "min_height_px": min(b["height_px"], 720) if b["band_id"] == "hero" else 0,
                      "surface_role": b["surface_role"], "gap_after_px": b.get("gap_after", 0)})
    used_assets = ([{"path": centre["path"], "role": "centerpiece", "alt": next(
        (i["alt"] for i in spec_items if i.get("src")), "artwork")}] if centre and any(i.get("src") for i in spec_items) else [])
    if bg_img:
        used_assets.append(bg_img)
    L = st["layout_spec"]
    return {
        "title": cl.get("brand") or st["meta"].get("brand") or "Landing page",
        "family": st["meta"]["family"], "query_context": st["query_context"],
        "palette": pal, "css_vars": {f"--{r.replace('_', '-')}": h for r, h in pal.items()},
        "fonts": fams, "fonts_css": [g.google_css(f, f in italic_fams) for f in fams],
        "levels": levels, "type_scale": {k: v for k, v in st["facts"]["type_scale"].items() if k.startswith("--fs-")},
        "canvas": {"max_width_px": 1440, "content_width_px": scn["geo"].cw, "gutter_px": scn["geo"].gut, "columns": 12},
        "layout": {"nav": L["nav"], "hero": L["hero"], "cards": L["cards"], "density": L["density"],
                   "hero_arrangement": cl.get("hero_arrangement", "stack")},
        "background": {"layers": wg["background_layers"], "image": bg_img["path"] if bg_img else None,
                       "treatment": bs["treatment"] if bg_img else "none", "fixed": True,
                       "abstract": bool(bg_img and bg_img.get("abstract")),
                       "grain": any(Lr["kind"] == "grain" for Lr in wg["background_layers"])
                       or "grain" in bs["texture_and_pattern_cues"]},
        "bands": bands, "groups": spec_groups, "items": spec_items, "motifs": motifs, "assets": used_assets,
        "copy": copy, "item_ids": [x["item_id"] for x in spec_items], "group_ids": [x["group_id"] for x in spec_groups],
        "motif_ids": [m["motif_id"] for m in motifs],
    }


# --------------------------------------------------------------------------- the A5 spec (the design document, merged)
def css_px(size_css: str, vw: float = 1440, rem: float = 16) -> float | None:
    """'clamp(2.6rem, 5.2vw, 4.75rem)' / '1.6rem' / '24px' -> px at a 1440 px viewport (None if unreadable)."""
    def one(v):
        v = v.strip()
        m = re.fullmatch(r"(-?[\d.]+)(px|rem|em|vw)?", v)
        if not m:
            return None
        n, u = float(m.group(1)), m.group(2) or "px"
        return n * (rem if u in ("rem", "em") else vw / 100 if u == "vw" else 1)
    s = (size_css or "").strip().lower()
    m = re.fullmatch(r"clamp\(([^,]+),([^,]+),([^)]+)\)", s.replace(" ", ""))
    if m:
        lo, mid, hi = (one(x) for x in m.groups())
        if None in (lo, mid, hi):
            return None
        return max(lo, min(mid, hi))
    return one(s)


def assemble_doc_spec(st: State) -> dict:
    d, plan, cp, dec = st["doc"], st["plan"], st["copy_final"], st["decor_final"]
    pal = st["palette_final"]
    colors = d["colors"] + cp.get("added_colors", [])
    var_of = {c["name"]: c["var"] for c in colors}
    items = cp["items"]
    used = {x["level"] for x in items} | {"display", "body"}
    typo, levels = {}, {}
    for lvl in sc.LEVELS:
        v = d["typography"][lvl]
        typo[lvl] = {**{k: v[k] for k in ("family", "weight", "case", "letter_spacing", "italic", "classification",
                                         "visual_traits", "reference_style", "size_css", "line_height")},
                     "stack": font_stack(v["family"])}
        if lvl == "display":
            typo[lvl]["shadow_treatment"] = v.get("shadow_treatment", "none")
        levels[lvl] = {"family": v["family"], "weight": v["weight"], "used": lvl in used,
                       "size_px": css_px(v["size_css"])}
    typo["text_treatment_rules"] = d["typography"].get("text_treatment_rules", "")
    fams = list(dict.fromkeys(typo[lvl]["family"] for lvl in sc.LEVELS if levels[lvl]["used"]))
    italic = {typo[lvl]["family"] for lvl in sc.LEVELS if levels[lvl]["used"] and typo[lvl]["italic"]}
    lay = layer_of(d)
    placed = {L["element_id"]: L for L in plan["layers"]}
    assets_by = {a["element_id"]: a for a in dec["assets"]}
    decor = []
    for k in ("background", "midground", "foreground"):
        for e in d["elements"][k]:
            L = placed.get(e["id"], {})
            a = assets_by.get(e["id"])
            decor.append({"element_id": e["id"], "layer": f"z{L.get('z', lay[e['id']][1])}", "what": e["what"],
                          "geometry": e.get("geometry", ""), "where": e["where"], "anchor": L.get("anchor", ""),
                          "placement": L.get("placement", ""),
                          "asset": ({"kind": a["kind"], a["kind"]: a[a["kind"]], "opacity": a["opacity"]}
                                    if a else None)})
    bg = backdrop(st)
    centre = centerpiece_asset(st["assets"]) if d["centerpiece"]["use"] else None
    psec = {s["section_id"]: s for s in plan["sections"]}
    scol = {s["section_id"]: s for s in cp["section_colors"]}
    cards = {c["card_id"]: c for c in d["strategic_cards"]}
    hero = next((s["section_id"] for s in d["content_sections"] if s["role"] == "hero"), None)
    sections, flat = [], []
    for s in d["content_sections"]:
        sid = s["section_id"]
        p, c = psec.get(sid, {}), scol.get(sid, {})
        its = []
        for x in [x for x in items if x["section_id"] == sid]:
            it = {k: x[k] for k in ("item_id", "kind", "level", "text", "href")}
            if x["kind"] == "card":
                cd = cards.get(x["card_id"], {})
                acc = cd.get("accent_color_key", "overlay_primary")
                it.update(text="", card={"tag": cd.get("tag", ""), "heading": cd.get("heading", ""),
                                         "body": cd.get("body", ""), "accent": f"var(--{acc.replace('_', '-')})"})
            its.append(it)
            flat.append({"item_id": x["item_id"], "kind": x["kind"], "section_id": sid, "level": x["level"]})
        if centre and sid == hero:
            its.append({"item_id": "centerpiece", "kind": "image", "src": centre["path"],
                        "alt": cut(d["centerpiece"]["description"], 120), "where": d["centerpiece"]["where"]})
            flat.append({"item_id": "centerpiece", "kind": "centerpiece", "section_id": sid, "level": "body"})
        sections.append({"section_id": sid, "role": s["role"], "what": s["what"], "where": s["where"],
                         "layout": p.get("layout", ""), "size": p.get("size", ""), "responsive": p.get("responsive", ""),
                         "colors": {k: var_of.get(c.get(k), "") for k in ("surface", "text", "heading", "accent")},
                         "items": its})
    copy_ = [x["text"] for x in items if x["kind"] != "card" and x["text"]]
    copy_ += [v for x in items if x["kind"] == "card" for cd in [cards.get(x["card_id"], {})]
              for v in (cd.get("heading"), cd.get("body")) if v]
    assets = ([{"path": centre["path"], "role": "centerpiece", "alt": cut(d["centerpiece"]["description"], 120),
                "description": d["centerpiece"]["description"]}] if centre else [])
    if bg:
        assets.append({**bg, "description": d["background_layer"]["base_surface"]})
    css_vars = {c["var"]: c["hex"] for c in colors}
    css_vars.update({f"--{r.replace('_', '-')}": h for r, h in pal.items()})
    return {
        "title": cp.get("brand") or st["meta"].get("brand") or d["design_system_name"],
        "family": st["meta"]["family"], "design_system_name": d["design_system_name"],
        "aesthetic_direction": d["aesthetic_direction"], "query_context": d["query_context"],
        "colors": [{k: c[k] for k in ("name", "var", "hex", "group", "usage")} for c in colors],
        "roles": {r: f"var(--{r.replace('_', '-')})" for r in pal},
        "palette": {**{c["name"]: c["hex"] for c in colors}, **pal},
        "css_vars": css_vars,
        "typography": typo, "levels": levels, "fonts": fams,
        "fonts_css": [g.google_css(f, f in italic) for f in fams],
        "type_scale": {k: v for k, v in st["facts"]["type_scale"].items() if k.startswith("--fs-")},
        "canvas": {"max_width_px": 1440, **plan["canvas"]},
        "composition": {**d["composition_and_overlap_rules"], "canvas_use": plan["canvas"].get("canvas_use", "")},
        "background": {"image": bg["path"] if bg else None, "treatment": d["background_layer"]["treatment"] if bg else "none",
                       "abstract": bool(bg and bg["abstract"]), "base_surface": d["background_layer"]["base_surface"]},
        "sections": sections, "decor": decor, "assets": assets,
        "layout": {"hero_section": hero},
        "items": flat, "copy": copy_, "item_ids": [x["item_id"] for x in flat],
        "section_ids": [s["section_id"] for s in sections],
        "motif_ids": [x["element_id"] for x in decor if x["asset"] and x["asset"]["kind"] == "svg"],
    }
