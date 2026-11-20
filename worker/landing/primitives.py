"""primitives.py - parametric SVG motifs for the overlay layers (z5 / z20).

A4 picks a primitive and bounded parameters; code draws it, so geometry is always valid and colours are always
palette roles (CSS variables, never literals). An optional `path_d` (validated: SVG path grammar, <= 600 chars,
0-100 coordinate space) lets A4 add a custom shape. Same output for the same motif (shapes seeded by motif_id).
"""
from __future__ import annotations

import hashlib
import math
import re
from html import escape

PATH_D = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9.,\s\-]{1,600}$")


def var(role: str | None) -> str:
    return "none" if not role or role == "none" else f"var(--{role.replace('_', '-')})"


def _rng(seed: str):
    h = hashlib.sha1(seed.encode()).digest()
    i = 0
    while True:
        yield h[i % len(h)] / 255
        i += 1


def _f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def path_ok(d: str) -> bool:
    return bool(d) and bool(PATH_D.match(d))


def render(m: dict, w: float, h: float) -> str:
    """-> an <svg> sized to its box (w x h px at 1440), data-motif = motif_id."""
    prim, n = m["primitive"], int(m.get("count") or 4)
    fill, stroke = var(m.get("fill_role")), var(m.get("stroke_role"))
    sw = max(1.0, float(m.get("stroke_width") or 4))
    w, h = max(8.0, w), max(8.0, h)
    rnd = _rng(m["motif_id"])
    body = []
    cx, cy, r = w / 2, h / 2, min(w, h) / 2
    if prim == "ribbon":
        k = max(2, min(5, n))
        band = min(w / (2 * k + 1), sw * 3)
        for i in range(k):
            R = (w - band) / 2 - i * band
            if R <= band:
                break
            col = fill if i % 2 == 0 else stroke
            body.append(f'<path d="M{_f(cx - R)} {_f(h)} L{_f(cx - R)} {_f(band / 2 + i * band + R)} '
                        f'A{_f(R)} {_f(R)} 0 0 1 {_f(cx + R)} {_f(band / 2 + i * band + R)} L{_f(cx + R)} {_f(h)}" '
                        f'fill="none" stroke="{col}" stroke-width="{_f(band)}"/>')
    elif prim == "arch":
        k = max(2, min(6, n))
        for i in range(k):
            R = (w / 2 - sw) * (1 - i / k)
            body.append(f'<path d="M{_f(cx - R)} {_f(h)} A{_f(R)} {_f(R)} 0 0 1 {_f(cx + R)} {_f(h)}" fill="none" '
                        f'stroke="{fill if i % 2 == 0 else stroke}" stroke-width="{_f(sw)}"/>')
    elif prim == "sunburst":
        k = max(8, min(24, n * 2))
        pts = []
        for i in range(k):
            a0, a1 = 2 * math.pi * i / k, 2 * math.pi * (i + 0.5) / k
            pts.append(f'<path d="M{_f(cx)} {_f(cy)} L{_f(cx + r * math.cos(a0))} {_f(cy + r * math.sin(a0))} '
                       f'L{_f(cx + r * math.cos(a1))} {_f(cy + r * math.sin(a1))} Z" fill="{fill}"/>')
        body += pts + [f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r * 0.28)}" fill="{stroke}"/>']
    elif prim in ("badge", "star"):
        k = max(4, min(24, n))
        outer, inner = r - sw, (r - sw) * (0.86 if prim == "badge" else 0.48)
        pts = " ".join(f"{_f(cx + (outer if i % 2 == 0 else inner) * math.cos(math.pi * i / k - math.pi / 2))},"
                       f"{_f(cy + (outer if i % 2 == 0 else inner) * math.sin(math.pi * i / k - math.pi / 2))}"
                       for i in range(2 * k))
        body.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{_f(sw)}" '
                    f'stroke-linejoin="round"/>')
        if prim == "badge":
            body.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(inner * 0.72)}" fill="none" stroke="{stroke}" '
                        f'stroke-width="{_f(max(1, sw / 2))}" stroke-dasharray="3 4"/>')
    elif prim == "tape":
        th = h * 0.42
        y0 = (h - th) / 2
        teeth = max(3, min(9, n))
        left = " ".join(f"{_f(4 * (i % 2))},{_f(y0 + th * i / teeth)}" for i in range(teeth + 1))
        right = " ".join(f"{_f(w - 4 * (i % 2))},{_f(y0 + th * (teeth - i) / teeth)}" for i in range(teeth + 1))
        body.append(f'<polygon points="{left} {right}" fill="{fill}" opacity=".85"/>')
    elif prim == "blob":
        k = max(5, min(9, n + 3))
        ps = []
        for i in range(k):
            a = 2 * math.pi * i / k
            rr = r * (0.7 + 0.3 * next(rnd))
            ps.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d = f"M{_f((ps[0][0] + ps[-1][0]) / 2)} {_f((ps[0][1] + ps[-1][1]) / 2)} "
        for i, p in enumerate(ps):
            q = ps[(i + 1) % k]
            d += f"Q{_f(p[0])} {_f(p[1])} {_f((p[0] + q[0]) / 2)} {_f((p[1] + q[1]) / 2)} "
        body.append(f'<path d="{d}Z" fill="{fill}" stroke="{stroke}" stroke-width="{_f(sw / 2)}"/>')
    elif prim == "dots":
        k = max(3, min(12, n))
        step = min(w, h) / k
        rad = step * 0.18
        for i in range(int(w / step)):
            for j in range(int(h / step)):
                body.append(f'<circle cx="{_f(step * (i + 0.5))}" cy="{_f(step * (j + 0.5))}" r="{_f(rad)}" fill="{fill}"/>')
    elif prim == "stripe_band":
        k = max(3, min(16, n * 2))
        gap = (w + h) / k
        for i in range(k):
            x = i * gap - h
            body.append(f'<line x1="{_f(x)}" y1="{_f(h)}" x2="{_f(x + h)}" y2="0" stroke="{fill if i % 2 else stroke}" '
                        f'stroke-width="{_f(sw)}"/>')
        body.insert(0, f'<clipPath id="c-{escape(m["motif_id"])}"><rect width="{_f(w)}" height="{_f(h)}"/></clipPath>')
        body = [body[0], f'<g clip-path="url(#c-{escape(m["motif_id"])})">', *body[1:], "</g>"]
    elif prim == "squiggle":
        k = max(2, min(8, n))
        d = f"M0 {_f(cy)} " + " ".join(
            f"Q{_f(w * (i + 0.25) / k)} {_f(cy + (h * 0.38) * (1 if i % 2 == 0 else -1))} {_f(w * (i + 0.5) / k)} {_f(cy)} "
            f"T{_f(w * (i + 1) / k)} {_f(cy)}" for i in range(k))
        body.append(f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{_f(sw)}" stroke-linecap="round"/>')
    elif prim == "frame":
        body.append(f'<rect x="{_f(sw)}" y="{_f(sw)}" width="{_f(w - 2 * sw)}" height="{_f(h - 2 * sw)}" fill="none" '
                    f'stroke="{fill}" stroke-width="{_f(sw)}"/>')
        t = min(w, h) * 0.18
        for x, y, dx, dy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
            body.append(f'<path d="M{_f(x)} {_f(y + dy * t)} L{_f(x)} {_f(y)} L{_f(x + dx * t)} {_f(y)}" fill="none" '
                        f'stroke="{stroke}" stroke-width="{_f(sw * 1.5)}"/>')
    elif prim == "perspective_grid":
        k = max(4, min(14, n * 2))
        for i in range(1, k + 1):
            y = h * (i / k) ** 1.8
            body.append(f'<line x1="0" y1="{_f(y)}" x2="{_f(w)}" y2="{_f(y)}" stroke="{fill}" stroke-width="{_f(max(1, sw / 3))}"/>')
        for i in range(-k, k + 1):
            body.append(f'<line x1="{_f(cx)}" y1="0" x2="{_f(cx + i * w / k)}" y2="{_f(h)}" stroke="{stroke}" '
                        f'stroke-width="{_f(max(1, sw / 3))}"/>')
    if path_ok(m.get("path_d") or ""):
        body.append(f'<path d="{escape(m["path_d"])}" transform="scale({_f(w / 100)} {_f(h / 100)})" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{_f(sw)}" vector-effect="non-scaling-stroke"/>')
    return (f'<svg data-motif="{escape(m["motif_id"])}" viewBox="0 0 {_f(w)} {_f(h)}" width="100%" height="100%" '
            f'preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">{"".join(body)}</svg>')
