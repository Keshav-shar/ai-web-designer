"""qa.py - measure a compiled landing page in a real browser (Playwright), at 1440 and 390 px.

These are measurements of whether the spec was rendered well, not style rules. Each applies only when its case
exists on the page (no logo -> no wordmark check, no background image -> no backdrop check, ...):

  text vs decor    a decoration never paints ON TOP of a text line (measured by paint order at the overlap, so a
                   motif layered behind text, as a design may intend, is fine)
  decor vs image   a decoration never paints over more than 15% of an image (a corner sticker is fine)
  text vs text     no two items' text lines overlap
  overflow         no horizontal scroll
  dead space       a panel, card or plated item is not much taller than its content
  hero balance     beside a text panel, the image is not much shorter than the text and their centres line up
  canvas coverage  the hero's content spans at least half the page width (no forgotten empty half)
  gap outliers     inside a group, no gap is far larger than the group's usual rhythm
  backdrop         when A1 chose to use the background image, it covers the viewport, is visible, and opaque
                   surfaces don't hide it everywhere
  wordmark         the logo renders in the wordmark face, weight and size the spec asks for
  readability      every HTML text item: contrast of its colour against the pixels behind it (median, text hidden)
                   and whether it shows any ink at all (a full-page shot with and without text: no pixel changes =
                   covered by something opaque or drawn in its background's colour). SVG <text> is drawing, not copy.
                   Measured, reported and handed to the improver; it never blocks a page.
Returns {width: {problems[], overflow, items, motifs, metrics, readability}} and optional screenshots.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

JS = r"""(path) => {
  const vis = el => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 1 && r.height > 1; };
  const shown = el => { let p = el; while (p && p.nodeType === 1) { if (getComputedStyle(p).display === 'none') return false;
    p = p.parentElement; } return vis(el); };
  const rect = el => { const r = el.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; };
  const lines = el => { const out = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) { if (!n.textContent.trim()) continue;
      if (n.parentElement && n.parentElement.closest('[data-layer]') !== el.closest('[data-layer]')) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const r of rg.getClientRects()) if (r.width > 1 && r.height > 1) out.push([r.left, r.top + scrollY, r.width, r.height]); }
    return out; };
  // the text an item owns: not the text of an item nested inside it (a card holding its tag / heading / body would
  // otherwise "overlap" its own children). Used by the text-over-text check; content() keeps the full text.
  const own = el => { const out = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) { if (!n.textContent.trim() || !n.parentElement) continue;
      if (n.parentElement.closest('[data-item]') !== el) continue;
      if (n.parentElement.closest('[data-layer]') !== el.closest('[data-layer]')) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const r of rg.getClientRects()) if (r.width > 1 && r.height > 1) out.push([r.left, r.top + scrollY, r.width, r.height]); }
    return out; };
  const content = el => { let top = Infinity, bottom = -Infinity;
    const add = b => { top = Math.min(top, b[1]); bottom = Math.max(bottom, b[1] + b[3]); };
    lines(el).forEach(add);
    el.querySelectorAll('img,.cta,.tag,svg').forEach(c => { if (c.closest('[data-layer]') && !el.closest('[data-layer]')) return;
      if (vis(c)) add(rect(c)); });
    return top === Infinity ? null : [top, bottom]; };
  const pads = el => { const s = getComputedStyle(el); return [parseFloat(s.paddingTop) || 0, parseFloat(s.paddingBottom) || 0]; };
  const painted = el => { const s = getComputedStyle(el);
    return (s.backgroundColor && !/rgba\(0, 0, 0, 0\)|transparent/.test(s.backgroundColor)) || (s.backdropFilter && s.backdropFilter !== 'none'); };
  const items = [...document.querySelectorAll('[data-item]')].filter(shown).map(el => ({
    id: el.dataset.item, sec: (el.closest('[data-section]') || {dataset: {}}).dataset.section || '',
    lines: lines(el), own: own(el), box: rect(el), pads: pads(el), content: content(el), painted: painted(el),
    card: el.classList.contains('k-card'), img: el.tagName === 'IMG' || !!el.querySelector('img'),
    imgbox: el.tagName === 'IMG' ? rect(el) : (el.querySelector('img') ? rect(el.querySelector('img')) : null),
    wordmark: el.classList.contains('lv-wordmark') || el.dataset.item === 'logo',
    font: (() => { const s = getComputedStyle(el); return {family: s.fontFamily, size: parseFloat(s.fontSize), weight: s.fontWeight}; })()}));
  const groups = [...document.querySelectorAll('[data-group]')].filter(shown).map(el => ({
    id: el.dataset.group, box: rect(el), pads: pads(el), content: content(el), painted: painted(el),
    kids: [...el.children].filter(c => !c.dataset.layer && !c.closest('[data-layer]') && vis(c)).map(rect)}));
  const plates = [...document.querySelectorAll('header *, main *')].filter(el => !el.closest('[data-layer]') && shown(el)
      && painted(el) && !el.querySelector('img') && el.tagName !== 'IMG' && rect(el)[2] < 0.9 * innerWidth
      && (el.matches('[data-item]') || el.querySelector('[data-item]')) && !el.matches('.cta, .k-cta, a'))
    .map(el => { const inner = el.matches('[data-item]') ? el : el.querySelector('[data-item]');
      return {id: el.dataset.group || el.dataset.item || ((inner && inner.dataset.item) + ' plate'), box: rect(el),
              pads: pads(el), content: content(el)}; });
  const opaque = [...document.querySelectorAll('[data-opaque]')].map(el => ({id: el.dataset.item || el.dataset.group, box: rect(el)}));
  // decoration vs content by real paint order: at the centre of each overlap, is the motif drawn ON TOP of the
  // text / image (covers) or behind it (a deliberate layered overlap, allowed)?
  const pe = document.createElement('style'); pe.textContent = '*{pointer-events:auto!important}';
  document.head.appendChild(pe);
  const itemEls = [...document.querySelectorAll('[data-item]')].filter(shown);
  const hitb = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
  const ov = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) *
    Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  const onTop = (m, host, a, b) => {
    const x = (Math.max(a[0], b[0]) + Math.min(a[0] + a[2], b[0] + b[2])) / 2;
    const y = (Math.max(a[1], b[1]) + Math.min(a[1] + a[3], b[1] + b[3])) / 2;
    window.scrollTo(0, Math.max(0, y - innerHeight / 2));
    const list = document.elementsFromPoint(x, y - scrollY);
    const inM = e => e === m || m.contains(e);
    const ia = list.findIndex(inM);
    const ib = list.findIndex(e => !inM(e) && (e === host || host.contains(e)));
    return ia >= 0 && (ib < 0 || ia < ib); };
  const motifs = [...document.querySelectorAll('[data-motif]')].filter(shown).map(el => {
    const r = el.getBoundingClientRect(); const L = el.closest('[data-layer]'); const R = el.closest('[data-relation]');
    const T = el.closest('[data-target]');
    const box = [r.left, r.top + scrollY, r.width, r.height];
    const layer = L ? L.dataset.layer : '';
    const over = [], overImg = [];
    if (!['z0', 'z50'].includes(layer)) {
      for (const it of itemEls) {
        for (const ln of lines(it)) { if (hitb(box, ln) && onTop(el, it, box, ln)) { over.push(it.dataset.item); break; } }
        const img = it.tagName === 'IMG' ? it : it.querySelector('img');
        if (img && !el.contains(img)) { const ib = rect(img); const o = ov(box, ib);
          if (o > 0.15 * ib[2] * ib[3] && onTop(el, img, box, ib)) overImg.push([it.dataset.item, o / (ib[2] * ib[3])]); }
      } }
    return {id: el.dataset.motif, layer, relation: R ? R.dataset.relation : '', target: T ? T.dataset.target : '',
            box, over, overImg}; });
  window.scrollTo(0, 0);
  let bg = null;
  if (path) {
    const z0s = [...document.querySelectorAll('[data-layer="z0"]')];
    let el = null;
    for (const z0 of z0s) { el = el || [...z0.querySelectorAll('img')].find(i => (i.getAttribute('src') || '') === path)
      || [...z0.querySelectorAll('*'), z0].find(e => getComputedStyle(e).backgroundImage.includes(path)) || null; }
    if (el) { const r = el.getBoundingClientRect(); let op = 1, p = el;
      while (p && p.nodeType === 1) { op *= parseFloat(getComputedStyle(p).opacity); p = p.parentElement; }
      const ix = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
      const iy = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
      let hidden = 0;                                 // sample points where an opaque surface covers the backdrop
      for (const [fx, fy] of [[.15, .2], [.85, .2], [.5, .55], [.15, .85], [.85, .85]]) {
        for (const e of document.elementsFromPoint(fx * innerWidth, fy * innerHeight)) {
          if (e === el || e.closest('[data-layer="z0"]')) break;
          if (e === document.body || e === document.documentElement) continue;
          const m = getComputedStyle(e).backgroundColor.match(/rgba?\(([^)]+)\)/);
          const parts = m ? m[1].split(',') : [];
          const a = m ? (parts.length > 3 ? parseFloat(parts[3]) : 1) : 0;
          if (a >= 0.92) { hidden++; break; } } }
      bg = {found: true, shown: shown(el), opacity: op, cover: (ix * iy) / (innerWidth * innerHeight), hidden}; }
    else bg = {found: false};
  }
  return {items, groups, plates, opaque, motifs, bg, scrollW: document.documentElement.scrollWidth, innerW: innerWidth};
}"""


def _hit(a, b, pad=1.0):
    return a[0] + pad < b[0] + b[2] and b[0] + pad < a[0] + a[2] and a[1] + pad < b[1] + b[3] and b[1] + pad < a[1] + a[3]


def _inside(a, b, slack=2.0):
    return a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[0] + a[2] <= b[0] + b[2] + slack and \
        a[1] + a[3] <= b[1] + b[3] + slack


def _overlap(a, b) -> float:
    return max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def _px(v, d=16.0):
    try:
        return float(str(v).replace("px", ""))
    except (TypeError, ValueError):
        return d


def analyze(data: dict, spec: dict | None = None, width: int = 1440) -> dict:
    probs, metrics = [], {}
    opaque = {o["id"]: o["box"] for o in data.get("opaque", [])}
    imgs = [it for it in data["items"] if it.get("imgbox")]
    for m in data["motifs"]:                     # paint order measured in the browser (JS onTop)
        for iid in m.get("over", []):
            probs.append(f"motif {m['id']} ({m['layer'] or 'decor'}) covers text of {iid}")
        for iid, frac in m.get("overImg", []):
            if iid != m.get("target"):
                probs.append(f"motif {m['id']} ({m['layer'] or 'decor'}) covers image {iid} ({round(100 * frac)}% of it)")
    its = data["items"]
    for i in range(len(its)):
        for j in range(i + 1, len(its)):
            a_, b_ = its[i].get("own", its[i]["lines"]), its[j].get("own", its[j]["lines"])
            if any(_hit(a, b, 2) for a in a_ for b in b_):          # each item's own text, not its nested items'
                probs.append(f"text of {its[i]['id']} overlaps text of {its[j]['id']}")
    over = data["scrollW"] > data["innerW"] + 1
    if over:
        probs.append(f"horizontal overflow: {data['scrollW']}px > {data['innerW']}px")
    # dead space: any painted box holding content (a panel, a card, a plate around an item, whatever the markup),
    # and the hero's text group, that is much taller than what it holds
    boxes = [g for g in data.get("groups", []) if g["id"] == "hero_text" and not g.get("painted")]
    card_ids = {x["item_id"] for x in (spec or {}).get("items", []) if x.get("kind") == "card"}
    boxes += [it for it in its if it["card"] or it["id"] in card_ids] + data.get("plates", [])
    seen = set()
    for b in boxes:
        key = tuple(round(v) for v in b["box"])
        if not b.get("content") or key in seen:
            continue
        seen.add(key)
        inner_bottom = b["box"][1] + b["box"][3] - b["pads"][1]
        dead = inner_bottom - b["content"][1]
        if dead > max(40.0, 0.2 * b["box"][3]):
            probs.append(f"dead space: {b['id']} is {round(b['box'][3])}px tall but its content ends "
                         f"{round(dead)}px above its inner bottom")
    groups = {g["id"]: g for g in data.get("groups", [])}
    # the hero: a section of the design document (data-section) or the fallback page's groups
    hero_sec = ((spec or {}).get("layout") or {}).get("hero_section")
    t, im = None, None
    if hero_sec:
        hero_its = [x for x in its if x.get("sec") == hero_sec]
        tl = [ln for x in hero_its if not x.get("imgbox") for ln in x["lines"]]
        if tl:
            x0, x1 = min(b[0] for b in tl), max(b[0] + b[2] for b in tl)
            t = {"box": [x0, min(b[1] for b in tl), x1 - x0, 0],
                 "content": [min(b[1] for b in tl), max(b[1] + b[3] for b in tl)]}
        im = next((x for x in hero_its if x.get("imgbox")), None)
        spans = tl + [x["imgbox"] for x in hero_its if x.get("imgbox")]
    else:
        t = groups.get("hero_text")
        im = next((x for x in imgs if (groups.get("hero_media") and _inside(x["imgbox"], groups["hero_media"]["box"], 4))), None)
        spans = [b for g_ in ("hero_text", "hero_media") if g_ in groups for b in [groups[g_]["box"]]]
    if width >= 1024 and spans:                      # canvas coverage
        cov = (max(b[0] + b[2] for b in spans) - min(b[0] for b in spans)) / max(1, data["innerW"])
        metrics["hero_coverage"] = round(cov, 2)
        if cov < 0.5:
            probs.append(f"canvas coverage: the hero's content spans only {round(100 * cov)}% of the page width, "
                         f"leaving the rest empty")
    # hero balance: only when the text block and the image sit side by side
    if width >= 1024 and t and t.get("content") and im:
        ib = im["imgbox"]
        side = ib[0] >= t["box"][0] + t["box"][2] - 2 or ib[0] + ib[2] <= t["box"][0] + 2
        if side:
            th = t["content"][1] - t["content"][0]
            tc = (t["content"][0] + t["content"][1]) / 2
            ic = ib[1] + ib[3] / 2
            metrics["hero"] = {"text_h": round(th), "image_h": round(ib[3]), "centre_gap": round(abs(tc - ic))}
            if ib[3] < 0.6 * th:
                probs.append(f"hero balance: the image is {round(ib[3])}px tall beside {round(th)}px of text")
            elif abs(tc - ic) > 0.25 * max(th, ib[3]):
                probs.append(f"hero balance: the text and the image centres are {round(abs(tc - ic))}px apart")
    # gap outliers inside a group (a stack of blocks with one rhythm)
    for g in data.get("groups", []):
        if g["id"] in ("cards", "nav", "hero_media") or len(g["kids"]) < 3:
            continue
        ks = sorted(g["kids"], key=lambda k: k[1])
        gaps = [b[1] - (a[1] + a[3]) for a, b in zip(ks, ks[1:]) if b[1] >= a[1] + a[3] - 2]
        if len(gaps) >= 2:
            worst = max(gaps)
            rest = sorted(gaps)[:-1]                     # the group's usual rhythm, without the gap in question
            med = statistics.median(rest)
            if worst > max(96.0, 3 * max(med, 8)):
                probs.append(f"gap outlier in {g['id']}: {round(worst)}px between two blocks (the others ~{round(med)}px)")
    # the backdrop A1 asked for
    bgspec = (spec or {}).get("background") or {}
    if bgspec.get("image"):
        bg = data.get("bg") or {"found": False}
        metrics["backdrop"] = bg
        if not bg.get("found"):
            probs.append(f"backdrop: the background image {bgspec['image']} is not in the z0 layer")
        elif not bg.get("shown") or bg.get("opacity", 1) < 0.15:
            probs.append(f"backdrop: the background image is invisible (opacity {bg.get('opacity', 0):.2f})")
        elif bg.get("cover", 0) < 0.9:
            probs.append(f"backdrop: the background image covers only {round(100 * bg['cover'])}% of the viewport")
        elif bg.get("hidden", 0) >= 4:
            probs.append(f"backdrop: opaque surfaces hide the background image at {bg['hidden']} of 5 sample points")
    # the wordmark A1 designed
    lv = ((spec or {}).get("levels") or {}).get("wordmark")
    logo_id = next((x["item_id"] for x in (spec or {}).get("items", []) if x.get("kind") == "logo"), None)
    logo = next((x for x in its if x["id"] == logo_id), None)
    if width >= 1024 and lv and logo:
        want = lv.get("size_px") or _px((spec.get("type_scale") or {}).get(lv.get("size_token", "--fs-3")), 25)
        f = logo["font"]
        metrics["wordmark"] = {"family": f["family"][:60], "size": f["size"], "weight": f["weight"], "want": want}
        if lv["family"].lower() not in f["family"].lower():
            probs.append(f"wordmark: rendered in {f['family'][:40]}, the spec's wordmark face is {lv['family']}")
        if f["size"] < 0.85 * want:
            probs.append(f"wordmark: rendered at {round(f['size'])}px, the spec asks for ~{round(want)}px")
        if str(f["weight"]) != str(lv["weight"]):
            probs.append(f"wordmark: rendered at weight {f['weight']}, the spec asks for {lv['weight']}")
    return {"problems": list(dict.fromkeys(probs)), "overflow": over, "items": len(its), "motifs": len(data["motifs"]),
            "metrics": metrics}


READ_JS = r"""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (w.nextNode()) { const t = w.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || seen.has(el) || el.closest('svg')) continue; seen.add(el);
    let p = el, hid = false, op = 1;
    while (p && p.nodeType === 1) { const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility === 'hidden') { hid = true; break; } op *= parseFloat(s.opacity); p = p.parentElement; }
    if (hid || op < 0.05) continue;
    const r = document.createRange(); r.selectNodeContents(t); const b = r.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) continue;
    const cs = getComputedStyle(el);
    out.push({item: (el.closest('[data-item]') || {dataset: {}}).dataset.item || '', tag: el.tagName.toLowerCase(),
      text: t.textContent.trim().replace(/\s+/g, ' ').slice(0, 60), color: cs.color, x: b.left + scrollX, y: b.top + scrollY,
      w: b.width, h: b.height, fs: parseFloat(cs.fontSize), fw: parseInt(cs.fontWeight) || 400}); }
  return out; }"""
HIDE_TEXT = ("*{color:transparent!important;text-shadow:none!important;-webkit-text-stroke:0!important;"
             "text-decoration-color:transparent!important;caret-color:transparent!important}")


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def _ratio(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readability(pg) -> dict:
    """Rendered text vs what is really behind it (see the module doc). -> {texts, unreadable: [...]}; restores the page."""
    import io
    import re
    from PIL import Image, ImageChops
    items = pg.evaluate(READ_JS)
    fg = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
    tag = pg.add_style_tag(content=HIDE_TEXT)
    pg.wait_for_timeout(150)
    bg = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
    tag.evaluate("el => el.remove()")
    bad, seen = [], set()
    for it in items:
        v = [float(x) for x in re.findall(r"[\d.]+", it["color"])]
        c, a = tuple(int(x) for x in v[:3]), (v[3] if len(v) > 3 else 1.0)
        x0, y0 = max(0, int(it["x"])), max(0, int(it["y"]))
        x1, y1 = min(bg.width, int(it["x"] + it["w"])), min(bg.height, int(it["y"] + it["h"]))
        if x1 <= x0 or y1 <= y0:
            continue
        crop = bg.crop((x0, y0, x1, y1))
        px = list(crop.resize((12, 6)).getdata())
        med = tuple(int(statistics.median(q[i] for q in px)) for i in range(3))
        ink = None
        if fg.size == bg.size:
            hist = ImageChops.difference(fg.crop((x0, y0, x1, y1)), crop).convert("L").histogram()
            ink = sum(hist[25:]) / max(1, sum(hist))
        if a < 1:
            c = tuple(round(a * c[i] + (1 - a) * med[i]) for i in range(3))
        cr = _ratio(c, med)
        need = 3.0 if it["fs"] >= 24 or (it["fs"] >= 18.66 and it["fw"] >= 700) else 4.5
        visible = ink is None or ink >= 0.01
        if cr < need or not visible:
            key = (it["item"] or it["tag"], it["text"])
            if key in seen:
                continue
            seen.add(key)
            bad.append({"item": it["item"] or it["tag"], "text": it["text"], "fg": "#%02X%02X%02X" % c,
                        "bg": "#%02X%02X%02X" % med, "ratio": round(cr, 2), "need": need,
                        "ink": None if ink is None else round(ink, 3), "visible": visible, "y": int(it["y"])})
    bad.sort(key=lambda r: (r["visible"], r["ratio"]))
    return {"texts": len(items), "unreadable": bad}


def readability_problems(r: dict, top: int = 8) -> list[str]:
    out = []
    for b in (r or {}).get("unreadable", [])[:top]:
        why = ("shows no ink (covered, or drawn in the colour behind it)" if not b["visible"]
               else f"{b['fg']} on {b['bg']} is {b['ratio']}:1, needs {b['need']}:1")
        out.append(f"unreadable text: {b['item']} \"{b['text'][:40]}\" {why}")
    return out


def _jpeg(png: bytes, path: Path, width: int | None = None, max_h: int | None = None) -> None:
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if max_h and im.height > max_h:
        im = im.crop((0, 0, im.width, max_h))
    im.save(path, "JPEG", quality=82, optimize=True)


def run(index_html: Path, widths=(1440, 390), shots: bool = False, spec: dict | None = None,
        shots_dir: Path | None = None, read: bool = True) -> dict:
    from labio import SERPMAN_SRC
    if str(SERPMAN_SRC) not in sys.path:
        sys.path.insert(0, str(SERPMAN_SRC))
    import serpman_paths  # noqa: F401  (Playwright browsers on D:)
    from playwright.sync_api import sync_playwright
    index_html = Path(index_html)
    if spec is None and (index_html.parent / "spec.json").exists():
        spec = json.loads((index_html.parent / "spec.json").read_text(encoding="utf-8"))
    path = ((spec or {}).get("background") or {}).get("image")
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            for w in widths:
                pg = b.new_page(viewport={"width": w, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
                pg.goto(index_html.resolve().as_uri(), wait_until="networkidle", timeout=60_000)
                pg.wait_for_timeout(400)
                res = analyze(pg.evaluate(JS, path), spec, w)
                if read:
                    res["readability"] = readability(pg)
                    res["problems"] = list(dict.fromkeys(res["problems"] + readability_problems(res["readability"])))
                if shots:
                    res["png"] = pg.screenshot(full_page=True)
                if shots_dir:                                # what the improver looks at
                    shots_dir.mkdir(parents=True, exist_ok=True)
                    if w >= 1024:
                        _jpeg(pg.screenshot(), shots_dir / f"{w}_fold.jpg")
                        _jpeg(pg.screenshot(full_page=True), shots_dir / f"{w}_full.jpg", width=960, max_h=7000)
                    else:
                        _jpeg(pg.screenshot(full_page=True), shots_dir / f"{w}_full.jpg", max_h=5200)
                out[w] = res
                pg.close()
        finally:
            b.close()
    return out
