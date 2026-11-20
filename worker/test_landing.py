"""test_landing.py - offline checks for the landing-page agent pipeline (no keys, no quota, no network calls to models).

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe worker\\test_landing.py [--qa]

Uses the recorded lab runs in fixtures/landing (tools/landing_fixture.py), a design document transcribed from a
hand-run example (fixtures/landing/doc_1976.json) and fake providers that answer like models would (valid JSON, then
hostile HTML), to exercise routing, the design-document contracts, budgets, repair, cache, the gate and fallbacks.
--qa also runs the Playwright browser checks (slower; needs network for Google Fonts).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="landing_test_", dir=r"D:\caches\tmp"))
os.environ["LANDING_CACHE"] = str(TMP / "cache")
os.environ["LANDING_LEDGER"] = str(TMP / "quota.json")
os.environ["LANDING_OUT"] = str(TMP / "out")
os.environ["LANDING_ENV_FILE"] = str(TMP / "no-such.env")        # never read the real worker/.env keys in tests
for _k in [k for k in os.environ if k.startswith(("GEMINI_API_KEY", "GROQ_API_KEY"))]:
    os.environ.pop(_k)
os.environ["GEMINI_API_KEY"] = "fake-gemini"
os.environ["GROQ_API_KEY"] = "fake-groq"

import brief as B  # noqa: E402
import split as SP  # noqa: E402
from landing import (budget, cache, compile_spec, flow, handoff, keys, pipeline, providers,  # noqa: E402
                     schemas as sc, state as S, validate_page)

NOTES: list[str] = []
keys.notify = NOTES.append                      # capture the terminal lines instead of printing them

FIX = HERE.parent / "fixtures" / "landing"
FAILS: list[str] = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def load(name):
    d = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    res = {k: Path(v) for k, v in d["resolve"].items()}
    sp = SP.fallback(d["q"])
    sp["vibe_query"] = d["q"]
    resolve = lambda f, i: res.get(f"{f}/{i}")  # noqa: E731
    text_lines = lambda f, i: {"clip": d["text"][f"{f}/{i}"]} if f"{f}/{i}" in d["text"] else None  # noqa: E731
    # fixtures carry no CLIP encoder: the recorded lab sections stand in for brief.prompt_context
    brief, files = B.build_brief(d["o"], query=sp["full_query"], split=sp, sections_src=d["o"]["sections"],
                                 resolve=resolve, text_lines=text_lines)
    return handoff.build(d["o"], sp, brief, files, resolve=resolve, text_lines=text_lines)


def doc_1976() -> dict:
    d = json.loads((FIX / "doc_1976.json").read_text(encoding="utf-8"))
    d.pop("$comment", None)
    return d


def render_doc_page(spec: dict, cover_h1_with: str | None = None) -> str:
    """A plain but valid composition of a design-document spec (what a model page must at least provide)."""
    T = spec["typography"]
    css = [":root{" + ";".join(f"{k}:{v}" for k, v in spec["css_vars"].items()) + "}",
           f"body{{margin:0;font-family:{T['body']['stack']};color:var(--text-body);background:var(--bg-primary)}}",
           '[data-layer="z0"]{position:fixed;inset:0;z-index:0}[data-layer="z0"] img{width:100%;height:100%;object-fit:cover}',
           ".s{position:relative;z-index:10;max-width:1100px;margin:0 auto;padding:40px 24px}",
           f"h1,h2,h3{{font-family:{T['display']['stack']};margin:0 0 12px}}img{{max-width:100%}}",
           ".d{position:relative;width:120px;height:120px;margin:8px 0}.ov{position:absolute;inset:0;z-index:20}"]
    bg = spec["background"].get("image")
    out = ['<div data-layer="z0" aria-hidden="true">' + (f'<img src="{escape(bg)}" alt="">' if bg else "") + "</div>"]
    svgs = {x["element_id"]: x["asset"]["svg"] for x in spec.get("decor", []) if (x.get("asset") or {}).get("kind") == "svg"}
    placed = set()
    for s in spec["sections"]:
        body = []
        for it in s.get("items", []):
            a = f'data-item="{escape(it["item_id"])}"'
            k = it["kind"]
            if k == "image":
                body.append(f'<img {a} src="{escape(it["src"])}" alt="{escape(it.get("alt", ""))}">')
            elif k == "card":
                c = it["card"]
                body.append(f'<article {a}><h3>{escape(c.get("heading", ""))}</h3><p>{escape(c.get("body", ""))}</p></article>')
            elif k == "h1":
                body.append(f"<h1 {a}>{escape(it['text'])}</h1>")
            elif k in ("logo", "nav_link", "cta"):
                body.append(f'<a {a} href="{escape(it.get("href", "#"))}">{escape(it.get("text", ""))}</a> ')
            elif k in ("h2", "h3"):
                body.append(f"<{k} {a}>{escape(it['text'])}</{k}>")
            else:
                body.append(f"<p {a}>{escape(it['text'])}</p>")
        if cover_h1_with and any(it["kind"] == "h1" for it in s.get("items", [])) and cover_h1_with in svgs:
            body.append(f'<div class="ov" data-layer="z20">{svgs[cover_h1_with]}</div>')
            placed.add(cover_h1_with)
        out.append(f'<section data-section="{escape(s["section_id"])}" class="s">{"".join(body)}</section>')
    rest = "".join(f'<div class="d" data-layer="z5">{v}</div>' for k, v in svgs.items() if k not in placed)
    out.append(f'<section class="s" aria-hidden="true">{rest}</section>')
    return f"<style>{''.join(css)}</style><body>{''.join(out)}</body>"


# --------------------------------------------------------------------------- fakes
class Calls:
    log: list[tuple[str, str]] = []


class FakeGemini:
    per_part_res = thinking = True
    # simulate: these keys' projects already used Flash's 20/day; "bad" is a revoked key
    quota_day = {("fake-gemini", "gemini-4-hydrogen"), ("g1", "gemini-4-hydrogen")}
    busy: set = set()                       # models that answer 503 (the router must move to the alternate)
    a5_attempts = 0
    a5_mode = "hostile_then_cover"

    def models(self, key):
        if key == "bad":
            raise providers.ProviderError("auth", "HTTP 400: key rejected")
        return ["gemini-4-hydrogen", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]   # lite / older listed, never used

    def generate(self, model, system, parts, *, key, schema=None, max_out=4096, temperature=0.2, **kw):
        Calls.log.append(("gemini", model, key))
        if key == "bad":
            raise providers.ProviderError("auth", "HTTP 400: key rejected")
        if (key, model) in self.quota_day:
            raise providers.ProviderError("quota_day", "GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        if model in self.busy:
            raise providers.ProviderError("overloaded", "HTTP 503: high demand (after the provider's own retries)")
        if schema is not None:                      # A1: a model-like variation on the default document
            FakeGemini.a1_parts = parts
            out = copy.deepcopy(flow.default_doc(H))
            out["strategic_cards"][0]["heading"] = "Neon nights, live"
            out["typography"]["display"]["family"] = "Not A Real Font"           # code resolves it to a real face
            if any("previous answer failed" in p.get("text", "") for p in parts):
                return providers.Reply(json.dumps(out), model, "STOP", {"in": 4000, "out": 900})
            bad = copy.deepcopy(out)
            bad["strategic_cards"][1]["card_id"] = "card_1"             # consistency failure -> repair call
            return providers.Reply(json.dumps(bad), model, "STOP", {"in": 4000, "out": 800})
        FakeGemini.a5_attempts += 1                 # A5: hostile first, then a page whose decor covers the h1
        spec = json.loads(parts[0]["text"].split("\n\nYour previous")[0])
        motif = (spec.get("motif_ids") or [None])[0]
        page = render_doc_page(spec, cover_h1_with=motif)
        if FakeGemini.a5_attempts == 1:
            page = page.replace("<body>", '<body><script>alert(1)</script><img src="https://evil.example/x.png" onerror="x()">'
                                          '<h1>A second, invented headline</h1>')
            page = page.replace(":root{", ":root{--evil:#123456;color:#123456;")
        return providers.Reply(page, model, "STOP", {"in": 5000, "out": 9000})


class FakeGroq:
    def __init__(self, buckets):
        self.buckets = buckets

    def models(self, key):
        return ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    def chat(self, model, messages, *, key, kid="", schema=None, name="out", max_out=2500, temperature=0.4, **kw):
        Calls.log.append(("groq", model, name, key))
        if key == "q1" and model == "openai/gpt-oss-120b":   # simulate: this org's minute window is full
            raise providers.ProviderError("rate", "Rate limit reached for model (TPM)", 30.0)
        st = STATE["st"]
        if name == "a2":
            out = flow.default_plan(st)
        elif name == "a3":
            out = flow.default_copy(st, H)
            items = out["copy"]["items"]
            h1 = next(x for x in items if x["kind"] == "h1")
            items.append(dict(h1, item_id="h1_again", text="A second headline"))          # -> demoted to h2
            sc0 = out["copy"]["section_colors"][0]
            sc0["text"] = sc0["surface"]                                                 # unreadable -> fixed
        else:
            out = flow.default_decor(st)
            if out["decor"]["assets"]:
                a = out["decor"]["assets"][0]
                a["svg"] = a["svg"].replace("<svg ", '<svg onload="x()" ', 1).replace(
                    "</svg>", '<script>alert(1)</script><circle r="3" fill="#123456"/></svg>')
        return providers.Reply(json.dumps(out), model, "stop", {"in": 1800, "out": 700, "cached": 400},
                               {"x-ratelimit-remaining-tokens": "7000", "x-ratelimit-reset-tokens": "1s"})


STATE: dict = {}


def patch():
    pipeline.Gemini, pipeline.Groq = FakeGemini, FakeGroq
    orig_put = S.State.put

    def spy_put(self, who, key, value):              # let the fake Groq agents see the run's blackboard
        orig_put(self, who, key, value)
        if key == "doc":
            STATE["st"] = self
    S.State.put = spy_put


# --------------------------------------------------------------------------- tests: contracts
def t_schemas(h):
    for name, s in (("a1", sc.a1()), ("a2", sc.a2(["nav", "hero"], ["bg-1"], ["Ink", "Paper"])),
                    ("a3", sc.a3(["nav", "hero"], ["Ink", "Paper"])), ("a4", sc.a4(["bg-1"]))):
        check(not sc.strict_problems(s), f"{name} schema is strict (all required, no extra properties)")
        check("$ref" not in json.dumps(sc.inline_refs(s)), f"{name} schema inlines for Gemini")
    check(len(h["enums"]["hex"]) >= 6 and len(h["enums"]["fonts"]) >= 2, "handoff enums: hexes + fonts")
    check(set(h["images"]) >= {"LAYOUT_REF", "PALETTE_REF", "ELEMENTS_REF"}, f"A1 images: {sorted(h['images'])}")


def t_fonts(h):
    pool = h["font_pool"]
    pair = [h["facts"]["fonts"]["heading"], h["facts"]["fonts"]["body"]]
    check(all(f in pool for f in pair) and len(pool) >= len(set(pair)) + 2, f"font pool = lab pair + buffer ({len(pool)})")
    check(all(i["weights"] for i in pool.values()), "every pool family lists its real weights")
    fam, note = handoff.resolve_font("fraunces", pool)
    check(fam == "Fraunces" and note is None, "any Google Fonts family is allowed (case-insensitive)")
    fam, note = handoff.resolve_font("Shrikhand", pool, "bold retro brush script")
    check(fam in pool and pool[fam]["category"] == "Handwriting" and note,
          f"an unknown family stands in from the pool by its described category ({fam})")
    one = next((f for f, i in pool.items() if len(i["weights"]) == 1), None)
    if one:
        w = pool[one]["weights"][0]
        check(handoff.snap_weight(one, 900 if w < 900 else 300) == str(w), f"weights snap to what {one} has ({w})")


def t_doc(h):
    """A1's descriptive document: free names and descriptions, checked hexes / fonts / ids."""
    st = S.State(h)
    log = flow.after_a1(st, doc_1976(), h)
    d = st["doc"]
    allowed = {x.upper() for x in h["enums"]["hex"]}
    extra = {c["hex"] for c in d["colors"]} - allowed - set(st["palette_final"].values())
    check(len(extra) <= sc.EXTRA_HEXES, f"at most {sc.EXTRA_HEXES} unmeasured colours survive ({len(extra)})")
    check(any("snapped to the nearest measured" in o["why"] for o in log), "further unmeasured colours are snapped (logged)")
    check(len({c["var"] for c in d["colors"]}) == len(d["colors"]) and all(c["var"].startswith("--c-") for c in d["colors"]),
          "every named colour gets its own CSS variable")
    check(d["typography"]["display"]["family"] == "Fraunces" and d["typography"]["body"]["family"] == "DM Sans",
          "A1's chosen catalogue fonts are kept")
    check(any(o["token"] == "typography.wordmark.family" for o in log), "a non-catalogue font is replaced (logged)")
    check([s["section_id"] for s in d["content_sections"]] == ["nav", "hero", "about", "highlights", "footer"],
          "A1's own sections are kept (not a fixed nav/hero/intro/cards)")
    check(len(d["elements"]["midground"]) == 3 and len(d["elements"]["foreground"]) == 2, "bespoke decor elements kept")
    check(st["background_spec"]["treatment"] == "none" and S.backdrop(st) is None, "A1 kept the photo off: no backdrop image")
    if any(a["role"] == "background" for a in h["assets"]):
        d2 = doc_1976()
        d2["background_layer"].update(use_background_image=True, treatment="tinted", alignment_mode="nuance_extract")
        st2 = S.State(h)
        flow.after_a1(st2, d2, h)
        b = S.backdrop(st2)
        check(b and b["abstract"] and b["path"].endswith("-soft.webp") and b["blur"],
              "an off-subject photo A1 chose to use is rendered abstracted (blurred derivative)")


def t_budget_fit(h):
    """Every Groq request fits its model's minute window: rich documents are trimmed, never rejected."""
    st = S.State(h)
    flow.after_a1(st, doc_1976(), h)
    big = copy.deepcopy(st["doc"])
    for k in ("background", "midground", "foreground"):
        for e in big["elements"][k]:
            e["what"] = (e["what"] + " ") * 12
    for s in big["content_sections"]:
        s["what"] = [w + " with a long elaborate description of its components" * 6 for w in s["what"]]
    st.d["doc"] = big
    NOTES.clear()
    s2 = sc.a2(*flow.a2_enums(st))
    r = pipeline.groq_request(st, "a2", s2, None, "openai/gpt-oss-120b")
    lim = budget.limits("openai/gpt-oss-120b")["tpm"] * budget.MARGIN
    check(r[3] + int(pipeline.MAX_OUT["a2"] * 0.6) <= lim, f"A2's request fits the minute window ({r[3]} tokens)")
    check(any("trimmed" in n for n in NOTES), "a too-rich slice is trimmed (and said so on the terminal)")
    st.d["doc"] = st["doc"] if False else big
    flow.after_a2(st, flow.default_plan(st))
    flow.after_a3(st, flow.default_copy(st, h))
    s4 = sc.a4(flow.a2_enums(st)[1])
    r = pipeline.groq_request(st, "a4", s4, None, "qwen/qwen3.8-27b")
    check(r[3] + int(pipeline.MAX_OUT["a4"] * 0.6) <= budget.limits("qwen/qwen3.8-27b")["tpm"] * budget.MARGIN,
          f"A4's request fits Qwen's window ({r[3]} tokens)")


def t_copy(h):
    st = S.State(h)
    flow.after_a1(st, doc_1976(), h)
    flow.after_a2(st, flow.default_plan(st))
    c = flow.default_copy(st, h)
    items = c["copy"]["items"]
    items.append(dict(next(x for x in items if x["kind"] == "h1"), item_id="dup", text="Another"))
    items.append({"item_id": "ghost", "section_id": "hero", "kind": "card", "level": "display", "text": "", "href": "#",
                  "card_id": "card_4"})
    c["copy"]["section_colors"][1]["text"] = c["copy"]["section_colors"][1]["surface"]
    log = flow.after_a3(st, c)
    cf = st["copy_final"]
    check(sum(x["kind"] == "h1" for x in cf["items"]) == 1 and any(o["why"] == "one h1 per page" for o in log),
          "a second h1 is demoted")
    check(not any(x["item_id"] == "ghost" for x in cf["items"]), "a card A1 never wrote is dropped")
    import guardrails as g
    names = {x["name"]: x["hex"] for x in st["doc"]["colors"] + cf["added_colors"]}
    s1 = cf["section_colors"][1]
    check(g.contrast(names[s1["text"]], names[s1["surface"]]) >= 4.5, "unreadable section text is replaced (WCAG 4.5:1)")
    c2 = flow.default_copy(st, h)
    c2["copy"]["items"] = [x for x in c2["copy"]["items"] if x["kind"] != "h1"]
    st2 = S.State(h)
    flow.after_a1(st2, doc_1976(), h)
    flow.after_a2(st2, flow.default_plan(st2))
    flow.after_a3(st2, c2)
    check(sum(x["kind"] == "h1" for x in st2["copy_final"]["items"]) == 1, "a missing h1 is the one element code adds")


def t_backoff():
    """A busy Gemini model (503) is retried on the same model with backoff before the router may switch."""
    import httpx
    calls, sleeps = [], []
    replies = [503, 503, 200]

    def handler(req):
        calls.append(str(req.url))
        code = replies.pop(0)
        if code != 200:
            return httpx.Response(code, json={"error": {"message": "This model is currently experiencing high demand."}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}],
                                         "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1}})
    g = providers.Gemini()
    g.http = httpx.Client(transport=httpx.MockTransport(handler))
    real_sleep = providers.time.sleep
    providers.time.sleep = sleeps.append
    try:
        r = g.generate("gemini-4-hydrogen", "sys", [{"text": "hi"}], key="k")
    finally:
        providers.time.sleep = real_sleep
    check(r.text == "ok" and len(calls) == 3 and all("gemini-4-hydrogen" in u for u in calls),
          f"503s are retried on the same model ({len(calls)} calls)")
    check(sleeps == list(providers.OVERLOAD_BACKOFF[:2]), f"with growing backoff ({sleeps})")


def t_svg():
    pal = ["#FFFFFF", "#E05A47", "#2B2B2B", "#DA9100"]
    raw = ('<svg width="200" height="100" onload="x()"><script>a()</script><foreignObject><div>x</div></foreignObject>'
           '<image href="http://x"/><use href="#a"/><path d="M0 0L5 5" fill="tomato" stroke="#123456"/></svg>')
    out, notes = validate_page.clean_svg(raw, pal, "m1")
    check(out.startswith("<svg") and 'data-motif="m1"' in out and 'viewBox="0 0 200.0 100.0"' in out,
          "an A4 svg gets its hook and a viewBox")
    check(not any(x in out for x in ("onload", "script", "foreignObject", "<image", "<use", "http")),
          "scripts, handlers, foreign objects and external refs are removed")
    check("tomato" not in out and "#123456" not in out and "<path" in out, "off-palette colours snap to the palette")
    check(validate_page.clean_svg("<div>no</div>", pal, "m2")[0] == "", "a non-svg asset is rejected")
    css, _ = validate_page.clean_css("background: radial-gradient(circle,#E15A40,transparent); z-index:99; "
                                     "background-image:url(http://x)", pal)
    check("z-index" not in css and "http" not in css and "#E05A47" in css, "an A4 CSS recipe is made safe")


def t_validate(h):
    st, spec, _ = flow.deterministic(h)
    page = render_doc_page(spec)
    clean = validate_page.check(page, spec)
    check(not clean["errors"], f"a composed design-document page conforms ({clean['errors']})")
    raw = page.replace("<body>", '<body><script>steal()</script><a href="https://x.example" onclick="y()">x</a>'
                                 '<img src="https://evil/a.png"><h1>Second</h1>').replace(":root{", ":root{color:#ABCDEF;") + \
        "<style>@import url(https://evil/x.css);.x{z-index:99}</style>"
    bad = validate_page.check(raw, spec)
    html = bad["html"]
    check("<script" not in html and "onclick" not in html and "https://x.example" not in html and "evil" not in html,
          "scripts, handlers, external links and images are stripped")
    check(any("#ABCDEF" in e for e in bad["errors"]), "a colour outside the palette is blocking")
    check(any("one <h1>" in e for e in bad["errors"]), "a second h1 is blocking")
    check(any("z-index" in e for e in bad["errors"]), "z-index outside 0-50 is blocking")
    stray = page.replace(":root{", ".x{color:black;background:rgba(0,0,0,.6);border:1px solid olive}:root{")
    fx = validate_page.check(stray, spec, fix_colors_=True)
    check(not fx["errors"] and any("snapped" in f for f in fx["fixes"]) and "color-mix(in srgb" in fx["html"],
          "stray colours on a model page are snapped to the palette by code (alpha kept), not a reason to discard it")
    miss = validate_page.check(page, {**spec, "copy": spec["copy"] + ["Never written"]})
    check(any("copy missing" in e for e in miss["errors"]), "missing copy is blocking")
    nosec = validate_page.check(page.replace('data-section="hero"', 'data-x="hero"'), spec)
    check(any("data-section missing: hero" in e for e in nosec["errors"]), "a section without its hook is blocking")
    if spec["motif_ids"]:
        nomotif = validate_page.check(page.replace("data-motif=", "data-x="), spec)
        check(not nomotif["errors"] and any("decor not on the page" in a for a in nomotif["advisories"]),
              "decor the composer left out is advisory, not blocking")
    fb, _ = flow.fallback(st, h)
    chk = validate_page.check(compile_spec.render(fb), fb)
    check(not chk["errors"], f"the fallback compile_spec page conforms ({chk['errors']})")
    safe, _ = flow.safe(st, h)
    chk = validate_page.check(compile_spec.render(safe), safe)
    check(not safe["motifs"] and not chk["errors"], "the safe page conforms, without decoration")
    h1 = next(x for x in st["copy_final"]["items"] if x["kind"] == "h1")["text"]
    check(h1 in chk["html"], "the fallback pages carry A3's copy")


def t_backdrop(h):
    if not any(a["role"] == "background" for a in h["assets"]):
        check(True, "no background asset in this fixture (skipped)")
        return
    d = flow.default_doc(h)
    d["background_layer"].update(use_background_image=True, treatment="photo_fill", alignment_mode="exact_adapt")
    st = S.State(h)
    flow.after_a1(st, d, h)
    flow.after_a2(st, flow.default_plan(st))
    flow.after_a3(st, flow.default_copy(st, h))
    flow.after_a4(st, flow.default_decor(st))
    spec = flow.spec(st)
    check(bool(spec["background"]["image"]), "the spec carries the backdrop A1 chose")
    page = render_doc_page(spec).replace(f'<img src="{spec["background"]["image"]}" alt="">', "")
    strict = validate_page.check(page, spec)
    check(any("background image" in e for e in strict["errors"]), "a page that drops it fails the strict check")
    fixed = validate_page.check(page, spec, inject_backdrop=True)
    check(not fixed["errors"] and fixed["fixes"] and 'data-injected="backdrop"' in fixed["html"],
          "the gate injects it instead of discarding the page")
    fb, _ = flow.fallback(st, h)
    chk = validate_page.check(compile_spec.render(fb), fb)
    check(not chk["errors"] and 'class="bg-img"' in chk["html"], "the fallback page shows it in z0 too")


def t_measure():
    """The browser measurements on synthetic layouts (no browser): each problem names its numbers."""
    from landing import qa as QA

    def item(i, box, lines=None, **kw):
        return {"id": i, "sec": "", "box": box, "lines": lines if lines is not None else [box], "pads": [0, 0],
                "content": [box[1], box[1] + box[3]], "painted": False, "card": False, "img": False, "imgbox": None,
                "wordmark": False, "font": {"family": "x", "size": 16, "weight": "400"}, **kw}
    spec = {"background": {"image": "assets/bg.webp"}, "layout": {"hero_section": "hero"},
            "levels": {"wordmark": {"family": "Bold Face", "weight": "800", "size_px": 31.2}},
            "items": [{"item_id": "logo", "kind": "logo"}, {"item_id": "card_1", "kind": "card"}]}
    data = {"items": [item("logo", [100, 20, 200, 30], font={"family": "Other, serif", "size": 16, "weight": "400"}),
                      item("card_1", [100, 900, 360, 500], pads=[28, 28], content=[928, 1040]),
                      item("h1", [100, 200, 300, 300], sec="hero"),
                      item("centerpiece", [430, 200, 140, 120], lines=[], img=True, imgbox=[430, 200, 140, 120], sec="hero")],
            "groups": [{"id": "intro", "box": [300, 1500, 800, 400], "pads": [0, 0], "content": [1500, 1900],
                        "painted": False, "kids": [[300, 1500, 800, 40], [300, 1556, 800, 40], [300, 1760, 800, 40]]}],
            "plates": [], "opaque": [],
            "motifs": [{"id": "m1", "layer": "z20", "relation": "", "target": "", "box": [0, 0, 1, 1],
                        "over": ["h1"], "overImg": [["centerpiece", 0.6]]},
                       {"id": "m2", "layer": "z5", "relation": "", "target": "", "box": [0, 0, 1, 1], "over": [], "overImg": []}],
            "bg": {"found": True, "shown": True, "opacity": 1, "cover": 1, "hidden": 5}, "scrollW": 1440, "innerW": 1440}
    probs = QA.analyze(data, spec, 1440)["problems"]
    for frag, what in (("m1 (z20) covers text of h1", "decoration painted over text"),
                       ("covers image centerpiece (60%", "decoration painted over an image"),
                       ("dead space: card_1", "an empty card bottom"), ("hero balance", "an image much shorter than the text"),
                       ("canvas coverage", "a hero using under half the width"),
                       ("gap outlier in intro", "an outsized gap inside a group"),
                       ("opaque surfaces hide", "a backdrop hidden behind opaque surfaces"),
                       ("wordmark: rendered in", "the wrong wordmark face"), ("wordmark: rendered at 16px", "a tiny wordmark")):
        check(any(frag in p for p in probs), f"measured: {what}")
    check(not any("m2" in p for p in probs), "decoration layered behind text is allowed")
    calm = {**data, "items": [item("h1", [100, 300, 900, 80])], "groups": [], "motifs": [], "bg": None}
    check(not QA.analyze(calm, {}, 1440)["problems"], "checks only apply when their case exists")
    chk = {"errors": ["colours not in the spec palette: #123456"], "advisories": ["decor not on the page: x"]}
    q = {1440: {"problems": ["text of a overlaps text of b", "motif m1 (z20) covers text of h1", "dead space: p is 9px"]}}
    c = pipeline.classify(chk, q)
    check(len(c["blocking"]) == 2 and c["fix_motifs"] == {"m1"} and len(c["advisory"]) == 2,
          "the gate classifies: blocking / fixed by code / advisory")


def t_state():
    h = load("neon-synthwave-music-festival")
    st = S.State(h)
    st.merge("a1", {"design_doc": flow.default_doc(h)})
    try:
        st.put("a2", "design_doc", {})
        check(False, "a2 writing a1's key is rejected")
    except S.WriteConflict:
        check(True, "a2 writing a1's key is rejected")
    try:
        st.put("code", "design_doc", {})
        check(False, "code overwriting an agent key is rejected")
    except S.WriteConflict:
        check(True, "code overwriting an agent key is rejected")


def t_budget():
    b = budget.Buckets()
    check(b.wait_for("openai/gpt-oss-120b", 9000) == float("inf"), "a request larger than the TPM is refused up front")
    b.note("openai/gpt-oss-120b", 6500)
    w = b.wait_for("openai/gpt-oss-120b", 2000)
    check(50 < w <= 60, f"a full minute window makes the next request wait ({w:.0f}s)")
    check(abs(budget._dur("2m59.56s") - 179.56) < 1e-6 and budget._dur("120ms") == 0.12, "Groq reset headers parse")


def t_image_roles(h):
    """A1 is told what every reference image is for, by role name, in the JSON and before each image."""
    st = S.State(h)
    roles = S.slice_for(st, "a1")["image_roles"]
    check(list(roles) == ["background", "layout", "palette", "elements", "typography"],
          f"image_roles lists the five roles in send order ({list(roles)})")
    check(roles["palette"]["image"] == "palette-image" and roles["palette"]["label"] == "PALETTE_REF"
          and roles["palette"]["present"] is True and roles["palette"]["position"] == 3,
          f"palette: palette-image, position 3 ({roles['palette']})")
    check(all(r["use"] for r in roles.values()), "every role says what the image is for")
    h2 = json.loads(json.dumps(h))
    h2["images"].pop("TYPOGRAPHY_REF", None)
    r2 = S.slice_for(S.State(h2), "a1")["image_roles"]
    check(r2["typography"]["present"] is False and "position" not in r2["typography"],
          "a missing reference is listed with present: false (and no position)")
    check(sc.image_header("PALETTE_REF", 3, "palette", False).startswith("[IMAGE 3 · palette: palette-image · PALETTE_REF]"),
          "image header format")


# --------------------------------------------------------------------------- tests: the run, with fake models
def t_pipeline_models(h, qa):
    Calls.log.clear()
    FakeGemini.a5_attempts = 0
    r = pipeline.run(h, enabled=True, qa=qa, log=lambda *a: None)
    tr = {}
    for t in r["trace"]:
        tr.setdefault(t["agent"], t)
    check(tr["a1"]["source"] == "repaired" and tr["a1"]["model"] == "gemini-3.8-flash",
          f"A1: Hydrogen daily quota -> 3.8 Flash (the only alternate), failed check -> one repair ({tr['a1'].get('source')}, {tr['a1'].get('model')})")
    check(budget.Ledger().left("gemini-4-hydrogen", keys.kid("fake-gemini"))["exhausted"],
          "the ledger marks Hydrogen exhausted for today, for that key")
    check(any("daily limit for gemini-4-hydrogen" in n and "no gemini key left" in n for n in NOTES),
          "single key: the terminal is told Hydrogen is out and why")
    check(any(n.startswith("models: A1 gemini-4-hydrogen -> gemini-3.8-flash") for n in NOTES), "the terminal names each agent's chain once")
    used = {c[1] for c in Calls.log}
    check(not any("lite" in m or m.endswith("-20b") or "3.7" in m for m in used), f"never a lite, small or older model ({sorted(used)})")
    a5m = [t["model"] for t in r["trace"] if t["agent"] == "a5" and t.get("model")]
    check(a5m and all(m == tr["a1"]["model"] for m in a5m), f"sticky: A5 stays on the model A1 used ({a5m})")
    check(all(tr[a]["source"] == "model" for a in ("a2", "a3", "a4")), "A2-A4 answered by their models")
    check(tr["a4"]["model"] == "qwen/qwen3.8-27b" and tr["a2"]["model"] == "openai/gpt-oss-120b", "Qwen on A4, gpt-oss on A2/A3")
    ov = [o["why"] for o in r["overrides"]]
    check(any("not a Google Fonts family" in w for w in ov), "A1's unknown font is replaced by a real one (logged)")
    check(any(w == "one h1 per page" for w in ov), "A3's second h1 is demoted (logged)")
    check(any("needs 4.5:1" in w or "reaches 4.5:1" in w for w in ov), "A3's unreadable colour is fixed (logged)")
    check(any("removed svg[onload]" in w or "<script>" in w for w in ov), "A4's svg is sanitized (logged)")
    cands = r["candidates"]
    check(len(cands) == 2 and cands[0]["blocking"] and not cands[1]["blocking"],
          f"A5: the hostile page is blocked, the repaired one ships ({[len(c['blocking']) for c in cands]})")
    check(r["page_source"] == "repaired" and all((Path(r["out"]) / c["file"]).exists() for c in cands),
          f"every candidate is kept on disk; the repaired page ships ({r['page_source']})")
    html = (Path(r["out"]) / "index.html").read_text(encoding="utf-8")
    check("<script" not in html and "evil.example" not in html and "#123456" not in html, "the final page is clean")
    check("Neon nights, live" in html, "A1's card copy reaches the page")
    if qa:
        check(any("removed decor that covered" in o["why"] for o in r["overrides"]),
              "decoration painted over the h1 is removed by code (the page still ships)")
        check(not any(c for p in r["qa"].values() for c in p["problems"] if "overlaps text" in c),
              "browser: no text overlaps on the shipped page")
    heads = [p["text"] for p in getattr(FakeGemini, "a1_parts", []) if "text" in p and p["text"].startswith("[IMAGE")]
    n_img = sum(1 for p in getattr(FakeGemini, "a1_parts", []) if "image" in p)
    check(len(heads) == n_img == len(h["images"]) and heads[2].startswith("[IMAGE 3 · palette: palette-image · PALETTE_REF]"),
          f"A1 got each image right after its role header ({heads[:1]}…)")
    a5_calls = [c for c in Calls.log if c[0] == "gemini"]
    n = len(Calls.log)
    r2 = pipeline.run(h, enabled=True, qa=False, log=lambda *a: None)
    check(len(Calls.log) == n, f"second run: 0 model calls ({len(Calls.log) - n})")
    check(all(t["source"] == "cache" for t in r2["trace"]), "second run: every agent from cache")
    html2 = (Path(r2["out"]) / "index.html").read_text(encoding="utf-8")
    check(qa or html2 == html, "cached run reproduces the page byte-for-byte")
    os.environ["AGENTS_REPLAY"] = os.environ["LANDING_CACHE"]
    r3 = pipeline.run(h, enabled=True, qa=False, log=lambda *a: None)
    check(len(Calls.log) == n and (Path(r3["out"]) / "index.html").read_text(encoding="utf-8") == html2,
          "AGENTS_REPLAY reproduces the run with no calls")
    os.environ.pop("AGENTS_REPLAY")
    r4 = pipeline.run(h, enabled=True, force_from="a3", qa=False, log=lambda *a: None)
    srcs = {t["agent"]: t["source"] for t in r4["trace"]}
    check(srcs["a1"] == "cache" and srcs["a2"] == "cache" and srcs["a3"] == "model", f"force_from=a3 re-runs only A3 onward ({srcs})")
    check(len(a5_calls) >= 2, "A5 was called (and repaired once)")
    # both Gemini models unavailable -> A1 is code's default document, with no fallback to another provider
    FakeGemini.busy = {"gemini-3.8-flash"}
    n0 = len(Calls.log)
    r5 = pipeline.run(h, enabled=True, force_from="a1", qa=False, a5_repair=False, log=lambda *a: None)
    t1 = next(t for t in r5["trace"] if t["agent"] == "a1")
    a1_calls = [c for c in Calls.log[n0:] if c[0] == "groq" and c[2] == "a1"]
    check(t1["source"] == "default" and not a1_calls, f"both Gemini models out: A1 uses the default document, no Groq ({t1['source']})")
    FakeGemini.busy = set()
    pipeline._PREFERRED.clear()


def t_keys_collect():
    saved = {k: os.environ.pop(k) for k in [k for k in os.environ if k.startswith(("GEMINI_API_KEY", "GROQ_API_KEY"))]}
    env_file = TMP / "keys.env"
    env_file.write_text("# test\nGROQ_API_KEY=from-file\nGEMINI_API_KEY_2=file-two\nSUPABASE_URL=ignored\n", encoding="utf-8")
    os.environ["LANDING_ENV_FILE"] = str(env_file)
    os.environ.update({"GEMINI_API_KEY": "a", "GEMINI_API_KEY_3": "c", "GEMINI_API_KEYS": "d, a ;e"})
    try:
        check(keys.collect("gemini") == ["a", "file-two", "c", "d", "e"],
              f"key order: X_API_KEY, X_API_KEY_2.., X_API_KEYS; env + file; duplicates dropped ({keys.collect('gemini')})")
        check(keys.collect("groq") == ["from-file"], "keys are read from the env file when the environment has none")
        check(keys.kid("a") != "a" and len(keys.kid("a")) == 8, "keys are only ever shown as a short hash")
    finally:
        for k in ("GEMINI_API_KEY", "GEMINI_API_KEY_3", "GEMINI_API_KEYS"):
            os.environ.pop(k, None)
        os.environ.update(saved)
        os.environ["LANDING_ENV_FILE"] = str(TMP / "no-such.env")


def t_multikey(h):
    """Several keys: a rejected key is skipped, a key out of Flash's daily quota hands over to the next key (not to
    3.8 Flash), a per-minute limit on Groq rotates keys, and every switch is announced on the terminal."""
    saved = {k: os.environ.pop(k) for k in ("GEMINI_API_KEY", "GROQ_API_KEY")}
    os.environ.update({"GEMINI_API_KEYS": "bad,g1,g2", "GROQ_API_KEYS": "q1,q2",
                       "LANDING_LEDGER": str(TMP / "quota_multi.json")})
    cache.ROOT = TMP / "cache_multi"
    pipeline._PREFERRED.clear()
    NOTES.clear()
    FakeGemini.a5_attempts = 0
    try:
        r = pipeline.run(h, enabled=True, qa=False, log=lambda *a: None)
        tr = {}
        for t in r["trace"]:
            tr.setdefault(t["agent"], t)
        check(tr["a1"]["model"] == "gemini-4-hydrogen" and tr["a1"].get("key") == "gemini key 3/3",
              f"A1 stays on Hydrogen via the third key ({tr['a1'].get('model')}, {tr['a1'].get('key')})")
        check(tr["a2"].get("key") == "groq key 2/2" and tr["a2"]["model"] == "openai/gpt-oss-120b",
              f"A2 rotates to the second Groq key on a per-minute limit ({tr['a2'].get('key')})")
        check(any("gemini key 1/3 was rejected" in n for n in NOTES), "terminal: rejected key announced")
        check(any("gemini key 2/3 reached its daily limit for gemini-4-hydrogen" in n and "-> using gemini key 3/3" in n
                  for n in NOTES), "terminal: daily limit + the key that takes over")
        check(any("groq key 1/2 hit the per-minute limit on openai/gpt-oss-120b -> using groq key 2/2" in n for n in NOTES),
              "terminal: per-minute limit + the key that takes over")
        check(not any(("bad" in n) or ("g1" in n) or ("q1" in n) for n in NOTES), "terminal lines never contain key values")
        q = r["ledger"].get("gemini-4-hydrogen", {})
        check(q.get("keys") == 3 and q.get("keys_out") == 1, f"quota summary across keys ({q})")
        NOTES.clear()
        n0 = len(Calls.log)
        pipeline.run(h, enabled=True, force_from="a1", qa=False, log=lambda *a: None)
        g1_again = [c for c in Calls.log[n0:] if c[0] == "gemini" and c[2] == "g1" and c[1] == "gemini-4-hydrogen"]
        check(not g1_again, "next run: the ledger skips the key that is out for today (no wasted call)")
    finally:
        for k in ("GEMINI_API_KEYS", "GROQ_API_KEYS"):
            os.environ.pop(k, None)
        os.environ.update(saved)
        os.environ["LANDING_LEDGER"] = str(TMP / "quota.json")
        cache.ROOT = TMP / "cache"


def t_doc_page_qa(h):
    """The 1976 document through A2-A4 defaults, composed plainly, then measured: nothing blocking."""
    from landing import qa as QA
    import assets as A
    st = S.State(h)
    flow.after_a1(st, doc_1976(), h)
    flow.after_a2(st, flow.default_plan(st))
    flow.after_a3(st, flow.default_copy(st, h))
    flow.after_a4(st, flow.default_decor(st))
    spec = flow.spec(st)
    chk = validate_page.check(render_doc_page(spec), spec, inject_backdrop=True)
    od = TMP / "doc1976"
    pipeline.write_site(od, chk["html"], spec, h, A)
    c = pipeline.classify(chk, QA.run(od / "index.html", spec=spec))
    check(not c["blocking"], f"a composed 1976-style page has nothing blocking ({c['blocking'][:2]})")


def main():
    qa = "--qa" in sys.argv
    names = sorted(p.stem for p in FIX.glob("*.json") if not p.stem.startswith("doc_"))
    check(len(names) >= 4, f"fixtures: {names}")
    global H
    for n in names:
        h = load(n)
        print(f"--- {n} ({h['meta']['family']})")
        t_schemas(h)
        t_fonts(h)
        t_image_roles(h)
        t_doc(h)
        t_budget_fit(h)
        t_copy(h)
        t_validate(h)
        t_backdrop(h)
        if qa:
            r = pipeline.run(h, enabled=False, qa=True, log=lambda *a: None)
            check(not any("overlaps text" in p or "overflow" in p for x in r["qa"].values() for p in x["problems"]),
                  f"agents-off page: nothing blocking in the browser ({n}, {r['page_source']})")
            t_doc_page_qa(h)
    t_svg()
    t_backoff()
    t_state()
    t_budget()
    t_measure()
    print("--- fake models (routing, repair, the design document, the A5 gate, cache, replay)")
    H = load(names[0])
    patch()
    t_pipeline_models(H, qa)
    print("--- several keys per provider (failover + terminal notices)")
    t_keys_collect()
    t_multikey(H)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'}")
    return 1 if FAILS else 0


H = None
if __name__ == "__main__":
    sys.exit(main())
