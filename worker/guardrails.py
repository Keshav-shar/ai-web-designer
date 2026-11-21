"""guardrails.py - deterministic design rules applied on top of the lab's picks.

The lab ranks ingredients by similarity; it does not guarantee a usable result (its dreamy run gave
text/bg 4.05:1, a handwriting heading against a "soft italic serif" cue and an 18px h1). These rules repair
only what breaks a hard constraint, keep the lab's choice wherever it passes, and log every change in
`overrides` so a brief always says what was changed and why. Shared by tools/export_tokens.py (the app's own
theme) and worker/brief.py (every generated site).
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

# the font catalogue under the serpman data root (same variable as serpman_paths.SERPMAN_DATA)
FONT_ROOT = Path(os.getenv("SERPMAN_DATA", r"D:\serpman_data")) / "fonts"

# WCAG 2.x targets
AA_TEXT, AAA_TEXT, AA_UI = 4.5, 7.0, 3.0


# --------------------------------------------------------------------------- colour math
def _hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_hex(rgb) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02X}" for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _delin(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def luminance(h: str) -> float:
    r, g, b = (_lin(c) for c in _hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def to_oklab(h: str) -> tuple[float, float, float]:
    r, g, b = (_lin(c) for c in _hex_rgb(h))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def from_oklab(L: float, a: float, b: float) -> str:
    for _ in range(24):                      # shrink chroma until the colour is inside sRGB
        l_ = L + 0.3963377774 * a + 0.2158037573 * b
        m_ = L - 0.1055613458 * a - 0.0638541728 * b
        s_ = L - 0.0894841775 * a - 1.2914855480 * b
        l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
        rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
               -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
               -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
        if all(-1e-4 <= c <= 1.0001 for c in rgb):
            return _rgb_hex(_delin(min(1.0, max(0.0, c))) for c in rgb)
        a, b = a * 0.9, b * 0.9
    return _rgb_hex(_delin(min(1.0, max(0.0, c))) for c in rgb)


def chroma(h: str) -> float:
    _, a, b = to_oklab(h)
    return math.hypot(a, b)


def push_to_contrast(fg: str, bg: str, target: float, direction: str | None = None) -> str:
    """Move fg's OKLab lightness away from bg (hue/chroma kept) until contrast >= target; minimal step."""
    if contrast(fg, bg) >= target:
        return fg
    L, a, b = to_oklab(fg)
    if direction is None:
        direction = "down" if luminance(bg) > 0.18 else "up"
    lo, hi = (0.0, L) if direction == "down" else (L, 1.0)
    end = from_oklab(lo if direction == "down" else hi, a, b)
    if contrast(end, bg) < target:           # even the extreme fails: fall back to black / white
        return "#000000" if direction == "down" else "#FFFFFF"
    for _ in range(30):                      # bisection on L for the closest passing colour
        mid = (lo + hi) / 2
        ok = contrast(from_oklab(mid, a, b), bg) >= target
        if direction == "down":
            lo, hi = (lo, mid) if not ok else (mid, hi)
        else:
            lo, hi = (mid, hi) if not ok else (lo, mid)
    return from_oklab(lo if direction == "down" else hi, a, b)


def mix(a: str, b: str, t: float) -> str:
    A, B = to_oklab(a), to_oklab(b)
    return from_oklab(*(x + (y - x) * t for x, y in zip(A, B)))


# --------------------------------------------------------------------------- colour roles
def colour_roles(swatches: list[str], lab_roles: dict[str, str], theme: str = "auto") -> tuple[dict, dict, list, list]:
    """-> (roles, derived, visuals, overrides).

    theme 'auto' keeps the lab's polarity (dark bg stays dark); 'light' / 'dark' re-seat the palette by
    lightness. Text/muted/accent are then pushed (OKLab L only) to WCAG targets; decorative swatches are
    left untouched and returned as `visuals` for gradients and illustrations.
    """
    sw = list(dict.fromkeys(s.upper() for s in swatches if re.fullmatch(r"#[0-9A-Fa-f]{6}", s)))
    over: list[dict] = []
    lab_bg = lab_roles.get("--bg", sw[0] if sw else "#FFFFFF")
    if theme == "auto":
        theme = "light" if luminance(lab_bg) > 0.4 else "dark"
    by_l = sorted(sw, key=luminance)                     # darkest .. lightest
    if theme == "light":
        bg, surface = by_l[-1], (by_l[-2] if len(by_l) > 1 else by_l[-1])
        ink = by_l[0]
    else:
        bg, surface = by_l[0], (by_l[1] if len(by_l) > 1 else by_l[0])
        ink = by_l[-1]
    if bg != lab_roles.get("--bg"):
        over.append({"token": "--bg", "from": lab_roles.get("--bg"), "to": bg,
                     "why": f"{theme} theme: background re-seated to the {'lightest' if theme == 'light' else 'darkest'} swatch"})
    if surface != lab_roles.get("--surface"):
        over.append({"token": "--surface", "from": lab_roles.get("--surface"), "to": surface,
                     "why": f"{theme} theme: surface = next swatch by lightness, so cards stay close to the background"})
    d = "down" if theme == "light" else "up"
    text = push_to_contrast(ink, bg, AAA_TEXT, d)
    text = push_to_contrast(text, surface, AA_TEXT, d)
    muted = push_to_contrast(mix(ink, bg, 0.25), bg, AA_TEXT, d)
    muted = push_to_contrast(muted, surface, AA_TEXT, d)
    rest = [s for s in sw if s not in (bg, surface, ink)]
    accent_src = max(rest or [ink], key=chroma)          # the most colourful remaining swatch
    # The accent is a button fill: its label (on-accent) must reach 4.5:1 on it, and the fill must reach 3:1 on
    # the page. Fix the label at white (light theme) / the background (dark theme) and move only the fill.
    on_accent = "#FFFFFF" if theme == "light" else bg
    accent = push_to_contrast(accent_src, on_accent, AA_TEXT, d)
    accent = push_to_contrast(accent, bg, AA_UI, d)
    accent2_src = max([s for s in rest if s != accent_src] or [accent_src], key=chroma)
    roles = {"--bg": bg, "--surface": surface, "--text": text, "--text-muted": muted,
             "--accent": accent, "--accent-2": accent2_src, "--on-accent": on_accent,
             "--border": mix(surface, text, 0.18)}
    for k in ("--text", "--text-muted", "--accent"):
        if roles[k] != lab_roles.get(k):
            over.append({"token": k, "from": lab_roles.get(k), "to": roles[k],
                         "why": "pushed along OKLab lightness to meet WCAG "
                                + ("AAA 7:1 on bg / AA on surface" if k == "--text" else
                                   "AA 4.5:1 on bg and surface" if k == "--text-muted" else
                                   "4.5:1 under its button label and 3:1 on the page")})
    roles["--accent-soft"] = accent_src                      # the untouched lab colour, for tints and glows
    derived = {"--accent-hover": push_to_contrast(mix(accent, text, 0.15), bg, AA_UI, d),
               "--surface-2": mix(surface, bg, 0.5),
               "--focus-ring": push_to_contrast(accent, bg, AA_UI, d)}
    visuals = [s for s in sw if s not in (roles["--bg"],)]
    return roles, derived, visuals, over


def contrast_report(roles: dict[str, str]) -> list[dict]:
    pairs = [("--text", "--bg", AA_TEXT), ("--text", "--surface", AA_TEXT), ("--text-muted", "--bg", AA_TEXT),
             ("--text-muted", "--surface", AA_TEXT), ("--on-accent", "--accent", AA_TEXT), ("--accent", "--bg", AA_UI)]
    out = []
    for fg, bg, t in pairs:
        if fg in roles and bg in roles:
            r = contrast(roles[fg], roles[bg])
            out.append({"pair": f"{fg[2:]}/{bg[2:]}", "ratio": round(r, 2), "pass": r >= t})
    return out


# --------------------------------------------------------------------------- fonts
_catalog: dict | None = None


def font_catalog() -> dict[str, dict]:
    """family -> {category, styles, tags, nweights, popularity} from the lab's Google Fonts catalogue."""
    global _catalog
    if _catalog is None:
        meta = json.loads((FONT_ROOT / "meta.json").read_text(encoding="utf-8"))
        styles = {m["family"]: set(m.get("fonts", {})) for m in meta.get("familyMetadataList", [])}
        _catalog = {}
        for c in json.loads((FONT_ROOT / "catalog.json").read_text(encoding="utf-8")):
            _catalog[c["family"]] = {"category": c["category"], "styles": styles.get(c["family"], set()),
                                     "tags": c.get("tags", []), "nweights": c.get("nweights", 1),
                                     "popularity": c.get("popularity", 9999), "cls": c.get("cls", [])}
    return _catalog


def cue_constraints(cues: str) -> dict:
    """Hard constraints a vibe's own cue text states about type (only what it says literally)."""
    c = cues.lower()
    want = {}
    if re.search(r"\bserifs?\b", c) and "sans" not in c:
        want["heading_category"] = "Serif"
    elif "monospace" in c or re.search(r"\bmono\b", c):
        want["heading_category"] = "Monospace"
    elif "blackletter" in c or "script" in c:
        want["heading_category"] = "Handwriting" if "script" in c else "Display"
    if "italic" in c:
        want["heading_italic"] = True
    return want


NARROW = re.compile(r"narrow|condensed|compressed|extra ?condensed", re.I)


def pick_fonts(shortlist: list[str], body_cands: list[str], lab_heading: str, lab_body: str, cues: str,
               pin_heading: str | None = None, pin_body: str | None = None) -> tuple[str, str, bool, list]:
    """-> (heading, body, heading_italic, overrides). Keeps the lab pick when it satisfies the cue constraints."""
    cat = font_catalog()
    want = cue_constraints(cues)
    over = []

    def ok_head(f):
        m = cat.get(f)
        if not m:
            return False
        if want.get("heading_category") and m["category"] != want["heading_category"]:
            return False
        return not want.get("heading_italic") or any(s.endswith("i") for s in m["styles"])

    heading = lab_heading
    if pin_heading:
        heading = pin_heading
        over.append({"token": "heading", "from": lab_heading, "to": pin_heading, "why": "pinned by hand (--heading)"})
    elif not ok_head(lab_heading):
        pool = [f for f in shortlist if ok_head(f)]
        src = "lab shortlist"
        if not pool:
            pool = sorted((f for f in cat if ok_head(f)), key=lambda f: cat[f]["popularity"])
            src = "catalogue by popularity (no shortlist font met the cue)"
        if pool:
            heading = pool[0]
            over.append({"token": "heading", "from": lab_heading, "to": heading,
                         "why": f"vibe cue requires {json.dumps(want)}; first match from {src}"})

    def ok_body(f):
        m = cat.get(f)
        return bool(m) and m["category"] in ("Sans Serif", "Serif") and not NARROW.search(f) and m["nweights"] >= 3

    body = lab_body
    if pin_body:
        body = pin_body
        over.append({"token": "body", "from": lab_body, "to": pin_body, "why": "pinned by hand (--body)"})
    elif not ok_body(lab_body):
        pool = [f for f in body_cands if ok_body(f) and f != heading]
        if pool:
            body = pool[0]
            over.append({"token": "body", "from": lab_body, "to": body,
                         "why": "body text needs a normal-width text face with >= 3 weights (lab pick is narrow/limited)"})
    italic = bool(want.get("heading_italic")) and any(s.endswith("i") for s in cat.get(heading, {}).get("styles", ()))
    return heading, body, italic, over


def google_css(family: str, italic: bool, weights=(400, 500, 600, 700)) -> str:
    cat = font_catalog().get(family, {})
    have = cat.get("styles", set())
    ws = [w for w in weights if str(w) in have] or [400]
    fam = family.replace(" ", "+")
    if italic and any(f"{w}i" in have for w in ws):
        axis = ";".join([f"0,{w}" for w in ws] + [f"1,{w}" for w in ws if f"{w}i" in have])
        return f"https://fonts.googleapis.com/css2?family={fam}:ital,wght@{axis}&display=swap"
    return f"https://fonts.googleapis.com/css2?family={fam}:wght@{';'.join(map(str, ws))}&display=swap"


# --------------------------------------------------------------------------- type scale
def type_scale(lab_tokens: dict, landing: bool = True) -> tuple[dict, list]:
    """Keep the lab's base size and leading where usable; floor the ratio for landing-page display type."""
    over = []
    base = float(str(lab_tokens.get("--fs-1", "16px")).rstrip("px") or 16)
    ratio = float(lab_tokens.get("--ratio", 1.25))
    lh_b = float(lab_tokens.get("--lh-body", 1.5))
    lh_h = float(lab_tokens.get("--lh-heading", 1.1))
    if base < 16:
        over.append({"token": "--fs-1", "from": base, "to": 16, "why": "body text floor 16px"})
        base = 16.0
    if landing and ratio < 1.25:
        over.append({"token": "--ratio", "from": ratio, "to": 1.25,
                     "why": "landing pages need display contrast; lab ratio gave a %.0fpx top step" % (base * ratio ** 5)})
        ratio = 1.25
    if lh_b < 1.5:
        over.append({"token": "--lh-body", "from": lh_b, "to": 1.5, "why": "WCAG 1.4.12 readable body leading"})
        lh_b = 1.5
    lh_h2 = min(1.2, max(1.05, lh_h))
    if lh_h2 != lh_h:
        over.append({"token": "--lh-heading", "from": lh_h, "to": lh_h2, "why": "heading leading clamped to 1.05-1.2"})
    steps = 8 if landing else 6
    out = {f"--fs-{i + 1}": f"{round(base * ratio ** i, 1)}px" for i in range(steps)}
    out.update({"--ratio": ratio, "--lh-body": lh_b, "--lh-heading": lh_h2,
                "--tracking-display": lab_tokens.get("--tracking-display", "-0.02em"),
                "--case-display": lab_tokens.get("--case-display", "none")})
    return out, over
