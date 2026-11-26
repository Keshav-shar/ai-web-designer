"""handoff.py - a lab run -> what the agents may know and choose from (no model).

build() takes the job's ONE DesignBrief (brief.build_brief from brief.prompt_context, built by the caller: the worker's
Engine.recipe, the lab bench, the fixture tools; never rebuilt here, so the agents see exactly the brief the job
recorded; its `sections` are ignored: this path makes one thematic landing page) and derives:
  meta     query (full + vibe), brand, family, niche / avoid, vibe name / cues / effect
  facts    measured alignment, type scale + roles, the lab's font pair and colour tokens
  enums    every real hex the lab measured or derived, every catalogue font the lab shortlisted
  images   the five labelled references for A1 (BACKGROUND / LAYOUT / PALETTE / ELEMENTS / TYPOGRAPHY), with metadata
  assets   page-eligible images (text-free central graphics, the background) as assets/<ref_id>.webp: only images
           that show the request's subject (brief on_page); the rest inspire the agents' own components
Colour role pairs that pass WCAG are computed after A1 assigns roles (role_pairs / repair_palette).
"""
from __future__ import annotations

import re
from pathlib import Path

import brief as B
import guardrails as g

from . import schemas as sc

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_HEX, MAX_FONTS = 24, 16
# Families never offered to or kept from the agents (the user's call, R0 2026-11-26: Monofett's pill letters read as a
# smeared bold at every size and were unreadable on buttons and headings). Lower-case names.
BLOCKED_FONTS = {"monofett"}


def blocked(family: str) -> bool:
    return (family or "").strip().strip("'\"").lower() in BLOCKED_FONTS


def image_size(path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return None


def _hexes(*groups) -> list[str]:
    out = []
    for grp in groups:
        for h in grp or []:
            if isinstance(h, str) and HEX.match(h):
                out.append(h.upper())
    return list(dict.fromkeys(out))[:MAX_HEX]


def build(o: dict, split: dict, brief: dict, files: dict, *, theme: str = "auto", resolve=None,
          text_lines=None) -> dict:
    """o = route_engine.lab() output; split = {full_query, vibe_query, brand_name, audience, category_hint};
    (brief, files) = brief.build_brief(o, ..., sections_src=brief.prompt_context(enc, full_query)) for this job."""
    t = brief["tokens"]
    pal = o.get("palette") or {}
    hexes = _hexes(t["color"].values(), t["derived"].values(), t["palette"], t["family_dna"],
                   brief["typography"].get("visuals"), [s.get("hex") for s in (pal.get("chosen") or {}).get("sw", [])],
                   [d.get("hex") for d in pal.get("dna", [])])
    for must in ("#FFFFFF", "#000000"):          # die-cut outlines / inverse text always need a neutral option
        if must not in hexes:
            hexes.append(must)

    f = o.get("fonts") or {}
    pair = [brief["fonts"]["heading"]["family"], brief["fonts"]["body"]["family"]]
    cands = [x.get("name") for x in f.get("shortlist", [])] + [x.get("name") for x in f.get("body_cands", [])]
    cands += [x.get("name") for x in (o.get("template") or {}).get("names", []) if x.get("slug")]
    pool = font_pool(pair, cands)
    fonts = list(pool)

    def ref_of(fam, id_, cluster="", typ=None, note=""):
        local = resolve(fam, id_) if resolve else None
        if local is None:
            return None
        reading = text_lines(fam, id_) if text_lines else None
        return {"ref_id": B.ref_id(fam, id_), "fam": fam, "id": id_, "cluster": cluster, "type": typ or cluster,
                "text": B.texty(reading) is not None if reading is not None else None,
                "text_score": (reading or {}).get("clip"), "local": str(local), "note": note}

    by_role = {}
    for a in brief["assets"]:
        by_role.setdefault(a["role"], []).append(a)
    images = {}
    for label, role in (("BACKGROUND_REF", "background"), ("LAYOUT_REF", "layout"), ("PALETTE_REF", "palette")):
        a = (by_role.get(role) or [None])[0]
        if a:
            images[label] = ref_of(a["fam"], a["id"], a["cluster"], a.get("type"), a.get("note") or "")
    central = by_role.get("central") or []
    el = next((a for a in central if "primary" in (a.get("note") or "") and not a.get("text")), None) \
        or next((a for a in central if not a.get("text")), None) or (central or [None])[0]
    if el:
        images["ELEMENTS_REF"] = ref_of(el["fam"], el["id"], el["cluster"], el.get("type"), "primary central graphic")
    for s in (o.get("typography") or {}).get("sheets", [])[:1]:
        images["TYPOGRAPHY_REF"] = ref_of(s["fam"], s["id"], s.get("cluster", "type specimen"), "type specimen",
                                          "the family's font-pairing / type-specimen sheet")
    images = {k: v for k, v in images.items() if v}
    for label, im in images.items():                # role, image name and use travel with every image (sc.IMAGE_ROLES)
        role, image, use = sc.ROLE_OF_LABEL[label]
        im.update(role=role, image=image, use=use)

    assets = []
    for a in brief["assets"]:        # on_page False: not about the request -> an A1 reference only, never on the page
        if a["role"] in ("central", "background") and a["ref_id"] in files and a.get("on_page", True):
            wh = image_size(files[a["ref_id"]])          # the frame A5 builds follows the image's real proportions
            assets.append({"ref_id": a["ref_id"], "role": a["role"], "type": a.get("type"), "cluster": a["cluster"],
                           "fam": a["fam"], "id": a["id"], "text": bool(a.get("text")), "path": a["path"],
                           "note": a.get("note"), "local": str(files[a["ref_id"]]), "relevance": a.get("relevance"),
                           "width": wh[0] if wh else None, "height": wh[1] if wh else None})
    v = brief["vibe"]
    ta = brief["taste"]
    return {
        "meta": {"query": split["full_query"], "full_query": split["full_query"], "vibe_query": split["vibe_query"],
                 "brand": split.get("brand_name"), "audience": split.get("audience"),
                 "family": brief["meta"]["routed_family"], "category": ta["category"],
                 "category_name": ta["category_name"], "niche": ta.get("niche"), "niche_cues": ta.get("niche_cues"),
                 "avoid": ta.get("avoid", []), "vibe": {"name": v["name"], "cues": v["cues"], "effect": v["effect"]},
                 "theme": theme},
        "facts": {"alignment": brief["typography"].get("alignment", "left"), "type_scale": t["type"],
                  "type_roles": brief["typography"]["roles"],
                  "fonts": {"heading": brief["fonts"]["heading"]["family"], "body": brief["fonts"]["body"]["family"]},
                  "lab_tokens": {**t["color"], **t["derived"]},
                  "layout_measure": o.get("layout_measure")},
        "enums": {"hex": hexes, "fonts": fonts or pair},
        "font_pool": pool,
        "images": images,
        "assets": assets,
        "brief": brief,
    }


# --------------------------------------------------------------------------- the font pool
BUFFER = 8                      # extra families beyond the lab's pair, for the wordmark / accent / misc roles
CORE_CATEGORIES = ["Serif", "Sans Serif", "Display", "Handwriting", "Monospace"]


def font_info(family: str) -> dict:
    """Catalogue facts A1 needs to choose well: category, the weights the family really has, italic, style tags."""
    c = g.font_catalog().get(family, {})
    styles = c.get("styles", set())
    weights = sorted({int(s.rstrip("i")) for s in styles if s.rstrip("i").isdigit()}) or [400]
    tags = [t.rsplit("/", 1)[-1].lower() for t in c.get("tags", [])][:5]
    return {"category": c.get("category", ""), "weights": weights, "italic": any(s.endswith("i") for s in styles),
            "tags": list(dict.fromkeys(tags))}


def font_pool(pair: list[str], candidates: list[str]) -> dict[str, dict]:
    """The lab's pair + a buffer of up to BUFFER more families from the lab's own candidates, picked round-robin by
    category so the type system can vary its levels; topped up from the catalogue only for a missing core category."""
    cat = g.font_catalog()
    out = [n for n in dict.fromkeys(pair) if n in cat and not blocked(n)]
    rest = [n for n in dict.fromkeys(candidates) if n and n in cat and n not in out and not blocked(n)]
    by_cat: dict[str, list[str]] = {}
    for n in rest:
        by_cat.setdefault(cat[n]["category"], []).append(n)
    buf = []
    while len(buf) < BUFFER and any(by_cat.values()):
        for k in list(by_cat):                       # one per category per round: diversity before depth
            if by_cat[k] and len(buf) < BUFFER:
                buf.append(by_cat[k].pop(0))
    have = {cat[n]["category"] for n in out + buf}
    for k in [c for c in CORE_CATEGORIES if c not in have and c != "Monospace"][:2]:
        top = sorted((n for n, v in cat.items() if v["category"] == k and n not in out + buf and not blocked(n)),
                     key=lambda n: cat[n].get("popularity", 9999))[:1]
        buf += top
    return {n: font_info(n) for n in out + buf}


CATEGORY_WORDS = [("Monospace", ("mono", "typewriter", "code")),
                  ("Handwriting", ("script", "hand", "brush", "cursive", "calligraph", "swash")),
                  ("Serif", ("serif", "didone", "slab", "garalde", "old style", "transitional", "blackletter",
                             "gothic")),
                  ("Display", ("display", "decorative", "poster", "groovy", "stencil")),
                  ("Sans Serif", ("sans", "grotesk", "grotesque", "geometric", "humanist", "neo-grotesque"))]


def guess_category(text: str) -> str | None:
    t = (text or "").lower()
    if "sans" in t:
        return "Sans Serif"
    return next((cat for cat, words in CATEGORY_WORDS if any(w in t for w in words)), None)


def resolve_font(name: str, pool: dict[str, dict], hint: str = "") -> tuple[str, str | None]:
    """A family name an agent wrote -> a real Google Fonts family (-> (family, note or None)). Any catalogue family
    is allowed; an unknown name becomes its closest catalogue spelling, else the pool face of the category the
    description suggests (hint = classification / traits), else the pool's first face."""
    import difflib
    cat = g.font_catalog()
    lower = {k.lower(): k for k in cat}
    n = (name or "").strip().strip("'\"")
    if blocked(n):
        want = guess_category(hint) or (cat.get(lower.get(n.lower(), ""), {}) or {}).get("category")
        pick = next((f for f, i in pool.items() if want and i.get("category") == want and not blocked(f)), None)             or next((f for f in pool if not blocked(f)), "Inter")
        return pick, f"'{n}' is blocked (unreadable when set heavy); {pick} stands in"
    if n.lower() in lower:
        return lower[n.lower()], None
    close = difflib.get_close_matches(n.lower(), list(lower), n=1, cutoff=0.86)
    if close:
        return lower[close[0]], f"'{n}' is spelled '{lower[close[0]]}' in the catalogue"
    want = guess_category(f"{n} {hint}")
    pick = next((f for f, i in pool.items() if want and i.get("category") == want), None) or next(iter(pool), "Inter")
    return pick, f"'{n}' is not a Google Fonts family; {pick} ({want or 'pool'}) stands in"


def snap_weight(family: str, weight) -> str:
    """The family's real weight closest to the requested one (a missing weight is faked by the browser)."""
    ws = font_info(family)["weights"]
    try:
        w = int(str(weight))
    except ValueError:
        w = 400
    return str(min(ws, key=lambda x: (abs(x - w), -x)))


# --------------------------------------------------------------------------- colour roles after A1
BODY, DISPLAY = 4.5, 3.0


def role_pairs(palette: dict[str, str]) -> dict[str, float]:
    """'text_role/surface_role' -> contrast ratio, for every pair that reaches at least 3:1."""
    out = {}
    for tr in sc.TEXT_ROLES:
        for sr in sc.SURFACE_ROLES:
            r = g.contrast(palette[tr], palette[sr])
            if r >= DISPLAY:
                out[f"{tr}/{sr}"] = round(r, 2)
    return out


REQUIRED = [("text_body", "bg_primary", BODY), ("text_top_heading", "bg_primary", DISPLAY),
            ("text_subheading", "bg_primary", BODY), ("text_body", "bg_secondary", BODY),
            ("text_inverse", "cta_fill", BODY)]


def repair_palette(palette: dict[str, str]) -> tuple[dict[str, str], list[dict]]:
    """Make the pairs every landing page needs pass, moving only the text colour (guardrails.push_to_contrast)."""
    p, log = dict(palette), []
    for fg, bg, target in REQUIRED:
        if g.contrast(p[fg], p[bg]) < target:
            new = g.push_to_contrast(p[fg], p[bg], target)
            log.append({"token": fg, "from": p[fg], "to": new,
                        "why": f"{fg} on {bg} was {g.contrast(p[fg], p[bg]):.2f}:1, needs {target}:1"})
            p[fg] = new
    return p, log
