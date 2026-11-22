"""brief.py - lab output (route_engine.lab) -> DesignBrief v1, the contract the site agent consumes.

What this adds on top of route_engine.payload():
  * sections come from the FULL query (domain axis), not the vibe query the lab was given, and follow a
    landing-page narrative order;
  * a `taste` block: the niche the request names (prompt_context / niche_scores; else the category's niche closest
    to the routed vibe), the routed vibe's taste_affinity score for it, a clash flag and the vibes to avoid;
  * guardrails (worker/guardrails.py) on colour roles, fonts and type scale, each change logged in
    `typography.overrides` (token, from, to, why);
  * portable assets: ref_id = sha1(fam/id)[:12], served as assets/<ref_id>.<ext>; local paths never leave here.
"""
from __future__ import annotations

import hashlib
import json
import os
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
# the lab's p1 root (same variable as context_clusters.SERPMAN_P1); the Windows default is this PC's D: layout
CREAM = Path(os.getenv("SERPMAN_P1", r"D:\serpman_data\ui_drafts\p1")) / "context-cream"
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


# ---------------------------------------------------------------- the request's niche
# A niche is read from the REQUEST (CLIP: full query vs each niche's own example search queries + its cues), not
# from the routed family. Picking it from the family's affinity alone made a mis-routed family choose a niche that
# agreed with it (sports-high-energy -> "Street food / cloud kitchen", sticker-style, for a banana-bread bakery).
NICHE_MARGIN = 0.03        # the request's best niche must beat its runner-up by this much (cosine) to be trusted
_niche_ex = None


def _niche_exemplars(enc):
    global _niche_ex
    if _niche_ex is None:
        rows, texts = [], []
        for c in tc.CATEGORIES:
            for i, v in enumerate(c.values):
                for t in (v.main, v.alt, f"{v.name}: {v.cues}"):
                    rows.append((c.key, i))
                    texts.append(t)
        _niche_ex = (rows, enc(texts))
    return _niche_ex


def niche_scores(enc, full_query: str) -> dict[str, list[float]]:
    """{category: [best exemplar similarity of the request, per niche]} for every category (the split's
    category_hint may still change the category after this)."""
    rows, T = _niche_exemplars(enc)
    sims = T @ enc([full_query])[0]
    out = {c.key: [-1.0] * len(c.values) for c in tc.CATEGORIES}
    for (k, i), s in zip(rows, sims):
        out[k][i] = max(out[k][i], round(float(s), 4))
    return out


def prompt_context(enc, full_query: str) -> dict:
    """What the request itself says, for build_brief's `sections_src`: section_plan's category (keyword / CLIP)
    plus the request's niche scores. Every caller (worker, lab bench, tools) builds the brief through this."""
    src = sp.suggest(enc, full_query)
    src["niche_scores"] = niche_scores(enc, full_query)
    return src


def request_niche(scores: list[float] | None) -> int | None:
    """Index of the niche the request clearly names, or None when it is ambiguous / unknown."""
    if not scores:
        return None
    order = sorted(range(len(scores)), key=lambda j: -scores[j])
    if len(order) == 1 or scores[order[0]] - scores[order[1]] >= NICHE_MARGIN:
        return order[0]
    return None


def taste_block(category_key: str, category_name: str, how: str, family: str,
                niche_scores: list[float] | None = None) -> dict:
    """The niche = the one the request names (niche_how 'prompt'); when the request is ambiguous, the category's
    niche closest to the routed family (niche_how 'family'). affinity / clash / avoid always rate the routed family
    against THAT niche, so a family that fights the request shows up as a clash."""
    v = VIBE_BY_FAMILY.get(family)
    cat = CATEGORY[category_key]
    i = request_niche(niche_scores)
    niche_how = "prompt" if i is not None else "family"
    if v is None:
        niche = cat.values[i] if i is not None else None
        return {"category": category_key, "category_name": category_name, "how": how,
                "niche": niche.name if niche else None, "niche_cues": niche.cues if niche else None,
                "niche_how": niche_how, "affinity": 0.0, "clash": False, "avoid": []}
    A = affinity()
    if i is None:
        i = max(range(len(cat.values)), key=lambda j: A[(v.key, f"{cat.key}/{j}")])
    niche, best = cat.values[i], A[(v.key, f"{cat.key}/{i}")]
    avoid = sorted(((A[(k, f"{cat.key}/{i}")], k) for k in VIBE_NAME if k != v.key), key=lambda t: t[0])
    return {"category": cat.key, "category_name": cat.name, "how": how, "niche": niche.name,
            "niche_cues": niche.cues, "niche_how": niche_how, "affinity": round(float(best), 2),
            "clash": bool(best < 0), "avoid": [VIBE_NAME[k] for s, k in avoid if s <= -0.3][:6]}


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
        p = local_dest(d) if d else None
        return p if p and p.exists() else None
    return resolve


def local_dest(d: str) -> Path:
    """A manifest's absolute `dest` from the machine that built the cream layer -> a path that exists here: unchanged
    when it exists (this PC), else rebased onto this machine's CREAM (the data moved, e.g. to a Linux server)."""
    p = Path(d)
    if p.exists():
        return p
    parts = re.split(r"[\\/]", d)
    return CREAM.joinpath(*parts[parts.index("context-cream") + 1:]) if "context-cream" in parts else p


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
# CLIP zero-shot "contains text" score = mean sim(5 text prompts) - mean sim(5 no-text prompts), on the stored
# image embeddings. Calibrated 2026-11-20 over 10,427 cream images: type specimens median +0.019, 3D renders -0.052,
# abstract art -0.060; the three known text-baked listing graphics from the Dew run scored -0.001..+0.017.
# The pixel detector (lines/hmax) flagged ~80% of 3D renders, so CLIP is used whenever the worker provides it.
CLIP_TEXT_T = -0.02
TEXT_POS = ["a graphic with a large text headline", "a poster with big typography",
            "a product listing image with a title banner", "a screenshot of a page full of text",
            "a flyer with printed words"]
TEXT_NEG = ["a 3d render with no text", "an illustration with no words", "an abstract artwork without any text",
            "a photograph without any text", "a clean image with no lettering"]


def clip_text_scores(enc, E):
    """CLIP zero-shot 'contains text' score per image row of E (unit CLIP image embeddings); enc = the same CLIP's
    text tower. Shared by worker.Engine and the serpman lab's compose bench, so both filter identically."""
    P, N = enc(TEXT_POS), enc(TEXT_NEG)
    return (E @ P.T).mean(1) - (E @ N.T).mean(1)


def texty(reading) -> str | None:
    """reading = {"clip": score} (worker) or (lines, hmax) (lab colour cache) -> reason if the image carries text."""
    if reading is None:
        return None
    if isinstance(reading, dict):
        s = reading["clip"]
        return f"CLIP reads baked-in text ({s:+.3f} > {CLIP_TEXT_T})" if s > CLIP_TEXT_T else None
    lines, hmax = reading
    if lines > MAX_TEXT_LINES:
        return f"{int(lines)} text lines detected"
    if hmax > MAX_TEXT_HEIGHT:
        return f"a text block {hmax:.0%} of the image height (headline banner)"
    return None


# Query relevance: only images that show what the site is about go ON the page; the rest stay style references
# (A1 reads them for shapes, colour and finish; A5 recreates the components). score = mean CLIP similarity of the
# image to the request's subject (site words stripped) minus its similarity to neutral design prompts.
# Calibrated 2026-11-22 on contact sheets for six requests: images that show the subject score >= +0.028 (a cafe
# interior for a coffee roastery, a spa bathroom for skincare, packaging +0.141); the lab's picks for
# "A wisconsin puppy website" (kawaii icons, a game score card) scored -0.075..-0.130, and nothing in the corpus
# shows a puppy (best: a glass bear, +0.020).
REL_T = 0.025
REL_NEUTRAL = ["a website", "a web page design", "a graphic design", "an image", "a picture", "an abstract pattern",
               "a user interface", "an illustration"]
SITE_WORDS = re.compile(r"\b(website|web ?site|site|landing page|home ?page|web ?page|page|app|online store|e-?shop)\b",
                        re.I)


def query_subject(query: str) -> str:
    """'A wisconsin puppy website' -> 'A wisconsin puppy' (the word 'website' would pull site screenshots)."""
    return re.sub(r"\s+", " ", SITE_WORDS.sub(" ", query or "")).strip(" ,.-") or (query or "")


def neutral_base(enc, E):
    return (E @ enc(REL_NEUTRAL).T).mean(1)


def relevance_scores(enc, E, query: str, base=None):
    """Per image row of E (unit CLIP image embeddings): similarity to the request's subject minus the neutral
    baseline (pass base = neutral_base(enc, E) to reuse it). Shared by the worker and the lab bench."""
    s = query_subject(query)
    P = enc([s, f"a picture of {s}", f"an illustration of {s}"])
    return (E @ P.T).mean(1) - (neutral_base(enc, E) if base is None else base)


def clean_central(o: dict, text_lines, over: list, relevance=None) -> list[dict]:
    """Central graphics go ON the page, so drop any with baked-in text (marketplace listings, posters, mockups)
    and refill from the lab's own ranked candidates. text_lines(fam, id) -> (lines, hmax) or None.
    relevance(fam, id) -> score or None: when no pick shows the request's subject, the most relevant text-free lab
    candidate that clears REL_T joins first; off-subject picks stay as style references (build_brief marks on_page)."""
    el = o.get("el") or {}
    picks = (el.get("central") or {}).get("picks") or o["payload"]["elements"].get("central") or []
    cands = [c for c in (el.get("central") or {}).get("cands", []) if c not in picks]
    free = (lambda c: True) if text_lines is None else (lambda c: texty(text_lines(c["fam"], c["id"])) is None)
    used = {(p["fam"], p["id"]) for p in picks}
    out = []
    for p in picks:
        why = None if text_lines is None else texty(text_lines(p["fam"], p["id"]))
        if why is None:
            out.append(p)
            continue
        repl = next((c for c in cands if (c["fam"], c["id"]) not in used and free(c)), None)
        over.append({"token": f"central:{p.get('role', '')}", "from": p["id"], "to": repl["id"] if repl else None,
                     "why": f"{why} (baked-in text); "
                            + ("next text-free lab candidate used" if repl else "no text-free candidate, dropped")})
        if repl:
            used.add((repl["fam"], repl["id"]))
            out.append({**repl, "role": p.get("role", "supporting")})
    rel = (lambda c: relevance(c["fam"], c["id"])) if relevance else None
    if rel is None or any((rel(p) if rel(p) is not None else -1) >= REL_T for p in out):
        return out
    used |= {(p["fam"], p["id"]) for p in out}
    scored = [(s, c) for c in cands if (c["fam"], c["id"]) not in used and free(c)
              for s in [rel(c)] if s is not None and s >= REL_T]
    if scored:
        s, best = max(scored, key=lambda x: x[0])
        over.append({"token": "central:relevant", "from": None, "to": best["id"],
                     "why": f"no lab pick shows the request's subject; a candidate at relevance {s:+.3f} goes on the page"})
        out.insert(0, {**best, "role": "primary"})
    return out


FOLDER_PER_CLUSTER = 3     # best + 2 alternates from each of the family's cluster folders
FOLDER_MAX = 18


def build_brief(o: dict, *, query: str, split: dict, sections_src: dict, job_id: str | None = None,
                theme: str = "auto", resolve=None, text_lines=None, folder_sections: list | None = None,
                sections_override: list[str] | None = None, relevance=None) -> tuple[dict, dict[str, Path]]:
    """-> (brief, {ref_id: local file}). `sections_src` = prompt_context(enc, full_query) (section_plan's category +
    the request's niche scores; a bare section_plan.suggest dict still works and falls back to the family niche).
    text_lines(fam, id) (the worker passes the lab's ColorStore reading) enables the baked-in-text filter.
    folder_sections = route_engine.route(...)["in_family"]: the best images of each cluster folder of the routed
    family; they become `section` assets the composer places by cluster type."""
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
    if sections_override:
        sections = [{"id": s, "layer": sp.SECTIONS[s][0], "purpose": sp.SECTIONS[s][1]}
                    for s in dict.fromkeys(sections_override) if s in sp.SECTIONS]
    else:
        sections = sections_for(cat_key, split.get("must_sections") or [])

    # Palette: at least two valid swatches, padded from the family's colour DNA, then neutrals.
    hexok = lambda s: isinstance(s, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", s)  # noqa: E731
    swatches = [s for s in ((p.get("palette") or {}).get("swatches") or []) if hexok(s)]
    if len(swatches) < 2:
        pad = [s for s in (p.get("family_dna") or []) if hexok(s)] + ["#FFFFFF", "#111111"]
        over.append({"token": "palette", "from": len(swatches), "to": "padded",
                     "why": "the lab returned fewer than 2 usable swatches; padded from the family DNA / neutrals"})
        swatches = list(dict.fromkeys(swatches + pad))[:6]
    roles, derived, visuals, o_col = g.colour_roles(swatches, p.get("color_tokens") or {}, theme)
    # Fonts: the lab's pair when it produced one, else a safe serif/sans pair (logged).
    f = o.get("fonts") or {}
    lab_fonts = p.get("fonts") or {}
    lab_head = (lab_fonts.get("heading") or {}).get("family") or "Fraunces"
    lab_body = (lab_fonts.get("body") or {}).get("family") or "DM Sans"
    if not lab_fonts:
        over.append({"token": "fonts", "from": None, "to": f"{lab_head} / {lab_body}",
                     "why": "the lab returned no font pair for this run; using a safe default pair"})
    heading, body, italic, o_font = g.pick_fonts([s["name"] for s in f.get("shortlist", []) if "name" in s],
                                                 [s["name"] for s in f.get("body_cands", []) if "name" in s],
                                                 lab_head, lab_body, v.get("cues") or "")
    scale, o_scale = g.type_scale(lab_fonts.get("tokens") or {}, landing=True)
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
        item = {"ref_id": rid, "role": role, "fam": ref["fam"], "id": ref["id"], "cluster": ref.get("cluster", ""),
                "type": typ, "note": note, "path": f"assets/{rid}.webp"}   # assets.py re-encodes to webp
        if text_lines is not None:
            item["text"] = texty(text_lines(ref["fam"], ref["id"])) is not None
        if relevance is not None and role in ("central", "background"):
            s = relevance(ref["fam"], ref["id"])
            if s is not None:
                item["relevance"] = round(float(s), 3)
                item["on_page"] = bool(s >= REL_T)
                if not item["on_page"]:
                    over.append({"token": f"{role}:on_page", "from": ref["id"], "to": "style reference only",
                                 "why": f"not about the request (relevance {s:+.3f} < {REL_T:+.3f}); the agents "
                                        "read it for style, the page never shows it"})
        assets.append(item)
        files[rid] = local

    add(p.get("layout"), "layout", "website", "layout reference: follow its structure, never copy its text")
    bg = p.get("background") or {}
    add(bg if bg.get("id") else None, "background", bg.get("cluster"), f"L0 background ({bg.get('approach')})")
    el = p.get("elements") or {}
    add(el.get("hero_ref"), "hero", "website", "hero reference")
    for c in clean_central(o, text_lines, over, relevance):
        add(c, "central", c.get("type"), f"{c.get('role')} central graphic")
    add(p.get("palette"), "palette", "palette", "palette source image")
    n_folder = 0
    for best in folder_sections or []:
        if not best:
            continue
        for ref in [best, *best.get("alts", [])][:FOLDER_PER_CLUSTER]:
            if n_folder >= FOLDER_MAX:
                break
            before = len(assets)
            add(ref, "section", ref.get("type") or best.get("type"), f"folder section: {best.get('cluster')}")
            n_folder += len(assets) - before

    brief = {
        "meta": {"version": 1, "job_id": job_id, "query": query[:300], "full_query": split["full_query"][:300],
                 "vibe_query": split["vibe_query"][:300], "routed_family": fam,
                 "router": (p.get("router") or {}).get("version", "v1"), "pi_log": p.get("pi_log", []),
                 "lab_ms": int(o.get("ms", 0)), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "taste": taste_block(cat_key, cat_name, how, fam, (sections_src.get("niche_scores") or {}).get(cat_key)),
        "vibe": {"key": vibe.key if vibe else fam, "name": v["name"], "cues": v["cues"], "effect": v["effect"]},
        "tokens": {"color": {k: val for k, val in roles.items()}, "derived": derived, "type": scale,
                   "contrast": g.contrast_report(roles), "palette": [s.upper() for s in swatches],
                   "family_dna": [s.upper() for s in (p.get("family_dna") or []) if hexok(s)]},
        "fonts": {"heading": {"family": heading, "category": g.font_catalog().get(heading, {}).get("category", ""),
                              "color": "var(--text)", "google_css": g.google_css(heading, italic)},
                  "body": {"family": body, "category": g.font_catalog().get(body, {}).get("category", ""),
                           "color": "var(--text)", "google_css": g.google_css(body, False)},
                  "pairing": {"lab": [lab_head, lab_body],
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
