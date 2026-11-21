"""worker.py - the PC side of serpman Studio: claim a job, run the lab, build the site, upload it.

    python worker.py once --prompt "a skincare brand that feels vintage" [--out D:\\serpman-studio\\out\\x] [--theme light]
    python worker.py run                 # poll Supabase for queued jobs (outbound only; nothing listens here)
    python worker.py doctor [--write-test] [--keys]   # health report: env, Supabase grants, storage, Playwright, web

Run with D:\\caches\\venvs\\uifp\\Scripts\\python.exe (torch + open_clip + the lab's deps).
Env: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (run mode), SECTION_MODE=compose|qwen|agents (default compose: no
model; agents = worker/landing, one thematic landing page, GEMINI_API_KEY + GROQ_API_KEY for the models),
QWEN_* (qwen.py: SECTION_MODE=qwen, and the prompt split when set; else the rule-based split.py), SERPMAN_SRC
(default: the serpman folder). Every job's prompt is split here, never by the web.
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

import netfix  # noqa: E402
netfix.install()                     # survive "[Errno 11001] getaddrinfo failed" blips on this PC (see netfix.py)

import agent  # noqa: E402
import assemble  # noqa: E402
import mockup  # noqa: E402
import assets as A  # noqa: E402
from brief import build_brief, clip_text_scores, prompt_context  # noqa: E402
from labio import lab_path  # noqa: E402
from qwen import Qwen  # noqa: E402
from split import MAX_PROMPT, normalize  # noqa: E402
from split import split as do_split  # noqa: E402


def sanitize_prompt(p: object) -> str:
    return normalize(p)[:MAX_PROMPT] or "website"


def code_stamp() -> float:
    """Newest modification time of the code a running worker depends on (worker, landing, agent prompts)."""
    files = list(HERE.glob("*.py")) + list((HERE / "landing").glob("*.py")) + \
        list((HERE.parent / "contracts" / "prompts" / "agents").glob("*.md"))
    return max((f.stat().st_mtime for f in files), default=0.0)


def stamp_str(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class Engine:
    """The lab, loaded once: Index (CLIP image matrix), TextEncoder, Lab (palette/font stores, pi cursor)."""

    def __init__(self):
        lab_path()
        import palette_lab as pl
        import route_engine as re_
        t0 = time.time()
        self.re, self.pl = re_, pl
        self.ix = re_.Index()
        self.enc = re_.TextEncoder()
        self.L = re_.Lab(self.ix)
        self.text_score = self._clip_text_score()
        print(f"engine ready in {time.time() - t0:.0f}s: {len(self.ix.ids)} images, {len(self.ix.families)} families,"
              f" lab AI {'on' if self.L.ai.ok else 'off'}", flush=True)

    def _clip_text_score(self):
        """CLIP zero-shot 'contains text' score for every corpus image (threshold: brief.CLIP_TEXT_T)."""
        return clip_text_scores(self.enc, self.ix.E)

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
        src = prompt_context(self.enc, split["full_query"])   # category + the niche the request names
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
    if agent.section_mode(qwen) == "agents":
        return run_landing(eng, o, brief, files, split, theme, emit, publish_assets)
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


def run_landing(eng: Engine, o: dict, brief: dict, files: dict, split: dict, theme: str, emit,
                publish_assets=None) -> dict:
    """SECTION_MODE=agents: the lab run + the job's brief (Engine.recipe) -> worker/landing's 5-agent pipeline -> one
    thematic landing page. Models are called when GEMINI_API_KEY / GROQ_API_KEY are set; each agent falls back to its
    default otherwise."""
    from landing import handoff as LH, pipeline as LP
    job_id = brief["meta"].get("job_id")
    emit("recipe", f"family {brief['meta']['routed_family']} -> {brief['taste']['niche'] or brief['taste']['category_name']}",
         {"family": brief["meta"]["routed_family"], "families": o.get("route_families", [])[:5],
          "vibe_query": split["vibe_query"], "taste": brief["taste"]})
    h = LH.build(o, split, brief, files, theme=theme, resolve=eng.resolve, text_lines=eng.text_lines)
    od = Path(os.environ["SERPMAN_TMP"]) / f"landing-{job_id or 'local'}-{int(time.time())}"
    emit("generating", "the agent pipeline is designing the landing page", {"mode": "agents"})
    r = LP.run(h, enabled=True, out_dir=od, qa=True, log=lambda m: emit("generating", str(m)[:200], None))
    for t in r["trace"]:
        emit("generating", f"{t['agent']}: {t['source']}" + (f" ({t['model']})" if t.get("model") else ""),
             {k: t.get(k) for k in ("agent", "source", "model", "usage", "ms")})
    page = (od / "index.html").read_text(encoding="utf-8")
    files_out = {f"assets/{p.name}": p.read_bytes() for p in (od / "assets").glob("*.webp")}
    if publish_assets:
        publish_assets(h["brief"], files_out)
    emit("assembling", f"page by {r['page_source']}", {"qa": {w: len(x['problems']) for w, x in (r['qa'] or {}).items()}})
    return {"brief": h["brief"], "page": page, "css": "/* landing page: styles are inline in index.html */\n",
            "files": files_out, "landing": {k: r[k] for k in ("page_source", "trace", "overrides", "qa", "ledger")},
            "sections": [{"id": "landing", "html": "", "fallback": r["page_source"] in ("compile_spec", "safe_spec"),
                          "errors": [],
                          "source": r["page_source"]}]}


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
    hb_id = socket.gethostname()                   # one engine_status row per machine, reused across restarts
    mode = agent.section_mode(qwen)

    # Preflight before loading the lab or claiming anything: a job is only claimed if it can be finished.
    problems = sb.preflight(hb_id)
    if problems:
        print("the worker can't serve requests yet:", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        return 2
    requeued, failed = sb.recover(hb_id)
    if requeued or failed:
        print(f"recovered unfinished jobs from an earlier run: {requeued} re-queued, {failed} marked failed", flush=True)

    # the heartbeat runs on its own thread from here on: the badge stays online through model calls, QA and the
    # mockup screenshot (beating only from progress events let long steps go silent for > 2 min -> "offline")
    pulse = sb.pulse(hb_id, mode, every=15.0).start()   # < the 20 s keep-alive: each beat reuses its socket
    eng = Engine()
    loaded = code_stamp()
    print(f"worker {worker_id} polling (sections: {mode}; code from {stamp_str(loaded)}); Ctrl+C to stop", flush=True)
    if mode == "agents":
        from landing import keys as K
        print(f"agents mode: {len(K.collect('mistral'))} Mistral, {len(K.collect('groq'))} Groq, "
              f"{len(K.collect('gemini'))} Gemini (last fallback) key(s)"
              " (agents without a key use their deterministic default)", flush=True)
    try:
        _serve(sb, qwen, eng, worker_id, pulse.set, a.theme, loaded)
    except KeyboardInterrupt:
        print("stopping", flush=True)
    finally:
        pulse.stop("offline")                      # the studio badge switches to offline right away
    return 0


def user_message(e: Exception) -> str:
    """What the studio shows when a job fails; the technical text goes to jobs.error and this console."""
    from supa import is_network
    t = str(e).lower()
    if is_network(e) or "retries exhausted" in t:
        return "The engine lost its connection while saving. Please try again."
    if "permission denied" in t or "42501" in t or " 401 " in t or " 403 " in t:
        return "The engine isn't fully set up yet (database permissions). Please try again later."
    if "tailwind" in t:
        return "The engine couldn't compile this page. Please try again."
    return "The engine couldn't build this one. Try rephrasing it, for example: what it is + how it should feel."


def _serve(sb, qwen, eng, worker_id, beat, theme, loaded: float = 0.0) -> None:
    """beat(state): tells the heartbeat thread (supa.Pulse) the engine's state; it does the beating."""
    from supa import is_network
    idle, warned = 2.0, False
    while True:
        beat("idle")
        if loaded and not warned and code_stamp() > loaded + 1:
            warned = True
            print(f"note: the worker's code changed on disk ({stamp_str(code_stamp())}) since it started "
                  f"({stamp_str(loaded)}): restart it (Ctrl+C, then run again) to use the new code", flush=True)
        try:
            job = sb.claim(worker_id)
        except Exception as e:  # noqa: BLE001
            if is_network(e):
                print(f"claim failed: network unavailable ({type(e).__name__}: {str(e)[:90]}) - retrying in 30 s",
                      flush=True)
                n = sb.requeue_mine(worker_id)        # the claim may have gone through with its reply lost
                if n:
                    print(f"re-queued {n} job(s) whose claim reply was lost", flush=True)
            else:
                print(f"claim failed: {str(e)[:300]}", flush=True)
            time.sleep(30)
            continue
        if not job:
            time.sleep(idle)
            idle = min(20.0, idle * 1.5)
            continue
        idle = 2.0
        beat("busy")
        jid, uid = job["id"], job["user_id"]
        prompt = sanitize_prompt(job.get("prompt"))
        # The worker is the only place a prompt is split (split.py): a split stored by an older web build or
        # written by hand is ignored, and the one actually routed is written back for the studio and gallery.
        split = do_split(prompt, qwen)
        print(f"job {jid}: {prompt!r} -> vibe {split['vibe_query']!r}", flush=True)
        try:
            sb.update_job(jid, split=split)
        except Exception as e:  # noqa: BLE001 - display only; the job runs on the split in hand
            print(f"warning: split not written back ({str(e)[:160]})", flush=True)

        stage_now = [None]

        def emit(stage, message, data=None):
            # the job's status column only changes when the stage does: one PATCH per stage, not one per message
            # (an agents run emits ~10 "generating" lines; each used to re-PATCH the same status)
            if stage in ("recipe", "generating", "assembling") and stage != stage_now[0]:
                stage_now[0] = stage
                sb.progress(jid, stage)                  # best effort: drives the UI only
            sb.event(job, stage, message, data)          # best effort

        base = f"{uid}/{jid}"

        def publish(brief, files):
            sb.update_job(jid, brief=brief)
            for rel, data in files.items():
                sb.upload(f"{base}/{rel}", data, "image/webp")

        try:
            out = run_job(eng, qwen, prompt, split, jid, theme, emit, publish)
            sb.upload(f"{base}/styles.css", out["css"].encode(), "text/css")
            sb.upload(f"{base}/index.html", out["page"].encode(), "text/html")
            row = {"job_id": jid, "user_id": uid, "html_path": f"{base}/index.html", "css_path": f"{base}/styles.css",
                   "title": (split.get("brand_name") or split["full_query"])[:80]}
            shot = render_mockup(out["page"], out["css"], out["files"])
            if shot:
                sb.upload(f"{base}/mockup.webp", shot, "image/webp")
                row["mockup_path"] = f"{base}/mockup.webp"
            if sb.job_status(jid) in ("failed", "done"):  # cancelled by the user (or finished elsewhere) meanwhile
                print(f"job {jid}: cancelled before it finished, site not saved", flush=True)
                continue
            site = sb.insert_site(row)
            sb.update_job(jid, status="done", finished_at=now_iso())
            sb.event(job, "done", "site ready", {"site_id": site["id"],
                                                 "fallback": sum(s["fallback"] for s in out["sections"])})
            print(f"job {jid}: site ready", flush=True)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            detail = f"{type(e).__name__}: {e}"[:400]
            try:
                sb.update_job(jid, status="failed", error=detail, finished_at=now_iso())
            except Exception:  # noqa: BLE001
                traceback.print_exc()          # recover() picks it up on the next start
            sb.event(job, "failed", user_message(e), None)


def cmd_doctor(a) -> int:
    """Health report for the public pipeline. Read-only except --write-test (a 1-byte storage object, then deleted);
    never prints secrets; no model generation calls (--keys only lists models per key)."""
    import httpx
    bad = []

    def line(status: str, what: str, detail: str = "") -> None:
        print(f"  [{status:^4}] {what}" + (f": {detail}" if detail else ""), flush=True)
        if status == "FAIL":
            bad.append(what)

    print(f"serpman worker doctor (code from {stamp_str(code_stamp())})")
    print("environment")
    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    line("ok" if url.startswith("https://") else "FAIL", "SUPABASE_URL", "set" if url else "missing")
    kind = ("secret key (sb_secret_)" if key.startswith("sb_secret_") else "legacy service_role JWT" if key.startswith("eyJ")
            else "publishable key: wrong one" if key.startswith("sb_publishable_") else "missing" if not key else "unknown format")
    line("ok" if kind.startswith(("secret", "legacy")) else "FAIL", "SUPABASE_SERVICE_ROLE_KEY", kind)
    qwen = Qwen()
    mode = agent.section_mode(qwen)
    line("ok", "SECTION_MODE", f"{mode}" + ("" if os.getenv("SECTION_MODE") else " (default; add SECTION_MODE=agents to worker/.env for the agents landing)"))
    from landing import keys as K
    nm, ng, nq = len(K.collect("mistral")), len(K.collect("gemini")), len(K.collect("groq"))
    line("ok" if (nm and nq) or mode != "agents" else "warn", "agent keys",
         f"Mistral {nm}, Groq {nq}, Gemini {ng} (last fallback)" + ("" if nm else " - add MISTRAL_API_KEY to worker/.env"))
    line("ok" if qwen.ok else "info", "Prompt split", "Qwen (QWEN_*)" if qwen.ok else "rule-based (split.py)")
    print("supabase")
    if not bad:
        from supa import Supa
        sb = Supa()
        problems = sb.preflight(socket.gethostname(), beat=False)
        if problems:
            for p in problems:
                line("FAIL", p.split(":", 1)[0], p.split(":", 1)[1].strip() if ":" in p else "")
        else:
            line("ok", "tables, write permissions (update jobs, insert job_events / sites), bucket 'sites'")
        if a.write_test and not problems:
            path = f"_doctor/{socket.gethostname()}.txt"
            try:
                sb.upload(path, b"1", "text/plain")
                sb.delete_object(path)
                line("ok", "storage write test", "uploaded and deleted 1 byte")
            except Exception as e:  # noqa: BLE001
                line("FAIL", "storage write test", str(e)[:160])
    print("local")
    try:
        import serpman_paths  # noqa: F401  (Playwright browsers on D:)
    except ImportError:
        lab_path()
        import serpman_paths  # noqa: F401
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        line("ok", "Playwright Chromium", "launches (mockups + browser QA)")
    except Exception as e:  # noqa: BLE001
        line("FAIL", "Playwright Chromium", str(e)[:160])
    try:
        line("ok", "Tailwind CLI", assemble.tailwind_bin()[0].rsplit("\\", 1)[-1])
    except Exception as e:  # noqa: BLE001
        line("FAIL" if mode == "compose" else "info", "Tailwind CLI", str(e)[:120])
    try:
        import guardrails as g
        line("ok", "font catalogue", f"{len(g.font_catalog())} families")
    except Exception as e:  # noqa: BLE001
        line("FAIL", "font catalogue", str(e)[:120])
    src = lab_path()
    line("ok" if (src / "route_engine.py").exists() else "FAIL", "serpman lab source", str(src))
    print("web")
    site = os.getenv("STUDIO_URL", "https://ai-web-designer-gamma.vercel.app")
    try:
        r = httpx.get(site, timeout=20, follow_redirects=True)
        line("ok" if r.status_code < 400 else "FAIL", "studio", f"{site} -> HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        line("FAIL", "studio", f"{site}: {type(e).__name__}")
    if a.keys:
        print("agent keys (model lists only, no generation)")
        from landing.providers import Gemini, Groq, Mistral, ProviderError
        from landing import budget, pipeline as LP
        for name, prov in (("mistral", Mistral(budget.Buckets())), ("groq", Groq(budget.Buckets())), ("gemini", Gemini())):
            for i, k in enumerate(K.collect(name)):
                try:
                    ms = prov.models(k)
                    prov._models = None
                    extra = ""
                    if name == "mistral":
                        want = list(dict.fromkeys(LP.PREFS["mistral:vision"] + LP.PREFS["mistral:text"]))
                        extra = "; " + ", ".join(f"{m} {'(vision)' if prov.vision(m) else '(text)' if m in ms else 'MISSING'}"
                                                 for m in want)
                    line("ok", f"{name} key {i + 1}", f"{len(ms)} models{extra}")
                except ProviderError as e:
                    line("FAIL", f"{name} key {i + 1}", str(e)[:120])
    print("result: " + ("healthy" if not bad else f"{len(bad)} problem(s): " + ", ".join(bad)))
    return 0 if not bad else 1


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
    d = sub.add_parser("doctor")
    d.add_argument("--write-test", action="store_true", help="also upload + delete a 1-byte storage object")
    d.add_argument("--keys", action="store_true", help="list models with each agent key (no generation calls)")
    a = ap.parse_args(argv)
    if platform.system() == "Windows":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return {"once": cmd_once, "run": cmd_run, "doctor": cmd_doctor}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
