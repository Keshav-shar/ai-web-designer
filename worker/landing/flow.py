"""flow.py - the code steps between the agents (no model): check and normalize each section of the design document.

The agents write freely; code keeps only what must hold: real hexes (the measured ones, plus a few observed extras),
real Google Fonts with real weights, unique ids, one h1, readable text on every section's surface, safe SVG/CSS.
Every change is logged as {token, from, to, why}.

pipeline.run calls after_a1..after_a4 between agent calls; deterministic() runs the defaults (tests, the contract
export, agents off). fallback() / safe() build the deterministic compile_spec page from the same document (A1's
palette + type, A3's copy) when A5's page can't ship.
"""
from __future__ import annotations

import copy
import re

from . import defaults, handoff as H, schemas as sc, spatial, state as S, validate_page as V
from .handoff import font_info

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
CSS_SAFE = re.compile(r"^[0-9a-zA-Z.,()%\s+\-*/]{1,64}$")
CAPS = {"logo": 40, "nav_link": 24, "cta": 32, "eyebrow": 60, "h1": 100, "h2": 100, "h3": 80, "paragraph": 420,
        "label": 40, "quote": 260, "stat": 40, "list_item": 140, "caption": 140, "card": 0}
LEVEL_OF = {"logo": "wordmark", "nav_link": "subheading", "cta": "subheading", "eyebrow": "accent", "h1": "display",
            "h2": "display", "h3": "subheading", "paragraph": "body", "label": "accent", "quote": "display",
            "stat": "display", "list_item": "body", "caption": "accent", "card": "display"}
LEGACY_KEYS = ("query_context", "background_spec", "layout_spec", "palette", "strategic_cards", "design_elements",
               "palette_final", "pairs", "type_system")


def slug(s: str, n: int = 32) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n] or "x"


def _unique(base: str, seen: set) -> str:
    out, i = base, 2
    while out in seen:
        out, i = f"{base}-{i}", i + 1
    seen.add(out)
    return out


def _log(log, token, frm, to, why):
    log.append({"token": token, "from": frm, "to": to, "why": why})


# Characters a composer won't retype verbatim (a non-breaking hyphen looks like '-'; zero-width marks are invisible):
# the copy is stored plain so the page check compares like with like.
PLAIN = str.maketrans({"\u2010": "-", "\u2011": "-", "\u00ad": "", "\u200b": "", "\u2060": "", "\ufeff": ""})


def plain(s: str) -> str:
    return (s or "").translate(PLAIN)


# --------------------------------------------------------------------------- A1: the design document
def normalize_doc(doc: dict, st: S.State, h: dict) -> tuple[dict, list]:
    log = []
    allowed = [x.upper() for x in st["enums"]["hex"]]
    lab = defaults.a1(h)["palette"]
    extras, colors, names, vars_ = [], [], set(), set()

    def add_color(name, hx, group, usage):
        nm = _unique(S.cut(name or group, 40), names)
        colors.append({"name": nm, "hex": hx, "group": group, "usage": S.cut(usage, 160),
                       "var": _unique("--c-" + slug(nm, 24), vars_)})
        return colors[-1]
    for grp in sc.PALETTE_GROUPS:
        for e in (doc.get("color_palette_distribution") or {}).get(grp, [])[:12]:
            hx = (e.get("hex") or "").strip().upper()
            if not HEX.match(hx):
                _log(log, f"colour {e.get('name')}", e.get("hex"), None, "not a #RRGGBB hex")
                continue
            if hx not in allowed and hx not in extras:
                if len(extras) < sc.EXTRA_HEXES:
                    extras.append(hx)
                    _log(log, f"colour {e.get('name')}", hx, hx, "observed colour outside the measured set (kept)")
                else:
                    new = V.nearest_hex(hx, allowed)
                    _log(log, f"colour {e.get('name')}", hx, new, f"more than {sc.EXTRA_HEXES} unmeasured colours: "
                                                                  f"snapped to the nearest measured one")
                    hx = new
            add_color(e.get("name"), hx, grp, e.get("usage", ""))
    by_name = {c["name"].lower(): c for c in colors}
    by_hex = {}
    for c in colors:
        by_hex.setdefault(c["hex"], c)
    role_hex, role_names = {}, {}
    for r in sc.PALETTE_ROLES:
        v = str((doc.get("role_map") or {}).get(r) or "").strip()
        hx = v.upper() if HEX.match(v) else (by_name.get(v.lower()) or {}).get("hex")
        if hx and hx not in allowed and hx not in extras:
            hx = V.nearest_hex(hx, allowed)
        if not hx:
            hx = lab[r]
            _log(log, f"role_map.{r}", v, hx, "no usable colour named; the lab's measured one")
        if hx not in by_hex:
            by_hex[hx] = add_color(defaults.ROLE_NAME[r], hx, defaults.ROLE_GROUP[r], defaults.ROLE_USE[r])
        role_hex[r], role_names[r] = hx, by_hex[hx]["name"]
    pool = st["font_pool"]
    typo = {}
    for lvl in sc.LEVELS:
        v = dict((doc.get("typography") or {}).get(lvl) or {})
        hint = f"{v.get('classification', '')} {v.get('visual_traits', '')}"
        fam, note = H.resolve_font(v.get("family", ""), pool, hint)
        if note:
            _log(log, f"typography.{lvl}.family", v.get("family"), fam, note)
        w = H.snap_weight(fam, v.get("weight", 400))
        if w != str(v.get("weight")):
            _log(log, f"typography.{lvl}.weight", v.get("weight"), w, f"{fam} has weights {font_info(fam)['weights']}")
        size = v.get("size_css") or defaults.SIZE_CSS[lvl]
        if not CSS_SAFE.match(size):
            _log(log, f"typography.{lvl}.size_css", size, defaults.SIZE_CSS[lvl], "not a plain CSS length")
            size = defaults.SIZE_CSS[lvl]
        ls = v.get("letter_spacing") or "0em"
        ls = ls if re.fullmatch(r"-?[\d.]+(em|px|rem)|normal|0", ls.strip()) else "0em"
        lh = str(v.get("line_height") or "1.5")
        lh = lh if re.fullmatch(r"[\d.]+(px|rem|em)?|normal", lh.strip()) else "1.5"
        italic = bool(v.get("italic")) and font_info(fam)["italic"]
        typo[lvl] = {"family": fam, "weight": w, "case": v.get("case") if v.get("case") in sc.CASES else "none",
                     "letter_spacing": ls, "italic": italic, "classification": S.cut(v.get("classification", ""), 120),
                     "visual_traits": S.cut(v.get("visual_traits", ""), 220),
                     "reference_style": S.cut(v.get("reference_style", ""), 80), "size_css": size, "line_height": lh}
        if lvl == "display":
            typo[lvl]["shadow_treatment"] = v.get("shadow_treatment") if v.get("shadow_treatment") in sc.SHADOWS else "none"
    typo["text_treatment_rules"] = S.cut((doc.get("typography") or {}).get("text_treatment_rules", ""), 300)
    bl = dict(doc.get("background_layer") or {})
    has_bg = any(a["role"] == "background" for a in st["assets"])
    treatment = bl.get("treatment") if bl.get("treatment") in sc.BG_TREATMENT else "none"
    want = bool(bl.get("use_background_image"))
    if want and treatment == "none" and has_bg:
        treatment = "tinted"
        _log(log, "background.treatment", "none", "tinted", "A1 chose to use the image but gave no treatment")
    if not want and treatment != "none":
        want = True                                   # a treatment is a decision to use it
    use = want and treatment != "none" and has_bg
    mode = bl.get("alignment_mode") if bl.get("alignment_mode") in ("exact_adapt", "nuance_extract") else "nuance_extract"
    seen_ids = set()

    def els(lst, prefix):
        out = []
        for e in (lst or [])[:8]:
            out.append({"id": _unique(slug(e.get("id") or prefix, 32), seen_ids), "what": S.cut(e.get("what", ""), 480),
                        "where": S.cut(e.get("where", ""), 280), "geometry": S.cut(e.get("geometry", ""), 320),
                        "source": e.get("source") if e.get("source") in sc.SOURCES else "inferred"})
        return out
    elements = {"background": els(bl.get("elements"), "bg"), "midground": els(doc.get("midground_decor"), "decor"),
                "foreground": els(doc.get("foreground_overlays"), "overlay")}
    sec_seen, sections = set(), []
    for s in (doc.get("content_sections") or [])[:8]:
        sections.append({"section_id": _unique(slug(s.get("section_id") or s.get("role") or "section", 24), sec_seen),
                         "role": s.get("role") if s.get("role") in sc.SECTION_ROLES else "other",
                         "where": S.cut(s.get("where", ""), 200), "what": [S.cut(w, 160) for w in (s.get("what") or [])[:8]]})
    if not sections:
        sections = [{"section_id": "hero", "role": "hero", "where": "first screen", "what": ["headline"]}]
        _log(log, "content_sections", None, "hero", "the page needs at least its main section")
    if not any(s["role"] == "hero" for s in sections):
        first = next((s for s in sections if s["role"] != "nav"), sections[0])
        _log(log, f"section {first['section_id']}.role", first["role"], "hero", "the first content section is the hero")
        first["role"] = "hero"
    cp = dict(doc.get("centerpiece") or {})
    has_c = any(a["role"] == "central" and not a["text"] for a in st["assets"])
    rules = dict(doc.get("composition_and_overlap_rules") or {})
    cards, card_ids = [], set()
    for c in (doc.get("strategic_cards") or [])[:4]:
        if c.get("card_id") in sc.CARD_IDS and c["card_id"] not in card_ids and (c.get("heading") or "").strip():
            card_ids.add(c["card_id"])
            cards.append({"card_id": c["card_id"], "tag": plain(S.cut(c.get("tag", ""), 24)),
                          "heading": plain(S.cut(c["heading"], 60)), "body": plain(S.cut(c.get("body", ""), 220)),
                          "accent_color_key": c.get("accent_color_key") if c.get("accent_color_key") in sc.PALETTE_ROLES
                          else "overlay_primary"})
    L = dict(doc.get("layout_spec") or {})
    layout = {"nav": L.get("nav") if L.get("nav") in sc.NAV else "bar_left_logo",
              "hero": L.get("hero") if L.get("hero") in sc.HERO else "split_left_text",
              "intro": L.get("intro") if L.get("intro") in sc.INTRO else "centered_statement",
              "cards": L.get("cards") if L.get("cards") in sc.CARDS else "grid3",
              "density": L.get("density") if L.get("density") in sc.DENSITY else "balanced",
              "notes": S.cut(L.get("notes", ""), 200)}
    nd = {"design_system_name": S.cut(doc.get("design_system_name") or "Landing page", 80),
          "aesthetic_direction": S.cut(doc.get("aesthetic_direction", ""), 700),
          "query_context": S.cut(doc.get("query_context", "") or st["meta"]["full_query"], 600),
          "colors": colors, "role_map": role_hex, "role_names": role_names, "typography": typo,
          "background_layer": {"alignment_mode": mode, "use_background_image": use, "treatment": treatment if use else "none",
                               "abstract": use and mode == "nuance_extract",
                               "ignored_irrelevant_subjects": [S.cut(x, 60) for x in (bl.get("ignored_irrelevant_subjects") or [])[:6]],
                               "base_surface": S.cut(bl.get("base_surface", ""), 240), "elements": elements["background"]},
          "elements": elements, "content_sections": sections,
          "centerpiece": {"use": bool(cp.get("use")) and has_c, "description": S.cut(cp.get("description", ""), 240),
                          "where": S.cut(cp.get("where", ""), 200)},
          "composition_and_overlap_rules": {
              "alignment_grid": S.cut(rules.get("alignment_grid", ""), 240),
              "permitted_overlaps": [{"a": S.cut(o.get("a", ""), 60), "b": S.cut(o.get("b", ""), 60),
                                      "why": S.cut(o.get("why", ""), 200)} for o in (rules.get("permitted_overlaps") or [])[:8]],
              "prohibited_overlaps": [S.cut(x, 200) for x in (rules.get("prohibited_overlaps") or [])[:8]]},
          "layout_spec": layout, "strategic_cards": cards}
    return nd, log


def legacy_type(nd: dict) -> dict:
    t = nd["typography"]

    def f(lvl):
        v = t[lvl]
        return {"family": v["family"], "weight": v["weight"], "letter_spacing": v["letter_spacing"], "case": v["case"],
                "italic": v["italic"]}
    px = S.css_px(t["wordmark"]["size_css"]) or 31
    scale = "xl" if px >= 36 else "l" if px >= 29 else "m" if px >= 23 else "s"
    return {"wordmark_font": {**f("wordmark"), "scale": scale},
            "display_font": {**f("display"), "shadow_treatment": t["display"].get("shadow_treatment", "none")},
            "subheading_font": f("subheading"), "accent_font": f("accent"),
            "body_font": {"family": t["body"]["family"], "weight": t["body"]["weight"],
                          "line_height": defaults._near(t["body"]["line_height"], sc.LINE_HEIGHTS)},
            "layer_assignment": {"top_z10": [], "bottom_z0_z5": []}}


def after_a1(st: S.State, doc: dict, h: dict) -> list:
    st.merge("a1", {"design_doc": doc})
    nd, log = normalize_doc(doc, st, h)
    pal, log2 = H.repair_palette(nd["role_map"])
    for o in log2:                                     # a text role pushed for contrast becomes a named colour too
        role = o["token"]
        if not any(c["hex"] == o["to"] for c in nd["colors"]):
            nm = f"{nd['role_names'][role]} (readable)"
            nd["colors"].append({"name": nm, "hex": o["to"], "group": "text_color",
                                 "usage": f"{defaults.ROLE_USE[role]}, adjusted for contrast",
                                 "var": "--c-" + slug(nm, 24)})
            nd["role_names"][role] = nm
    st.put("code", "doc", nd)
    st.put("code", "palette", nd["role_map"])
    st.put("code", "palette_final", pal)
    st.put("code", "pairs", H.role_pairs(pal))
    st.put("code", "type_system", legacy_type(nd))
    st.put("code", "query_context", nd["query_context"])
    st.put("code", "layout_spec", nd["layout_spec"])
    st.put("code", "strategic_cards", nd["strategic_cards"])
    bl = nd["background_layer"]
    text = " ".join(e["what"] for e in bl["elements"]).lower()
    cues = [t for t in sc.TEXTURES if t != "none" and t.replace("_", " ") in text][:3]
    st.put("code", "background_spec", {"alignment_mode": bl["alignment_mode"], "treatment": bl["treatment"],
                                       "texture_and_pattern_cues": cues or ["grain"],
                                       "ignored_irrelevant_subjects": bl["ignored_irrelevant_subjects"],
                                       "base_surface_description": bl["base_surface"], "backdrop_focal_geometry": ""})
    st.put("code", "design_elements", [{"element_id": e["id"], "motif_type": defaults.guess_primitive(e["what"]),
                                        "geometry": S.cut(e.get("geometry") or e["what"], 60),
                                        "visual_cues": S.cut(e["where"], 60),
                                        "source": e["source"] if e.get("source") in sc.IMAGE_LABELS else "ELEMENTS_REF"}
                                       for e in nd["elements"]["midground"] + nd["elements"]["foreground"]][:5])
    return log + log2


# --------------------------------------------------------------------------- A2: the layout plan
def a2_enums(st: S.State) -> tuple[list, list, list]:
    d = st["doc"]
    return ([s["section_id"] for s in d["content_sections"]],
            [e["id"] for k in ("background", "midground", "foreground") for e in d["elements"][k]],
            [c["name"] for c in d["colors"]])


def after_a2(st: S.State, out: dict) -> list:
    st.merge("a2", out)
    lp, d, log = out["layout_plan"], st["doc"], []
    sids, eids, names = (set(x) for x in a2_enums(st))
    fb = defaults.layout_plan(d)["layout_plan"]
    cv = lp.get("canvas") or {}
    canvas = {"content_width_px": int(spatial.clamp(cv.get("content_width_px") or 1200, 960, 1440)),
              "gutter_px": int(spatial.clamp(cv.get("gutter_px") or 24, 0, 64)),
              "canvas_use": S.cut(cv.get("canvas_use", ""), 300)}
    secs, seen = [], set()
    for s in lp.get("sections") or []:
        if s.get("section_id") in sids and s["section_id"] not in seen:
            seen.add(s["section_id"])
            surf = s.get("surface") if s.get("surface") in names else d["role_names"]["bg_primary"]
            secs.append({"section_id": s["section_id"], "layout": S.cut(s.get("layout", ""), 400),
                         "size": S.cut(s.get("size", ""), 160), "surface": surf,
                         "responsive": S.cut(s.get("responsive", ""), 200)})
    for s in fb["sections"]:
        if s["section_id"] not in seen:
            secs.append(s)
            _log(log, f"plan.section {s['section_id']}", None, "default", "A2 left this section unplanned")
    order = [s["section_id"] for s in d["content_sections"]]
    secs.sort(key=lambda s: order.index(s["section_id"]))
    hero = next(s["section_id"] for s in d["content_sections"] if s["role"] == "hero")
    group_z = S.layer_of(d)
    lays, seen = [], set()
    for L in lp.get("layers") or []:
        if L.get("element_id") in eids and L["element_id"] not in seen:
            seen.add(L["element_id"])
            z = L.get("z")
            if z not in sc.DECOR_Z:                    # z10 is the text layer: decor there gets painted over words
                _log(log, f"layer {L['element_id']}.z", z, group_z[L["element_id"]][1],
                     "decoration never shares the text layer; it goes to its A1 group's layer")
                z = group_z[L["element_id"]][1]
            lays.append({"element_id": L["element_id"], "z": z,
                         "anchor": L.get("anchor") if L.get("anchor") in sids else hero,
                         "placement": S.cut(L.get("placement", ""), 260), "notes": S.cut(L.get("notes", ""), 160)})
    for L in fb["layers"]:
        if L["element_id"] not in seen:
            lays.append(L)
    st.put("code", "plan", {"canvas": canvas, "sections": secs, "layers": lays})
    return log


# --------------------------------------------------------------------------- A3: the copy
def readable(colors: list[dict], surface: dict, cur: dict, need: float, log: list, token: str, added: list) -> dict:
    """A text colour that reads on the surface: the chosen one, else the best palette colour, else a pushed one."""
    import guardrails as g
    if g.contrast(cur["hex"], surface["hex"]) >= need:
        return cur
    pool = colors + added
    ok = [c for c in pool if g.contrast(c["hex"], surface["hex"]) >= need]
    if ok:
        best = max(ok, key=lambda c: (c["group"] == "text_color", g.contrast(c["hex"], surface["hex"])))
        _log(log, token, cur["name"], best["name"], f"{cur['hex']} on {surface['hex']} is "
                                                   f"{g.contrast(cur['hex'], surface['hex']):.2f}:1, needs {need}:1")
        return best
    hx = g.push_to_contrast(cur["hex"], surface["hex"], need)
    nm = f"{cur['name']} on {surface['name']}"
    c = {"name": nm, "hex": hx, "group": "text_color", "usage": f"readable text on {surface['name']}",
         "var": "--c-" + slug(nm, 24)}
    added.append(c)
    _log(log, token, cur["name"], nm, f"no palette colour reaches {need}:1 on {surface['name']}; adjusted to {hx}")
    return c


def after_a3(st: S.State, out: dict) -> list:
    st.merge("a3", out)
    c, d, log = out["copy"], st["doc"], []
    sids = [s["section_id"] for s in d["content_sections"]]
    role_of = {s["section_id"]: s["role"] for s in d["content_sections"]}
    hero = next(s for s in sids if role_of[s] == "hero")
    cards = {x["card_id"] for x in d["strategic_cards"]}
    items, ids, used_cards = [], set(), set()
    for x in c.get("items") or []:
        k = x.get("kind")
        if k not in sc.COPY_KINDS or x.get("section_id") not in sids:
            continue
        text = plain(S.cut(x.get("text", ""), CAPS[k])) if CAPS[k] else ""
        if k == "card":
            if x.get("card_id") not in cards or x["card_id"] in used_cards:
                _log(log, f"item {x.get('item_id')}", x.get("card_id"), None, "no such strategic card (A1 owns them)")
                continue
            used_cards.add(x["card_id"])
        elif not text:
            continue
        href = (x.get("href") or "").strip()
        href = href if re.fullmatch(r"#[A-Za-z0-9_-]*|mailto:[^\s\"'<>]+", href) else "#top"
        items.append({"item_id": _unique(slug(x.get("item_id") or k, 32), ids), "section_id": x["section_id"],
                      "kind": k, "level": x.get("level") if x.get("level") in sc.LEVELS else LEVEL_OF[k],
                      "text": text, "href": href, "card_id": x.get("card_id", "") if k == "card" else ""})
    h1s = [x for x in items if x["kind"] == "h1"]
    for x in h1s[1:]:
        x["kind"] = "h2"
        _log(log, x["item_id"], "h1", "h2", "one h1 per page")
    if not h1s:
        cand = next((x for x in items if x["kind"] == "h2" and x["section_id"] == hero), None)
        if cand:
            cand["kind"] = "h1"
            _log(log, cand["item_id"], "h2", "h1", "the hero's headline is the page's h1")
        else:
            items.insert(0, {"item_id": _unique("h1", ids), "section_id": hero, "kind": "h1", "level": "display",
                             "text": S.cut(c.get("brand") or st["meta"]["full_query"], 90), "href": "#top", "card_id": ""})
            _log(log, "h1", None, "added", "a page needs one h1")
    colors = d["colors"]
    by_name = {x["name"]: x for x in colors}
    rn = d["role_names"]
    given = {x.get("section_id"): x for x in c.get("section_colors") or [] if x.get("section_id") in sids}
    plan_surf = {s["section_id"]: s["surface"] for s in st["plan"]["sections"]}
    added, scols = [], []
    for sid in sids:
        g_ = given.get(sid) or {}
        pick = lambda key, role: by_name.get(g_.get(key)) or by_name[rn[role]]  # noqa: E731
        surface = by_name.get(g_.get("surface")) or by_name.get(plan_surf.get(sid)) or by_name[rn["bg_primary"]]
        text = readable(colors, surface, pick("text", "text_body"), 4.5, log, f"{sid}.text", added)
        heading = readable(colors, surface, pick("heading", "text_top_heading"), 3.0, log, f"{sid}.heading", added)
        scols.append({"section_id": sid, "surface": surface["name"], "text": text["name"], "heading": heading["name"],
                      "accent": pick("accent", "overlay_primary")["name"]})
    st.put("code", "copy_final", {"brand": S.cut(c.get("brand") or st["meta"].get("brand") or "", 40), "items": items,
                                  "section_colors": scols, "added_colors": added})
    return log


# --------------------------------------------------------------------------- A4: the decor assets
def after_a4(st: S.State, out: dict) -> list:
    st.merge("a4", out)
    dec, d, log = out["decor"], st["doc"], []
    allowed = sorted({x["hex"] for x in d["colors"] + st["copy_final"]["added_colors"]} | set(st["palette_final"].values()))
    eids = set(a2_enums(st)[1])
    assets, seen = [], set()
    for a in dec.get("assets") or []:
        eid = a.get("element_id")
        if eid not in eids or eid in seen:
            continue
        kind = a.get("kind") if a.get("kind") in sc.DECOR_KINDS else "svg"
        if kind == "svg":
            body, notes = V.clean_svg(a.get("svg", ""), allowed, eid)
        else:
            body, notes = V.clean_css(a.get("css", ""), allowed)
        for n in notes:
            _log(log, f"decor {eid}", kind, None if not body else kind, n)
        if not body:
            continue
        seen.add(eid)
        assets.append({"element_id": eid, "kind": kind, "svg": body if kind == "svg" else "",
                       "css": body if kind == "css" else "", "anchor": S.cut(a.get("anchor", ""), 120),
                       "placement": S.cut(a.get("placement", ""), 240),
                       "opacity": round(spatial.clamp(a.get("opacity") or 1, 0.1, 1), 2), "notes": S.cut(a.get("notes", ""), 160)})
    st.put("code", "decor_final", {"intent": dec.get("intent") if dec.get("intent") in sc.INTENTS else "subtle",
                                   "assets": assets})
    return log


def spec(st: S.State) -> dict:
    return S.assemble_doc_spec(st)


# --------------------------------------------------------------------------- defaults (agents off / agent failed)
def default_doc(h: dict) -> dict:
    return defaults.design_doc(h)


def default_plan(st: S.State) -> dict:
    return defaults.layout_plan(st["doc"])


def default_copy(st: S.State, h: dict) -> dict:
    return defaults.copy(h, st)


def default_decor(st: S.State) -> dict:
    return defaults.decor(st["doc"], st["plan"])


def deterministic(h: dict) -> tuple[S.State, dict, list]:
    """Every agent at its default -> (state, A5 spec, overrides). No model, no network."""
    st, log = S.State(h), []
    log += after_a1(st, default_doc(h), h)
    log += after_a2(st, default_plan(st))
    log += after_a3(st, default_copy(st, h))
    log += after_a4(st, default_decor(st))
    return st, spec(st), log


# --------------------------------------------------------------------------- the deterministic fallback page
def _view(fs: S.State) -> dict:
    return {k: fs[k] for k in ("layout_spec", "background_spec", "palette", "strategic_cards", "design_elements")}


def legacy_copy(st: S.State) -> dict[str, list]:
    """A3's copy -> the fallback layout's slots: {legacy kind: [item, ...]} in page order."""
    d = st["doc"]
    role_of = {s["section_id"]: s["role"] for s in d["content_sections"]}
    out: dict[str, list] = {}
    for x in st["copy_final"]["items"]:
        role, k = role_of[x["section_id"]], x["kind"]
        lk = None
        if k in ("logo", "nav_link", "h1", "card"):
            lk = k
        elif k == "cta":
            lk = "cta"
        elif k == "eyebrow" and role == "hero":
            lk = "eyebrow"
        elif k == "paragraph" and role == "hero":
            lk = "subheading"
        elif k in ("h2", "quote") and role not in ("hero", "nav", "cards"):
            lk = "intro_heading"
        elif k == "paragraph" and role not in ("hero", "nav", "cards", "footer"):
            lk = "intro_body"
        if lk:
            out.setdefault(lk, []).append(x)
    return out


def _fallback_state(st: S.State, h: dict, decorate: bool) -> tuple[S.State, list]:
    from .spatial import agent_areas, scene_for_agent
    fs, log = S.State(h), []
    for k in LEGACY_KEYS:
        fs.put("code", k, st[k])
    used = S.uses_bg_image(fs["background_spec"], fs["assets"])
    fb2 = defaults.a2(_view(fs), bg_image=used)
    wg, l1 = spatial.normalize_wireframe(fb2["wireframe_grid"], fb2["wireframe_grid"], used)
    fs.put("code", "wireframe", wg)
    fs.put("code", "wireframe_default", copy.deepcopy(wg))
    d3 = defaults.a3(h, _view(fs), {"wireframe_grid": wg})
    by_kind = legacy_copy(st)
    items = []
    for x in d3["content_layer"]["items"]:
        if x["kind"] == "card":
            if any(c["card_id"] == x["card_id"] for c in by_kind.get("card", [])):
                items.append(x)
            continue
        if x["kind"] == "centerpiece":
            if st["doc"]["centerpiece"]["use"]:
                items.append({**x, "text": S.cut(st["doc"]["centerpiece"]["description"], 110) or x["text"]})
            continue
        src = by_kind.get(x["kind"])
        if src:
            y = src.pop(0)
            items.append({**x, "text": y["text"], "href": y["href"] if y["href"].startswith("#") else x["href"]})
        elif x["kind"] == "h1":
            items.append(x)
    L = fs["layout_spec"]
    cl, l2 = spatial.normalize_content({**d3["content_layer"], "brand": st["copy_final"]["brand"], "items": items}, wg,
                                       fs["pairs"], d3, has_centerpiece=st["doc"]["centerpiece"]["use"],
                                       has_bg_image=used, card_ids=[c["card_id"] for c in fs["strategic_cards"]],
                                       fb_wireframe=wg, hero_style=L["hero"], nav_style=L["nav"])
    fs.put("code", "content", cl)
    scn = spatial.scene(wg, cl, fs["facts"]["type_scale"], fs["type_system"],
                        {c["card_id"]: c for c in fs["strategic_cards"]})
    fs.put("code", "scene", scn)
    ol, l3, plc = {"motifs": []}, [], {}
    if decorate:
        a4 = defaults.a4(_view(fs), scene_for_agent(scn), agent_areas(scn))
        ol, l3, plc = spatial.enforce_overlays(a4["overlay_layer"], scn, fs["palette_final"], cl, wg)
    for k, v in (("wireframe_final", wg), ("content_final", cl), ("scene_final", scn), ("overlay", ol),
                 ("placements", plc)):
        fs.put("code", k, v)
    return fs, l1 + l2 + l3


def fallback(st: S.State, h: dict, decorate: bool = True) -> tuple[dict, list]:
    """The compile_spec page: A1's palette + type, A3's copy, the default layout (+ conservative decoration)."""
    fs, log = _fallback_state(st, h, decorate)
    return S.assemble_spec(fs), log


def safe(st: S.State, h: dict) -> tuple[dict, list]:
    """The last resort, known to be clean: the fallback page without any decoration."""
    sp, log = fallback(st, h, decorate=False)
    return sp, [{"token": "page", "from": "spec", "to": "safe spec", "why": "the last resort: default layout, A3's "
                 "copy, no decoration"}] + log
