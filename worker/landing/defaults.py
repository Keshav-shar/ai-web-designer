"""defaults.py - a deterministic output for every agent, from the lab's facts alone (no model).

Used when an agent is off, has no key or quota, or fails its checks after one repair, so the pipeline always
yields a page. Each default obeys the same schema and semantic checks as a model's output. They are generic on
purpose (no style is assumed beyond what the lab measured) and conservative where a wrong guess is visible: the
default decoration only goes into space the scene map shows as free, or behind the hero image.
"""
from __future__ import annotations

import re

import compose

from . import schemas as sc
from .handoff import font_info, repair_palette, role_pairs, snap_weight


def _near(value: str, options: list[str]) -> str:
    try:
        v = float(re.sub(r"[^0-9.\-]", "", str(value)) or 0)
        return min(options, key=lambda o: abs(float(re.sub(r"[^0-9.\-]", "", o) or 0) - v))
    except ValueError:
        return options[0]


def short(text: str, n: int) -> str:
    """Cut at a word boundary (a logo, a label): 'Neon synthwave music festival' -> 'Neon synthwave music'."""
    text = (text or "").strip()
    return text if len(text) <= n else (text[:n].rsplit(" ", 1)[0] or text[:n])


# --------------------------------------------------------------------------- A1
def type_system(h: dict) -> dict:
    """Five roles from the lab's pair + the pool: wordmark and display from the heading face, an accent from a
    different category in the pool (so labels read apart from body text), subheading + body from the body face."""
    f = h["facts"]
    head, body = f["fonts"]["heading"], f["fonts"]["body"]
    roles = f["type_roles"]
    pool = h.get("font_pool") or {head: font_info(head), body: font_info(body)}
    cats = {pool.get(head, {}).get("category"), pool.get(body, {}).get("category")}
    accent = next((n for n, i in pool.items() if n not in (head, body) and i["category"] not in cats), None) or body
    h1_case = roles["h1"].get("text_transform", "none")
    h1_case = h1_case if h1_case in sc.CASES else "none"
    heavy = max([w for w in font_info(head)["weights"] if w <= 800] or [400])
    ai = font_info(accent)
    thin_script = pool.get(head, {}).get("category") in ("Handwriting", "Display") and heavy <= 400
    return {
        "wordmark_font": {"family": head, "weight": str(heavy), "letter_spacing": "0.04em" if h1_case == "uppercase" else
                          ("0em" if thin_script else "-0.02em"), "case": h1_case, "italic": False,
                          "scale": "xl" if thin_script else "l"},   # a single-weight script needs size for presence
        "display_font": {"family": head, "weight": snap_weight(head, roles["h1"].get("weight", 600)),
                         "letter_spacing": _near(roles["h1"].get("letter_spacing", "0em"), sc.TRACKING), "case": h1_case,
                         "shadow_treatment": "none", "italic": bool(roles["h1"].get("italic"))},
        "subheading_font": {"family": body, "weight": snap_weight(body, 500), "letter_spacing": "0.08em",
                            "case": "uppercase"},
        "accent_font": {"family": accent, "weight": snap_weight(accent, ai["weights"][len(ai["weights"]) // 2]),
                        "letter_spacing": "0.14em" if accent == body else "0.04em",
                        "case": "uppercase" if accent == body else "none", "italic": accent == body and ai["italic"]},
        "body_font": {"family": body, "weight": snap_weight(body, 400),
                      "line_height": _near(f["type_scale"].get("--lh-body", 1.6), sc.LINE_HEIGHTS)},
        "layer_assignment": {"top_z10": ["nav", "headline", "content"], "bottom_z0_z5": ["background", "motifs"]},
    }


def a1(h: dict) -> dict:
    m, f, t = h["meta"], h["facts"], h["facts"]["lab_tokens"]
    cues = f"{m['vibe']['cues']} {m['vibe']['effect']}".lower()
    tex = [x for x, pat in (("perspective_grid", r"perspective|grid"), ("scanlines", r"scanline|crt"),
                            ("halftone", r"halftone|print|risograph"), ("paper", r"paper|letterpress|kraft"),
                            ("radial_glow", r"glow|neon|aurora|dream"), ("stripes", r"stripe|70s|retro"),
                            ("grain", r"grain|noise|film|analog")) if re.search(pat, cues)] or ["grain", "radial_glow"]
    hero = {"center": "centered"}.get(f["alignment"], "split_left_text")
    prims = [p for p, pat in (("perspective_grid", r"grid|hud|cyber"), ("sunburst", r"sun|70s|disco|retro"),
                              ("ribbon", r"ribbon|stripe|70s|groov"), ("arch", r"arch|curve|soft|calm"),
                              ("blob", r"organic|blob|fluid|calm"), ("badge", r"badge|sticker|stamp|y2k|retro"),
                              ("star", r"star|sparkle|y2k"), ("tape", r"tape|collage|zine|scrapbook"))
             if re.search(pat, cues)][:3] or ["blob", "arch", "dots"]
    kit = compose.kit_for(m["category"])
    tags = [w for w in re.split(r"[ /,]+", (m.get("niche") or m["category_name"] or "").strip()) if w][:3] or ["New"]
    return {
        "query_context": f"{m['full_query']}. Look: {m['vibe']['name']} ({m['vibe']['cues']}).",
        "background_spec": {"alignment_mode": "nuance_extract", "ignored_irrelevant_subjects": [],
                            "base_surface_description": f"{m['vibe']['name']} surface from the family palette",
                            "texture_and_pattern_cues": tex[:3], "treatment": "none",
                            "backdrop_focal_geometry": "soft focal glow behind the hero"},
        "layout_spec": {"nav": "bar_left_logo", "hero": hero, "intro": "centered_statement", "cards": "grid3",
                        "density": "balanced", "notes": f"measured alignment: {f['alignment']}"},
        "palette": {"bg_primary": t["--bg"], "bg_secondary": t["--surface"], "text_top_heading": t["--text"],
                    "text_subheading": t["--text-muted"], "text_body": t["--text"], "text_inverse": t["--on-accent"],
                    "accent_muted": t.get("--accent-soft", t["--accent"]), "overlay_primary": t["--accent"],
                    "overlay_secondary": t.get("--accent-2", t["--accent"]), "cta_fill": t["--accent"]},
        "typography": type_system(h),
        "design_elements": [{"element_id": f"el_{i + 1}", "motif_type": p, "geometry": p.replace("_", " "),
                             "visual_cues": m["vibe"]["cues"][:80], "source": "ELEMENTS_REF"}
                            for i, p in enumerate(prims)],
        "strategic_cards": [{"card_id": sc.CARD_IDS[i], "tag": tags[i % len(tags)].capitalize(), "heading": ti,
                             "body": d, "accent_color_key": ["overlay_primary", "overlay_secondary", "cta_fill"][i]}
                            for i, (ti, d) in enumerate(kit["features"][:3])],
    }


# --------------------------------------------------------------------------- A2
def a2(a1_out: dict, bg_image: bool = False) -> dict:
    L = a1_out["layout_spec"]
    bs = a1_out["background_spec"]
    tex = bs["texture_and_pattern_cues"]
    centered = L["hero"] in ("centered", "full_bleed", "editorial_stack")
    layers = [{"kind": "solid", "roles": ["bg_primary"], "opacity": 1, "angle_deg": 0, "position": "full",
               "blend": "normal", "scale": "medium"}]
    if bg_image:
        layers += [{"kind": "image", "roles": ["bg_primary"], "opacity": 1, "angle_deg": 0, "position": "full",
                    "blend": "normal", "scale": "medium"},
                   {"kind": "linear_gradient", "roles": ["bg_primary", "bg_secondary"], "opacity": 0.35, "angle_deg": 180,
                    "position": "full", "blend": "normal", "scale": "medium"}]
    layers += [{"kind": "radial_glow", "roles": ["overlay_primary"], "opacity": 0.3, "angle_deg": 0,
                "position": "top_right", "blend": "screen", "scale": "bold"},
               {"kind": "radial_glow", "roles": ["overlay_secondary"], "opacity": 0.22, "angle_deg": 0,
                "position": "bottom_left", "blend": "screen", "scale": "bold"}]
    for k in tex:
        if k in ("perspective_grid", "stripes", "grid", "dots", "halftone", "scanlines", "paper", "mesh"):
            layers.append({"kind": k, "roles": ["overlay_secondary"], "opacity": 0.16, "angle_deg": 135,
                           "position": "bottom" if k == "perspective_grid" else "full", "blend": "normal",
                           "scale": "medium"})
            break
    if "grain" in tex:
        layers.append({"kind": "grain", "roles": ["text_body"], "opacity": 0.06, "angle_deg": 0, "position": "full",
                       "blend": "overlay", "scale": "fine"})
    safe = {"col_start": 3, "col_span": 8} if centered else {"col_start": 1, "col_span": 12}
    bands = [{"band_id": "nav", "height_px": 84, "padding": "tight", "surface_role": "transparent", "rows": 1,
              "safe_box": {"col_start": 1, "col_span": 12}},
             {"band_id": "hero", "height_px": 600, "padding": "loose", "surface_role": "transparent", "rows": 4,
              "safe_box": safe},
             {"band_id": "intro", "height_px": 260, "padding": "regular", "surface_role": "transparent", "rows": 2,
              "safe_box": {"col_start": 3, "col_span": 8}},
             {"band_id": "cards", "height_px": 420, "padding": "regular", "surface_role": "transparent", "rows": 1,
              "safe_box": {"col_start": 1, "col_span": 12}}]
    ns = [{"region_id": "hero.left_wing", "band_id": "hero", "col_start": 0, "col_span": 1, "y0": 0.1, "y1": 0.9},
          {"region_id": "hero.right_wing", "band_id": "hero", "col_start": 13, "col_span": 1, "y0": 0.1, "y1": 0.9}]
    return {"wireframe_grid": {"canvas": {"content_width_px": 1200, "gutter_px": 24}, "background_layers": layers,
                               "bands": bands, "negative_space": ns}}


# --------------------------------------------------------------------------- A3
def best_pair(pairs: dict[str, float], text: str, surfaces: list[str], need: float) -> str:
    for s in surfaces:
        k = f"{text}/{s}"
        if pairs.get(k, 0) >= need:
            return k
    ok = [k for k, r in pairs.items() if r >= need] or list(pairs)
    return max(ok, key=lambda k: pairs[k])


def a3(h: dict, a1_out: dict, a2_out: dict) -> dict:
    m = h["meta"]
    kit = compose.kit_for(m["category"])
    brand = m.get("brand") or compose.headline_from(m["full_query"])
    pal, _ = repair_palette(a1_out["palette"])
    pairs = role_pairs(pal)
    bands = {b["band_id"]: b for b in a2_out["wireframe_grid"]["bands"]}
    surf = lambda b: "bg_primary" if bands.get(b, {}).get("surface_role", "transparent") == "transparent" \
        else bands[b]["surface_role"]  # noqa: E731
    L = a1_out["layout_spec"]
    centered = L["hero"] in ("centered", "full_bleed", "editorial_stack")
    has_c = any(a["role"] == "central" and not a["text"] for a in h["assets"])

    def it(item_id, group, kind, c, s, row, text="", *, level="body", text_role="text_body", href="#top", card_id=""):
        return {"item_id": item_id, "band_id": sc.GROUP_BAND[group], "group": group, "kind": kind, "col_start": c,
                "col_span": s, "row": row, "row_span": 1,
                "align": "center" if (centered and group == "hero_text") or group == "intro" else "left",
                "text": text, "href": href, "level": level, "text_role": text_role, "card_id": card_id}

    nav_labels = [("About", "#intro"), ("Highlights", "#cards"), ("Join", "#cards")]
    items = [it("logo", "nav", "logo", 1, 4, 1, short(brand, 24), level="wordmark", text_role="text_top_heading")]
    items += [it(f"nav_{i + 1}", "nav", "nav_link", 5 + 2 * i, 2, 1, lbl, level="subheading",
                 text_role="text_subheading", href=hr) for i, (lbl, hr) in enumerate(nav_labels)]
    items.append(it("nav_cta", "nav", "cta", 11, 2, 1, short(kit["cta"][0], 24), level="subheading",
                    text_role="text_inverse", href="#cards"))
    tc, ts = (3, 8) if centered else (1, 6)
    items += [it("eyebrow", "hero_text", "eyebrow", tc, ts, 1, short(m.get("niche") or m["category_name"], 40),
                 level="accent", text_role="text_subheading"),
              it("h1", "hero_text", "h1", tc, ts, 2, short(brand, 70), level="display", text_role="text_top_heading"),
              it("sub", "hero_text", "subheading", tc, ts, 3, short(kit["tagline"], 160)),
              it("hero_cta", "hero_text", "cta", tc, ts, 4, short(kit["cta"][0], 24), level="subheading",
                 text_role="text_inverse", href="#cards")]
    if has_c:
        items.append(it("centerpiece", "hero_media", "centerpiece", 4 if centered else 7, 6, 5 if centered else 1,
                        f"{m['vibe']['name']} artwork"))
    items += [it("intro_h", "intro", "intro_heading", 3, 8, 1, short(kit["cta_band"][0], 70), level="display",
                 text_role="text_top_heading"),
              it("intro_p", "intro", "intro_body", 3, 8, 2, short(kit["cta_band"][1], 200))]
    cards = a1_out.get("strategic_cards", [])
    span = 12 // max(1, len(cards)) if cards else 4
    for i, c in enumerate(cards):
        items.append(it(c["card_id"], "cards", "card", 1 + i * span, span, 1, card_id=c["card_id"], level="display",
                        text_role="text_body"))
    groups = [{"group_id": "nav", "pair": best_pair(pairs, "text_subheading", [surf("nav")], 4.5), "backing": "none",
               "align": "start"},
              {"group_id": "hero_text", "pair": best_pair(pairs, "text_body", [surf("hero")], 4.5), "backing": "none",
               "align": "center" if centered else "start"},
              {"group_id": "intro", "pair": best_pair(pairs, "text_body", [surf("intro")], 4.5), "backing": "none",
               "align": "center"},
              {"group_id": "cards", "pair": best_pair(pairs, "text_body", ["bg_secondary", "bg_primary"], 4.5),
               "backing": "solid", "align": "start"}]
    if has_c:
        groups.append({"group_id": "hero_media", "pair": groups[1]["pair"], "backing": "none", "align": "center"})
    return {"content_layer": {"brand": short(brand, 40), "groups": groups, "items": items}}


# --------------------------------------------------------------------------- A4
ROUND = {"blob", "arch", "sunburst", "badge", "star", "dots"}


def a4(a1_out: dict, scene: list[dict], areas: list[dict]) -> dict:
    """Conservative: one shape peeking out behind the hero image (if there is one) and one motif in the largest
    genuinely free area; no corner badges, no adjustments."""
    els = a1_out.get("design_elements") or []
    prim = next((e["motif_type"] for e in els if e["motif_type"] in ROUND), "blob")
    el_id = next((e["element_id"] for e in els if e["motif_type"] == prim), els[0]["element_id"] if els else "")
    motifs = []
    base = {"element_id": el_id, "area_id": "", "target": "", "corner": "none", "edge": "none", "size_px": 0,
            "rotation_deg": 0, "fill_role": "overlay_primary", "stroke_role": "none", "stroke_width": 0, "count": 6,
            "opacity": 0.55, "path_d": ""}
    img = next((s for s in scene if s.get("is_image")), None)
    if img:
        motifs.append({**base, "motif_id": "m1", "primitive": prim, "relation": "behind_element",
                       "target": img["id"], "x": 0.16, "y": 0.14, "w": 0.95, "h": 0.95})
    free = sorted((a for a in areas if (a["kind"] in ("side", "below") and a["box_px"][2] >= 160 and a["box_px"][3] >= 120)
                   or (a["kind"] == "wing" and a["band_id"] == "hero" and a["box_px"][2] >= 96 and a["box_px"][3] >= 240)),
                  key=lambda a: (a["kind"] == "wing", -a["box_px"][2] * a["box_px"][3]))
    if free:
        narrow = free[0]["box_px"][2] < 0.5 * free[0]["box_px"][3]       # a tall strip (e.g. a page wing)
        second = next((e for e in els if e["motif_type"] in ("dots", "stripe_band", "squiggle")), None) if narrow \
            else next((e for e in els if e["motif_type"] != prim), None)
        if narrow and not second:
            second = {"motif_type": "dots", "element_id": el_id}
        motifs.append({**base, "motif_id": f"m{len(motifs) + 1}",
                       "primitive": second["motif_type"] if second else "dots",
                       "element_id": second["element_id"] if second else el_id, "relation": "in_free_area",
                       "area_id": free[0]["area_id"], "x": 0.15, "y": 0.15, "w": 0.7, "h": 0.7,
                       "fill_role": "overlay_secondary", "opacity": 0.45})
    return {"overlay_layer": {"decoration_intent": "subtle" if motifs else "none",
                              "rationale": "default: decoration only where the scene is free, or behind the hero image",
                              "motifs": motifs, "adjustments": []}}


# =========================================================================== the design document (agents A1..A4)
# The agents write a descriptive design document; these are its deterministic versions, derived from the legacy
# defaults above so agents-off pages and agent fallbacks stay what the lab measured.
ROLE_NAME = {"bg_primary": "Page ground", "bg_secondary": "Card surface", "text_top_heading": "Headline ink",
             "text_subheading": "Label ink", "text_body": "Body ink", "text_inverse": "Inverse ink",
             "accent_muted": "Muted accent", "overlay_primary": "Primary accent", "overlay_secondary": "Second accent",
             "cta_fill": "Action fill"}
ROLE_GROUP = {"bg_primary": "background_element_color", "bg_secondary": "background_element_color",
              "text_top_heading": "text_color", "text_subheading": "text_color", "text_body": "text_color",
              "text_inverse": "text_color", "accent_muted": "muted_accent_color",
              "overlay_secondary": "muted_accent_color", "overlay_primary": "overlay_elements_color",
              "cta_fill": "overlay_elements_color"}
ROLE_USE = {"bg_primary": "the page ground behind every section", "bg_secondary": "card and panel surfaces",
            "text_top_heading": "headlines and the wordmark", "text_subheading": "navigation and small labels",
            "text_body": "running text", "text_inverse": "text on the action fill", "accent_muted": "quiet accents",
            "overlay_primary": "decoration and highlights", "overlay_secondary": "secondary decoration",
            "cta_fill": "buttons"}
SIZE_CSS = {"wordmark": "clamp(1.6rem, 2.4vw, 2.2rem)", "display": "clamp(2.6rem, 5.2vw, 4.75rem)",
            "subheading": "1.05rem", "accent": "0.85rem", "body": "1.05rem"}
WM_SIZE = {"s": "1.25rem", "m": "1.6rem", "l": "clamp(1.6rem, 2.4vw, 2.2rem)", "xl": "clamp(2rem, 3vw, 2.6rem)"}
PRIM_WORDS = [("perspective_grid", r"perspective|grid"), ("sunburst", r"sunburst|ray|sun"), ("ribbon", r"ribbon|rainbow"),
              ("stripe_band", r"stripe|band|line"), ("squiggle", r"squiggle|wave|wavy"), ("tape", r"tape"),
              ("badge", r"badge|sticker|seal|stamp"), ("star", r"star|sparkle"), ("arch", r"arch|arc"),
              ("dots", r"dot|halftone|speck"), ("frame", r"frame|border"), ("blob", r"blob|organic|shape|leaf")]


def guess_primitive(text: str) -> str:
    t = (text or "").lower()
    return next((p for p, pat in PRIM_WORDS if re.search(pat, t)), "blob")


def design_doc(h: dict) -> dict:
    a = a1(h)
    m, pal, T = h["meta"], a["palette"], a["typography"]
    pool = h.get("font_pool") or {}
    cpd = {g: [] for g in sc.PALETTE_GROUPS}
    for r, hx in pal.items():
        cpd[ROLE_GROUP[r]].append({"name": ROLE_NAME[r], "hex": hx, "usage": ROLE_USE[r], "source": "PALETTE_REF"})

    def lvl(v, level, size):
        info = pool.get(v["family"]) or font_info(v["family"])
        return {"family": v["family"], "weight": str(v["weight"]), "case": v.get("case", "none"),
                "letter_spacing": v.get("letter_spacing", "0em"), "italic": bool(v.get("italic")),
                "classification": info.get("category", ""), "visual_traits": ", ".join(info.get("tags", [])[:3]),
                "reference_style": v["family"], "size_css": size,
                "line_height": {"display": "1.05", "wordmark": "1"}.get(level, v.get("line_height", "1.6"))}
    typo = {"wordmark": lvl(T["wordmark_font"], "wordmark", WM_SIZE[T["wordmark_font"].get("scale", "l")]),
            "display": {**lvl(T["display_font"], "display", SIZE_CSS["display"]),
                        "shadow_treatment": T["display_font"].get("shadow_treatment", "none")},
            "subheading": lvl(T["subheading_font"], "subheading", SIZE_CSS["subheading"]),
            "accent": lvl(T["accent_font"], "accent", SIZE_CSS["accent"]),
            "body": lvl(T["body_font"], "body", SIZE_CSS["body"]),
            "text_treatment_rules": "display type carries the mood; labels and body stay flat and readable"}
    bs = a["background_spec"]
    cues = ", ".join(c for c in bs["texture_and_pattern_cues"] if c != "none") or "soft light"
    has_c = any(x["role"] == "central" and not x["text"] for x in h["assets"])
    els = a["design_elements"][:2]
    cards = a["strategic_cards"]
    sections = [{"section_id": "nav", "role": "nav", "where": "top bar", "what": ["wordmark", "links", "action"]},
                {"section_id": "hero", "role": "hero", "where": "first screen",
                 "what": ["eyebrow", "headline", "supporting line", "action"] + (["the central graphic"] if has_c else [])},
                {"section_id": "intro", "role": "intro", "where": "below the hero, centred",
                 "what": ["statement heading", "short paragraph"]}]
    if cards:
        sections.append({"section_id": "cards", "role": "cards", "where": "lower band",
                         "what": [f"{len(cards)} strategic cards"]})
    return {
        "design_system_name": f"{m['vibe']['name']} landing",
        "aesthetic_direction": f"{m['vibe']['name']}: {m['vibe']['cues']}. {m['vibe']['effect']}".strip(),
        "query_context": a["query_context"],
        "color_palette_distribution": cpd,
        "role_map": dict(pal),
        "typography": typo,
        "background_layer": {
            "alignment_mode": bs["alignment_mode"], "use_background_image": False, "treatment": "none",
            "ignored_irrelevant_subjects": [], "base_surface": bs["base_surface_description"],
            "elements": [{"id": "bg-ground", "what": f"{ROLE_NAME['bg_primary']} ground with {cues}",
                          "where": "the whole page, fixed behind everything",
                          "geometry": "a flat full-bleed surface", "source": "BACKGROUND_REF"},
                         {"id": "bg-glow", "what": f"a soft radial glow in {ROLE_NAME['overlay_primary']}",
                          "where": "behind the hero, upper right",
                          "geometry": "one radial gradient, about 60vw across, fading to transparent",
                          "source": "inferred"}]},
        "centerpiece": {"use": has_c, "description": f"{m['vibe']['name']} artwork", "where": "beside the hero text"},
        "midground_decor": [{"id": f"decor-{i + 1}",
                             "what": f"{e['motif_type'].replace('_', ' ')}: {e['geometry']}; {e['visual_cues']}",
                             "where": "behind the hero image" if i == 0 and has_c else "in the outer margin beside the hero",
                             "geometry": e["geometry"], "source": e.get("source") or "ELEMENTS_REF"}
                            for i, e in enumerate(els)],
        "foreground_overlays": [],
        "content_sections": sections,
        "composition_and_overlap_rules": {"alignment_grid": "12-column centred container, 1200 px",
                                          "permitted_overlaps": [], "prohibited_overlaps":
                                              ["decoration never sits on text or on the central graphic"]},
        "layout_spec": a["layout_spec"],
        "strategic_cards": cards,
    }


LAYOUT_OF = {"nav": ("one row: wordmark left, links and the action right", "about 88px tall"),
             "hero": ("12 columns: the text block in cols 1-6, the central graphic in cols 7-12, centred vertically",
                      "min-height 640px; padding 96px 0"),
             "intro": ("centred column, max-width 760px", "padding 80px 0"),
             "cards": ("a 12-column grid of equal cards", "padding 80px 0")}


def layout_plan(doc: dict) -> dict:
    """doc = the normalized design document (flow.normalize_doc)."""
    names = doc["role_names"]
    secs = []
    for s in doc["content_sections"]:
        lay, size = LAYOUT_OF.get(s["role"], ("a centred column", "padding 72px 0"))
        secs.append({"section_id": s["section_id"], "layout": lay, "size": size,
                     "surface": names["bg_secondary"] if s["role"] == "footer" else names["bg_primary"],
                     "responsive": "one column under 1024px"})
    hero = next((s["section_id"] for s in doc["content_sections"] if s["role"] == "hero"),
                doc["content_sections"][0]["section_id"])
    layers = []
    for z, key in ((0, "background"), (5, "midground"), (20, "foreground")):
        for e in doc["elements"][key]:
            layers.append({"element_id": e["id"], "z": z, "anchor": hero, "placement": e["where"], "notes": ""})
    return {"layout_plan": {"canvas": {"content_width_px": 1200, "gutter_px": 24,
                                       "canvas_use": "the hero's text and graphic share the full width"},
                            "sections": secs, "layers": layers}}


COPY_KIND = {"logo": "logo", "nav_link": "nav_link", "eyebrow": "eyebrow", "h1": "h1", "subheading": "paragraph",
             "intro_heading": "h2", "intro_body": "paragraph", "card": "card", "cta": "cta"}


def copy(h: dict, st) -> dict:
    """st = the run state after A1/A2 (doc, legacy keys)."""
    doc = st["doc"]
    view = {k: st[k] for k in ("layout_spec", "background_spec", "palette", "strategic_cards", "design_elements")}
    leg = a3(h, view, a2(view))["content_layer"]
    sec = {}
    for s in doc["content_sections"]:
        sec.setdefault(s["role"], s["section_id"])
    first = doc["content_sections"][0]["section_id"]
    items = []
    for x in leg["items"]:
        if x["kind"] == "centerpiece":
            continue
        role = {"nav": "nav", "hero_text": "hero", "intro": "intro", "cards": "cards"}[x["group"]]
        sid = sec.get(role) or sec.get("hero") or first
        items.append({"item_id": x["item_id"], "section_id": sid, "kind": COPY_KIND[x["kind"]], "level": x["level"],
                      "text": x["text"], "href": x["href"], "card_id": x.get("card_id", "")})
    n = doc["role_names"]
    colors = [{"section_id": s["section_id"], "surface": n["bg_primary"], "text": n["text_body"],
               "heading": n["text_top_heading"], "accent": n["overlay_primary"]} for s in doc["content_sections"]]
    return {"copy": {"brand": leg["brand"], "items": items, "section_colors": colors}}


def decor(doc: dict, plan: dict) -> dict:
    from . import primitives
    by_id = {e["id"]: e for k in ("midground", "foreground") for e in doc["elements"][k]}
    assets = []
    for L in plan["layers"]:
        e = by_id.get(L["element_id"])
        if not e or L["z"] == 0:
            continue
        prim = guess_primitive(e["what"])
        m = {"motif_id": e["id"], "primitive": prim, "count": 6, "fill_role": "overlay_primary",
             "stroke_role": "overlay_secondary", "stroke_width": 3}
        assets.append({"element_id": e["id"], "kind": "svg", "svg": primitives.render(m, 240, 240), "css": "",
                       "anchor": L["anchor"], "placement": L["placement"], "opacity": 0.55,
                       "notes": f"default: the {prim} primitive"})
    return {"decor": {"intent": "subtle" if assets else "none", "assets": assets}}
