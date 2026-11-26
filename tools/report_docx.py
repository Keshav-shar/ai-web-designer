"""report_docx.py - build a Word report from collect_jobs.py folders + a notes module (the written analysis).

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\report_docx.py DATA_DIR NOTES.py OUT.docx

DATA_DIR holds one folder per job (job.json, result.json, spec.json, contrast.json, journal.txt, shots/, refs/).
NOTES.py defines TITLE, SUBTITLE, ORDER (job8 list), JOBS {job8: {...}} and build_front(doc, R) / build_back(doc, R)
hooks that write the narrative chapters with the helpers in R (this module).
Facts (models, times, tokens, fallbacks, counts, measurements) are read from the data, never typed by hand.
"""
from __future__ import annotations

import io
import json
import re
import runpy
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

INK = RGBColor(0x1F, 0x23, 0x2B)
MUTED = RGBColor(0x5A, 0x62, 0x70)
ACCENT = RGBColor(0x1E, 0x5A, 0x8C)
BAD = RGBColor(0xB0, 0x2A, 0x1E)
GOOD = RGBColor(0x2A, 0x7A, 0x3B)
HEAD_FILL = "E8EDF3"

# --------------------------------------------------------------------------- what each model is
MODEL_INFO = {
    "gemini-4-hydrogen": ("Gemini 4 Hydrogen", "Google", "multimodal (image + text), free tier"),
    "gemini-3.8-flash": ("Gemini 3.8 Flash", "Google", "multimodal flash model, free tier"),
    "gemini-3.6-flash": ("Gemini 3.6 Flash", "Google", "multimodal flash model, free tier"),
    "gemma-4-31b-it": ("Gemma 4 31B", "Google (Gemini API)", "open-weight multimodal, 31B"),
    "gemma-4-26b-a4b-it": ("Gemma 4 26B-A4B", "Google (Gemini API)", "open-weight multimodal MoE"),
    "inclusionai/ling-3.2-flash:free": ("Ling 3.2 Flash", "OpenRouter (inclusionAI)", "vision-language, free pool"),
    "nvidia/nemotron-3.5-super-vl:free": ("Nemotron 3.5 Super VL", "OpenRouter (NVIDIA)",
                                          "vision-language reasoning model, free pool"),
    "nvidia/nemotron-3-ultra-550b-a55b:free": ("Nemotron 3 Ultra 550B-A55B", "OpenRouter (NVIDIA)",
                                               "text-only MoE, 550B total / 55B active, long context, free pool"),
    "openai/gpt-oss-120b": ("gpt-oss-120b", "Groq", "open-weight text MoE, 120B"),
    "qwen/qwen3.8-27b": ("Qwen 3.8 27B", "Groq", "vision-capable 27B, used text-only here"),
    "ministral-14b-latest": ("Ministral 14B", "Mistral", "small multimodal model, free tier"),
    "ministral-8b-latest": ("Ministral 8B", "Mistral", "small text model, free tier"),
    "codestral-latest": ("Codestral", "Mistral", "code model"),
    "mistral-medium-latest": ("Mistral Medium", "Mistral", "mid-size multimodal"),
}

AGENT_ROLE = {
    "a1": "A1 · Art director (sees the images)",
    "a2": "A2 · Layout planner",
    "a3": "A3 · Copywriter",
    "a4": "A4 · Decoration artist",
    "a5": "A5 · Composer (writes the page)",
    "a6": "A6 · Improver (sees the rendered page)",
}


def model_info(mid: str | None):
    if not mid:
        return ("code (no model)", "-", "deterministic default")
    k = mid.replace("openrouter/", "")
    name, prov, typ = MODEL_INFO.get(k, (k, "?", "?"))
    return name, prov, typ


# --------------------------------------------------------------------------- docx helpers
def shade(cell, hexfill: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexfill.lstrip("#").upper())
    tcPr.append(shd)


def cell_margins(table, top=50, bottom=50, left=80, right=80):
    tblPr = table._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    tblPr.append(m)


def keep_header(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trPr.append(e)


def run(p, text, bold=False, italic=False, size=None, color=None, mono=False):
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color
    if mono:
        r.font.name = "Consolas"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    return r


def para(doc_or_cell, text="", size=10.5, bold=False, italic=False, color=None, align=None, space_after=4, mono=False):
    p = doc_or_cell.add_paragraph()
    if text:
        # **bold** spans inside text
        parts = re.split(r"(\*\*[^*]+\*\*)", text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                run(p, part[2:-2], bold=True, italic=italic, size=size, color=color, mono=mono)
            elif part:
                run(p, part, bold=bold, italic=italic, size=size, color=color, mono=mono)
    p.paragraph_format.space_after = Pt(space_after)
    if align:
        p.alignment = align
    return p


def bullet(doc, text, level=0, size=10.5):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run(p, part[2:-2], bold=True, size=size)
        elif part:
            run(p, part, size=size)
    p.paragraph_format.space_after = Pt(2)
    return p


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = INK if level > 1 else ACCENT
    return h


def table(doc, header: list[str], rows: list[list], widths: list[float] | None = None, size=9, head_fill=HEAD_FILL,
          fills: dict | None = None):
    """rows: lists of str (or callables(cell) for custom content). fills: {(r, c): hex} for shaded cells."""
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_margins(t)
    hdr = t.rows[0]
    keep_header(hdr)
    for i, h in enumerate(header):
        c = hdr.cells[i]
        c.paragraphs[0].text = ""
        run(c.paragraphs[0], h, bold=True, size=size, color=INK)
        shade(c, head_fill)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, v in enumerate(row):
            c = cells[ci]
            if callable(v):
                v(c)
                continue
            c.paragraphs[0].text = ""
            parts = re.split(r"(\*\*[^*]+\*\*)", str(v))
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    run(c.paragraphs[0], part[2:-2], bold=True, size=size)
                elif part:
                    run(c.paragraphs[0], part, size=size)
            if fills and (ri, ci) in fills:
                shade(c, fills[(ri, ci)])
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def picture(doc_or_cell, path: Path | bytes, width_in: float):
    p = doc_or_cell.add_paragraph() if not hasattr(doc_or_cell, "paragraphs") or doc_or_cell.paragraphs[0].text \
        else doc_or_cell.paragraphs[0]
    r = p.add_run()
    src = io.BytesIO(path) if isinstance(path, (bytes, bytearray)) else str(path)
    r.add_picture(src, width=Inches(width_in))
    p.paragraph_format.space_after = Pt(2)
    return p


def caption(doc_or_cell, text, size=8):
    p = doc_or_cell.add_paragraph()
    run(p, text, italic=True, size=size, color=MUTED)
    p.paragraph_format.space_after = Pt(4)
    return p


def chunks(img_path: Path, aspect: float, maxn: int) -> list[bytes]:
    """Cut a tall full-page shot into screen-sized pieces (height = width * aspect)."""
    im = Image.open(img_path).convert("RGB")
    h = int(im.width * aspect)
    out = []
    for y in range(0, im.height, h):
        if len(out) >= maxn:
            break
        piece = im.crop((0, y, im.width, min(im.height, y + h)))
        if piece.height < 40:
            break
        b = io.BytesIO()
        piece.save(b, "JPEG", quality=82)
        out.append(b.getvalue())
    return out


def thumb_bytes(path: Path, max_aspect: float = 1.25) -> bytes:
    """A reference image for the gallery: tall screenshots are cut to their top (height <= width * max_aspect)."""
    im = Image.open(path).convert("RGB")
    if im.height > im.width * max_aspect:
        im = im.crop((0, 0, im.width, int(im.width * max_aspect)))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return b.getvalue()


def grid_images(doc, images: list[bytes | Path], cols: int, width_in: float, captions: list[str] | None = None):
    t = doc.add_table(rows=0, cols=cols)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i in range(0, len(images), cols):
        cells = t.add_row().cells
        for j, im in enumerate(images[i:i + cols]):
            picture(cells[j], im, width_in)
            if captions:
                caption(cells[j], captions[i + j])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def verdict_cell(c):
    c.paragraphs[0].text = ""
    run(c.paragraphs[0], "☐ Good   ☐ Wrong", size=9)


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------------------- data
def load(d: Path) -> dict:
    j = {k: json.loads((d / f"{k}.json").read_text(encoding="utf-8")) for k in ("job", "result", "spec", "contrast")
         if (d / f"{k}.json").exists()}
    j["journal"] = (d / "journal.txt").read_text(encoding="utf-8") if (d / "journal.txt").exists() else ""
    j["dir"] = d
    m = re.search(r"took (\d+)s \(([^)]*)\)", j["journal"])
    j["took"] = int(m.group(1)) if m else None
    j["steps"] = {k: int(v) for k, v in re.findall(r"(\w+) (\d+)s", m.group(2))} if m else {}
    return j


def readable_rows(J, page="index", width="1440"):
    rows = ((J.get("contrast") or {}).get(page) or {}).get(width, {}).get("contrast") or []
    return rows, [r for r in rows if not (r["ratio"] >= r["need"] and r["visible"])]


def why_unreadable(r):
    if not r["visible"]:
        if r["ratio"] < 1.5 or not r.get("covered_by"):
            return f"no visible ink: drawn in the colour of what's under it ({r['ratio']}:1)"
        return f"no visible ink: covered by {r['covered_by']}"
    return f"contrast {r['ratio']}:1, needs {r['need']}:1"


def tried_text(t):
    out = []
    for x in t.get("tried") or []:
        name = model_info(x.get("model"))[0]
        why = x.get("error") or x.get("skip") or ""
        why = re.sub(r"HTTP 503: This model is currently experiencing high demand.*", "HTTP 503 overloaded", why)
        out.append(f"{name}: {why[:70]}")
    return "; ".join(out) or "-"


def agent_rows(J) -> list[list]:
    r, s = J["result"], J["spec"]
    raw = r.get("raw") or {}
    dd, lp, cp, dc = raw.get("design_doc") or {}, raw.get("layout_plan") or {}, raw.get("copy") or {}, raw.get("decor") or {}
    steps = J["steps"]
    job = J["job"]
    n_refs = sum(len(v) for v in (job.get("refs") or {}).values())
    rows = [["Route (code)", "CLIP + lab data (no LLM)", "deterministic",
             f"prompt → rule-based split → family **{(job.get('meta') or {}).get('routed_family')}** "
             f"({(job.get('vibe') or {}).get('name')}) → reference images, palette, fonts",
             f"{steps.get('route', '?')} s", "-", "-"]]
    a1d = r.get("a1_depth") or {}
    typo = dd.get("typography") or {}
    fams = ", ".join(dict.fromkeys(v.get("family") for v in typo.values() if isinstance(v, dict) and v.get("family")))
    what = {
        "a1": f"5 labelled reference images + the request + a font pool → design document: {a1d.get('colours')} named "
              f"colours ({a1d.get('colours_traced')} traced to an image), type system ({fams}), "
              f"{a1d.get('elements')} decor elements, {a1d.get('sections')} content sections, centerpiece "
              f"{'brief (to be drawn)' if (dd.get('centerpiece') or {}).get('use') else 'none'}",
        "a2": f"design document → layout plan: {len(lp.get('sections') or [])} sections laid out, "
              f"{len(lp.get('layers') or [])} decor layers placed, canvas {(lp.get('canvas') or {}).get('content_width_px', '?')} px",
        "a3": f"design document + plan → copy: {len(cp.get('items') or [])} text items "
              f"(h1: “{next((i.get('text') for i in cp.get('items') or [] if i.get('kind') == 'h1'), '?')}”)",
        "a4": f"design document + plan → {len(dc.get('assets') or [])} decorations "
              f"({sum(1 for a in dc.get('assets') or [] if a.get('kind') == 'svg')} SVG, "
              f"{sum(1 for a in dc.get('assets') or [] if a.get('kind') == 'css')} CSS), intent “{dc.get('intent', '')}”",
        "a5": f"merged spec ({len(s.get('items') or [])} items, {len(s.get('colors') or [])} colours, "
              f"{len(s.get('decor') or []) if isinstance(s.get('decor'), list) else '?'} decor, "
              f"{len(s.get('assets') or [])} images; no images sent) → a full HTML/CSS page",
    }
    for t in r.get("trace") or []:
        ag = t["agent"]
        name, prov, typ = model_info(t.get("model"))
        u = t.get("usage") or {}
        tok = f"{u.get('in', 0):,} / {u.get('out', 0):,} / {u.get('thinking', 0):,}" if u else "-"
        label = AGENT_ROLE.get(ag, ag)
        w = what.get(ag, "")
        if ag == "a1" and t.get("depth", {}).get("thin"):
            dp = t["depth"]
            w += (f" · DEPTH GATE: first document thin ({'; '.join(dp['thin'])}) on "
                  f"{model_info(dp['first'].get('model'))[0]}; asked the next model: "
                  + (f"{model_info(dp['second'].get('model'))[0]} wrote {dp['second'].get('chars')} chars, "
                     f"{dp['second'].get('words_per_section')} words/section" if dp.get("second", {}).get("model")
                     else f"failed ({dp.get('second', {}).get('error', '')[:80]})")
                  + f" → kept the {dp.get('kept')}")
        if ag == "a6":
            cands = {c["file"]: c for c in r.get("candidates") or []}
            base = cands.get(t.get("improves") or "a5-1.html", {})
            imp = cands.get("a6.html", {})
            w = (f"A5's rendered page (screenshot tiles, 1440 + 390 px) + {len(base.get('advisory') or [])} measured "
                 f"findings + the markup → the improved page ({len(imp.get('advisory') or [])} findings left)"
                 + (f" · REJECTED: {t['rejected']}" if t.get("rejected") else ""))
            if t.get("source") == "failed":
                name, prov, typ = "no model answered", "-", "A5's page shipped"
                w = "; ".join(t.get("why") or [])[:200]
        if t.get("source") == "repaired":
            label = "A5 · Repair round"
            w = "its page + the gate's findings → page v2. Findings: " + "; ".join((t.get("why") or [])[:3])[:300]
        elif t.get("source") == "default":
            name, prov, typ = "code default", "-", "model output failed the schema"
            w = "(fell back to the code default) " + "; ".join(str(x)[:120] for x in (t.get("why") or [])[:1])
        rows.append([label, f"**{name}**\n{prov}", typ, w, f"{(t.get('ms') or 0) / 1000:.0f} s model"
                     + (f"\n{steps.get(ag)} s step" if ag in steps and t.get("source") != "repaired" else ""),
                     tok, tried_text(t)])
    qa = r.get("qa") or {}
    probs = sum(len(v.get("problems") or []) for v in qa.values())
    rows.append(["Gate + QA (code)", "sanitizer, fixers, Chromium at 1440 / 390 px", "deterministic",
                 f"{len(r.get('overrides') or [])} code changes logged, {probs} QA findings on the shipped page; "
                 f"shipped: **{r.get('page_source')}**", f"{steps.get('check', '?')} s", "-", "-"])
    rows.append(["Publish (code)", "Supabase upload + mockup", "deterministic", "page + images → Studio site",
                 f"{steps.get('publish', '?')} s", "-", "-"])
    return rows


def palette_table(doc, J):
    dd = (J["result"].get("raw") or {}).get("design_doc") or {}
    rm = dd.get("role_map") or {}
    if not rm:
        return
    roles = list(rm.items())
    rows, fills = [], {}
    for i, (k, v) in enumerate(roles):
        rows.append([k.replace("_", " "), str(v), ""])
        if isinstance(v, str) and re.match(r"^#[0-9A-Fa-f]{6}$", v):
            fills[(i, 2)] = v
    table(doc, ["A1 role", "hex", "swatch"], rows, widths=[1.6, 0.9, 0.9], size=8, fills=fills)


def ref_gallery(doc, J):
    d = J["dir"] / "refs"
    job = J["job"]
    by = {a["ref_id"]: a for a in job.get("assets") or []}
    order = ["layout", "background", "palette", "hero", "central"]
    ims, caps = [], []
    for role in order:
        for name in (job.get("refs") or {}).get(role, []):
            rid = name.split("_", 1)[1].rsplit(".", 1)[0]
            a = by.get(rid, {})
            rel = a.get("relevance")
            cap = f"{role} · {a.get('type', '')}"
            if rel is not None:
                cap += f" · relevance {rel:+.3f} → {'ON PAGE' if a.get('on_page') else 'reference only'}"
            ims.append(thumb_bytes(d / name))
            caps.append(cap)
    if ims:
        grid_images(doc, ims, 4, 1.62, caps)


def shots(doc, J, notes):
    sd = J["dir"] / "shots"
    src = J["result"].get("page_source")
    if (sd / "index_1440_fold.jpg").exists():
        if src in ("repaired", "improved") and (sd / "a5-1_1440_fold.jpg").exists():
            after = "the improver (A6)" if src == "improved" else "the repair round"
            grid_images(doc, [sd / "a5-1_1440_fold.jpg", sd / "index_1440_fold.jpg"], 2, 3.35,
                        [f"A5's page (before {after}), first screen at 1440 px",
                         f"The page that shipped (after {after}), first screen at 1440 px"])
        else:
            picture(doc, sd / "index_1440_fold.jpg", 6.7)
            caption(doc, "The page that shipped, first screen at 1440 px")
    if (sd / "index_1440_full.jpg").exists():
        para(doc, "Whole page at 1440 px, top to bottom:", size=9, bold=True)
        grid_images(doc, chunks(sd / "index_1440_full.jpg", 1.15, 8), 3, 2.2)
    if (sd / "index_390_full.jpg").exists():
        para(doc, "Phone (390 px), first three screens:", size=9, bold=True)
        grid_images(doc, chunks(sd / "index_390_full.jpg", 2.0, 3), 3, 1.7)


def readability(doc, J):
    rows, bad = readable_rows(J)
    rows3, bad3 = readable_rows(J, "index", "390")
    para(doc, f"Rendered text check (measured on the shipped page in Chromium): **{len(bad)} of {len(rows)}** text "
              f"items unreadable at 1440 px, **{len(bad3)} of {len(rows3)}** at 390 px.", size=9.5)
    if "a5-1" in (J.get("contrast") or {}) and J["result"].get("page_source") in ("repaired", "improved"):
        r1, b1 = readable_rows(J, "a5-1", "1440")
        what = "the improver" if J["result"].get("page_source") == "improved" else "the repair round"
        para(doc, f"A5's page before {what}: {len(b1)} of {len(r1)} unreadable at 1440 px.", size=9.5, color=MUTED)
    if bad:
        seen, out = set(), []
        for r in sorted(bad, key=lambda x: (x["visible"], x["ratio"])):
            k = (r["item"], r["text"])
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        trs, fills = [], {}
        for i, r in enumerate(out[:10]):
            trs.append([r["item"] or r["tag"], r["text"][:40], r["fg"], r["bg"], why_unreadable(r)])
            fills[(i, 2)] = r["fg"]
            fills[(i, 3)] = r["bg"]
        table(doc, ["item", "text", "text colour", "behind it", "why unreadable"], trs,
              widths=[1.3, 1.9, 0.8, 0.8, 2.0], size=8, fills=fills)


def phase_verdicts(doc, J, notes):
    jn = dict(notes.get("phases") or {})
    if not jn and J.get("result"):                  # no written notes: each phase says who did it, from the trace
        for t in J["result"]["trace"]:
            key = "repair" if t.get("source") == "repaired" else t["agent"]
            if key in jn:
                continue
            who = "code default" if t.get("source") == "default" else model_info(t.get("model"))[0]
            jn[key] = f"{who} · {t.get('source')} · {(t.get('ms') or 0) / 1000:.0f} s"
        jn["page"] = f"shipped: {J['result'].get('page_source')}"
    rows = []
    for key, label in (("route", "Route (family, images)"), ("a1", "A1 design document"), ("a2", "A2 layout plan"),
                       ("a3", "A3 copy"), ("a4", "A4 decorations"), ("a5", "A5 page"),
                       ("repair", "A5 repair round"), ("a6", "A6 improver"), ("page", "Final page")):
        if key in jn:
            rows.append([label, jn[key], verdict_cell, ""])
    if rows:
        table(doc, ["phase", "what I see (my analysis)", "your verdict", "your note"], rows,
              widths=[1.2, 3.9, 1.15, 0.75], size=8.5)


def journal_block(doc, J, max_lines=40):
    lines = []
    for ln in J["journal"].splitlines():
        m = re.match(r"(\S+)\s+\S+\s+python\[\d+\]:\s*(.*)", ln)
        if not m:
            continue
        t, msg = m.group(1)[11:19], m.group(2)
        msg = re.sub(r"^\d\d:\d\d:\d\d \[landing\] ", "", msg)
        msg = re.sub(r"\(overloaded: HTTP 503: This model is currently experiencing high demand\.[^)]*\)", "(HTTP 503)", msg)
        lines.append(f"{t}  {msg[:230]}")
    for ln in lines[:max_lines]:
        p = para(doc, ln, size=7, mono=True, space_after=0)
        p.paragraph_format.left_indent = Cm(0.3)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def job_chapter(doc, J, n, notes):
    job, r = J["job"], J["result"]
    row = job["row"]
    heading(doc, f"{n}. “{row.get('prompt')}”", 1)
    if notes.get("headline"):
        para(doc, notes["headline"], size=11, bold=True, color=BAD if notes.get("bad", True) else GOOD)
    sp = row.get("split") or {}
    meta = job.get("meta") or {}
    tst = job.get("taste") or {}
    table(doc, ["", ""], [
        ["Job", f"{row.get('id')} · {str(row.get('created_at'))[:16].replace('T', ' ')} UTC · status {row.get('status')}"],
        ["Total time", f"**{J['took']} s** (" + ", ".join(f"{k} {v}s" for k, v in J["steps"].items()) + ")"
         if J["took"] else "?"],
        ["Split", f"source “{sp.get('source')}” · vibe query: “{sp.get('vibe_query', '')[:160]}”"],
        ["Routed to", f"family **{meta.get('routed_family')}** · vibe “{(job.get('vibe') or {}).get('name')}” · niche "
                      f"“{tst.get('niche')}” · category {tst.get('category')}"],
        ["Shipped", f"**{r.get('page_source')}** page · candidates: " + ", ".join(
            f"#{c['n']} {c['source']}" for c in r.get("candidates") or [])],
    ], widths=[1.2, 5.8], size=8.5, head_fill="FFFFFF")
    if notes.get("observations"):
        heading(doc, "What happened", 2)
        for o in notes["observations"]:
            if o.startswith("  – "):
                bullet(doc, o[4:], level=1, size=10)
            else:
                bullet(doc, o, size=10)
    heading(doc, "The agents: model, what it turned into what, time, tokens", 2)
    table(doc, ["step", "model / provider", "type", "turned what → into what", "time", "tokens in / out / thinking",
                "tried first (why it moved on)"],
          agent_rows(J), widths=[1.0, 1.15, 0.95, 2.1, 0.6, 0.8, 1.4], size=7.5)
    heading(doc, "Reference images the route picked (what A1 looked at)", 2)
    ref_gallery(doc, J)
    heading(doc, "A1's palette roles", 2)
    palette_table(doc, J)
    heading(doc, "Screens", 2)
    shots(doc, J, notes)
    heading(doc, "Readability of the shipped page", 2)
    readability(doc, J)
    heading(doc, "Phase-by-phase: your verdict", 2)
    phase_verdicts(doc, J, notes)
    page_break(doc)


def new_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(1.6))
    sec.top_margin, sec.bottom_margin = Cm(1.5), Cm(1.5)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st.font.color.rgb = INK
    return doc


def main():
    data, notes_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    N = runpy.run_path(str(notes_path))
    R = sys.modules[__name__]
    jobs = {p.name: load(p) for p in data.iterdir() if p.is_dir() and (p / "job.json").exists()}
    doc = new_doc()
    t = para(doc, N["TITLE"], size=22, bold=True, color=ACCENT, space_after=2)
    para(doc, N["SUBTITLE"], size=11, color=MUTED, space_after=10)
    N["build_front"](doc, R, jobs)
    for i, k in enumerate(N["ORDER"], 1):
        if k in jobs:
            job_chapter(doc, jobs[k], N.get("NUM", {}).get(k, i), N["JOBS"].get(k, {}))
    N["build_back"](doc, R, jobs)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
