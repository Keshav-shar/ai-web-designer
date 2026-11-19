"""worker.py - the PC side of serpman Studio: claim a job, run the lab, build the site, upload it.

    python worker.py once --prompt "a skincare brand that feels vintage" [--out D:\\serpman-studio\\out\\x] [--theme light]
    python worker.py run                 # poll Supabase for queued jobs (outbound only; nothing listens here)

Run with D:\\caches\\venvs\\uifp\\Scripts\\python.exe (torch + open_clip + the lab's deps).
Env: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (run mode), SECTION_MODE=compose|qwen (default compose: no model),
QWEN_* (qwen.py, only for SECTION_MODE=qwen and the CLI split), SERPMAN_SRC (default: the serpman folder).
An optional worker/.env (gitignored, written by you, never by the tools) is read for any of these not already set.
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


def load_dotenv(path: Path = HERE / ".env") -> None:
    """KEY=VALUE lines; existing environment variables win. Values are never printed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()
os.environ.setdefault("SERPMAN_TMP", r"D:\caches\tmp")
Path(os.environ["SERPMAN_TMP"]).mkdir(parents=True, exist_ok=True)

import agent  # noqa: E402
import assemble  # noqa: E402
import mockup  # noqa: E402
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
        self.text_score = self._clip_text_score()
        print(f"engine ready in {time.time() - t0:.0f}s: {len(self.ix.ids)} images, {len(self.ix.families)} families,"
              f" lab AI {'on' if self.L.ai.ok else 'off'}", flush=True)

    TEXT_POS = ["a graphic with a large text headline", "a poster with big typography",
                "a product listing image with a title banner", "a screenshot of a page full of text",
                "a flyer with printed words"]
    TEXT_NEG = ["a 3d render with no text", "an illustration with no words", "an abstract artwork without any text",
                "a photograph without any text", "a clean image with no lettering"]

    def _clip_text_score(self):
        """CLIP zero-shot 'contains text' score for every corpus image (threshold: brief.CLIP_TEXT_T)."""
        P, N = self.enc(self.TEXT_POS), self.enc(self.TEXT_NEG)
        return (self.ix.E @ P.T).mean(1) - (self.ix.E @ N.T).mean(1)

    def text_lines(self, fam: str, id_: str):
        """Text reading for one corpus image: {"clip": score}; see brief.texty."""
        k = self.ix.key.get((fam, id_))
        return None if k is None else {"clip": float(self.text_score[k])}

    def resolve(self, fam: str, id_: str):
        k = self.ix.key.get((fam, id_))
        return Path(self.ix.dest[k]) if k is not None else None

    def folder_sections(self, vibe_query: str, family: str, w: float = 0.25) -> list[dict]:
        """The routed family's cluster folders (3D render, illustration, UI kit, ...): best image + alternates each."""
        r = self.re.route(self.ix, self.enc, vibe_query, w, force_fam=family)
        return [b for b in r["in_family"] if b]

    def recipe(self, prompt: str, split: dict, job_id: str | None, theme: str, serve: bool = True,
               force_fam: str | None = None, sections_override: list[str] | None = None) -> tuple[dict, dict, dict]:
        P = self.pl.parse_params({"serve": "1" if serve else "0", "roles": "ai" if self.L.ai.ok else "code"})
        o = self.re.lab(self.ix, self.enc, self.L, split["vibe_query"], P, force_fam)
        if "error" in o:
            raise RuntimeError(f"lab: {o['error']}")
        src = self.sp.suggest(self.enc, split["full_query"])
        folders = self.folder_sections(split["vibe_query"], o["routed"], P["w"])
        brief, files = build_brief(o, query=prompt, split=split, sections_src=src, job_id=job_id, theme=theme,
                                   resolve=self.resolve, text_lines=self.text_lines, folder_sections=folders,
                                   sections_override=sections_override)
        return o, brief, files


def run_job(eng: Engine, qwen: Qwen, prompt: str, split: dict, job_id: str | None, theme: str, emit,
            publish_assets=None, copy: dict | None = None, serve: bool = True, force_fam: str | None = None,
            sections_override: list[str] | None = None) -> dict:
    """Shared by `once` and `run`. emit(stage, message, data) reports progress; publish_assets(brief, files) is
    called as soon as the images are ready. -> {brief, page, css, files, sections}."""
    emit("routing", f"routing the vibe: {split['vibe_query']!r}", {"split": split})
    o, brief, files = eng.recipe(prompt, split, job_id, theme, serve, force_fam, sections_override)
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
    mode = agent.section_mode(qwen)
    if mode == "qwen" and layout and qwen.vl_model and layout["path"] in files_out:
        tmp = Path(os.environ["SERPMAN_TMP"]) / f"{layout['ref_id']}.webp"
        tmp.write_bytes(files_out[layout["path"]])
        try:
            note = qwen.describe_layout(tmp)
        except Exception as e:  # noqa: BLE001
            emit("recipe", f"layout note skipped: {e}"[:200], None)
    emit("generating", "composing sections from the family's folders" if mode == "compose" else "Qwen is writing sections",
         {"layout_note": note, "mode": mode})

    def on_section(res, i, n):
        emit("generating", f"section {i + 1}/{n}: {res['id']}" + (" (composed fallback)" if res["fallback"] else ""),
             {"id": res["id"], "i": i, "n": n, "fallback": res["fallback"], "errors": res["errors"][:5]})

    sections = agent.generate(brief, split, qwen, note, on_section, copy)
    emit("assembling", "compiling the page", None)
    page, css = assemble.build(brief, split, sections)
    return {"brief": brief, "page": page, "css": css, "files": files_out, "sections": sections}


def render_mockup(page: str, css: str, files: dict[str, bytes]) -> bytes | None:
    """Write the site to a scratch folder and screenshot it; a failed screenshot never fails the job."""
    import shutil
    import tempfile
    d = Path(tempfile.mkdtemp(dir=os.environ["SERPMAN_TMP"]))
    try:
        assemble.write_local(d / "site", page, css, files)
        return mockup.screenshot(d / "site")
    except Exception as e:  # noqa: BLE001
        print(f"mockup skipped: {type(e).__name__}: {e}", flush=True)
        return None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def cmd_once(a) -> int:
    qwen = Qwen()
    split = do_split(a.prompt, qwen)
    print(json.dumps(split, indent=1))
    eng = Engine()
    out = run_job(eng, qwen, a.prompt, split, None, a.theme,
                  lambda st, msg, data=None: print(f"[{st}] {msg}", flush=True), force_fam=a.fam)
    slug = re.sub(r"[^a-z0-9]+", "-", a.prompt.lower()).strip("-")[:48]
    od = Path(a.out or (HERE.parent / "out" / slug))
    assemble.write_local(od, out["page"], out["css"], out["files"])
    (od / "brief.json").write_text(json.dumps(out["brief"], indent=1), encoding="utf-8")
    shot = mockup.screenshot(od) if a.mockup else None
    if shot:
        (od / "mockup.webp").write_bytes(shot)
    fb = sum(s["fallback"] for s in out["sections"])
    print(f"wrote {od / 'index.html'}  ({len(out['sections'])} sections, {fb} fallback, {len(out['files'])} images"
          f"{', mockup.webp' if shot else ''})")
    return 0


def cmd_run(a) -> int:
    from supa import Supa
    sb, qwen = Supa(), Qwen()
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    eng = Engine()
    print(f"worker {worker_id} polling (sections: {agent.section_mode(qwen)})", flush=True)
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
            row = {"job_id": jid, "user_id": uid, "html_path": f"{base}/index.html", "css_path": f"{base}/styles.css",
                   "title": job["split"].get("brand_name") or job["split"]["full_query"][:80]}
            shot = render_mockup(out["page"], out["css"], out["files"])
            if shot:
                sb.upload(f"{base}/mockup.webp", shot, "image/webp")
                row["mockup_path"] = f"{base}/mockup.webp"
            site = sb.insert_site(row)
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
    o.add_argument("--fam", help="pin the aesthetic family (e.g. dreamy-ethereal)")
    o.add_argument("--no-mockup", dest="mockup", action="store_false", help="skip the mockup.webp screenshot")
    r = sub.add_parser("run")
    r.add_argument("--theme", default="auto", choices=["auto", "light", "dark"])
    a = ap.parse_args(argv)
    if platform.system() == "Windows":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return cmd_once(a) if a.cmd == "once" else cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
