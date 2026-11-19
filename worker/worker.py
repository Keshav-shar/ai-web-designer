"""worker.py - the PC side of serpman Studio: claim a job, run the lab, build the site, upload it.

    python worker.py once --prompt "a skincare brand that feels vintage" [--out D:\\serpman-studio\\out\\x] [--theme light]
    python worker.py run                 # poll Supabase for queued jobs (outbound only; nothing listens here)

Run with D:\\caches\\venvs\\uifp\\Scripts\\python.exe (torch + open_clip + the lab's deps).
Env: QWEN_* (qwen.py), SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (run mode), SERPMAN_SRC (default: the serpman
folder), optional LAB_AI_* to let the lab's own AI comparers use the same Qwen endpoint.
One process, one job at a time: the lab holds one CLIP model and shared caches (~3 GB free RAM on this machine).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("SERPMAN_TMP", r"D:\caches\tmp")
Path(os.environ["SERPMAN_TMP"]).mkdir(parents=True, exist_ok=True)

import agent  # noqa: E402
import assemble  # noqa: E402
import assets as A  # noqa: E402
from brief import build_brief  # noqa: E402
from labio import lab_path  # noqa: E402
from qwen import Qwen  # noqa: E402
from split import split as do_split  # noqa: E402


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class Engine:
    """The lab, loaded once: Index (CLIP image matrix), TextEncoder, Lab (palette/font stores, pi cursor)."""

    def __init__(self):
        lab_path()
        import palette_lab as pl
        import route_engine as re_
        import section_plan as sp
        t0 = time.time()
        self.re, self.pl, self.sp = re_, pl, sp
        self.ix = re_.Index()
        self.enc = re_.TextEncoder()
        self.L = re_.Lab(self.ix)
        print(f"engine ready in {time.time() - t0:.0f}s: {len(self.ix.ids)} images, {len(self.ix.families)} families,"
              f" lab AI {'on' if self.L.ai.ok else 'off'}", flush=True)

    def text_lines(self, fam: str, id_: str):
        """(text lines, tallest text box / image height) for one corpus image, from the lab's colour cache."""
        k = self.ix.key.get((fam, id_))
        if k is None:
            return None
        self.L.store.ensure([k], save=False)
        return float(self.L.store.a["lines"][k]), float(self.L.store.a["hmax"][k])

    def resolve(self, fam: str, id_: str):
        k = self.ix.key.get((fam, id_))
        return Path(self.ix.dest[k]) if k is not None else None

    def recipe(self, prompt: str, split: dict, job_id: str | None, theme: str) -> tuple[dict, dict, dict]:
        P = self.pl.parse_params({"serve": "1", "roles": "ai" if self.L.ai.ok else "code"})
        o = self.re.lab(self.ix, self.enc, self.L, split["vibe_query"], P)
        if "error" in o:
            raise RuntimeError(f"lab: {o['error']}")
        src = self.sp.suggest(self.enc, split["full_query"])
        brief, files = build_brief(o, query=prompt, split=split, sections_src=src, job_id=job_id, theme=theme,
                                   resolve=self.resolve, text_lines=self.text_lines)
        return o, brief, files


def run_job(eng: Engine, qwen: Qwen, prompt: str, split: dict, job_id: str | None, theme: str, emit,
            publish_assets=None) -> dict:
    """Shared by `once` and `run`. emit(stage, message, data) reports progress; publish_assets(brief, files) is
    called as soon as the images are ready. -> {brief, page, css, files, sections}."""
    emit("routing", f"routing the vibe: {split['vibe_query']!r}", {"split": split})
    o, brief, files = eng.recipe(prompt, split, job_id, theme)
    emit("recipe", f"family {brief['meta']['routed_family']} -> {brief['taste']['niche'] or brief['taste']['category_name']}",
         {"family": brief["meta"]["routed_family"], "families": o.get("route_families", [])[:5],
          "palette": brief["tokens"]["palette"], "color": brief["tokens"]["color"],
          "fonts": [brief["fonts"]["heading"]["family"], brief["fonts"]["body"]["family"]],
          "sections": [s["id"] for s in brief["sections"]], "taste": brief["taste"],
          "assets": [{k: a[k] for k in ("path", "role", "type")} for a in brief["assets"]],
          "overrides": len(brief["typography"]["overrides"])})
    files_out = A.prepare(brief, files)
    if publish_assets:                              # run mode: the Studio's recipe cards can show them now
        publish_assets(brief, files_out)
        emit("recipe", f"{len(files_out)} images ready", {"assets_uploaded": True})
    layout = next((a for a in brief["assets"] if a["role"] == "layout"), None)
    note = None
    if layout and qwen.vl_model and layout["path"] in files_out:
        tmp = Path(os.environ["SERPMAN_TMP"]) / f"{layout['ref_id']}.webp"
        tmp.write_bytes(files_out[layout["path"]])
        try:
            note = qwen.describe_layout(tmp)
        except Exception as e:  # noqa: BLE001
            emit("recipe", f"layout note skipped: {e}"[:200], None)
    emit("generating", "writing sections" + ("" if qwen.ok else " (no Qwen key: fallback templates)"),
         {"layout_note": note, "qwen": qwen.ok})

    def on_section(res, i, n):
        emit("generating", f"section {i + 1}/{n}: {res['id']}" + (" (fallback)" if res["fallback"] else ""),
             {"id": res["id"], "i": i, "n": n, "fallback": res["fallback"], "errors": res["errors"][:5]})

    sections = agent.generate(brief, split, qwen, note, on_section)
    emit("assembling", "compiling the page", None)
    page, css = assemble.build(brief, split, sections)
    return {"brief": brief, "page": page, "css": css, "files": files_out, "sections": sections}


def cmd_once(a) -> int:
    qwen = Qwen()
    split = do_split(a.prompt, qwen)
    print(json.dumps(split, indent=1))
    eng = Engine()
    out = run_job(eng, qwen, a.prompt, split, None, a.theme,
                  lambda st, msg, data=None: print(f"[{st}] {msg}", flush=True))
    slug = re.sub(r"[^a-z0-9]+", "-", a.prompt.lower()).strip("-")[:48]
    od = Path(a.out or (HERE.parent / "out" / slug))
    assemble.write_local(od, out["page"], out["css"], out["files"])
    (od / "brief.json").write_text(json.dumps(out["brief"], indent=1), encoding="utf-8")
    fb = sum(s["fallback"] for s in out["sections"])
    print(f"wrote {od / 'index.html'}  ({len(out['sections'])} sections, {fb} fallback, {len(out['files'])} images)")
    return 0


def cmd_run(a) -> int:
    from supa import Supa
    sb, qwen = Supa(), Qwen()
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    eng = Engine()
    print(f"worker {worker_id} polling ({'Qwen on' if qwen.ok else 'NO QWEN: fallback sections only'})", flush=True)
    idle = 2.0
    while True:
        try:
            job = sb.claim(worker_id)
        except Exception as e:  # noqa: BLE001
            print(f"claim failed: {e}", flush=True)
            time.sleep(30)
            continue
        if not job:
            time.sleep(idle)
            idle = min(20.0, idle * 1.5)
            continue
        idle = 2.0
        jid, uid = job["id"], job["user_id"]
        print(f"job {jid}: {job['prompt']!r}", flush=True)

        def emit(stage, message, data=None):
            if stage in ("recipe", "generating", "assembling"):
                sb.update_job(jid, status=stage)
            sb.event(job, stage, message, data)

        base = f"{uid}/{jid}"

        def publish(brief, files):
            sb.update_job(jid, brief=brief)
            for rel, data in files.items():
                sb.upload(f"{base}/{rel}", data, "image/webp")

        try:
            out = run_job(eng, qwen, job["prompt"], job["split"], jid, a.theme, emit, publish)
            sb.upload(f"{base}/styles.css", out["css"].encode(), "text/css")
            sb.upload(f"{base}/index.html", out["page"].encode(), "text/html")
            site = sb.insert_site({"job_id": jid, "user_id": uid, "html_path": f"{base}/index.html",
                                   "css_path": f"{base}/styles.css",
                                   "title": job["split"].get("brand_name") or job["split"]["full_query"][:80]})
            sb.update_job(jid, status="done", finished_at=now_iso())
            sb.event(job, "done", "site ready", {"site_id": site["id"],
                                                 "fallback": sum(s["fallback"] for s in out["sections"])})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            msg = f"{type(e).__name__}: {e}"[:400]
            try:
                sb.update_job(jid, status="failed", error=msg, finished_at=now_iso())
                sb.event(job, "failed", msg, None)
            except Exception:  # noqa: BLE001
                traceback.print_exc()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("once")
    o.add_argument("--prompt", required=True)
    o.add_argument("--out")
    o.add_argument("--theme", default="auto", choices=["auto", "light", "dark"])
    r = sub.add_parser("run")
    r.add_argument("--theme", default="auto", choices=["auto", "light", "dark"])
    a = ap.parse_args(argv)
    if platform.system() == "Windows":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return cmd_once(a) if a.cmd == "once" else cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
