"""collect_jobs.py - gather everything a report needs about finished Studio jobs (runs ON the engine server).

    /srv/cosmogon/venv/bin/python collect_jobs.py OUT_DIR JOB_ID [JOB_ID ...]
    /srv/cosmogon/venv/bin/python collect_jobs.py OUT_DIR --last 5

Read-only: it never writes to Supabase, the job folders or the lab. Per job it writes OUT_DIR/<job8>/:
  job.json        the jobs row (prompt, split, timestamps) + the brief's assets / vibe / taste / fonts
  result.json     the landing pipeline's result (trace, overrides, QA, candidates, raw agent outputs, ledger)
  spec.json       the merged document A5 composed from
  journal.txt     the worker's journal from claim to "took"
  shots/*.jpg     index (shipped) and a5-1 (A5's first page) at 1440 px (first screen + full page) and 390 px
  contrast.json   rendered readability of every HTML text node (SVG <text> is drawing, not copy, and is left out):
                  colour vs the median pixel under it with text hidden, and whether it shows any ink at all
  refs/*.jpg      the A1 reference images that could be found + the images placed on the page
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageChops

TMP = Path(os.getenv("SERPMAN_TMP", "/srv/cosmogon/tmp"))
WORKER = Path("/srv/cosmogon/studio/worker")
CREAM = Path("/srv/cosmogon/data/serpman_data/ui_drafts/p1/context-cream")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/srv/cosmogon/cache/ms-playwright")


def env():
    for line in (WORKER / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def supa_get(table, params):
    u = os.environ["SUPABASE_URL"].rstrip("/")
    k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": k, **({"Authorization": f"Bearer {k}"} if k.startswith("eyJ") else {})}
    r = httpx.get(f"{u}/rest/v1/{table}", params=params, headers=h, timeout=40)
    r.raise_for_status()
    return r.json()


def job_dir(job_id):
    ds = sorted(glob.glob(str(TMP / f"landing-{job_id}-*")), key=os.path.getmtime)
    return Path(ds[-1]) if ds else None


def journal(row):
    """The worker's lines from just before the claim to just after the finish."""
    import datetime as dt
    def t(s, d):
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00")) + dt.timedelta(seconds=d)
        return x.strftime("%Y-%m-%d %H:%M:%S")
    a = t(row["claimed_at"] or row["created_at"], -5)
    b = t(row["finished_at"] or row["claimed_at"], 20)
    p = subprocess.run(["sudo", "-n", "journalctl", "-u", "cosmogon-worker", "-o", "short-iso", "--no-pager",
                        "--utc", "--since", a, "--until", b], capture_output=True, text=True)
    return p.stdout


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


TEXT_JS = """() => { const out=[]; const w=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
 const seen=new Set(); while(w.nextNode()){ const t=w.currentNode; if(!t.textContent.trim()) continue;
 const el=t.parentElement; if(!el||seen.has(el)||el.closest('svg')) continue; seen.add(el);
 let p=el, hid=false, op=1; while(p&&p.nodeType===1){const s=getComputedStyle(p); if(s.display==='none'||s.visibility==='hidden'){hid=true;break;} op*=parseFloat(s.opacity); p=p.parentElement;}
 if(hid||op<0.05) continue;
 const r=document.createRange(); r.selectNodeContents(t); const b=r.getBoundingClientRect(); if(b.width<2||b.height<2) continue;
 const cs=getComputedStyle(el);
 out.push({tag:el.tagName.toLowerCase(), item:(el.closest('[data-item]')||{dataset:{}}).dataset.item||'',
   section:(el.closest('[data-section]')||{dataset:{}}).dataset.section||'', text:t.textContent.trim().replace(/\\s+/g,' ').slice(0,60),
   color:cs.color, x:b.left+scrollX, y:b.top+scrollY, w:b.width, h:b.height, fs:parseFloat(cs.fontSize), fw:parseInt(cs.fontWeight)||400}); }
 return out; }"""


# text painted over by something opaque: the topmost element at the text's centre is neither the text's element nor
# inside it. Translucent layers (the guard's z50 grain at 7%, anything under 35% effective opacity) don't count; an
# ancestor reported on top means one of its ::before / ::after boxes covers the text.
OCC_JS = """()=>{const st=document.createElement('style'); st.textContent='*{pointer-events:auto!important}'; document.head.appendChild(st);
 const eop=x=>{let o=1,p=x; while(p&&p.nodeType===1){o*=parseFloat(getComputedStyle(p).opacity); p=p.parentElement;} return o;};
 const out=[]; const w=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); const seen=new Set();
 while(w.nextNode()){const t=w.currentNode; if(!t.textContent.trim())continue; const el=t.parentElement; if(!el||seen.has(el)||el.closest('svg'))continue; seen.add(el);
  const r=document.createRange(); r.selectNodeContents(t); const b=r.getBoundingClientRect(); if(b.width<2||b.height<2)continue;
  const y=b.top+scrollY+b.height/2; window.scrollTo(0, Math.max(0,y-innerHeight/2)); const cy=y-scrollY; const cx=b.left+b.width/2;
  if(cx<0||cx>innerWidth) continue;
  for(const x of document.elementsFromPoint(cx,cy)){
    if(x===el||el.contains(x)) break;
    if(x.closest('[data-layer="z50"]')||eop(x)<0.35) continue;
    const name=x.tagName.toLowerCase()+((x.className&&(x.className.baseVal??x.className))?'.'+String(x.className.baseVal??x.className).split(' ')[0]:'')+(x.dataset.motif?' (motif '+x.dataset.motif+')':'');
    out.push([(el.closest('[data-item]')||{dataset:{}}).dataset.item||el.tagName.toLowerCase(), t.textContent.trim().replace(/\\s+/g,' ').slice(0,30),
              x.contains(el)?('a ::before/::after of its ancestor '+name):name]); break; } }
 window.scrollTo(0,0); document.head.removeChild(st); return out;}"""


def rgba(s):
    v = [float(x) for x in re.findall(r"[\d.]+", s)]
    return tuple(int(x) for x in v[:3]), (v[3] if len(v) > 3 else 1.0)


def hexc(c):
    return "#%02X%02X%02X" % tuple(c[:3])


def jpg(png: bytes, width: int | None, path: Path, max_h: int = 16000):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if im.height > max_h:
        im = im.crop((0, 0, im.width, max_h))
    im.save(path, "JPEG", quality=82, optimize=True)


def shoot(br, html: Path, out: Path, tag: str, probe: bool):
    res = {}
    for w in (1440, 390):
        pg = br.new_page(viewport={"width": w, "height": 900 if w > 500 else 844}, device_scale_factor=1)
        try:
            pg.goto(html.resolve().as_uri(), wait_until="networkidle", timeout=60_000)
        except Exception:  # noqa: BLE001  (fonts slow: shoot what loaded)
            pass
        pg.wait_for_timeout(1200)
        H = pg.evaluate("document.documentElement.scrollHeight")
        W = pg.evaluate("document.documentElement.scrollWidth")
        if w == 1440:
            jpg(pg.screenshot(), 1440, out / f"{tag}_1440_fold.jpg")
        jpg(pg.screenshot(full_page=True), 720 if w == 1440 else 390, out / f"{tag}_{w}_full.jpg")
        r = {"height": H, "scroll_width": W}
        if probe:
            items = pg.evaluate(TEXT_JS)
            covered = {tuple(c[:2]): c[2] for c in pg.evaluate(OCC_JS)}
            # the same full page with its text and with every text colour transparent: a text box whose pixels don't
            # change between the two shows no ink (covered by something opaque, or drawn in its background's colour)
            fg_shot = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
            pg.add_style_tag(content="*{color:transparent!important;text-shadow:none!important;"
                                     "-webkit-text-stroke:0!important;text-decoration-color:transparent!important}")
            pg.wait_for_timeout(300)
            bg = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
            rows = []
            for it in items:
                c, a = rgba(it["color"])
                x0, y0 = max(0, int(it["x"])), max(0, int(it["y"]))
                x1, y1 = min(bg.width, int(it["x"] + it["w"])), min(bg.height, int(it["y"] + it["h"]))
                if x1 <= x0 or y1 <= y0:
                    continue
                crop_b = bg.crop((x0, y0, x1, y1))
                px = list(crop_b.resize((12, 6)).getdata())
                med = tuple(int(st.median(q[i] for q in px)) for i in range(3))
                if fg_shot.size == bg.size:
                    diff = ImageChops.difference(fg_shot.crop((x0, y0, x1, y1)), crop_b).convert("L")
                    hist = diff.histogram()
                    ink = sum(hist[25:]) / max(1, sum(hist))     # share of the box's pixels the text changes
                else:
                    ink = None
                if a < 1:                                    # translucent text: blend it over the background
                    c = tuple(round(a * c[i] + (1 - a) * med[i]) for i in range(3))
                cr = ratio(c, med)
                large = it["fs"] >= 24 or (it["fs"] >= 18.66 and it["fw"] >= 700)
                need = 3.0 if large else 4.5
                visible = ink is None or ink >= 0.01
                # the hit test only explains missing ink (a transparent ::before can top the hit list harmlessly)
                cov = None if visible else covered.get((it["item"] or it["tag"], it["text"][:30]))
                rows.append({"item": it["item"], "section": it["section"], "tag": it["tag"], "text": it["text"],
                             "fg": hexc(c), "bg": hexc(med), "ratio": round(cr, 2), "need": need,
                             "fs": it["fs"], "y": int(it["y"]), "ink": None if ink is None else round(ink, 3),
                             "covered_by": cov, "visible": visible, "pass": cr >= need and visible})
            r["contrast"] = rows
        res[w] = r
        pg.close()
    return res


def find_ref(fam, id_):
    h = re.sub(r"^[a-z]+__", "", id_).rsplit(".", 1)[0]
    hits = glob.glob(str(CREAM / fam / "*" / f"{h}.*"))
    return Path(hits[0]) if hits else None


def thumb(src: Path, dst: Path, side=640):
    try:
        im = Image.open(src).convert("RGB")
        im.thumbnail((side, side))
        im.save(dst, "JPEG", quality=82)
        return True
    except Exception:  # noqa: BLE001
        return False


def main():
    env()
    out = Path(sys.argv[1])
    args = sys.argv[2:]
    if args[:1] == ["--last"]:
        ds = sorted(glob.glob(str(TMP / "landing-*-*-*-*-*-*")), key=os.path.getmtime)[-int(args[1]):]
        ids = [re.match(r"landing-([0-9a-f-]{36})-", Path(d).name).group(1) for d in ds]
    else:
        ids = args
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        for jid in ids:
            d = job_dir(jid)
            o = out / jid[:8]
            shutil.rmtree(o, ignore_errors=True)
            (o / "shots").mkdir(parents=True)
            (o / "refs").mkdir()
            rows = supa_get("jobs", {"id": f"eq.{jid}", "select": "id,prompt,split,status,error,attempts,created_at,"
                                                                 "claimed_at,finished_at,brief"})
            row = rows[0] if rows else {"id": jid}
            brief = row.pop("brief", None) or {}
            site = supa_get("sites", {"job_id": f"eq.{jid}", "select": "id,title,created_at"})
            assets = [{k: a.get(k) for k in ("role", "type", "cluster", "note", "fam", "id", "ref_id", "text",
                                             "relevance", "on_page")} for a in brief.get("assets", [])]
            refs = {}
            for a in assets:
                if a["role"] in ("layout", "background", "palette", "central", "hero"):
                    f = find_ref(a["fam"], a["id"])
                    name = f"{a['role']}_{a['ref_id']}.jpg"
                    if f and thumb(f, o / "refs" / name):
                        refs.setdefault(a["role"], []).append(name)
            job = {"row": row, "site": site[0] if site else None, "assets": assets, "refs": refs,
                   "vibe": brief.get("vibe"), "taste": brief.get("taste"), "fonts": brief.get("fonts"),
                   "meta": brief.get("meta"), "dir": str(d) if d else None}
            if d:
                for f in ("result.json", "spec.json"):
                    if (d / f).exists():
                        shutil.copy(d / f, o / f)
                for f in (d / "assets").glob("*.webp"):
                    thumb(f, o / "refs" / f"onpage_{f.stem}.jpg")
                shots = {"index": shoot(br, d / "index.html", o / "shots", "index", True)}
                if (d / "a5-1.html").exists():
                    shots["a5-1"] = shoot(br, d / "a5-1.html", o / "shots", "a5-1", True)
                (o / "contrast.json").write_text(json.dumps(shots, indent=1), encoding="utf-8")
            if row.get("claimed_at"):
                (o / "journal.txt").write_text(journal(row), encoding="utf-8")
            (o / "job.json").write_text(json.dumps(job, indent=1, default=str), encoding="utf-8")
            fails = sum(not r["pass"] for r in (shots["index"][1440].get("contrast") or [])) if d else None
            print(f"{jid[:8]}: {row.get('status')} {str(row.get('prompt'))[:50]!r} dir={'yes' if d else 'no'} "
                  f"refs={sum(len(v) for v in refs.values())} contrast_fails@1440={fails}", flush=True)
        br.close()


if __name__ == "__main__":
    main()
