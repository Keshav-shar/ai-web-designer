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
import re
import os
import shutil
import sys
import tempfile
import time
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="landing_test_", dir=os.getenv("LANDING_TEST_TMP", r"D:\caches\tmp")))
os.environ["LANDING_CACHE"] = str(TMP / "cache")
os.environ["LANDING_LEDGER"] = str(TMP / "quota.json")
os.environ["LANDING_OUT"] = str(TMP / "out")
os.environ["LANDING_ENV_FILE"] = str(TMP / "no-such.env")        # never read the real worker/.env keys in tests
os.environ["LANDING_UNAVAIL"] = str(TMP / "unavailable.json")
for _k in [k for k in os.environ if k.startswith(("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
                                                   "OPENROUTER_API_KEY"))]:
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
    res = {k: B.local_dest(v) for k, v in d["resolve"].items()}     # recorded on this PC; rebased if the data moved
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

    rate_all = False                          # simulate: every Groq model's minute window is full (-> Mistral backup)

    def chat(self, model, messages, *, key, kid="", schema=None, name="out", max_out=2500, temperature=0.4, **kw):
        Calls.log.append(("groq", model, name, key))
        if FakeGroq.rate_all:
            raise providers.ProviderError("rate", "Rate limit reached for model (TPM)", 40.0)
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


class FakeMistral:
    """Mistral La Plateforme: lists aliases with capabilities; A1 gets interleaved [IMAGE n] headers + image parts."""
    quota_day: set = set()                  # (key, model) pairs whose monthly pool is gone
    busy: set = set()
    off_tier = {"mistral-medium-latest"}    # like the user's free tier: Medium answers "limit 0 req/min"
    a1_content: list = []
    a5_calls = 0

    def __init__(self, buckets):
        self.buckets = buckets

    def models(self, key):
        return ["mistral-medium-latest", "ministral-14b-latest", "ministral-8b-latest", "codestral-latest", "mistral-embed"]

    def vision(self, model):
        return model in ("mistral-medium-latest", "ministral-14b-latest", "ministral-8b-latest")

    def chat(self, model, messages, *, key, kid="", schema=None, name="out", max_out=2500, temperature=0.4, **kw):
        Calls.log.append(("mistral", model, name, key))
        if model in self.off_tier:
            raise providers.ProviderError("unavailable", f"{model} has a limit of 0 requests/min on this key's tier")
        if (key, model) in self.quota_day:
            raise providers.ProviderError("quota_day", "Monthly token limit exceeded")
        if model in self.busy:
            raise providers.ProviderError("overloaded", "HTTP 503: service unavailable")
        user = messages[-1]["content"]
        if name == "a1":
            FakeMistral.a1_content = user
            out = copy.deepcopy(flow.default_doc(H))
            out["strategic_cards"][0]["heading"] = "Seen by Mistral"
            return providers.Reply(json.dumps(out), model, "stop", {"in": 14000, "out": 1500})
        if name == "a5":
            FakeMistral.a5_calls += 1
            spec = json.loads(user.split("\n\nYour previous")[0])
            return providers.Reply(render_doc_page(spec), model, "stop", {"in": 6000, "out": 8000})
        st = STATE["st"]
        out = {"a2": lambda: flow.default_plan(st), "a3": lambda: flow.default_copy(st, H),
               "a4": lambda: flow.default_decor(st)}[name]()
        return providers.Reply(json.dumps(out), model, "stop", {"in": 1800, "out": 700})


class FakeOpenRouter:
    """OpenRouter: free models listed with their capabilities; A1 gets text first, then [IMAGE n] + detail-high parts."""
    LIST = {"nvidia/nemotron-3.5-super-vl:free": {"vision": True, "structured": True, "max_out": 131072},
            "google/gemma-4-31b-it:free": {"vision": True, "structured": True, "max_out": 32768},
            "google/gemma-4-26b-a4b-it:free": {"vision": True, "structured": False, "max_out": 32768},
            "nvidia/nemotron-3-ultra-550b-a55b:free": {"vision": False, "structured": False, "max_out": 65536}}
    quota_day = False                        # the account's free daily pool is used up
    a1_messages: list = []

    def __init__(self, buckets):
        self.buckets, self._caps = buckets, {}

    def models(self, key):
        self._caps = dict(self.LIST)
        return list(self.LIST)

    def key_info(self, key):
        return {"free_used": 3, "free_limit": 1000, "free_left": 997}

    def caps(self, model):
        return self._caps.get(model.removeprefix(budget.OR_PREFIX), {})

    def vision(self, model):
        return bool(self.caps(model).get("vision"))

    def structured(self, model):
        return bool(self.caps(model).get("structured"))

    def chat(self, model, messages, *, key, kid="", schema=None, name="out", max_out=2500, temperature=0.4, **kw):
        Calls.log.append(("openrouter", model, name, key))
        if FakeOpenRouter.quota_day:
            raise providers.ProviderError("quota_day", "Rate limit exceeded: free-models-per-day")
        if name == "a1":
            FakeOpenRouter.a1_messages = messages
            out = copy.deepcopy(flow.default_doc(H))
            out["strategic_cards"][0]["heading"] = "Seen through OpenRouter"
            return providers.Reply(json.dumps(out), model, "stop", {"in": 16000, "out": 6000})
        if name == "a5":
            spec = json.loads(messages[-1]["content"].split("\n\nYour previous")[0])
            return providers.Reply(render_doc_page(spec), model, "stop", {"in": 9000, "out": 12000})
        raise AssertionError(f"OpenRouter is not on {name}'s chain")


STATE: dict = {}


def patch():
    pipeline.Gemini, pipeline.Groq, pipeline.Mistral = FakeGemini, FakeGroq, FakeMistral
    pipeline.OpenRouter = FakeOpenRouter
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
    varn = validate_page.check(page.replace(":root{", ".v{color:var(--c-terminal-green);border-color:var(--c-near-white-ui)}"
                                                  ":root{--c-terminal-green:var(--text-body);--c-near-white-ui:var(--text-body);"),
                               spec, fix_colors_=True)
    check("var(--c-terminal-green)" in varn["html"] and "var(--c-near-white-ui)" in varn["html"]
          and not any("named colours" in e for e in varn["errors"]),
          "colour words inside CSS variable names are left alone (not snapped, not flagged)")
    ctas = [x for s_ in spec["sections"] for x in s_["items"] if x["kind"] in ("cta", "nav_link") and x.get("text")]
    if ctas:
        gone = ctas[0]
        cut = re.sub(r"<a [^>]*data-item=\"" + re.escape(gone["item_id"]) + r"\"[^>]*>.*?</a>", "", page, count=1)
        inj = validate_page.check(cut, spec, fix_colors_=True)
        check(cut != page and not inj["errors"] and any("added 1 item" in f for f in inj["fixes"])
              and f'data-item="{gone["item_id"]}"' in inj["html"],
              f"a {gone['kind']} the page left out is added to its own section by code, not a reason to discard it")
        strict = validate_page.check(cut, spec)
        check(any("data-item missing" in e for e in strict["errors"]), "without code fixes, a missing item still blocks")
    glyph = dict(spec, copy=spec["copy"] + ["● Online"])
    gp = page.replace("</body>", "<p><span class='dot'></span>Online</p></body>")
    check(not any("copy missing" in e for e in validate_page.check(gp, glyph)["errors"]),
          "decorative glyphs in copy (a dot before Online) may be drawn with CSS: the words still count")
    hiz = validate_page.check(page.replace(":root{", ".nav{z-index:100}.u{z-index:-3}:root{"), spec, fix_colors_=True)
    check(not hiz["errors"] and any("clamped 2 z-index" in f for f in hiz["fixes"]) and "z-index:49" in hiz["html"],
          f"z-index outside 0-50 on a model page is clamped by code, not a reason to discard it ({hiz['errors'][:1]})")
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


def t_nested_overlap():
    """In a real browser: a card holding its own tag / heading / body items is not text over text; two separate
    items stacked on each other still are."""
    from landing import qa as QA
    page = ("<!doctype html><html><body style='margin:0;font:16px sans-serif'><main><section data-section='s'>"
            "<article data-item='card-1' style='width:300px;padding:20px'><span data-item='card-1-tag'>New</span>"
            "<h3 data-item='card-1-heading'>Heading</h3><p data-item='card-1-body'>Body text here</p></article>"
            "<div style='position:relative;height:60px'><p data-item='a' style='position:absolute;top:0;margin:0'>First line"
            "</p><p data-item='b' style='position:absolute;top:2px;margin:0'>Second line</p></div>"
            "</section></main></body></html>")
    f = TMP / "nested" / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(page, encoding="utf-8")
    probs = [p for x in QA.run(f, widths=(1440,)).values() for p in x["problems"] if "overlaps text" in p]
    check(not any("card-1" in p for p in probs), f"a card's nested items are not text over text ({probs[:2]})")
    check(any("text of a overlaps text of b" in p for p in probs), "two separate items on top of each other still are")


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
        check(any("moved decor behind the content" in o["why"] for o in r["overrides"]),
              "decoration painted over the h1 is moved behind it by code, not deleted (the page still ships)")
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


def _reset_router():
    pipeline._PREFERRED.clear()
    pipeline._NONSTRICT.clear()
    keys._COOL.clear()
    keys._DISABLED.clear()
    keys._UNAVAIL.clear()


def t_pipeline_mistral(h):
    """Mistral key present: A1 (vision) and A5 on Mistral Large; Groq A2-A4 hand over to Mistral when their minute
    windows are full; Mistral Large out -> Medium; both Mistral models out -> Gemini (the last fallback)."""
    os.environ["MISTRAL_API_KEY"] = "fake-mistral"
    os.environ["LANDING_LEDGER"] = str(TMP / "quota_mistral.json")
    saved_limits = {m: dict(budget.LIMITS[m]) for m in budget.LIMITS if m.startswith(("ministral", "codestral", "mistral"))}
    for m in saved_limits:                        # fakes answer instantly: don't sit out the real 2 req/min windows
        budget.LIMITS[m]["rpm"] = 1000
    cache.ROOT = TMP / "cache_mistral"
    _reset_router()
    NOTES.clear()
    Calls.log.clear()
    FakeGemini.a5_attempts = 0
    try:
        r = pipeline.run(h, enabled=True, qa=False, a5_repair=False, log=lambda *a: None)
        tr = {}
        for t in r["trace"]:
            tr.setdefault(t["agent"], t)
        check(tr["a1"]["model"] == "ministral-14b-latest" and tr["a1"]["source"] == "model",
              f"Medium off the tier: A1 on Ministral 14B (vision) ({tr['a1'].get('model')}, {tr['a1'].get('source')})")
        check(tr["a5"]["model"] == "codestral-latest" and r["page_source"] == "model",
              f"A5 composes on Codestral and its page ships ({tr['a5'].get('model')}, {r['page_source']})")
        check(len(keys.Ring("mistral").order("ministral-14b-latest", budget.Ledger())) == 1 and not keys._DISABLED,
              "a model off the tier never disables the key (it keeps serving the other models)")
        check(any("limit of 0 requests/min" in n and "skipped for this key for 6 h" in n for n in NOTES),
              "terminal: the off-tier model is named once, with the model that takes over")
        n_med = len([c for c in Calls.log if c[1] == "mistral-medium-latest"])
        keys._UNAVAIL.clear()                     # a fresh process: it must learn the refusal from disk, not by asking
        check(keys.Ring("mistral").unavailable(0, "mistral-medium-latest"),
              "the off-tier model is remembered across restarts (no request spent re-learning it)")
        check(tr["a2"]["model"] == "openai/gpt-oss-120b" and tr["a4"]["model"] == "qwen/qwen3.8-27b",
              "A2-A4 stay on Groq while Groq answers")
        check(not [c for c in Calls.log if c[0] == "gemini"], "no Gemini call while Mistral answers")
        check(any(n.startswith("models: A1 mistral-medium-latest -> ministral-14b-latest -> gemini-4-hydrogen")
                  for n in NOTES), "terminal: A1 chain is Mistral Medium -> Ministral 14B -> Gemini")
        cont = FakeMistral.a1_content
        heads = [p["text"] for p in cont if p.get("type") == "text" and p["text"].startswith("[IMAGE")]
        imgs = [i for i, p in enumerate(cont) if p.get("type") == "image_url"]
        check(len(heads) == len(imgs) == len(h["images"]) and all(cont[i - 1]["text"].startswith("[IMAGE") for i in imgs)
              and all(cont[i]["image_url"].startswith("data:image/jpeg;base64,") for i in imgs),
              f"A1 on Mistral sees every image separately, each right after its role header ({len(imgs)} images)")
        html = (Path(r["out"]) / "index.html").read_text(encoding="utf-8")
        check("Seen by Mistral" in html, "Mistral A1's card copy reaches the page")

        FakeGroq.rate_all = True                  # Groq minute windows full -> Mistral takes A2-A4
        NOTES.clear()
        r2 = pipeline.run(h, enabled=True, force_from="a2", qa=False, a5_repair=False, log=lambda *a: None)
        m2 = {t["agent"]: t.get("model") for t in r2["trace"]}
        check(all(m2[a] == "ministral-8b-latest" for a in ("a2", "a3", "a4")),
              f"Groq rate-limited: A2-A4 answered by Mistral's Ministral 8B ({m2})")
        check(len([c for c in Calls.log if c[1] == "mistral-medium-latest"]) == n_med,
              "the off-tier model is not asked again in this process")
        FakeGroq.rate_all = False
        keys._COOL.clear()

        FakeMistral.quota_day = {("fake-mistral", "codestral-latest")}      # Codestral's pool is out -> Ministral 14B
        _reset_router()
        NOTES.clear()
        r3 = pipeline.run(h, enabled=True, force_from="a5", qa=False, a5_repair=False, log=lambda *a: None)
        m3 = {t["agent"]: t.get("model") for t in r3["trace"]}
        check(m3["a5"] == "ministral-14b-latest", f"Codestral out: A5 on Ministral 14B ({m3['a5']})")
        check(any("mistral key 1/1 reached its daily limit for codestral-latest" in n for n in NOTES),
              "terminal: Codestral's limit announced")

        FakeMistral.busy = {"ministral-14b-latest"}                        # every Mistral model out -> Gemini
        _reset_router()
        r4 = pipeline.run(h, enabled=True, force_from="a1", qa=False, a5_repair=False, log=lambda *a: None)
        m4 = {}
        for t in r4["trace"]:                     # the first entry per agent: the model that answered
            m4.setdefault(t["agent"], t.get("model"))
        check((m4["a1"] or "").startswith("gemini") and (m4["a5"] or "").startswith("gemini"),
              f"both Mistral models out: Gemini is the last fallback ({m4['a1']}, {m4['a5']})")
        check(not any("fake-mistral" in n for n in NOTES), "terminal lines never contain the Mistral key")
    finally:
        FakeMistral.quota_day, FakeMistral.busy, FakeGroq.rate_all = set(), set(), False
        keys._UNAVAIL.clear()
        budget.LIMITS.update(saved_limits)
        os.environ.pop("MISTRAL_API_KEY", None)
        os.environ["LANDING_LEDGER"] = str(TMP / "quota.json")
        cache.ROOT = TMP / "cache"
        _reset_router()


def t_mistral_provider():
    """The real Mistral client over a mock transport: request shape, error kinds, pacing, models + vision flags."""
    import httpx
    seen, replies = [], []

    def handler(req):
        seen.append((req.url.path, json.loads(req.content or b"{}"), time.monotonic()))
        return replies.pop(0)
    m = providers.Mistral(budget.Buckets())
    m.http = httpx.Client(transport=httpx.MockTransport(handler))
    replies.append(httpx.Response(200, json={"data": [
        {"id": "mistral-large-2512", "aliases": ["mistral-large-latest"], "capabilities": {"vision": True}},
        {"id": "ministral-8b-2512", "capabilities": {"vision": False}}]}))
    ms = m.models("k")
    check("mistral-large-latest" in ms and m.vision("mistral-large-latest") and not m.vision("ministral-8b-2512"),
          "Mistral models: aliases listed, vision flags read")
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}
    ok = {"choices": [{"message": {"content": '{"a":"x"}'}, "finish_reason": "stop"}],
          "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
    replies += [httpx.Response(200, json=ok), httpx.Response(200, json=ok)]
    m.chat("mistral-large-latest", [{"role": "user", "content": "hi"}], key="k", kid="x", schema=schema, name="a2")
    m.chat("mistral-large-latest", [{"role": "user", "content": "hi"}], key="k", kid="x", schema=schema, name="a2")
    b = seen[1][1]
    check(b.get("max_tokens") and "max_completion_tokens" not in b and "reasoning_effort" not in b
          and b["response_format"]["type"] == "json_schema" and b["response_format"]["json_schema"]["strict"],
          "Mistral request: max_tokens, strict json_schema, no Groq-only params")
    check(seen[2][2] - seen[1][2] >= 1.05, f"Mistral calls on one key are paced ~1/s ({seen[2][2] - seen[1][2]:.2f}s)")
    cases = [(httpx.Response(429, json={"message": "Monthly token limit exceeded"}), "quota_day"),
             (httpx.Response(429, json={"message": "Requests rate limit exceeded"}, headers={"retry-after": "2"}), "rate"),
             (httpx.Response(400, json={"message": "Invalid response_format: json_schema not supported"}), "bad_output"),
             (httpx.Response(401, json={"message": "Unauthorized"}), "auth"),
             (httpx.Response(429, json={"message": "Rate limit exceeded", "type": "rate_limited"},
                             headers={"x-ratelimit-limit-req-minute": "0", "x-ratelimit-remaining-req-minute": "0"}),
              "unavailable"),
             (httpx.Response(403, json={"message": "This model is not available in your subscription tier",
                                        "type": "tier_not_allowed"}), "unavailable")]
    for resp, kind in cases:
        replies.append(resp)
        try:
            m.chat("mistral-large-latest", [{"role": "user", "content": "hi"}], key="k", kid="y", schema=schema)
            got = "ok"
        except providers.ProviderError as e:
            got = e.kind
        check(got == kind, f"Mistral HTTP {resp.status_code} {resp.headers.get('x-ratelimit-limit-req-minute', '')}"
                           f" -> {kind} ({got})")
    replies.append(httpx.Response(429, json={"message": "Rate limit exceeded"},
                                  headers={"x-ratelimit-limit-req-minute": "2", "x-ratelimit-remaining-req-minute": "0"}))
    try:
        m.chat("ministral-14b-latest", [{"role": "user", "content": "hi"}], key="k", kid="z")
    except providers.ProviderError as e:
        check(e.kind == "rate" and e.retry_after == 60.0, f"Mistral 2 req/min window full -> rate, wait 60 s ({e.kind}, {e.retry_after})")


def t_pipeline_openrouter(h):
    """OpenRouter key present: A1 on Nemotron VL (high-detail images, the depth exemplar), A5 on Nemotron Ultra, one
    shared free daily pool learned from GET /key; the pool used up -> Mistral's models take A1 / A5."""
    os.environ["OPENROUTER_API_KEY"] = "fake-or"
    os.environ["MISTRAL_API_KEY"] = "fake-mistral"
    os.environ["LANDING_LEDGER"] = str(TMP / "quota_or.json")
    saved_free = dict(budget.OPENROUTER_FREE)
    saved_limits = {m: dict(budget.LIMITS[m]) for m in budget.LIMITS if m.startswith(("ministral", "codestral", "mistral"))}
    for m in saved_limits:
        budget.LIMITS[m]["rpm"] = 1000
    cache.ROOT = TMP / "cache_or"
    _reset_router()
    NOTES.clear()
    Calls.log.clear()
    try:
        r = pipeline.run(h, enabled=True, qa=False, a5_repair=False, log=lambda *a: None)
        tr = {}
        for t in r["trace"]:
            tr.setdefault(t["agent"], t)
        vl, ultra = budget.OR_PREFIX + "nvidia/nemotron-3.5-super-vl:free", budget.OR_PREFIX + "nvidia/nemotron-3-ultra-550b-a55b:free"
        check(tr["a1"]["model"] == vl and tr["a1"]["source"] == "model", f"A1 on Nemotron VL ({tr['a1'].get('model')})")
        check(tr["a5"]["model"] == ultra and r["page_source"] == "model",
              f"A5 composes on Nemotron Ultra and its page ships ({tr['a5'].get('model')}, {r['page_source']})")
        a1_chain = next((n for n in NOTES if n.startswith("models: A1 ")), "")
        check(a1_chain.startswith(f"models: A1 {vl} -> {budget.OR_PREFIX}google/gemma-4-31b-it:free -> mistral")
              and "gemma-4-26b" not in a1_chain.split(";")[0],
              f"A1 chain: Nemotron VL -> Gemma 4 31B (26B lacks structured outputs) -> Mistral ({a1_chain[:140]})")
        msgs = FakeOpenRouter.a1_messages
        cont = msgs[-1]["content"]
        imgs = [i for i, x in enumerate(cont) if x.get("type") == "image_url"]
        check(cont[0]["type"] == "text" and cont[0]["text"].startswith("INPUT:") and len(imgs) == len(h["images"])
              and all(cont[i - 1]["text"].startswith("[IMAGE") for i in imgs)
              and all(cont[i]["image_url"]["detail"] == "high" and cont[i]["image_url"]["url"].startswith("data:image/jpeg")
                      for i in imgs), f"A1 on OpenRouter: text first, each image after its header at detail high ({len(imgs)})")
        check("THE DEPTH EXPECTED" in msgs[0]["content"] and "Vintage Coral Red" in msgs[0]["content"],
              "A1's system prompt carries the depth exemplar")
        left = budget.Ledger().left(budget.OR_PREFIX + "google/gemma-4-31b-it:free", keys.kid("fake-or"))
        check(budget.OPENROUTER_FREE["rpd"] == 1000 and left["requests"] == 1000 - 3 - 2,
              f"one shared free pool per account: the key's 1000/day, 3 used elsewhere, + A1 + A5 ({left})")
        check(not [c for c in Calls.log if c[0] in ("mistral", "gemini") and c[2] in ("a1", "a5")],
              "no Mistral / Gemini A1 or A5 call while OpenRouter answers")
        d = r.get("a1_depth") or {}
        check(d.get("colours", 0) >= 4 and d.get("elements_traced", 0) >= 1, f"result.json reports A1's depth ({d})")
        html = (Path(r["out"]) / "index.html").read_text(encoding="utf-8")
        check("Seen through OpenRouter" in html, "OpenRouter A1's card copy reaches the page")

        FakeOpenRouter.quota_day = True             # the account's free pool is gone -> Mistral takes A1 / A5
        _reset_router()
        NOTES.clear()
        r2 = pipeline.run(h, enabled=True, force_from="a1", qa=False, a5_repair=False, log=lambda *a: None)
        m2 = {}
        for t in r2["trace"]:
            m2.setdefault(t["agent"], t.get("model"))
        check(m2["a1"] == "ministral-14b-latest" and m2["a5"] == "codestral-latest",
              f"free pool used up: A1 / A5 on Mistral ({m2['a1']}, {m2['a5']})")
        check(any("openrouter key 1/1 reached its daily limit" in n for n in NOTES), "terminal: the free pool's limit announced")
        n_or = len([c for c in Calls.log if c[0] == "openrouter"])
        check(n_or == 3, f"the shared pool: after the 429 no other free model is asked ({n_or} OpenRouter calls)")
        check(not any("fake-or" in n for n in NOTES), "terminal lines never contain the OpenRouter key")
    finally:
        FakeOpenRouter.quota_day = False
        budget.OPENROUTER_FREE.clear()
        budget.OPENROUTER_FREE.update(saved_free)
        budget.LIMITS.update(saved_limits)
        keys._UNAVAIL.clear()
        for k in ("OPENROUTER_API_KEY", "MISTRAL_API_KEY"):
            os.environ.pop(k, None)
        os.environ["LANDING_LEDGER"] = str(TMP / "quota.json")
        cache.ROOT = TMP / "cache"
        _reset_router()


def t_openrouter_provider():
    """The real OpenRouter client over a mock transport: capabilities, the key's pool, request shape, error kinds,
    errors inside a 200 reply, dropped connections."""
    import base64
    import io
    import httpx
    from PIL import Image
    seen, replies, sleeps = [], [], []

    def handler(req):
        seen.append((req.url.path, json.loads(req.content or b"{}") if req.method == "POST" else {}, dict(req.headers)))
        nxt = replies.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt
    o = providers.OpenRouter(budget.Buckets())
    o.pace_s = 0
    o.http = httpx.Client(transport=httpx.MockTransport(handler))
    replies.append(httpx.Response(200, json={"data": [
        {"id": "nvidia/nemotron-3.5-super-vl:free", "architecture": {"input_modalities": ["text", "image", "video"]},
         "supported_parameters": ["structured_outputs", "response_format"], "context_length": 1000000,
         "top_provider": {"max_completion_tokens": 131072}},
        {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "architecture": {"input_modalities": ["text"]},
         "supported_parameters": ["max_tokens"], "top_provider": {"max_completion_tokens": 65536}}]}))
    o.models("k")
    vl, ul = budget.OR_PREFIX + "nvidia/nemotron-3.5-super-vl:free", budget.OR_PREFIX + "nvidia/nemotron-3-ultra-550b-a55b:free"
    check(o.vision(vl) and o.structured(vl) and not o.vision(ul) and not o.structured(ul) and o.caps(ul)["max_out"] == 65536,
          "OpenRouter models: vision, structured outputs and output caps come from /models")
    replies.append(httpx.Response(200, json={"data": {"label": "x", "free_model_daily_requests":
                                                       {"used": 7, "limit": 50, "remaining": 43}}}))
    info = o.key_info("k")
    check(info == {"free_used": 7, "free_limit": 50, "free_left": 43}, f"GET /key: the account's free daily pool ({info})")
    img = TMP / "probe.png"
    Image.new("RGB", (3000, 1200), (200, 80, 40)).save(img)
    part = providers.image_part_or(img, 2048)
    size = Image.open(io.BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1]))).size
    check(part["image_url"]["detail"] == "high" and max(size) == 2048, f"image part: detail high, long side 2048 px ({size})")
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}
    ok = {"choices": [{"message": {"content": '{"a":"x"}'}, "finish_reason": "stop"}],
          "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
    replies.append(httpx.Response(200, json=ok))
    o.chat(vl, [{"role": "user", "content": [{"type": "text", "text": "hi"}, part]}], key="k", kid="x", schema=schema,
           name="a1")
    b, hdrs = seen[-1][1], {k.lower() for k in seen[-1][2]}
    check(b["model"] == "nvidia/nemotron-3.5-super-vl:free" and b.get("max_tokens") and b["response_format"]["type"] ==
          "json_schema" and b["response_format"]["json_schema"]["strict"] and b.get("provider") == {"require_parameters": True},
          "A1 request: the bare model id, max_tokens, strict json_schema routed only to endpoints that honour it")
    check(not hdrs & {"http-referer", "x-title", "x-openrouter-title"}, "no attribution headers leave the PC")
    check(b.get("reasoning") == {"effort": "low"},
          "reasoning effort is capped low, so thinking can't eat the JSON's output budget")
    replies += [httpx.Response(400, json={"error": {"code": 400, "message": "reasoning is not supported by this model"}}),
                httpx.Response(200, json=ok)]
    o.chat(vl, [{"role": "user", "content": "hi"}], key="k", kid="x", schema=schema, name="a1")
    check("reasoning" not in seen[-1][1] and "reasoning" in seen[-2][1],
          "a model that rejects the reasoning parameter is retried without it")
    o.drop.discard("reasoning")
    replies.append(httpx.Response(200, json=ok))
    o.chat(ul, [{"role": "user", "content": "compose"}], key="k", kid="x", name="a5")
    b = seen[-1][1]
    check("response_format" not in b and "provider" not in b, "A5 request: plain text, no schema routing")
    real_sleep = providers.time.sleep
    providers.time.sleep = sleeps.append
    try:
        soon = str(int((time.time() + 30) * 1000))
        cases = [(httpx.Response(429, json={"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-day"}}),
                  "quota_day"),
                 (httpx.Response(429, json={"error": {"code": 429, "message": "Rate limit exceeded"}},
                                 headers={"x-ratelimit-reset": soon}), "rate"),
                 (httpx.Response(402, json={"error": {"code": 402, "message": "Insufficient credits"}}), "quota_day"),
                 (httpx.Response(403, json={"error": {"code": 403, "message": "Input was flagged by moderation"}}), "blocked"),
                 (httpx.Response(404, json={"error": {"code": 404, "message": "No endpoints found that can handle the "
                                                                                 "requested parameters."}}), "bad_output"),
                 (httpx.Response(200, json={"error": {"code": 400, "message": "Provider returned error"}}), "server"),
                 (httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}), "server")]
        for resp, kind in cases:
            replies.append(resp)
            try:
                o.chat(vl, [{"role": "user", "content": "hi"}], key="k", kid="y", schema=schema)
                got, ra = "ok", 0
            except providers.ProviderError as e:
                got, ra = e.kind, e.retry_after
            check(got == kind, f"OpenRouter HTTP {resp.status_code} {resp.text[:60]} -> {kind} ({got})")
            if kind == "rate":
                check(20 <= ra <= 31, f"a 429's X-RateLimit-Reset becomes the wait ({ra:.0f}s)")
        replies += [httpx.Response(200, json={"error": {"code": 502, "message": "upstream down"}}), httpx.Response(200, json=ok)]
        r = o.chat(vl, [{"role": "user", "content": "hi"}], key="k", kid="y", schema=schema)
        check(r.text == '{"a":"x"}', "a 502 reported inside a 200 is retried on the same model")
        sleeps.clear()
        replies += [httpx.ConnectError("[WinError 10051] unreachable network"), httpx.ConnectError("again"),
                    httpx.Response(200, json=ok)]
        r = o.chat(vl, [{"role": "user", "content": "hi"}], key="k", kid="y", schema=schema)
        check(r.text == '{"a":"x"}' and sleeps[:2] == list(providers.NET_BACKOFF[:2]),
              f"a dropped connection is retried with backoff ({sleeps})")
    finally:
        providers.time.sleep = real_sleep


def t_copy_fold(h):
    """A composer types '-' for a non-breaking hyphen: the copy is stored plain and the check folds variants."""
    check(validate_page._norm("Sign\u2011up") == validate_page._norm("Sign-up")
          and validate_page._norm("It\u2019s\u00a0on") == validate_page._norm("It's on"),
          "page check: dash, quote and space variants compare equal")
    st = S.State(h)
    flow.after_a1(st, flow.default_doc(h), h)
    flow.after_a2(st, flow.default_plan(st))
    out = flow.default_copy(st, h)
    item = next(x for x in out["copy"]["items"] if x["kind"] != "card")
    item["text"] = "Sign\u2011up"
    flow.after_a3(st, out)
    texts = [x["text"] for x in st["copy_final"]["items"]]
    check("Sign-up" in texts and not any("\u2011" in t for t in texts), "A3's copy is stored with a plain hyphen")
    flow.after_a4(st, flow.default_decor(st))
    spec = flow.spec(st)
    page = render_doc_page(spec)
    spec2 = copy.deepcopy(spec)
    spec2["copy"] = ["Sign\u2011up" if t == "Sign-up" else t for t in spec2["copy"]]
    chk = validate_page.check(page, spec2, inject_backdrop=True)
    check(not any("spec copy missing" in e for e in chk["errors"]), f"U+2011 in the spec vs '-' on the page is not "
                                                                    f"'missing copy' ({chk['errors'][:2]})")


def t_decor_layers(h):
    """Decor never shares the text layer, and decor over text is first moved behind it."""
    st = S.State(h)
    flow.after_a1(st, doc_1976(), h)
    plan = flow.default_plan(st)
    L0 = plan["layout_plan"]["layers"][0]
    L0["z"] = 10
    log = flow.after_a2(st, plan)
    z = next(L["z"] for L in st["plan"]["layers"] if L["element_id"] == L0["element_id"])
    check(z == S.layer_of(st["doc"])[L0["element_id"]][1] and z != 10
          and any("never shares the text layer" in o["why"] for o in log),
          f"a z10 decor layer goes to its A1 group's layer ({z}, logged)")
    zs = sc.a2(*flow.a2_enums(st))["properties"]["layout_plan"]["properties"]["layers"]["items"]["properties"]["z"]["enum"]
    check(10 not in zs, f"A2's schema offers decor no z10 ({zs})")
    flow.after_a3(st, flow.default_copy(st, h))
    flow.after_a4(st, flow.default_decor(st))
    spec = flow.spec(st)
    motif = (spec.get("motif_ids") or [None])[0]
    if motif:
        chk = validate_page.check(render_doc_page(spec, cover_h1_with=motif), spec, demote_motifs={motif},
                                  inject_backdrop=True)
        html = chk["html"]
        check(html.count('data-demoted="1"') >= 2 and validate_page.DEMOTE_CSS in html
              and any("moved decor behind the content" in f for f in chk["fixes"]) and f'data-motif="{motif}"' in html,
              "decor over text: it and its layer wrapper are moved behind the content (kept on the page)")


def t_keys_collect():
    saved = {k: os.environ.pop(k) for k in [k for k in os.environ if k.startswith(("GEMINI_API_KEY", "GROQ_API_KEY"))]}
    env_file = TMP / "keys.env"
    env_file.write_text("# test\nGROQ_API_KEY=from-file\nGEMINI_API_KEY_2=file-two\nSUPABASE_URL=ignored\n"
                        "MISTRAL_API_KEY=m-file\nMISTRAL_API_KEY_2=m-two\nOPENROUTER_API_KEY=or-file\n", encoding="utf-8")
    os.environ["LANDING_ENV_FILE"] = str(env_file)
    os.environ.update({"GEMINI_API_KEY": "a", "GEMINI_API_KEY_3": "c", "GEMINI_API_KEYS": "d, a ;e"})
    try:
        check(keys.collect("gemini") == ["a", "file-two", "c", "d", "e"],
              f"key order: X_API_KEY, X_API_KEY_2.., X_API_KEYS; env + file; duplicates dropped ({keys.collect('gemini')})")
        check(keys.collect("groq") == ["from-file"], "keys are read from the env file when the environment has none")
        check(keys.collect("mistral") == ["m-file", "m-two"], f"MISTRAL_API_KEY / _2 are read ({len(keys.collect('mistral'))})")
        check(keys.collect("openrouter") == ["or-file"], "OPENROUTER_API_KEY is read")
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
        t_copy_fold(h)
        t_decor_layers(h)
        if qa:
            r = pipeline.run(h, enabled=False, qa=True, log=lambda *a: None)
            check(not any("overlaps text" in p or "overflow" in p for x in r["qa"].values() for p in x["problems"]),
                  f"agents-off page: nothing blocking in the browser ({n}, {r['page_source']})")
            t_doc_page_qa(h)
    if qa:
        t_nested_overlap()
    t_svg()
    t_backoff()
    t_state()
    t_budget()
    t_measure()
    t_mistral_provider()
    t_openrouter_provider()
    print("--- fake models, no Mistral key: Gemini fallback (routing, repair, the design document, the A5 gate, cache)")
    H = load(names[0])
    patch()
    t_pipeline_models(H, qa)
    print("--- fake models with a Mistral key (A1 / A5 on Mistral, Groq backup, Gemini last)")
    t_pipeline_mistral(H)
    print("--- fake models with an OpenRouter key (A1 / A5 on OpenRouter, Mistral next)")
    t_pipeline_openrouter(H)
    print("--- several keys per provider (failover + terminal notices)")
    t_keys_collect()
    t_multikey(H)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'}")
    return 1 if FAILS else 0


H = None
if __name__ == "__main__":
    sys.exit(main())
