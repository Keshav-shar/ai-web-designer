"""brief.py - lab output (route_engine.lab) -> DesignBrief v1, the contract the site agent consumes.

What this adds on top of route_engine.payload():
  * sections come from the FULL query (domain axis), not the vibe query the lab was given, and follow a
    landing-page narrative order;
  * a `taste` block from taste_affinity at runtime: the category's best niche for the routed vibe, its score,
    a clash flag and the vibes to avoid (the matrix was only used offline before);
  * guardrails (worker/guardrails.py) on colour roles, fonts and type scale, each change logged in
    `typography.overrides` (token, from, to, why);
  * portable assets: ref_id = sha1(fam/id)[:12], served as assets/<ref_id>.<ext>; local paths never leave here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import guardrails as g
from labio import lab_path

lab_path()
import section_plan as sp  # noqa: E402  (serpman)
import taste_affinity as ta  # noqa: E402
import taste_catalog as tc  # noqa: E402

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
CREAM = Path(r"D:\serpman_data\ui_drafts\p1\context-cream")
_schema = None
_affinity = None


def slug(s: str) -> str:                      # same rule as context_clusters.slug
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "cluster"


VIBE_BY_FAMILY = {slug(v.name): v for v in tc.VIBES}
VIBE_NAME = {v.key: v.name for v in tc.VIBES}
CATEGORY = {c.key: c for c in tc.CATEGORIES}

# Landing narrative: where each section sits. Category modules (not listed) go between features and testimonials.
ORDER_HEAD = ["announce_bar", "nav", "hero", "social_proof", "features"]
ORDER_TAIL = ["testimonials", "pricing", "faq", "cta_band", "footer"]


def schema() -> dict:
    global _schema
    if _schema is None:
        _schema = json.loads((CONTRACTS / "design_brief.v1.json").read_text(encoding="utf-8"))
    return _schema


def affinity() -> dict:
    global _affinity
    if _affinity is None:
        _affinity = ta.affinity_matrix(tc.CATEGORIES, tc.VIBES)
    return _affinity


def sections_for(category_key: str, must: list[str]) -> list[dict]:
    mods = [s for s in sp.BY_CATEGORY.get(category_key, []) if s not in ORDER_HEAD + ORDER_TAIL]
    tail = [s for s in ORDER_TAIL if s in sp.UNIVERSAL or s in sp.BY_CATEGORY.get(category_key, [])]
    extra = [s for s in must if s in sp.SECTIONS and s not in ORDER_HEAD + mods + tail]
    ids = list(dict.fromkeys(ORDER_HEAD + mods + extra + tail + ["overlay_fx"]))
    return [{"id": s, "layer": sp.SECTIONS[s][0], "purpose": sp.SECTIONS[s][1]} for s in ids]


def taste_block(category_key: str, category_name: str, how: str, family: str) -> dict:
    v = VIBE_BY_FAMILY.get(family)
    cat = CATEGORY[category_key]
    if v is None:
        return {"category": category_key, "category_name": category_name, "how": how, "niche": None,
                "niche_cues": None, "affinity": 0.0, "clash": False, "avoid": []}
    A = affinity()
    scores = [(A[(v.key, f"{cat.key}/{i}")], val) for i, val in enumerate(cat.values)]
    best, niche = max(scores, key=lambda t: t[0])
    i = cat.values.index(niche)
    avoid = sorted(((A[(k, f"{cat.key}/{i}")], k) for k in VIBE_NAME if k != v.key), key=lambda t: t[0])
    return {"category": cat.key, "category_name": cat.name, "how": how, "niche": niche.name,
            "niche_cues": niche.cues, "affinity": round(float(best), 2), "clash": bool(best < 0),
            "avoid": [VIBE_NAME[k] for s, k in avoid if s <= -0.3][:6]}


def ref_id(fam: str, id_: str) -> str:
    return hashlib.sha1(f"{fam}/{id_}".encode()).hexdigest()[:12]


def cream_resolver():
    """(fam, id) -> local file, from the cream manifests (the worker passes the in-memory Index instead)."""
    cache: dict[str, dict] = {}

    def resolve(fam: str, id_: str) -> Path | None:
        if fam not in cache:
            mf = CREAM / fam / "manifest.json"
            cache[fam] = ({it["id"]: it["dest"] for it in json.loads(mf.read_text(encoding="utf-8"))["files"]}
                          if mf.exists() else {})
        d = cache[fam].get(id_)
        return Path(d) if d and Path(d).exists() else None
    return resolve


def typography_roles(lab_typo: dict | None, heading: str, body: str, italic: bool, scale: dict) -> dict:
    """Role map in the new fonts and scale; keeps the lab's case / tracking / alignment readings."""
    lab_roles = (lab_typo or {}).get("roles", {})
    top = max(int(k.split("-")[-1]) for k in scale if k.startswith("--fs-"))
    plan = {"eyebrow": (body, "--fs-1", 500, False), "h1": (heading, f"--fs-{top}", 500, italic),
            "h2": (heading, f"--fs-{max(2, top - 2)}", 500, italic), "h3": (heading, f"--fs-{max(2, top - 4)}", 500, False),
            "body": (body, "--fs-1", 400, False), "small": (body, "--fs-1", 400, False)}
    out = {}
    for role, (font, size, weight, it) in plan.items():
        lr = lab_roles.get(role, lab_roles.get("h2" if role == "h3" else "body", {}))
        out[role] = {"font": font, "size_token": size, "weight": weight, "italic": it,
                     "text_transform": lr.get("text_transform", "uppercase" if role == "eyebrow" else "none"),
                     "letter_spacing": lr.get("letter_spacing", "0.1em" if role == "eyebrow" else "0em"),
                     "color_token": "--text-muted" if role in ("eyebrow", "small") else "--text"}
    return {"alignment": (lab_typo or {}).get("alignment", {}).get("value", "left"),
            "measure_ch": 66, "roles": out}


MAX_TEXT_LINES = 3      # same threshold the lab's background "mine" filter uses (palette_lab BASE["T"])
MAX_TEXT_HEIGHT = 0.15  # one text box taller than 15% of the image = a headline banner baked into the graphic


def texty(reading) -> str | None:
    """reading = (lines, hmax) from the lab's colour cache -> reason string if the image carries text."""
    if reading is None:
        return None
    lines, hmax = reading
    if lines > MAX_TEXT_LINES:
        return f"{int(lines)} text lines detected"
    if hmax > MAX_TEXT_HEIGHT:
        return f"a text block {hmax:.0%} of the image height (headline banner)"
    return None


def clean_central(o: dict, text_lines, over: list) -> list[dict]:
    """Central graphics go ON the page, so drop any with baked-in text (marketplace listings, posters, mockups)
    and refill from the lab's own ranked candidates. text_lines(fam, id) -> (lines, hmax) or None."""
    el = o.get("el") or {}
    picks = (el.get("central") or {}).get("picks") or o["payload"]["elements"].get("central") or []
    if text_lines is None:
        return picks
    cands = [c for c in (el.get("central") or {}).get("cands", []) if c not in picks]
    used = {(p["fam"], p["id"]) for p in picks}
    out = []
    for p in picks:
        why = texty(text_lines(p["fam"], p["id"]))
        if why is None:
            out.append(p)
            continue
        repl = next((c for c in cands if (c["fam"], c["id"]) not in used
                     and texty(text_lines(c["fam"], c["id"])) is None), None)
        over.append({"token": f"central:{p.get('role', '')}", "from": p["id"], "to": repl["id"] if repl else None,
                     "why": f"{why} (baked-in text); "
                            + ("next text-free lab candidate used" if repl else "no text-free candidate, dropped")})
        if repl:
            used.add((repl["fam"], repl["id"]))
            out.append({**repl, "role": p.get("role", "supporting")})
    return out


def build_brief(o: dict, *, query: str, split: dict, sections_src: dict, job_id: str | None = None,
                theme: str = "auto", resolve=None, text_lines=None) -> tuple[dict, dict[str, Path]]:
    """-> (brief, {ref_id: local file}). `sections_src` = section_plan.suggest(enc, full_query).
    text_lines(fam, id) (the worker passes the lab's ColorStore reading) enables the baked-in-text filter."""
    import jsonschema
    p = o["payload"]
    fam = p["family"]
    v = p.get("vibe") or {"name": fam, "cues": "", "effect": ""}
    vibe = VIBE_BY_FAMILY.get(fam)
    over: list[dict] = []

    cat_key, cat_name, how = sections_src["category"], sections_src["category_name"], sections_src["how"]
    hint = split.get("category_hint")
    if hint in CATEGORY and hint != cat_key:
        over.append({"token": "category", "from": cat_key, "to": hint, "why": "split's category_hint (domain read by the model)"})
        cat_key, cat_name, how = hint, CATEGORY[hint].name, "hint"
    sections = sections_for(cat_key, split.get("must_sections") or [])

    roles, derived, visuals, o_col = g.colour_roles(p["palette"]["swatches"], p["color_tokens"], theme)
    f = o.get("fonts", {})
    heading, body, italic, o_font = g.pick_fonts([s["name"] for s in f.get("shortlist", [])],
                                                 [s["name"] for s in f.get("body_cands", [])],
                                                 p["fonts"]["heading"]["family"], p["fonts"]["body"]["family"], v["cues"])
    scale, o_scale = g.type_scale(p["fonts"]["tokens"], landing=True)
    over += o_col + o_font + o_scale

    files: dict[str, Path] = {}
    assets = []
    resolve = resolve or cream_resolver()

    def add(ref, role, typ=None, note=None):
        if not ref:
            return
        rid = ref_id(ref["fam"], ref["id"])
        if any(a["ref_id"] == rid for a in assets):
            return
        local = resolve(ref["fam"], ref["id"])
        if local is None:
            return
        assets.append({"ref_id": rid, "role": role, "fam": ref["fam"], "id": ref["id"], "cluster": ref.get("cluster", ""),
                       "type": typ, "note": note, "path": f"assets/{rid}.webp"})   # assets.py re-encodes to webp
        files[rid] = local

    add(p["layout"], "layout", "website", "layout reference: follow its structure, never copy its text")
    bg = p.get("background") or {}
    add(bg if bg.get("id") else None, "background", bg.get("cluster"), f"L0 background ({bg.get('approach')})")
    el = p.get("elements") or {}
    add(el.get("hero_ref"), "hero", "website", "hero reference")
    for c in clean_central(o, text_lines, over):
        add(c, "central", c.get("type"), f"{c.get('role')} central graphic")
    add(p.get("palette"), "palette", "palette", "palette source image")

    brief = {
        "meta": {"version": 1, "job_id": job_id, "query": query[:300], "full_query": split["full_query"][:300],
                 "vibe_query": split["vibe_query"][:300], "routed_family": fam,
                 "router": (p.get("router") or {}).get("version", "v1"), "pi_log": p.get("pi_log", []),
                 "lab_ms": int(o.get("ms", 0)), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "taste": taste_block(cat_key, cat_name, how, fam),
        "vibe": {"key": vibe.key if vibe else fam, "name": v["name"], "cues": v["cues"], "effect": v["effect"]},
        "tokens": {"color": {k: val for k, val in roles.items()}, "derived": derived, "type": scale,
                   "contrast": g.contrast_report(roles), "palette": [s.upper() for s in p["palette"]["swatches"]],
                   "family_dna": [s.upper() for s in p.get("family_dna", [])]},
        "fonts": {"heading": {"family": heading, "category": g.font_catalog().get(heading, {}).get("category", ""),
                              "color": "var(--text)", "google_css": g.google_css(heading, italic)},
                  "body": {"family": body, "category": g.font_catalog().get(body, {}).get("category", ""),
                           "color": "var(--text)", "google_css": g.google_css(body, False)},
                  "pairing": {"lab": [p["fonts"]["heading"]["family"], p["fonts"]["body"]["family"]],
                              "heading_italic": italic}},
        "typography": {**typography_roles(p.get("typography"), heading, body, italic, scale), "overrides": over,
                       "visuals": visuals},
        "layers": {"L0": "background: mesh gradient from visuals or the background asset",
                   "L1": "navigation + footer", "L2": "hero + content sections",
                   "L3": f"overlay effect: {v['effect']} (pointer-events none, reduced-motion safe)"},
        "sections": sections,
        "assets": assets,
    }
    jsonschema.validate(brief, schema())
    return brief, files
