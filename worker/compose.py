"""compose.py - non-AI section composer: the lab's design decisions + the routed family's folder sections.

Design comes from the brief (tokens, type scale, fonts, measured alignment, vibe effect); imagery from the
family's cluster folders, placed by cluster type:
    hero visual   central graphics, then 3D render > abstract art > illustration > photo ... (text-free only)
    screens       UI kit / app screen / dashboard / website / game HUD captures, in browser frames (text allowed)
    galleries     product / illustration / 3D / print / abstract ... (text-free preferred)
    logos         logo / branding
Copy comes from contracts/copykit.json (per category) or a per-section override (the About page). Every section
is run through validate.check; nothing here calls a model.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import validate

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
_KIT: dict | None = None
FRAME_IDS = {"nav", "footer", "overlay_fx", "cookie_consent", "toasts_modals"}

HERO_TYPES = ["3D render", "abstract art", "illustration", "photo", "pattern / texture", "fashion / product", "moodboard"]
SCREEN_TYPES = ["UI kit", "app screen", "dashboard", "website", "game / HUD", "code / tutorial", "social post"]
GALLERY_TYPES = ["fashion / product", "illustration", "3D render", "photo", "print / packaging", "abstract art",
                 "social post", "moodboard", "pattern / texture", "website"]
LOGO_TYPES = ["logo / branding"]

TITLES = {
    "features": "What makes it different", "how_it_works": "How it works", "testimonials": "Kind words",
    "faq": "Questions", "pricing": "Simple pricing", "showcase": "A closer look", "gallery": "Selected work",
    "lookbook": "The lookbook", "product_grid": "Shop the collection", "menu": "The menu", "tour_dates": "On tour",
    "events": "What's on", "changelog": "What's new", "course_catalog": "Courses", "location_hours": "Find us",
    "listings_map": "Available now", "team": "The people", "community": "Join the community",
    "press_kit": "Press kit", "spec_sheet": "Specifications", "configurator": "Make it yours", "donate": "Give today",
    "impact_stats": "Our impact", "kpi_cards": "At a glance", "trust_security": "Safe by design",
    "integrations": "Works with your tools", "ingredients": "What's inside", "countdown_drop": "The next drop",
    "reservations": "Reserve a table", "booking": "Book a visit", "lineup": "The lineup", "media_player": "Listen",
    "game_trailer": "Watch the trailer", "code_demo": "Up and running in a minute", "stats": "In numbers",
}
LIST_IDS = {"menu", "tour_dates", "events", "changelog", "course_catalog", "location_hours", "listings_map",
            "reservations", "booking", "team", "press_kit", "spec_sheet", "configurator", "donate", "lineup",
            "community", "ingredients", "countdown_drop", "trust_security", "media_player"}
GRID_IDS = {"gallery", "lookbook", "product_grid", "game_trailer"}
STAT_IDS = {"stats", "impact_stats", "kpi_cards"}

H2 = "font-heading text-[length:var(--fs-5)] md:text-[length:var(--fs-6)] leading-[var(--lh-heading)] text-[var(--text)]"
H3 = "font-heading text-[length:var(--fs-3)] leading-[var(--lh-heading)] text-[var(--text)]"
MUTED = "text-[var(--text-muted)]"


def copykit() -> dict:
    global _KIT
    if _KIT is None:
        _KIT = json.loads((CONTRACTS / "copykit.json").read_text(encoding="utf-8"))
    return _KIT


def kit_for(category: str) -> dict:
    k = copykit()
    base, cat = k["default"], k.get(category, {})
    out = {**base, **cat}
    out["rows"] = {**base.get("rows", {}), **cat.get("rows", {})}
    return out


def headline_from(full_query: str) -> str:
    """'a natural wine bar in Lisbon, hand-drawn and loud' -> 'Natural wine bar in Lisbon'."""
    s = re.split(r",|;| that | which | who | with a | feels ", full_query.strip(), maxsplit=1)[0]
    s = re.sub(r"^(an?|the)\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"\s+website$", "", s, flags=re.I)
    return (s[:1].upper() + s[1:])[:70] or "Welcome"


class Pool:
    """The brief's page-usable images, handed out once each."""

    def __init__(self, brief: dict):
        self.assets = [a for a in brief["assets"] if a["role"] in ("central", "section")]
        self.used: set[str] = set()

    def take(self, types: list[str], n: int, text_ok: bool, roles=("section",)) -> list[dict]:
        out = []
        for t in types:
            for a in self.assets:
                if len(out) >= n:
                    return out
                if (a["ref_id"] in self.used or a["role"] not in roles or (a.get("type") or "") != t
                        or (a.get("text") and not text_ok)):
                    continue
                self.used.add(a["ref_id"])
                out.append(a)
        return out

    def hero(self) -> dict | None:
        c = [a for a in self.assets if a["role"] == "central" and a["ref_id"] not in self.used and not a.get("text")]
        if c:
            pick = next((a for a in c if "primary" in (a.get("note") or "")), c[0])
            self.used.add(pick["ref_id"])
            return pick
        got = self.take(HERO_TYPES, 1, text_ok=False)
        return got[0] if got else None


class Composer:
    def __init__(self, brief: dict, split: dict, copy: dict | None = None):
        self.b, self.split, self.copy = brief, split, copy or {}
        self.kit = kit_for(brief["taste"]["category"])
        self.pool = Pool(brief)
        self.center = (brief.get("typography") or {}).get("alignment") == "center"
        self.brand = split.get("brand_name") or headline_from(split["full_query"])
        self.family = brief["meta"]["routed_family"].replace("-", " ")
        self.ids = [s["id"] for s in content_sections(brief)]

    # ---------------------------------------------------------------- helpers
    def c(self, sid: str, key: str, default=None):
        return (self.copy.get(sid) or {}).get(key, default)

    def anchor(self, *prefs: str) -> str:
        return "#" + next((p for p in prefs if p in self.ids), "hero")

    def img(self, a: dict, cls: str, frame: bool = False) -> str:
        alt = escape(f"{a.get('type') or 'image'} from the {self.family} reference folder")
        tag = f'<img src="{a["path"]}" alt="{alt}" loading="lazy" class="{cls}">'
        return f'<div class="frame">{tag}</div>' if frame else tag

    def head(self, sid: str, eyebrow: str | None = None, sub: str | None = None, center: bool | None = None) -> str:
        center = self.center if center is None else center
        title = escape(self.c(sid, "title", TITLES.get(sid, sid.replace("_", " ").capitalize())))
        eb = escape(self.c(sid, "eyebrow", eyebrow or self.brand))
        sub = self.c(sid, "sub", sub)
        wrap = "mx-auto max-w-[46rem] text-center" if center else "max-w-[46rem]"
        return (f'<div class="{wrap}"><p class="eyebrow">{eb}</p><h2 class="{H2}">{title}</h2>'
                + (f'<p class="mt-4 text-[length:var(--fs-2)] {MUTED}">{escape(sub)}</p>' if sub else "") + "</div>")

    def rows(self, sid: str) -> list[list[str]]:
        return self.c(sid, "rows") or self.kit["rows"].get(sid) or self.kit["features"]

    # ---------------------------------------------------------------- templates
    def hero(self, sid: str) -> str:
        title = escape(self.c(sid, "title", self.brand))
        sub = escape(self.c(sid, "sub", self.split["full_query"] if self.split.get("brand_name") else self.kit["tagline"]))
        eb = escape(self.c(sid, "eyebrow", self.b["taste"].get("niche") or self.b["taste"]["category_name"]))
        c1 = self.c(sid, "cta", [self.kit["cta"][0], self.anchor("cta_band", "pricing", "features")])
        c2 = self.c(sid, "cta2", [self.kit["cta"][1], self.anchor("features", "how_it_works", "showcase")])
        btns = (f'<div class="mt-10 flex flex-wrap gap-4 {"justify-center" if self.center else ""}">'
                f'<a class="btn btn-primary" href="{escape(c1[1])}">{escape(c1[0])}</a>'
                f'<a class="btn btn-ghost" href="{escape(c2[1])}">{escape(c2[0])}</a></div>')
        h1 = (f'<h1 class="font-heading text-[length:var(--fs-7)] md:text-[length:var(--fs-8)] leading-[var(--lh-heading)] '
              f'text-[var(--text)]">{title}</h1>')
        p = f'<p class="mt-6 max-w-[56ch] text-[length:var(--fs-2)] {MUTED} {"mx-auto" if self.center else ""}">{sub}</p>'
        vis = self.pool.hero()
        if self.center:
            visual = (f'<div class="relative mx-auto mt-16 max-w-[60rem]"><div class="soft-glow" aria-hidden="true"></div>'
                      + self.img(vis, "float w-full rounded-[2rem] object-cover aspect-[16/9]") + "</div>") if vis else ""
            return (f'<section id="{sid}" class="container-x py-20 text-center md:py-28"><div class="fade-up">'
                    f'<p class="eyebrow">{eb}</p>{h1}{p}{btns}</div>{visual}</section>')
        visual = (f'<div class="relative"><div class="soft-glow" aria-hidden="true"></div>'
                  + self.img(vis, "float w-full rounded-[2rem] object-cover aspect-[4/5] md:aspect-[4/3]") + "</div>") if vis else ""
        cols = "md:grid-cols-[1.1fr_.9fr]" if vis else ""
        return (f'<section id="{sid}" class="container-x grid items-center gap-12 py-20 md:py-28 {cols}">'
                f'<div class="fade-up"><p class="eyebrow">{eb}</p>{h1}{p}{btns}</div>{visual}</section>')

    def announce(self, sid: str) -> str:
        text = escape(self.c(sid, "text", f"{self.kit['proof'][0]} · {self.kit['cta'][0]}"))
        return (f'<section id="{sid}" class="bg-[var(--surface)] py-2 text-center text-[length:var(--fs-1)] text-[var(--text)]">'
                f'<a href="{self.anchor("cta_band", "hero")}">{text}</a></section>')

    def social_proof(self, sid: str) -> str:
        logos = self.pool.take(LOGO_TYPES, 4, text_ok=True)
        if len(logos) >= 3:
            tiles = "".join(f'<li class="overflow-hidden rounded-2xl border border-[var(--border)] opacity-90">'
                            + self.img(a, "aspect-[3/2] w-full object-cover") + "</li>" for a in logos)
            body = f'<ul class="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">{tiles}</ul>'
        else:
            items = "".join(f'<li class="glass px-5 py-4 text-[var(--text)]">{escape(x)}</li>' for x in self.kit["proof"])
            body = f'<ul class="mt-8 grid gap-4 md:grid-cols-3">{items}</ul>'
        eb = escape(self.c(sid, "eyebrow", "Trusted and recommended"))
        return f'<section id="{sid}" class="container-x py-12"><p class="eyebrow {"text-center" if self.center else ""}">{eb}</p>{body}</section>'

    def features(self, sid: str) -> str:
        feats = self.c(sid, "features", self.kit["features"])[:3]
        card = lambda i, t, d, extra="": (  # noqa: E731
            f'<div class="glass flex flex-col gap-3 p-8 {extra}"><span class="glyph">{i}</span>'
            f'<h3 class="{H3}">{escape(t)}</h3><p class="{MUTED}">{escape(d)}</p></div>')
        if not self.center:
            pic = self.pool.take(GALLERY_TYPES, 1, text_ok=False)
            if pic:
                big = (f'<div class="glass overflow-hidden md:col-span-2 md:row-span-2">'
                       + self.img(pic[0], "aspect-[16/10] w-full object-cover")
                       + f'<div class="flex flex-col gap-3 p-8"><span class="glyph">1</span><h3 class="{H3}">{escape(feats[0][0])}</h3>'
                         f'<p class="{MUTED}">{escape(feats[0][1])}</p></div></div>')
                rest = "".join(card(i + 2, t, d) for i, (t, d) in enumerate(feats[1:]))
                return (f'<section id="{sid}" class="container-x py-20">{self.head(sid)}'
                        f'<div class="mt-12 grid gap-6 md:grid-cols-3">{big}{rest}</div></section>')
        cards = "".join(card(i + 1, t, d, "items-center text-center" if self.center else "") for i, (t, d) in enumerate(feats))
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}<div class="mt-12 grid gap-6 md:grid-cols-3">{cards}</div></section>'

    def showcase(self, sid: str) -> str:
        shots = self.pool.take(SCREEN_TYPES, 3, text_ok=True)
        if not shots:
            return self.listing(sid)
        # full-page captures can be very tall: crop every screen to a fixed window from the top
        main_cls, side_cls = "aspect-[16/10] w-full object-cover object-top", "aspect-[4/3] w-full object-cover object-top"
        if len(shots) == 1:
            body = f'<div class="mx-auto mt-12 max-w-[60rem]">{self.img(shots[0], main_cls, frame=True)}</div>'
        else:
            side = "".join(f'<div>{self.img(a, side_cls, frame=True)}</div>' for a in shots[1:])
            body = (f'<div class="mt-12 grid items-start gap-6 md:grid-cols-3"><div class="md:col-span-2">'
                    f'{self.img(shots[0], main_cls, frame=True)}</div><div class="grid gap-6">{side}</div></div>')
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}{body}</section>'

    def steps(self, sid: str) -> str:
        steps = self.c(sid, "steps", self.kit["steps"])[:4]
        items = "".join(f'<li class="glass p-8"><p class="font-heading text-[length:var(--fs-6)] text-[var(--accent)]">{i + 1:02d}</p>'
                        f'<h3 class="mt-3 {H3}">{escape(t)}</h3><p class="mt-3 {MUTED}">{escape(d)}</p></li>'
                        for i, (t, d) in enumerate(steps))
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}<ol class="mt-12 grid gap-6 md:grid-cols-{len(steps)}">{items}</ol></section>'

    def stats(self, sid: str) -> str:
        data = self.c(sid, "stats")
        rows = self.kit["rows"].get(sid) if sid != "stats" else None
        if not data and rows:            # kit rows are [label, "value delta"] for KPIs, [value, label] for impact
            data = [[r[1].split()[0], r[0]] for r in rows] if sid == "kpi_cards" else [[r[0], r[1]] for r in rows]
        data = data or self.kit["stats"]
        cells = "".join(f'<div class="text-center"><p class="font-heading text-[length:var(--fs-7)] text-[var(--text)]">{escape(v)}</p>'
                        f'<p class="mt-2 {MUTED}">{escape(lbl)}</p></div>' for v, lbl in data[:4])
        return (f'<section id="{sid}" class="container-x py-16"><div class="glass grid gap-10 px-8 py-12 '
                f'md:grid-cols-{min(4, len(data))}">{cells}</div></section>')

    def testimonials(self, sid: str) -> str:
        qs = self.c(sid, "quotes", self.kit["quotes"])[:3]
        cards = "".join(f'<figure class="glass flex flex-col justify-between gap-6 p-8"><blockquote class="font-heading '
                        f'text-[length:var(--fs-3)] leading-[var(--lh-heading)] text-[var(--text)]">&ldquo;{escape(q)}&rdquo;</blockquote>'
                        f'<figcaption class="{MUTED}">{escape(who)}</figcaption></figure>' for q, who in qs)
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}<div class="mt-12 grid gap-6 md:grid-cols-3">{cards}</div></section>'

    def pricing(self, sid: str) -> str:
        tiers = self.c(sid, "tiers", self.kit["tiers"])[:3]
        cards = []
        for i, (name, price, line) in enumerate(tiers):
            hi = i == 1
            cards.append(f'<div class="glass flex flex-col gap-4 p-8 {"ring-2 ring-[var(--accent)]" if hi else ""}">'
                         f'<h3 class="{H3}">{escape(name)}</h3><p class="font-heading text-[length:var(--fs-6)] text-[var(--text)]">'
                         f'{escape(price)}</p><p class="{MUTED}">{escape(line)}</p>'
                         f'<a class="btn {"btn-primary" if hi else "btn-ghost"} mt-auto" href="{self.anchor("cta_band", "hero")}">'
                         f'{escape(self.kit["cta"][0])}</a></div>')
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}<div class="mt-12 grid gap-6 md:grid-cols-3">{"".join(cards)}</div></section>'

    def faq(self, sid: str) -> str:
        items = self.c(sid, "items", self.kit["faq"])
        rows = "".join(f'<details class="faq-item border-b border-[var(--border)] py-6"><summary class="flex items-center '
                       f'justify-between gap-6 text-[length:var(--fs-3)] text-[var(--text)]">{escape(q)}'
                       f'<span class="faq-plus {MUTED}" aria-hidden="true">+</span></summary>'
                       f'<p class="mt-4 max-w-[66ch] {MUTED}">{escape(a)}</p></details>' for q, a in items)
        return (f'<section id="{sid}" class="container-x py-20">{self.head(sid)}'
                f'<div class="mx-auto mt-10 max-w-[52rem] border-t border-[var(--border)]">{rows}</div></section>')

    def cta_band(self, sid: str) -> str:
        title = escape(self.c(sid, "title", self.kit["cta_band"][0]))
        sub = escape(self.c(sid, "sub", self.kit["cta_band"][1]))
        cta = self.c(sid, "cta", [self.kit["cta"][0], "#hero"])
        return (f'<section id="{sid}" class="container-x py-20"><div class="relative overflow-hidden rounded-[2.5rem] px-8 py-20 text-center">'
                f'<div class="soft-glow" aria-hidden="true"></div>'
                f'<h2 class="mx-auto max-w-[18ch] {H2}">{title}</h2><p class="mx-auto mt-4 max-w-[46ch] {MUTED}">{sub}</p>'
                f'<a class="btn btn-primary mt-10" href="{escape(cta[1])}">{escape(cta[0])}</a></div></section>')

    def grid(self, sid: str) -> str:
        imgs = self.pool.take(GALLERY_TYPES, 6, text_ok=False) or self.pool.take(GALLERY_TYPES, 6, text_ok=True)
        if len(imgs) < 2:
            return self.listing(sid)
        names = self.kit["products"]
        prices = ["$28", "$36", "$48", "$22", "$64", "$18"]
        tiles = []
        for i, a in enumerate(imgs):
            cap = ""
            if sid == "product_grid":
                cap = (f'<div class="flex items-center justify-between gap-4 p-4"><span class="text-[var(--text)]">'
                       f'{escape(names[i % len(names)])}</span><span class="{MUTED}">{prices[i % len(prices)]}</span></div>')
            tiles.append(f'<li class="glass overflow-hidden {"md:row-span-2" if i == 0 and sid != "product_grid" else ""}">'
                         + self.img(a, "h-full w-full object-cover " + ("aspect-[4/5]" if sid == "product_grid" else "aspect-square"))
                         + cap + "</li>")
        return (f'<section id="{sid}" class="container-x py-20">{self.head(sid)}'
                f'<ul class="mt-12 grid grid-cols-2 gap-6 md:grid-cols-3">{"".join(tiles)}</ul></section>')

    def listing(self, sid: str) -> str:
        rows = self.rows(sid)
        mono = sid in ("code_demo", "changelog", "spec_sheet", "live_ticker", "kpi_cards")
        items = "".join(f'<li class="flex flex-col justify-between gap-2 border-b border-[var(--border)] py-5 md:flex-row md:items-baseline">'
                        f'<span class="{"font-mono" if mono else "font-heading text-[length:var(--fs-3)]"} text-[var(--text)]">{escape(t)}</span>'
                        f'<span class="{MUTED}">{escape(d)}</span></li>' for t, d in rows[:6])
        pic = self.pool.take(GALLERY_TYPES, 1, text_ok=False) if sid not in ("code_demo", "changelog", "spec_sheet") else []
        lst = f'<ul class="border-t border-[var(--border)]">{items}</ul>'
        if pic:
            body = (f'<div class="mt-12 grid items-start gap-10 md:grid-cols-2">{lst}'
                    f'<div class="relative"><div class="soft-glow" aria-hidden="true"></div>'
                    + self.img(pic[0], "w-full rounded-[2rem] object-cover aspect-[4/3]") + "</div></div>")
        else:
            body = f'<div class="mt-12">{lst}</div>'
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}{body}</section>'

    def ticker(self, sid: str) -> str:
        cells = "".join(f'<li class="flex gap-3"><span class="font-mono text-[var(--text)]">{escape(t)}</span>'
                        f'<span class="{MUTED}">{escape(d)}</span></li>' for t, d in self.rows(sid)[:4])
        return (f'<section id="{sid}" class="border-y border-[var(--border)] bg-[var(--surface)]/60 py-4">'
                f'<ul class="container-x flex flex-wrap justify-between gap-6 text-[length:var(--fs-1)]">{cells}</ul></section>')

    def integrations(self, sid: str) -> str:
        logos = self.pool.take(LOGO_TYPES + ["icons"], 6, text_ok=True)
        if len(logos) < 3:
            return self.listing(sid)
        tiles = "".join(f'<li class="glass overflow-hidden">{self.img(a, "aspect-square w-full object-cover")}</li>' for a in logos)
        return f'<section id="{sid}" class="container-x py-20">{self.head(sid)}<ul class="mt-12 grid grid-cols-3 gap-6 md:grid-cols-6">{tiles}</ul></section>'

    # ---------------------------------------------------------------- dispatch
    def section(self, sid: str) -> str:
        if sid == "hero":
            return self.hero(sid)
        if sid == "announce_bar":
            return self.announce(sid)
        if sid == "social_proof":
            return self.social_proof(sid)
        if sid == "features":
            return self.features(sid)
        if sid == "showcase":
            return self.showcase(sid)
        if sid == "how_it_works":
            return self.steps(sid)
        if sid in STAT_IDS:
            return self.stats(sid)
        if sid == "testimonials":
            return self.testimonials(sid)
        if sid == "pricing":
            return self.pricing(sid)
        if sid == "faq":
            return self.faq(sid)
        if sid == "cta_band":
            return self.cta_band(sid)
        if sid in GRID_IDS:
            return self.grid(sid)
        if sid == "live_ticker":
            return self.ticker(sid)
        if sid == "integrations":
            return self.integrations(sid)
        return self.listing(sid)            # every other module: rows from the copy kit (+ a folder image)


def content_sections(brief: dict) -> list[dict]:
    return [s for s in brief["sections"] if (s["layer"] == "L2" or s["id"] == "announce_bar") and s["id"] not in FRAME_IDS]


def compose(brief: dict, split: dict, copy: dict | None = None, on_section=None) -> list[dict]:
    """-> [{id, html, fallback, errors, source}] in page order; raises if a template ever fails the checker."""
    comp = Composer(brief, split, copy)
    paths = {a["path"] for a in brief["assets"]}
    secs = content_sections(brief)
    out = []
    for i, s in enumerate(secs):
        html, errs = validate.check(comp.section(s["id"]), s["id"], paths)
        if html is None:
            raise RuntimeError(f"composed section {s['id']} failed the checker: {errs}")
        res = {"id": s["id"], "html": html, "fallback": False, "errors": [], "source": "compose"}
        out.append(res)
        if on_section:
            on_section(res, i, len(secs))
    return out
